"""HR "Partial Pending": submissions that were submitted but have not yet cleared every
mandatory Reporting Manager / Partner level. Read-only for HR - the existing approval
hierarchy is untouched, and `ensure_hr_stage` stops the existing HR approve/reject
endpoints from being used to skip a level or to decide the same month twice.

Source of truth: Status.approval_status[].current_level / overall_status (the same
fields the HR Pending list already uses). Nothing is written by this module."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .common import HR_CODE, db, fmt_ist, safe_num


def hr_level_key(ps: dict) -> str:
    """HR is always the last configured level: L3 for 3-level, otherwise L2."""
    return "L3" if ps.get("total_levels", 2) == 3 else "L2"


def classify(ps: dict) -> str:
    """'partial' | 'hr_pending' | 'hr_approved' | 'hr_rejected' | 'other' for one Status month item."""
    lvl = ps.get("current_level")
    overall = (ps.get("overall_status") or "pending").lower()
    hr = hr_level_key(ps)
    if ps.get("hr_direct_approved"):
        return "hr_approved"  # HR decided early; RM/Partner approvals only update status afterwards
    if lvl in ("L1", "L2", "L3") and overall in ("pending", "partial"):
        return "hr_pending" if lvl == hr else "partial"
    if lvl == "Completed" or overall in ("approved", "rejected"):
        hr_info = ps.get(hr) or {}
        if overall == "approved" and hr_info.get("status"):
            return "hr_approved"
        if overall == "rejected" and (hr_info.get("rejected_count", 0) or hr_info.get("rejection_reason")):
            return "hr_rejected"
    return "other"


async def ensure_hr_stage(employee_id: str, month: Optional[str], action: str = "approve") -> None:
    """Backend guard for the existing HR approve/reject endpoints. Unknown / legacy
    records (no Status item) are left alone so historical data keeps working."""
    if not employee_id or not month:
        return
    doc = await db()["Status"].find_one({"employeeId": employee_id})
    ps = next((p for p in (doc or {}).get("approval_status", []) if p.get("payroll_month") == month), None)
    if not ps:
        return
    lvl = ps.get("current_level")
    if lvl in ("L1", "L2", "L3") and lvl != hr_level_key(ps):
        raise HTTPException(
            status_code=409,
            detail="This submission has not completed the Reporting Manager / Partner approvals yet, "
                   "so HR cannot approve or reject it.")
    if action == "approve" and ps.get("hr_direct_approved"):
        raise HTTPException(status_code=409, detail="HR has already approved this submission.")
    if action == "approve" and classify(ps) == "hr_approved":
        # every active entry is already HR-approved: a second HR approval is not allowed
        active = await db()["OPE_data"].find_one({"employeeId": employee_id}) or {}
        entries = [e for item in active.get("Data", []) for e in item.get(month, [])]
        if entries and all(e.get("hr_approved") for e in entries):
            raise HTTPException(status_code=409, detail="HR has already approved this submission.")


async def months_not_at_hr(employee_id: str) -> set:
    """Months still waiting on a Reporting Manager / Partner level (HR may not touch them)."""
    doc = await db()["Status"].find_one({"employeeId": employee_id}) or {}
    return {p.get("payroll_month") for p in doc.get("approval_status", [])
            if p.get("current_level") in ("L1", "L2", "L3") and p.get("current_level") != hr_level_key(p)}


def _label(info: Optional[dict], fallback: str) -> dict:
    info = info or {}
    if not info:
        return {"status": "Not required", "approver": None}
    if info.get("rejection_reason") or info.get("rejected_count"):
        st = "Rejected"
    elif info.get("status"):
        st = "Approved"
    else:
        st = "Pending"
    return {"status": st, "approver": info.get("approver_name") or fallback,
            "date": fmt_ist(info.get("approved_date")), "remark": info.get("approval_remark")}


async def build_partial_pending(q: str = "") -> list:
    d = db()
    q = (q or "").strip().lower()
    rows = []
    async for s in d["Status"].find({"approval_status.current_level": {"$in": ["L1", "L2"]}}):
        eid = s.get("employeeId")
        items = [p for p in s.get("approval_status", []) if classify(p) == "partial"]
        if not items:
            continue
        emp = await d["Employee_details"].find_one({"EmpID": eid}) or {}
        name = s.get("employeeName") or s.get("employee_name") or emp.get("Emp Name") or ""
        if q and q not in f"{eid} {name}".lower():
            continue
        for ps in items:
            if ps.get("restricted"):
                continue  # restricted employees only surface once HR can act (existing rule)
            levels = {l: ps.get(l) or {} for l in ("L1", "L2", "L3")}
            by_name = {v.get("level_name"): v for v in levels.values() if v}
            rm = by_name.get("Reporting Manager")
            partner = by_name.get("Partner")
            hr = levels[hr_level_key(ps)]
            cur = ps.get("current_level")
            rows.append({
                "employee_id": eid, "employee_name": name,
                "designation": emp.get("Designation Name") or "",
                "department": emp.get("Department") or emp.get("Department Name") or emp.get("Dept") or "",
                "reporting_manager": emp.get("ReportingEmpName") or "",
                "reporting_manager_code": emp.get("ReportingEmpCode") or "",
                "payroll_month": ps.get("payroll_month"),
                "submitted_amount": safe_num(ps.get("total_amount")),
                "submission_date": fmt_ist(ps.get("submission_date")),
                "total_levels": ps.get("total_levels", 2),
                "current_stage": f"Pending at {levels[cur].get('level_name', cur)}",
                "rm_status": _label(rm, "Reporting Manager"),
                "partner_status": _label(partner, "Partner"),
                "hr_status": {**_label(hr, "HR"), "status": "Pending"},
                "history": [{"level": l, "level_name": v.get("level_name"), **_label(v, "")}
                            for l, v in levels.items() if v],
                "hr_can_act": True,
            })
    rows.sort(key=lambda r: (r["employee_id"], r["payroll_month"] or ""))
    return rows


class DirectApproveBody(BaseModel):
    employee_id: str = Field(min_length=1, max_length=40)
    payroll_month: str = Field(min_length=3, max_length=60)
    remark: str = Field(default="", max_length=500)


async def hr_direct_approve(hr_code: str, employee_id: str, month: str, remark: str) -> int:
    """HR approves a submission that is still waiting on RM / Partner. The month's RM and
    Partner levels stay open: they can still approve later (updating status only) and the
    month then completes WITHOUT returning to HR Pending (see advance_level_if_ready)."""
    d = db()
    doc = await d["Status"].find_one({"employeeId": employee_id})
    idx = next((i for i, p in enumerate((doc or {}).get("approval_status", []))
                if p.get("payroll_month") == month), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    ps = doc["approval_status"][idx]
    if ps.get("hr_direct_approved") or classify(ps) != "partial":
        raise HTTPException(status_code=409, detail="This submission is not awaiting RM / Partner approval "
                                                    "or has already been approved by HR.")
    now = datetime.now(timezone.utc).isoformat()
    pre = f"approval_status.{idx}"
    # atomic claim: only one HR request can flip the flag (guards double clicks / two HR sessions)
    res = await d["Status"].update_one(
        {"employeeId": employee_id, f"{pre}.payroll_month": month,
         f"{pre}.current_level": ps.get("current_level"), f"{pre}.hr_direct_approved": {"$ne": True}},
        {"$set": {f"{pre}.hr_direct_approved": True, f"{pre}.hr_direct_approved_by": hr_code,
                  f"{pre}.hr_direct_approved_date": now, f"{pre}.hr_direct_remark": remark or "Approved by HR"}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="This submission was just updated by someone else. Refresh and retry.")
    ope = await d["OPE_data"].find_one({"employeeId": employee_id}) or {}
    n = 0
    for i, item in enumerate(ope.get("Data", [])):
        for j, e in enumerate(item.get(month, [])):
            if (e.get("status") or "").lower() in ("pending", "approved") and not e.get("hr_approved"):
                base = f"Data.{i}.{month}.{j}"
                await d["OPE_data"].update_one({"employeeId": employee_id}, {"$set": {
                    f"{base}.hr_approved": True, f"{base}.hr_approved_by": hr_code,
                    f"{base}.hr_approved_date": now, f"{base}.hr_direct_approved": True,
                    f"{base}.hr_approval_remark": remark or "Approved by HR"}})
                n += 1
    await d["HR_Approved"].update_one({"HR_Code": hr_code}, {"$addToSet": {"EmployeesCodes": employee_id}}, upsert=True)
    return n


def build_router(get_current_user) -> APIRouter:
    r = APIRouter()

    @r.get("/api/ope/hr/partial-pending")
    async def partial_pending(q: str = Query(""), u=Depends(get_current_user)):
        if str(u["employee_code"]).strip().upper() != HR_CODE:
            raise HTTPException(status_code=403, detail="Only HR can access Partial Pending")
        rows = await build_partial_pending(q)
        return {"rows": rows, "total_count": len(rows)}

    @r.post("/api/ope/hr/partial-pending/approve")
    async def partial_pending_approve(body: DirectApproveBody, u=Depends(get_current_user)):
        hr = str(u["employee_code"]).strip().upper()
        if hr != HR_CODE:
            raise HTTPException(status_code=403, detail="Only HR can approve from Partial Pending")
        n = await hr_direct_approve(hr, body.employee_id.strip().upper(), body.payroll_month, body.remark.strip())
        return {"success": True, "approved_entries": n,
                "message": "Approved by HR. Reporting Manager / Partner approvals will still update the status."}

    return r
