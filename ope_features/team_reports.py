"""Admin "Team Reports": Excel (and the supporting ticket PDFs) grouped by Partner or Reporting Manager.

The workbook has three sheets:
  Summary  - one line per Partner / Reporting Manager (people, records, amounts, status counts)
  Employee Months - one line per employee and payroll month (limit, submitted, stage amounts, status, IST times)
  Entries  - every expense entry behind those months (the supporting detail), with the name of the
             ticket PDF so it can be matched with the ZIP of supporting tickets."""
import io
import re
import zipfile
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .common import (
    db, find_bucket, fmt_ist, now_utc, require_admin, safe_num, stage_amounts_for,
)
from .reports import BUCKET_LABEL, _safe

GROUPS = {"partner": ("PartnerEmpCode", "Partner"), "manager": ("ReportingEmpCode", "ReportingEmpName")}
LABEL = {"partner": "Partner", "manager": "Reporting Manager"}
MAX_TICKETS = 600
MAX_ZIP_BYTES = 200 * 1024 * 1024


def _clean(part: str, default: str = "NA") -> str:
    s = re.sub(r"[^A-Za-z0-9._ -]+", "_", str(part or "")).strip(" ._")
    return (s or default)[:60]


def ticket_filename(entry: dict) -> str:
    return "_".join([_clean(entry.get("date"), "nodate"), _clean(entry.get("project_id"), "proj"),
                     f"{safe_num(entry.get('amount')):.0f}", str(entry.get("_id"))[-6:]]) + ".pdf"


async def _read_ticket(file_id: str) -> Optional[bytes]:
    """Read one ticket PDF from GridFS (None when it no longer exists)."""
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    try:
        stream = await AsyncIOMotorGridFSBucket(db()).open_download_stream(ObjectId(file_id))
        return await stream.read()
    except Exception:
        return None


async def group_options(group_by: str) -> list:
    code_f, name_f = GROUPS[group_by]
    out = {}
    async for e in db()["Employee_details"].find({}, {"EmpID": 1, code_f: 1, name_f: 1}):
        code = str(e.get(code_f) or "").strip().upper()
        if not code:
            continue
        o = out.setdefault(code, {"code": code, "name": e.get(name_f) or code, "employees": 0})
        o["employees"] += 1
    return sorted(out.values(), key=lambda x: str(x["name"]).lower())


async def collect(group_by: str, code: str, month: str, status: str) -> dict:
    """Everything the three sheets (and the ZIP) need, built once."""
    code_f, name_f = GROUPS[group_by]
    q = {code_f: code.strip().upper()} if code else {}
    emps = {e["EmpID"]: e async for e in db()["Employee_details"].find(q)}
    ids = list(emps)
    status_docs, ope, rej = [], {}, {}
    for i in range(0, len(ids), 300):
        chunk = ids[i:i + 300]
        status_docs += [s async for s in db()["Status"].find({"employeeId": {"$in": chunk}})]
        async for d in db()["OPE_data"].find({"employeeId": {"$in": chunk}}):
            ope[d["employeeId"]] = d
        async for d in db()["Reject_OPE_data"].find({"employeeId": {"$in": chunk}}):
            rej[d["employeeId"]] = d

    months, entries = [], []
    for s in status_docs:
        eid = s["employeeId"]
        emp = emps.get(eid, {})
        gcode = str(emp.get(code_f) or "").strip().upper() or "UNASSIGNED"
        gname = emp.get(name_f) or "Unassigned"
        for ps in s.get("approval_status", []):
            pm = ps.get("payroll_month")
            if month and pm != month:
                continue
            overall = ps.get("overall_status") or "pending"
            if status and overall != status:
                continue
            active = find_bucket(ope.get(eid), pm)
            rejected = find_bucket(rej.get(eid), pm)
            sa = ps.get("stage_amounts") or stage_amounts_for(ps, active, rejected)
            by_name = {(ps.get(l) or {}).get("level_name"): l for l in ("L1", "L2", "L3") if ps.get(l)}

            def amt(name):
                lvl = by_name.get(name)
                return sa.get(lvl, {}).get("approved_amount") if lvl else None

            submitted = round(sum(safe_num(e.get("original_amount", e.get("amount"))) for e in active + rejected), 2)
            marks = []
            for l in ("L1", "L2", "L3"):
                info = ps.get(l) or {}
                if info.get("rejection_reason"):
                    marks.append(f"{info.get('level_name')} rejected: {info['rejection_reason']}")
                elif info.get("approval_remark") and info.get("status"):
                    marks.append(f"{info.get('level_name')}: {info['approval_remark']}")
            months.append({
                "group_code": gcode, "group_name": gname, "employee_id": eid,
                "employee_name": s.get("employeeName") or emp.get("Emp Name") or "", "payroll_month": pm,
                "limit": ps.get("limit"), "submitted": submitted, "current_total": ps.get("total_amount"),
                "rm": None if ps.get("fixed_amount") else amt("Reporting Manager"),
                "partner": amt("Partner"), "hr": amt("HR"),
                "status": overall, "level": ps.get("current_level"),
                "submitted_at": fmt_ist(ps.get("submission_date")),
                "remarks": " | ".join(marks), "fixed": bool(ps.get("fixed_amount")),
            })
            for where, bucket in (("Active", active), ("Rejected", rejected)):
                for e in bucket:
                    entries.append({"group_code": gcode, "group_name": gname, "employee_id": eid,
                                    "employee_name": s.get("employeeName") or emp.get("Emp Name") or "",
                                    "payroll_month": pm, "where": where, "e": e})
    months.sort(key=lambda r: (str(r["group_name"]).lower(), r["employee_id"], r["payroll_month"] or ""))
    entries.sort(key=lambda r: (str(r["group_name"]).lower(), r["employee_id"], r["payroll_month"] or "",
                                str(r["e"].get("date") or "")))
    return {"group_by": group_by, "months": months, "entries": entries, "month": month,
            "code": code, "status": status}


def summarize(data: dict) -> list:
    groups = {}
    for r in data["months"]:
        g = groups.setdefault((r["group_code"], r["group_name"]), {
            "employees": set(), "records": 0, "submitted": 0.0, "hr": 0.0,
            "approved": 0, "pending": 0, "rejected": 0, "partial": 0})
        g["employees"].add(r["employee_id"])
        g["records"] += 1
        g["submitted"] += safe_num(r["submitted"])
        g["hr"] += safe_num(r["hr"])
        g[r["status"] if r["status"] in ("approved", "pending", "rejected", "partial") else "pending"] += 1
    return [{"code": k[0], "name": k[1], **{**v, "employees": len(v["employees"])}}
            for k, v in sorted(groups.items(), key=lambda kv: str(kv[0][1]).lower())]


def preview(data: dict) -> dict:
    tickets = sum(1 for x in data["entries"] if x["e"].get("ticket_pdf"))
    return {"groups": len(summarize(data)), "employees": len({r["employee_id"] for r in data["months"]}),
            "records": len(data["months"]), "entries": len(data["entries"]), "tickets": tickets,
            "ticket_limit": MAX_TICKETS,
            "submitted_amount": round(sum(safe_num(r["submitted"]) for r in data["months"]), 2)}


def build_workbook(data: dict, generated_by: str) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    label = LABEL[data["group_by"]]
    head_fill, head_font = PatternFill("solid", fgColor="14245C"), Font(bold=True, color="FFFFFF")
    wb = openpyxl.Workbook()

    def sheet(ws, columns, rows):
        for ci, (title, _k, w) in enumerate(columns, start=1):
            c = ws.cell(row=1, column=ci, value=title)
            c.fill, c.font = head_fill, head_font
            c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.column_dimensions[get_column_letter(ci)].width = w
        for ri, row in enumerate(rows, start=2):
            for ci, (_t, k, _w) in enumerate(columns, start=1):
                v = row.get(k)
                ws.cell(row=ri, column=ci, value=_safe(v) if isinstance(v, str) else v)
        ws.freeze_panes = "A2"
        if rows:
            ws.auto_filter.ref = ws.dimensions

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"OPE report by {label}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"Payroll month: {data['month'] or 'All months'}   |   Status: "
                f"{BUCKET_LABEL.get(data['status'], 'All')}   |   Generated {fmt_ist(now_utc())} by {generated_by}")
    cols = [(label + " code", "code", 14), (label, "name", 30), ("Employees", "employees", 12), ("Records", "records", 10),
            ("Submitted amount (INR)", "submitted", 22), ("HR approved amount (INR)", "hr", 24),
            ("Approved", "approved", 11), ("Pending", "pending", 10), ("Rejected", "rejected", 10),
            ("Partially approved", "partial", 18)]
    rows = summarize(data)
    for ci, (title, _k, w) in enumerate(cols, start=1):
        c = ws.cell(row=4, column=ci, value=title)
        c.fill, c.font = head_fill, head_font
        ws.column_dimensions[get_column_letter(ci)].width = w
    for ri, r in enumerate(rows, start=5):
        for ci, (_t, k, _w) in enumerate(cols, start=1):
            v = r[k]
            ws.cell(row=ri, column=ci, value=round(v, 2) if isinstance(v, float) else (_safe(v) if isinstance(v, str) else v))
    tot = len(rows) + 5
    ws.cell(row=tot, column=2, value="Total").font = Font(bold=True)
    for ci in (3, 4, 5, 6, 7, 8, 9, 10):
        col = get_column_letter(ci)
        ws.cell(row=tot, column=ci, value=f"=SUM({col}5:{col}{tot - 1})").font = Font(bold=True)

    sheet(wb.create_sheet("Employee Months"), [
        (label + " code", "group_code", 14), (label, "group_name", 28), ("Employee ID", "employee_id", 13),
        ("Employee Name", "employee_name", 28), ("Payroll Month", "payroll_month", 28), ("OPE Limit (INR)", "limit", 14),
        ("Submitted (INR)", "submitted", 15), ("Current Total (INR)", "current_total", 17),
        ("Reporting Manager Approved (INR)", "rm", 20), ("Partner Approved (INR)", "partner", 18),
        ("HR Approved (INR)", "hr", 16), ("Status", "status_label", 18), ("Pending At", "level", 12),
        ("Submitted (IST)", "submitted_at", 22), ("Remarks", "remarks", 50)],
        [{**r, "status_label": BUCKET_LABEL.get(r["status"], r["status"])} for r in data["months"]])

    ent_rows = []
    for x in data["entries"]:
        e = x["e"]
        st = (e.get("status") or "").lower()
        ent_rows.append({
            "group_code": x["group_code"], "group_name": x["group_name"], "employee_id": x["employee_id"],
            "employee_name": x["employee_name"], "payroll_month": x["payroll_month"], "date": e.get("date"),
            "client": e.get("client"), "project_id": e.get("project_id"), "project_name": e.get("project_name"),
            "project_type": e.get("project_type"), "from": e.get("location_from"), "to": e.get("location_to"),
            "mode": e.get("travel_mode"), "original": safe_num(e.get("original_amount", e.get("amount"))),
            "amount": safe_num(e.get("amount")), "remarks": e.get("remarks"),
            "status": "Rejected" if x["where"] == "Rejected" else st.capitalize(),
            "approved_by": e.get("approver_name") or e.get("approved_by"),
            "approved_at": fmt_ist(e.get("approved_date")), "approval_remark": e.get("approval_remark"),
            "rejected_by": e.get("rejector_name") or e.get("rejected_by"), "rejected_at": fmt_ist(e.get("rejected_date")),
            "rejection_reason": e.get("rejection_reason"),
            "ticket": "Yes" if e.get("ticket_pdf") else "No",
            "ticket_file": ticket_filename(e) if e.get("ticket_pdf") else "",
            "submitted_at": fmt_ist(e.get("submitted_time") or e.get("created_time")),
        })
    sheet(wb.create_sheet("Entries (supporting)"), [
        (label + " code", "group_code", 14), (label, "group_name", 26), ("Employee ID", "employee_id", 13),
        ("Employee Name", "employee_name", 26), ("Payroll Month", "payroll_month", 26), ("Date", "date", 12),
        ("Client", "client", 22), ("Project ID", "project_id", 14), ("Project Name", "project_name", 24),
        ("Type", "project_type", 14), ("From", "from", 16), ("To", "to", 16), ("Mode", "mode", 16),
        ("Submitted (INR)", "original", 15), ("Current (INR)", "amount", 14), ("Remarks", "remarks", 28),
        ("Status", "status", 12), ("Approved By", "approved_by", 22), ("Approved (IST)", "approved_at", 22),
        ("Approval Remark", "approval_remark", 28), ("Rejected By", "rejected_by", 22), ("Rejected (IST)", "rejected_at", 22),
        ("Rejection Reason", "rejection_reason", 30), ("Ticket PDF", "ticket", 11), ("Ticket file (in ZIP)", "ticket_file", 36),
        ("Submitted At (IST)", "submitted_at", 22)], ent_rows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def build_tickets_zip(data: dict) -> tuple:
    """-> (zip bytes, included, skipped_notes). Files are stored as
    <Partner|Manager>/<EmpID_Name>/<Month>/<ticket file>."""
    buf = io.BytesIO()
    notes, included, total = [], 0, 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for x in data["entries"]:
            e = x["e"]
            fid = e.get("ticket_pdf")
            if not fid:
                continue
            if included >= MAX_TICKETS:
                notes.append(f"Limit of {MAX_TICKETS} tickets reached - narrow the month/person to get the rest.")
                break
            blob = await _read_ticket(str(fid))
            if blob is None:
                notes.append(f"Missing in storage: {x['employee_id']} {x['payroll_month']} {ticket_filename(e)}")
                continue
            total += len(blob)
            if total > MAX_ZIP_BYTES:
                notes.append("Size limit reached - narrow the month/person to get the rest.")
                break
            path = "/".join([_clean(x["group_name"]), _clean(f"{x['employee_id']}_{x['employee_name']}"),
                             _clean(x["payroll_month"]), ticket_filename(e)])
            z.writestr(path, blob)
            included += 1
        z.writestr("README.txt",
                   f"Supporting tickets - {LABEL[data['group_by']]} wise\n"
                   f"Payroll month: {data['month'] or 'All months'}\nFiles: {included}\n\n"
                   "Each file name matches the 'Ticket file (in ZIP)' column of the Excel report.\n"
                   + ("\n".join(notes) if notes else "No files were skipped."))
    return buf.getvalue(), included, notes


def build_router(get_current_user) -> APIRouter:
    r = APIRouter()

    def code(u) -> str:
        return str(u["employee_code"]).strip().upper()

    def check(group_by: str):
        if group_by not in GROUPS:
            raise HTTPException(status_code=400, detail="group_by must be 'partner' or 'manager'")

    @r.get("/api/admin/team-report/options")
    async def options(group_by: str = Query("partner"), u=Depends(get_current_user)):
        await require_admin(code(u))
        check(group_by)
        return {"people": await group_options(group_by)}

    @r.get("/api/admin/team-report/preview")
    async def preview_ep(group_by: str = Query("partner"), person: str = "", month: str = "", status: str = "",
                         u=Depends(get_current_user)):
        await require_admin(code(u))
        check(group_by)
        return preview(await collect(group_by, person, month, status))

    @r.get("/api/admin/team-report/excel")
    async def excel(group_by: str = Query("partner"), person: str = "", month: str = "", status: str = "",
                    u=Depends(get_current_user)):
        await require_admin(code(u))
        check(group_by)
        data = await collect(group_by, person, month, status)
        if not data["months"]:
            raise HTTPException(status_code=404, detail="No records match these filters")
        blob = build_workbook(data, code(u))
        name = f"OPE_{group_by}_wise_{_clean(person or 'all')}_{_clean(month or 'all_months')}.xlsx".replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(blob), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @r.get("/api/admin/team-report/tickets")
    async def tickets(group_by: str = Query("partner"), person: str = "", month: str = "", status: str = "",
                      u=Depends(get_current_user)):
        await require_admin(code(u))
        check(group_by)
        data = await collect(group_by, person, month, status)
        if not any(x["e"].get("ticket_pdf") for x in data["entries"]):
            raise HTTPException(status_code=404, detail="No ticket PDFs are attached to the selected entries")
        blob, included, notes = await build_tickets_zip(data)
        name = f"OPE_tickets_{group_by}_{_clean(person or 'all')}_{_clean(month or 'all_months')}.zip".replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(blob), media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Tickets-Included": str(included),
                     "X-Tickets-Skipped": str(len(notes))})

    return r
