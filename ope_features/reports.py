"""Monthly HR report: one builder feeds both the on-screen summary/table and the
Excel export, so counts and amounts always agree. Counts use the *current*
state of each (employee, month) Status item; the status-change history stays in
the audit log and is never counted."""
import io
from typing import Optional

from .common import db, find_bucket, fmt_ist, now_utc, safe_num, stage_amounts_for, to_utc

BUCKETS = ("approved", "pending", "rejected", "partial")
BUCKET_LABEL = {"approved": "Approved", "pending": "Pending", "rejected": "Rejected",
                "partial": "Partially approved"}


def _stage_label(ps: dict) -> str:
    lvl = ps.get("current_level")
    if lvl in ("L1", "L2", "L3"):
        return f"Pending at {(ps.get(lvl) or {}).get('level_name', lvl)}"
    return "Completed"


def _decided(info: Optional[dict]):
    info = info or {}
    cands = [to_utc(info.get("approved_date")), to_utc(info.get("rejected_date"))]
    cands = [c for c in cands if c]
    return max(cands) if cands else None


async def build_report(month: str = "") -> dict:
    """`month` empty -> every payroll month ("All months")."""
    d = db()
    all_months = not month
    status_docs = [s async for s in d["Status"].find({} if all_months else {"approval_status.payroll_month": month})]
    ids = [s["employeeId"] for s in status_docs]
    ope, rej = {}, {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        async for x in d["OPE_data"].find({"employeeId": {"$in": chunk}}):
            ope[x["employeeId"]] = x
        async for x in d["Reject_OPE_data"].find({"employeeId": {"$in": chunk}}):
            rej[x["employeeId"]] = x

    rows, entries = [], []
    pairs = [(s, ps) for s in status_docs for ps in s.get("approval_status", [])
             if all_months or ps.get("payroll_month") == month]
    for s, ps in pairs:
        month = ps.get("payroll_month")
        # restricted employees appear in the final report only once HR has approved the month
        if ps.get("restricted") and ps.get("overall_status") != "approved":
            continue
        eid = s["employeeId"]
        active = find_bucket(ope.get(eid), month)
        rejected = find_bucket(rej.get(eid), month)
        sa = ps.get("stage_amounts") or stage_amounts_for(ps, active, rejected)
        by_name = {(ps.get(l) or {}).get("level_name"): l for l in ("L1", "L2", "L3") if ps.get(l)}

        def amt(name):
            lvl = by_name.get(name)
            return sa.get(lvl, {}).get("approved_amount") if lvl else None

        def when(name):
            lvl = by_name.get(name)
            return fmt_ist(_decided(ps.get(lvl))) if lvl else None

        status = ps.get("overall_status") or "pending"
        if status not in BUCKETS:
            status = "pending"
        remarks = []
        for l in ("L1", "L2", "L3"):
            info = ps.get(l) or {}
            if info.get("rejection_reason"):
                remarks.append(f"{info.get('level_name')} rejected: {info['rejection_reason']}")
            elif info.get("approval_remark") and info.get("status"):
                remarks.append(f"{info.get('level_name')}: {info['approval_remark']}")
        for where, bucket in (("Active", active), ("Rejected", rejected)):
            for e in bucket:
                entries.append({"employee_id": eid, "payroll_month": month, "where": where, "e": e,
                                "employee_name": s.get("employeeName") or ""})
        rows.append({
            "employee_id": eid,
            "employee_name": s.get("employeeName") or (ope.get(eid) or {}).get("employeeName") or "",
            "payroll_month": month,
            "submission_version": ps.get("submission_version", 1),
            "ope_limit": ps.get("limit"),
            "submitted_amount": round(sum(safe_num(e.get("original_amount", e.get("amount")))
                                          for e in active + rejected), 2),
            "current_total": ps.get("total_amount"),
            "rm_approved_amount": None if ps.get("fixed_amount") else amt("Reporting Manager"),
            "partner_approved_amount": amt("Partner"),
            "hr_approved_amount": amt("HR"),
            "status": status,
            "status_label": BUCKET_LABEL[status],
            "stage": _stage_label(ps) if status in ("pending",) else "Completed",
            "submitted_at": fmt_ist(ps.get("submission_date")),
            "rm_action_at": when("Reporting Manager"),
            "partner_action_at": when("Partner"),
            "hr_action_at": when("HR"),
            "remarks": " | ".join(remarks),
            "fixed_amount": bool(ps.get("fixed_amount")),
            "restricted": bool(ps.get("restricted")),
        })
    rows.sort(key=lambda r: (r["payroll_month"] or "", r["employee_id"]))

    counts = {b: 0 for b in BUCKETS}
    amounts = {b: 0.0 for b in BUCKETS}
    for r in rows:
        counts[r["status"]] += 1
        amounts[r["status"]] += safe_num(r["submitted_amount"])
    summary = {
        "payroll_month": "All months" if all_months else month,
        "total_records": len(rows),
        "total_employees": len({r["employee_id"] for r in rows}),
        "counts": counts,
        "submitted_amount_by_status": {k: round(v, 2) for k, v in amounts.items()},
        "total_submitted_amount": round(sum(amounts.values()), 2),
        "total_hr_approved_amount": round(sum(safe_num(r["hr_approved_amount"]) for r in rows), 2),
    }
    ptr = None if all_months else await d["OPE_monthly_active"].find_one({"payroll_month": month})
    if ptr:
        eligible = await d["OPE_monthly_rows"].count_documents({"version_id": ptr["version_id"]})
        summary["eligible_in_upload"] = eligible
        summary["upload_version"] = ptr.get("version")
        summary["not_submitted"] = max(0, eligible - len({r["employee_id"] for r in rows}))
    return {"summary": summary, "rows": rows, "entries": entries}


def filter_report(rep: dict, status: Optional[str] = None, q: str = "") -> dict:
    """Narrow a report to a status bucket / search text and recompute the summary so
    the screen and the Excel export agree."""
    rows = rep["rows"]
    if status in BUCKETS:
        rows = [x for x in rows if x["status"] == status]
    if q:
        ql = q.lower()
        rows = [x for x in rows if ql in x["employee_id"].lower() or ql in (x["employee_name"] or "").lower()]
    keys = {(x["employee_id"], x["payroll_month"]) for x in rows}
    counts = {b: sum(1 for x in rows if x["status"] == b) for b in BUCKETS}
    s = dict(rep["summary"])
    s.update({"total_records": len(rows), "total_employees": len({x["employee_id"] for x in rows}), "counts": counts,
              "total_submitted_amount": round(sum(safe_num(x["submitted_amount"]) for x in rows), 2),
              "total_hr_approved_amount": round(sum(safe_num(x["hr_approved_amount"]) for x in rows), 2)})
    return {"summary": s, "rows": rows,
            "entries": [e for e in rep.get("entries", []) if (e["employee_id"], e["payroll_month"]) in keys],
            "status_filter": status if status in BUCKETS else ""}


def _safe(v):
    """Neutralise spreadsheet formula injection from user-controlled text."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def export_xlsx(report: dict, generated_by: str) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    s, rows = report["summary"], report["rows"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    head_fill = PatternFill("solid", fgColor="1F3A5F")
    head_font = Font(bold=True, color="FFFFFF")
    sf = BUCKET_LABEL.get(report.get("status_filter"), "All statuses")
    ws["A1"] = f"OPE HR Report - {s['payroll_month']} - {sf}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Generated {fmt_ist(now_utc())} by {generated_by}"
    lines = [("Total records", s["total_records"]), ("Total employees", s["total_employees"])]
    for b in BUCKETS:
        lines.append((BUCKET_LABEL[b], s["counts"][b]))
    lines += [("Total submitted amount (INR)", s["total_submitted_amount"]),
              ("Total HR approved amount (INR)", s["total_hr_approved_amount"])]
    if "eligible_in_upload" in s:
        lines += [("Eligible employees (active upload)", s["eligible_in_upload"]),
                  ("Eligible but not submitted", s["not_submitted"])]
    for i, (k, v) in enumerate(lines, start=4):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 18

    ws2 = wb.create_sheet("Records")
    cols = [("Employee ID", "employee_id"), ("Employee Name", "employee_name"), ("Payroll Month", "payroll_month"),
            ("Version", "submission_version"), ("OPE Limit (INR)", "ope_limit"),
            ("Submitted Amount (INR)", "submitted_amount"), ("Current Total (INR)", "current_total"),
            ("Reporting Manager Approved (INR)", "rm_approved_amount"),
            ("Partner Approved (INR)", "partner_approved_amount"), ("HR Approved (INR)", "hr_approved_amount"),
            ("Status", "status_label"), ("Stage", "stage"), ("Submitted At (IST)", "submitted_at"),
            ("Reporting Manager Action (IST)", "rm_action_at"), ("Partner Action (IST)", "partner_action_at"),
            ("HR Action (IST)", "hr_action_at"), ("Remarks", "remarks")]
    for ci, (title, _k) in enumerate(cols, start=1):
        c = ws2.cell(row=1, column=ci, value=title)
        c.fill, c.font = head_fill, head_font
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws2.column_dimensions[get_column_letter(ci)].width = max(14, min(40, len(title) + 4))
    for ri, r in enumerate(rows, start=2):
        for ci, (_t, key) in enumerate(cols, start=1):
            v = r.get(key)
            ws2.cell(row=ri, column=ci, value=_safe(v) if v is not None else ("Not reviewed" if "approved" in key.lower() and key.endswith("amount") else None))
    ws2.freeze_panes = "C2"
    ws2.auto_filter.ref = ws2.dimensions

    ws3 = wb.create_sheet("Entries")
    ecols = [("Employee ID", 13), ("Employee Name", 26), ("Payroll Month", 26), ("Date", 12), ("Client", 22),
             ("Project ID", 14), ("Project Name", 24), ("From", 16), ("To", 16), ("Mode", 16),
             ("Submitted (INR)", 15), ("Approved/Current (INR)", 20), ("Entry Status", 14),
             ("Approved By", 22), ("Approval Remark", 28), ("Rejected By", 22), ("Rejection Reason", 30), ("Remarks", 28)]
    for ci, (title, w) in enumerate(ecols, start=1):
        c = ws3.cell(row=1, column=ci, value=title)
        c.fill, c.font = head_fill, head_font
        ws3.column_dimensions[get_column_letter(ci)].width = w
    for ri, x in enumerate(report.get("entries", []), start=2):
        e = x["e"]
        vals = [x["employee_id"], x["employee_name"], x["payroll_month"], e.get("date"), e.get("client"),
                e.get("project_id"), e.get("project_name"), e.get("location_from"), e.get("location_to"),
                e.get("travel_mode"), safe_num(e.get("original_amount", e.get("amount"))), safe_num(e.get("amount")),
                "Rejected" if x["where"] == "Rejected" else (e.get("status") or "").capitalize(),
                e.get("approver_name") or e.get("approved_by"), e.get("approval_remark"),
                e.get("rejector_name") or e.get("rejected_by"), e.get("rejection_reason"), e.get("remarks")]
        for ci, v in enumerate(vals, start=1):
            ws3.cell(row=ri, column=ci, value=_safe(v) if isinstance(v, str) else v)
    ws3.freeze_panes = "C2"
    ws3.auto_filter.ref = ws3.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
