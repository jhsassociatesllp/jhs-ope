"""Restricted employees: people who may not fill their own OPE.

They keep their normal login. For every payroll month a record is created for them
automatically (one per employee per month) and sent to HR; the employee sees
"Pending HR Approval" on the Status page until HR approves it."""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from .common import (
    IST, RESTRICTED, build_month_label, db, fmt_ist, is_restricted, now_utc, parse_amount,
    require_admin,
)
from .uploads import create_fixed_submission

log = logging.getLogger("ope.restricted")
MONTHS_GUARD = "ope_restricted_months"
PERIOD_START_DAY = 21  # payroll periods run 21st -> 20th, as configured in the OPE form


def current_period_label(now: Optional[datetime] = None) -> str:
    """Payroll month containing today (IST), e.g. 19 Oct 2026 -> 'September 2026 - October 2026'."""
    d = (now or now_utc()).astimezone(IST)
    if d.day >= PERIOD_START_DAY:
        return build_month_label(d.month, d.year)
    prev_month, prev_year = (12, d.year - 1) if d.month == 1 else (d.month - 1, d.year)
    return build_month_label(prev_month, prev_year)


async def ensure_month_record(employee_id: str, month: Optional[str] = None) -> str:
    """Create the month's HR-pending record for one restricted employee.
    Idempotent: a unique (employee, month) guard makes duplicates impossible."""
    employee_id = employee_id.strip().upper()
    r = await is_restricted(employee_id)
    if not r:
        return "not_restricted"
    month = month or current_period_label()
    amount = r.get("ope_limit")
    if amount is None:
        emp = await db()["Employee_details"].find_one({"EmpID": employee_id}) or {}
        amount = emp.get("OPE LIMIT", emp.get("OPE Limit"))
    try:
        amount = parse_amount(amount, allow_zero=False)
    except ValueError:
        return "no OPE amount configured"
    try:
        await db()[MONTHS_GUARD].insert_one(
            {"employee_id": employee_id, "payroll_month": month, "created_at": now_utc()})
    except DuplicateKeyError:
        return "exists"
    # also guards deployments where the unique index could not be built
    if await db()[MONTHS_GUARD].count_documents({"employee_id": employee_id, "payroll_month": month}) > 1:
        return "exists"
    try:
        outcome = await create_fixed_submission(employee_id, month, amount, amount, {"version": None},
                                                restricted=True)
    except Exception:
        await db()[MONTHS_GUARD].delete_one({"employee_id": employee_id, "payroll_month": month})
        raise
    await db()[MONTHS_GUARD].update_one({"employee_id": employee_id, "payroll_month": month},
                                        {"$set": {"outcome": outcome}})
    return outcome


async def ensure_all_current() -> int:
    created = 0
    async for r in db()[RESTRICTED].find({"active": True}):
        try:
            if await ensure_month_record(r["employee_id"]) == "created":
                created += 1
        except Exception:
            log.exception("could not create monthly record for %s", r.get("employee_id"))
    return created


async def month_watcher(interval_seconds: int = 1800) -> None:
    """Runs for the life of the app: when a new payroll month starts, records appear
    within `interval_seconds` (they are also created on login / status view)."""
    while True:
        try:
            n = await ensure_all_current()
            if n:
                log.info("created %s restricted-employee monthly records", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("restricted month watcher failed")
        await asyncio.sleep(interval_seconds)


def restriction_to_api(r: dict) -> dict:
    return {"employee_id": r["employee_id"], "employee_name": r.get("employee_name"),
            "ope_limit": r.get("ope_limit"), "active": bool(r.get("active")),
            "created_at_ist": fmt_ist(r.get("created_at")), "created_by": r.get("created_by"),
            "updated_at_ist": fmt_ist(r.get("updated_at")), "updated_by": r.get("updated_by")}


async def upsert_restriction(actor: str, employee_id: str, ope_limit, active: bool) -> dict:
    employee_id = employee_id.strip().upper()
    emp = await db()["Employee_details"].find_one({"EmpID": employee_id})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found in Employee Details")
    limit = emp.get("OPE LIMIT", emp.get("OPE Limit")) if ope_limit in (None, "") else ope_limit
    try:
        limit = parse_amount(limit, allow_zero=False)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=f"OPE limit: {ex}")
    now = now_utc()
    await db()[RESTRICTED].update_one(
        {"employee_id": employee_id},
        {"$set": {"employee_name": emp.get("Emp Name"), "ope_limit": limit, "active": bool(active),
                  "updated_at": now, "updated_by": actor},
         "$setOnInsert": {"created_at": now, "created_by": actor}},
        upsert=True)
    doc = await db()[RESTRICTED].find_one({"employee_id": employee_id})
    outcome = await ensure_month_record(employee_id) if active else None
    return {**restriction_to_api(doc), "current_month_record": outcome}


class RestrictionBody(BaseModel):
    employee_id: str = Field(min_length=1, max_length=40)
    ope_limit: Optional[float] = None
    active: bool = True


def build_router(get_current_user) -> APIRouter:
    r = APIRouter()

    def code(u) -> str:
        return str(u["employee_code"]).strip().upper()

    @r.get("/api/ope/my-restriction")
    async def my_restriction(u=Depends(get_current_user)):
        """Used by the employee screens right after login."""
        rec = await is_restricted(code(u))
        if not rec:
            return {"restricted": False}
        month = current_period_label()
        await ensure_month_record(code(u), month)
        return {"restricted": True, "payroll_month": month,
                "message": "You are not allowed to fill your own OPE. HR prepares and approves it for each "
                           "payroll month; see the Status page for this month's status."}

    @r.get("/api/admin/restricted-employees")
    async def list_restricted(u=Depends(get_current_user)):
        await require_admin(code(u))
        items = [restriction_to_api(x) async for x in db()[RESTRICTED].find({}).sort("employee_id", 1)]
        return {"items": items, "total": len(items), "current_month": current_period_label()}

    @r.post("/api/admin/restricted-employees")
    async def save_restricted(body: RestrictionBody, u=Depends(get_current_user)):
        await require_admin(code(u))
        return await upsert_restriction(code(u), body.employee_id, body.ope_limit, body.active)

    return r
