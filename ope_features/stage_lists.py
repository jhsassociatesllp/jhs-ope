"""One-call data for the Approve / Reject tabs.

The tabs used to fetch every employee one request at a time (hundreds of round trips for HR).
This returns the same entries, in the same shape, for the whole tab in a single request."""
from fastapi import APIRouter, Depends, HTTPException, Query

from .common import HR_CODE, db

# (kind, stage) -> (routing list collection, key field)
LISTS = {
    ("approved", "manager"): ("Approved", "ReportingEmpCode"),
    ("approved", "partner"): ("Partner_Approved", "PartnerEmpCode"),
    ("approved", "hr"): ("HR_Approved", "HR_Code"),
    ("rejected", "manager"): ("Rejected", "ReportingEmpCode"),
    ("rejected", "partner"): ("Partner_Rejected", "PartnerEmpCode"),
    ("rejected", "hr"): ("HR_Rejected", "HR_Code"),
}


def _approved_by_stage(e: dict, stage: str) -> bool:
    if stage == "manager":
        return bool(e.get("L1_approved")) and str(e.get("L1_approver_code") or "").upper() != "SYSTEM"
    if stage == "partner":
        return bool(e.get("L2_approved") or e.get("partner_approved"))
    return bool(e.get("hr_approved"))


def _common(e: dict, doc: dict, month: str) -> dict:
    return {
        "_id": str(e.get("_id", "")), "employee_id": doc.get("employeeId"),
        "employee_name": doc.get("employeeName", ""), "designation": doc.get("designation", ""),
        "month_range": month, "date": e.get("date"), "client": e.get("client"),
        "project_id": e.get("project_id"), "project_name": e.get("project_name"),
        "project_type": e.get("project_type", "N/A"), "location_from": e.get("location_from"),
        "location_to": e.get("location_to"), "travel_mode": e.get("travel_mode"),
        "amount": e.get("amount"), "remarks": e.get("remarks"), "ticket_pdf": e.get("ticket_pdf"),
        "created_time": e.get("created_time"),
    }


async def stage_entries(actor: str, kind: str, stage: str) -> list:
    actor = actor.strip().upper()
    if stage == "hr" and actor != HR_CODE:
        raise HTTPException(status_code=403, detail="Only HR can use the HR stage")
    if stage == "partner" and not await db()["Partner"].find_one({"PartnerEmpCode": actor}):
        raise HTTPException(status_code=403, detail="You are not a Partner")
    if stage == "manager" and not await db()["Reporting_managers"].find_one({"ReportingEmpCode": actor}):
        raise HTTPException(status_code=403, detail="You are not a reporting manager")
    coll, key = LISTS[(kind, stage)]
    lst = await db()[coll].find_one({key: actor})
    codes = list((lst or {}).get("EmployeesCodes", []))
    source = "OPE_data" if kind == "approved" else "Reject_OPE_data"
    out = []
    for i in range(0, len(codes), 300):
        async for doc in db()[source].find({"employeeId": {"$in": codes[i:i + 300]}}):
            for item in doc.get("Data", []):
                for month, entries in item.items():
                    for e in entries:
                        if kind == "approved":
                            direct = stage == "hr" and e.get("hr_direct_approved") and (e.get("status") or "").lower() == "pending"
                            if not direct and ((e.get("status") or "").lower() != "approved" or not _approved_by_stage(e, stage)):
                                continue
                            remark = e.get("approval_remark") or e.get("remark") or ""
                            row = _common(e, doc, month)
                            row.update({
                                "approved_by": e.get("approved_by"), "approver_name": e.get("approver_name"),
                                "approval_remark": remark, "approved_date": e.get("approved_date"),
                                "L1_approved": e.get("L1_approved"), "L1_approver_code": e.get("L1_approver_code"),
                                "L1_approver_name": e.get("L1_approver_name"),
                            })
                        else:
                            if str(e.get("rejected_by") or "").strip().upper() != actor:
                                continue
                            row = _common(e, doc, month)
                            row.update({
                                "rejected_by": e.get("rejected_by"), "rejector_name": e.get("rejector_name"),
                                "rejected_date": e.get("rejected_date"), "rejection_reason": e.get("rejection_reason"),
                                "rejected_level": e.get("rejected_level"),
                            })
                        out.append(row)
    return out


def build_router(get_current_user) -> APIRouter:
    r = APIRouter()

    @r.get("/api/ope/stage-entries")
    async def stage_entries_endpoint(kind: str = Query(...), stage: str = Query(...), u=Depends(get_current_user)):
        if kind not in ("approved", "rejected") or stage not in ("manager", "partner", "hr"):
            raise HTTPException(status_code=400, detail="Invalid kind or stage")
        return {"entries": await stage_entries(str(u["employee_code"]), kind, stage)}

    return r
