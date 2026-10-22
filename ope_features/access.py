"""One submission per employee per payroll month + HR/Admin-controlled reopening,
and the monthly eligibility / limit / fixed-amount policy lookups."""
import functools
import logging
from datetime import timedelta
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from .audit import write_audit
from .payroll_months import month_open
from .common import (
    db, employee_lock, is_restricted, find_bucket, find_month_status, fmt_ist, iso_utc,
    normalize_month, now_utc, safe_num,
)

log = logging.getLogger("ope.access")
PERMS = "OPE_reopen_permissions"
INFLIGHT = "OPE_submission_inflight"
CONTACT_HR = "Please contact HR if you need to resubmit."


# ---------------------------------------------------------------- policy
async def get_month_policy(employee_id: str, month: str) -> Optional[dict]:
    """Policy for one employee in one month from that month's ACTIVE upload
    version. None means no upload is active for the month (legacy behaviour:
    Employee_details.OPE LIMIT applies and anyone may submit)."""
    ptr = await db()["OPE_monthly_active"].find_one({"payroll_month": month})
    if not ptr:
        return None
    row = await db()["OPE_monthly_rows"].find_one(
        {"version_id": ptr["version_id"], "emp_id": employee_id.strip().upper()})
    base = {"version_id": ptr["version_id"], "version": ptr.get("version")}
    if not row:
        return {**base, "eligible": False, "ope_limit": None, "fixed_amount": None}
    return {**base, "eligible": True, "ope_limit": row.get("ope_limit"),
            "fixed_amount": row.get("fixed_amount")}


async def apply_month_policy_limit(emp: Optional[dict], month: str) -> Optional[dict]:
    """Return `emp` with 'OPE LIMIT' replaced by the month's uploaded limit (a
    copy; the Employee_details master and other months are never touched)."""
    if not emp:
        return emp
    try:
        month = normalize_month(month)
        pol = await get_month_policy(str(emp.get("EmpID") or "").upper(), month)
    except HTTPException:
        return emp
    if pol and pol["eligible"] and pol.get("ope_limit") is not None:
        emp = dict(emp)
        emp["OPE LIMIT"] = pol["ope_limit"]
    return emp


# ------------------------------------------------------------------ state
async def month_is_submitted(employee_id: str, month: str) -> bool:
    st = await db()["Status"].find_one({"employeeId": employee_id})
    idx, _ = find_month_status(st, month)
    if idx is not None:
        return True
    for coll in ("OPE_data", "Reject_OPE_data"):
        if find_bucket(await db()[coll].find_one({"employeeId": employee_id}), month):
            return True
    return False


async def active_permission(employee_id: str, month: str) -> Optional[dict]:
    return await db()[PERMS].find_one(
        {"employeeId": employee_id, "payroll_month": month, "status": "active"})


async def lock_state(employee_id: str, month: str) -> dict:
    """What the UI needs to know about one employee+month."""
    employee_id = employee_id.strip().upper()
    month = normalize_month(month)
    pol = await get_month_policy(employee_id, month)
    submitted = await month_is_submitted(employee_id, month)
    perm = await active_permission(employee_id, month) if submitted else None
    restricted = await is_restricted(employee_id)
    st = {
        "employee_id": employee_id, "payroll_month": month,
        "submitted": submitted,
        "eligible": True if pol is None else pol["eligible"],
        "policy_active": pol is not None,
        "ope_limit": (pol or {}).get("ope_limit"),
        "fixed_amount": (pol or {}).get("fixed_amount"),
        "upload_version": (pol or {}).get("version"),
        "reopen_permitted": perm is not None,
        "locked": False, "reason": None, "message": None,
    }
    if restricted:
        st.update(locked=True, reason="restricted",
                  message="You are not allowed to fill your own OPE. HR prepares and approves your OPE for each payroll month; check the Status page.")
    elif pol is not None and not pol["eligible"]:
        st.update(locked=True, reason="not_eligible",
                  message=f"You are not in the eligible employee list for {month}. Please contact HR.")
    elif pol is not None and pol.get("fixed_amount") is not None:
        amt = pol["fixed_amount"]
        st.update(locked=True, reason="fixed_amount",
                  message=(f"Your OPE amount for {month} is fixed at ₹{amt:,.2f} by HR. "
                           "You do not need to fill the OPE form; HR will review it."))
    elif submitted and perm is None:
        st.update(locked=True, reason="already_submitted",
                  message=f"OPE for {month} has already been submitted. You cannot submit again. {CONTACT_HR}")
    if not st["locked"] and not submitted and not await month_open(month):
        st.update(locked=True, reason="month_closed",
                  message=f"Submission for {month} is not open. Please contact HR.")
    return st


async def assert_can_save(employee_id: str, month: str) -> dict:
    s = await lock_state(employee_id, month)
    if s["locked"]:
        code = 403 if s["reason"] in ("not_eligible", "fixed_amount", "restricted", "month_closed") else 409
        raise HTTPException(status_code=code, detail=s["message"])
    return s


# ------------------------------------------------------- duplicate entries
def entry_signature(e: dict) -> tuple:
    """Two entries are the same claim when date, client, project, route, mode and amount all match
    (remarks and the ticket PDF are not part of the comparison; same rule as the existing save check)."""
    def t(v):
        return str(v if v is not None else "").strip().lower()
    return (t(e.get("date")), t(e.get("client")), t(e.get("project_id")), t(e.get("project_name")),
            t(e.get("project_type")), t(e.get("location_from")), t(e.get("location_to")),
            t(e.get("travel_mode")), round(safe_num(e.get("amount")), 2))


async def _live_signatures(employee_id: str, month: str) -> set:
    """Entries already submitted for this month that are still pending or approved."""
    doc = await db()["OPE_data"].find_one({"employeeId": employee_id})
    return {entry_signature(e) for e in find_bucket(doc, month)
            if (e.get("status") or "").lower() in ("pending", "approved")}


# ------------------------------------------------------- submit-final wrap
async def _acquire_inflight(employee_id: str, month: str) -> None:
    coll = db()[INFLIGHT]
    cutoff = now_utc() - timedelta(minutes=2)
    await coll.delete_many({"employeeId": employee_id, "payroll_month": month,
                            "created_at": {"$lt": cutoff}})  # stale lock from a crashed request
    try:
        await coll.insert_one({"employeeId": employee_id, "payroll_month": month,
                               "created_at": now_utc()})
    except DuplicateKeyError:
        raise HTTPException(status_code=409,
                            detail="A submission for this month is already in progress. Please wait a moment.")


async def _release_inflight(employee_id: str, month: str) -> None:
    await db()[INFLIGHT].delete_one({"employeeId": employee_id, "payroll_month": month})


def guarded_submit(fn):
    """Wrap POST /api/ope/submit-final:
    * month must be eligible / not fixed-amount;
    * a month that was already submitted stays locked unless HR/Admin granted a
      reopen permission, which is consumed atomically (single use);
    * a unique in-flight marker stops double-clicks / concurrent submits;
    * on success the new entries are stamped with original_amount and
      submission_version, and a 'submitted' audit event is written."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        request, user = kwargs.get("request"), kwargs.get("current_user")
        if request is None or user is None:
            return await fn(*args, **kwargs)
        try:
            body = await request.json()
            month = normalize_month(body.get("month_range"))
        except Exception:
            return await fn(*args, **kwargs)  # original endpoint produces the validation error
        emp = str(user["employee_code"]).strip().upper()

        async with employee_lock(emp):
            state = await assert_can_save(emp, month)
            is_resubmission = state["submitted"]
            perm_id = None
            if is_resubmission:
                perm = await db()[PERMS].find_one_and_update(
                    {"employeeId": emp, "payroll_month": month, "status": "active"},
                    {"$set": {"status": "used", "used_at": now_utc()}})
                if not perm:
                    raise HTTPException(status_code=409, detail=state["message"] or CONTACT_HR)
                perm_id = perm["_id"]

            temp_entries = find_bucket(await db()["Temp_OPE_data"].find_one({"employeeId": emp}), month)
            seen = await _live_signatures(emp, month)
            for te in temp_entries:
                sig = entry_signature(te)
                if sig in seen:
                    raise HTTPException(
                        status_code=409,
                        detail="Duplicate entries found: two entries for this month are identical "
                               f"(date {te.get('date')}, {te.get('project_name')}, {te.get('location_from')} to "
                               f"{te.get('location_to')}, Rs {te.get('amount')}). Remove the duplicate before submitting.")
                seen.add(sig)
            temp_ids = {str(e.get("_id")) for e in temp_entries}
            st0 = await db()["Status"].find_one({"employeeId": emp})
            _i0, ps0 = find_month_status(st0, month)
            prev_status = (ps0 or {}).get("overall_status")
            prev_version = (ps0 or {}).get("submission_version", 1) if ps0 else 0

            try:
                await _acquire_inflight(emp, month)
            except HTTPException:
                if perm_id:
                    await db()[PERMS].update_one({"_id": perm_id}, {"$set": {"status": "active"},
                                                                    "$unset": {"used_at": ""}})
                raise
            try:
                result = await fn(*args, **kwargs)
            except BaseException:
                if perm_id:  # nothing was submitted: give the permission back
                    await db()[PERMS].update_one({"_id": perm_id}, {"$set": {"status": "active"},
                                                                    "$unset": {"used_at": ""}})
                raise
            finally:
                await _release_inflight(emp, month)

            try:
                await _post_submit(emp, month, temp_ids, is_resubmission, prev_status, prev_version,
                                   perm_id, state)
            except Exception:  # pragma: no cover - submission is committed
                log.exception("post-submit stamping failed for %s %s", emp, month)
            return result
    return wrapper


async def _post_submit(emp, month, temp_ids, is_resubmission, prev_status, prev_version, perm_id, state):
    d = db()
    version = prev_version + 1 if is_resubmission else 1
    doc = await d["OPE_data"].find_one({"employeeId": emp})
    sets, total_orig, count = {}, 0.0, 0
    for i, item in enumerate(doc.get("Data", []) if doc else []):
        if month in item:
            for j, e in enumerate(item[month]):
                if str(e.get("_id")) in temp_ids:
                    amt = safe_num(e.get("amount"))
                    sets[f"Data.{i}.{month}.{j}.original_amount"] = amt
                    sets[f"Data.{i}.{month}.{j}.submission_version"] = version
                    total_orig += amt
                    count += 1
    if sets:
        await d["OPE_data"].update_one({"employeeId": emp}, {"$set": sets})
    st = await d["Status"].find_one({"employeeId": emp})
    idx, ps = find_month_status(st, month)
    new_status = None
    if idx is not None:
        upd = {f"approval_status.{idx}.submission_version": version}
        if state.get("upload_version") is not None:
            upd[f"approval_status.{idx}.limit_upload_version"] = state["upload_version"]
        await d["Status"].update_one({"employeeId": emp}, {"$set": upd})
        new_status = ps.get("overall_status")
    await write_audit(
        employeeId=emp, payroll_month=month, submission_version=version,
        action="resubmitted" if is_resubmission else "submitted",
        stage="Employee", actor_id=emp, actor_name=emp, actor_role="Employee",
        prev_status=prev_status, new_status=new_status,
        original_amount=round(total_orig, 2), entry_count=count,
        remark=("Resubmitted under HR reopen permission" if is_resubmission else None),
    )


def guarded_save(fn):
    """Wrap POST /api/ope/save-temp (Form endpoint): same eligibility/lock rules
    so an employee is stopped before filling a form that cannot be submitted."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        user, month_range = kwargs.get("current_user"), kwargs.get("month_range")
        if user is not None and month_range:
            emp = str(user["employee_code"]).strip().upper()
            month = normalize_month(month_range)
            await assert_can_save(emp, month)
            if entry_signature(kwargs) in await _live_signatures(emp, month):
                raise HTTPException(
                    status_code=409,
                    detail="Duplicate entry: an identical entry has already been submitted for this month.")
        return await fn(*args, **kwargs)
    return wrapper


# ----------------------------------------------------------- reopen CRUD
def perm_to_api(p: dict) -> dict:
    return {
        "id": str(p["_id"]),
        "employee_id": p.get("employeeId"),
        "employee_name": p.get("employee_name"),
        "payroll_month": p.get("payroll_month"),
        "status": p.get("status"),
        "reason": p.get("reason"),
        "granted_by": p.get("granted_by"),
        "granted_at_ist": fmt_ist(p.get("granted_at")),
        "granted_at_utc": iso_utc(p.get("granted_at")),
        "used_at_ist": fmt_ist(p.get("used_at")),
        "revoked_by": p.get("revoked_by"),
        "revoked_at_ist": fmt_ist(p.get("revoked_at")),
        "revoke_reason": p.get("revoke_reason"),
    }


async def grant_reopen(actor: str, actor_role: str, employee_id: str, month: str, reason: str) -> dict:
    employee_id = employee_id.strip().upper()
    month = normalize_month(month)
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=400, detail="A reason is required to reopen a month")
    if len(reason) > 500:
        raise HTTPException(status_code=400, detail="Reason is too long (max 500 characters)")
    emp = await db()["Employee_details"].find_one({"EmpID": employee_id})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    async with employee_lock(employee_id):
        if not await month_is_submitted(employee_id, month):
            raise HTTPException(status_code=400,
                                detail="This employee has not submitted for that month, so it is not locked")
        doc = {"employeeId": employee_id, "employee_name": emp.get("Emp Name"),
               "payroll_month": month, "status": "active", "reason": reason,
               "granted_by": actor, "granted_by_role": actor_role, "granted_at": now_utc()}
        try:
            res = await db()[PERMS].insert_one(doc)
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="An active reopen permission already exists for this month")
        # the partial unique index is the real guard; this covers deployments without it
        n = await db()[PERMS].count_documents({"employeeId": employee_id, "payroll_month": month, "status": "active"})
        if n > 1:
            await db()[PERMS].delete_one({"_id": res.inserted_id})
            raise HTTPException(status_code=409, detail="An active reopen permission already exists for this month")
        st = await db()["Status"].find_one({"employeeId": employee_id})
        _i, ps = find_month_status(st, month)
        await write_audit(
            employeeId=employee_id, payroll_month=month,
            submission_version=(ps or {}).get("submission_version", 1),
            action="reopened", stage=actor_role, actor_id=actor, actor_name=actor, actor_role=actor_role,
            prev_status=(ps or {}).get("overall_status"), new_status=(ps or {}).get("overall_status"),
            remark=reason)
        doc["_id"] = res.inserted_id
        return perm_to_api(doc)


async def revoke_reopen(actor: str, actor_role: str, employee_id: str, month: str, reason: str) -> dict:
    employee_id = employee_id.strip().upper()
    month = normalize_month(month)
    reason = (reason or "").strip() or "Revoked"
    async with employee_lock(employee_id):
        perm = await db()[PERMS].find_one_and_update(
            {"employeeId": employee_id, "payroll_month": month, "status": "active"},
            {"$set": {"status": "revoked", "revoked_by": actor, "revoked_at": now_utc(),
                      "revoke_reason": reason}})
        if not perm:
            raise HTTPException(status_code=404, detail="No active reopen permission for that employee and month")
        st = await db()["Status"].find_one({"employeeId": employee_id})
        _i, ps = find_month_status(st, month)
        await write_audit(
            employeeId=employee_id, payroll_month=month,
            submission_version=(ps or {}).get("submission_version", 1),
            action="reopen_revoked", stage=actor_role, actor_id=actor, actor_name=actor,
            actor_role=actor_role, prev_status=(ps or {}).get("overall_status"),
            new_status=(ps or {}).get("overall_status"), remark=reason)
        perm.update(status="revoked", revoked_by=actor, revoke_reason=reason)
        return perm_to_api(perm)
