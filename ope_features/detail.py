"""Per-submission detail view (employee, month) used by the Pending / Approved /
Rejected / Status screens: employee data, per-stage amounts, entries, IST timeline."""
from fastapi import HTTPException

from .access import lock_state
from .audit import AUDIT, event_to_api
from .common import (
    can_view_employee, db, find_bucket, find_month_status, fmt_ist, iso_utc, month_entries,
    normalize_month, safe_num, stage_amounts_for, to_utc,
)

STAGE_LABEL = {"L1": "Level 1", "L2": "Level 2", "L3": "Level 3"}


def entry_to_api(e: dict, where: str) -> dict:
    return {
        "id": str(e.get("_id")), "where": where,
        "date": e.get("date"), "client": e.get("client"), "project_id": e.get("project_id"),
        "project_name": e.get("project_name"), "project_type": e.get("project_type"),
        "location_from": e.get("location_from"), "location_to": e.get("location_to"),
        "travel_mode": e.get("travel_mode"), "remarks": e.get("remarks"),
        "amount": safe_num(e.get("amount")),
        "original_amount": safe_num(e.get("original_amount", e.get("amount"))),
        "original_amount_known": e.get("original_amount") is not None,
        "ticket_pdf": e.get("ticket_pdf"), "status": (e.get("status") or "").lower(),
        "submission_version": e.get("submission_version", 1),
        "is_fixed_amount": bool(e.get("is_fixed_amount")),
        "submitted_at_ist": fmt_ist(e.get("submitted_time") or e.get("created_time")),
        "approved_by": e.get("approved_by"), "approver_name": e.get("approver_name"),
        "approval_remark": e.get("approval_remark"), "approved_at_ist": fmt_ist(e.get("approved_date")),
        "rejected_by": e.get("rejected_by"), "rejector_name": e.get("rejector_name"),
        "rejection_reason": e.get("rejection_reason"), "rejected_level": e.get("rejected_level"),
        "rejected_at_ist": fmt_ist(e.get("rejected_date")),
        "amount_edited_by": e.get("amount_edited_by"), "amount_edited_by_role": e.get("amount_edited_by_role"),
        "amount_edited_at_ist": fmt_ist(e.get("amount_edited_date")),
    }


def reconstruct_timeline(employee_id: str, month: str, ps: dict) -> list:
    """For months that pre-date the audit log, rebuild what the Status item knows."""
    ev = []
    if ps.get("submission_date"):
        ev.append({"action": "submitted", "stage": "Employee", "actor_id": employee_id,
                   "actor_role": "Employee", "new_status": "pending", "remark": None,
                   "_t": to_utc(ps["submission_date"])})
    for lvl in ("L1", "L2", "L3"):
        info = ps.get(lvl) or {}
        name = info.get("level_name")
        if info.get("approved_date"):
            ev.append({"action": "approved", "stage": name, "level": lvl, "actor_id": info.get("approver_code"),
                       "actor_name": info.get("approver_name"), "actor_role": name,
                       "remark": info.get("approval_remark"), "_t": to_utc(info["approved_date"])})
        if info.get("rejected_date"):
            ev.append({"action": "rejected", "stage": name, "level": lvl, "actor_id": info.get("rejected_by"),
                       "actor_name": info.get("rejector_name"), "actor_role": name,
                       "remark": info.get("rejection_reason"), "_t": to_utc(info["rejected_date"])})
    ev.sort(key=lambda x: x["_t"] or to_utc("1970-01-01"))
    out = []
    for x in ev:
        t = x.pop("_t")
        x.update(at_utc=iso_utc(t), at_ist=fmt_ist(t), source="reconstructed")
        out.append(x)
    return out


def _stage_rejection_reason(lvl: str, rejected: list, events_by_stage: dict, stage_name):
    """Rejection remark for a stage: the reason stored on its rejected entries, else the audit event."""
    reasons = []
    for e in rejected:
        r = e.get("rejection_reason")
        if e.get("rejected_level") == lvl and r and r not in reasons:
            reasons.append(r)
    return "; ".join(reasons) or events_by_stage.get(stage_name)


def _stage_rejector(lvl: str, rejected: list):
    for e in rejected:
        if e.get("rejected_level") == lvl and (e.get("rejector_name") or e.get("rejected_by")):
            return e.get("rejector_name") or e.get("rejected_by")
    return None


def stage_status(info: dict, sa: dict, lvl: str, current_level: str, overall: str) -> str:
    appr, rej = sa.get("approved_count", 0), sa.get("rejected_count", 0)
    if rej and appr:
        return "partial"
    if rej:
        return "rejected"
    if info.get("status") or appr:
        return "approved"
    if lvl == current_level and overall in ("pending", None):
        return "pending"
    return "not_reached"


async def build_detail(actor: str, employee_id: str, month: str) -> dict:
    employee_id = employee_id.strip().upper()
    month = normalize_month(month)
    if not await can_view_employee(actor, employee_id):
        raise HTTPException(status_code=403, detail="You are not allowed to view this employee's OPE data")
    d = db()
    st = await d["Status"].find_one({"employeeId": employee_id})
    _idx, ps = find_month_status(st, month)
    active, rejected = await month_entries(employee_id, month)
    if ps is None and not active and not rejected:
        raise HTTPException(status_code=404, detail="No OPE submission found for this employee and month")
    ps = ps or {}
    emp = await d["Employee_details"].find_one({"EmpID": employee_id}) or {}

    sa = ps.get("stage_amounts") or stage_amounts_for(ps, active, rejected)
    events = [event_to_api(x) async for x in d[AUDIT].find(
        {"employeeId": employee_id, "payroll_month": month}).sort("at", 1)]
    events_by_stage = {}
    for ev in events:  # latest rejection remark recorded for each stage
        if ev["action"] == "rejected" and ev.get("remark"):
            events_by_stage[ev["stage"]] = ev["remark"]
    current_level = ps.get("current_level")
    overall = ps.get("overall_status", "pending")
    stages = []
    for lvl in ("L1", "L2", "L3"):
        info = ps.get(lvl)
        if not info:
            continue
        s = sa.get(lvl) or stage_amounts_for(ps, active, rejected).get(lvl, {})
        decided = info.get("rejected_date") or info.get("approved_date")
        stages.append({
            "level": lvl, "stage": info.get("level_name"),
            "approver_code": info.get("approver_code"), "approver_name": info.get("approver_name"),
            "status": stage_status(info, s, lvl, current_level, overall),
            "approved_amount": s.get("approved_amount"), "rejected_amount": s.get("rejected_amount", 0.0),
            "approved_count": s.get("approved_count", 0), "rejected_count": s.get("rejected_count", 0),
            "pending_count": info.get("pending_count"),
            "remark": info.get("approval_remark"),
            "rejection_reason": info.get("rejection_reason") or _stage_rejection_reason(lvl, rejected, events_by_stage, info.get("level_name")),
            "acted_by": (info.get("rejector_name") or _stage_rejector(lvl, rejected) or info.get("approver_name")) if decided or s.get("rejected_count") else None,
            "acted_at_ist": fmt_ist(decided), "acted_at_utc": iso_utc(decided),
        })

    all_entries = [entry_to_api(e, "active") for e in active] + [entry_to_api(e, "rejected") for e in rejected]
    all_entries.sort(key=lambda e: (e.get("date") or "", e["id"]))
    original_total = round(sum(e["original_amount"] for e in all_entries), 2)

    timeline = events or reconstruct_timeline(employee_id, month, ps)

    ls = await lock_state(employee_id, month)
    return {
        "employee": {
            "id": employee_id, "name": emp.get("Emp Name"), "designation": emp.get("Designation Name"),
            "gender": emp.get("Gender"), "partner": emp.get("Partner"),
            "reporting_manager": emp.get("ReportingEmpName"),
            "reporting_manager_code": emp.get("ReportingEmpCode"),
        },
        "payroll_month": month,
        "status": {
            "overall_status": overall, "current_level": current_level,
            "total_levels": ps.get("total_levels"), "submission_version": ps.get("submission_version", 1),
            "submitted_at_ist": fmt_ist(ps.get("submission_date")),
            "is_fixed_amount": bool(ps.get("fixed_amount")),
        },
        "limit": {"amount": ps.get("limit"), "upload_version": ps.get("limit_upload_version")},
        "amounts": {
            "original_submitted": original_total,
            "original_estimated": any(not e["original_amount_known"] for e in all_entries),
            "current_total": ps.get("total_amount"),
            "stages": stages,
            "edit_history": [
                {**h, "edited_date_ist": fmt_ist(h.get("edited_date"))}
                for h in ps.get("amount_edit_history", [])
            ],
        },
        "entries": all_entries,
        "timeline": timeline,
        "timeline_source": "audit_log" if events else "reconstructed",
        "lock": ls,
    }
