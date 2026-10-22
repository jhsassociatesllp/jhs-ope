"""Payroll months shown to employees, managed from the Admin panel.

Replaces the month list that used to be typed into index.html / script.js.
Months are never deleted, only hidden, so history and reports keep working."""
import logging
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from .audit import write_audit
from .common import (
    MONTH_NAMES, build_month_label, db, fmt_ist, normalize_month, now_utc, require_admin,
)

log = logging.getLogger("ope.months")
COLL = "ope_payroll_months"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The months that were hard-coded before this feature; inserted once if the collection is empty.
DEFAULTS = [
    ("june-july-2026", "June 2026 - July 2026", "2026-06-21", "2026-07-20", None, None),
    ("july-august-2026", "July 2026 - August 2026", "2026-07-21", "2026-08-20", "2026-09-02", "2026-09-05"),
    ("august-september-2026", "August 2026 - September 2026", "2026-08-21", "2026-09-20", "2026-09-26", None),
    ("september-october-2026", "September 2026 - October 2026", "2026-09-21", "2026-10-20", None, None),
]


def key_and_label(start_month: int, start_year: int):
    """('august-september-2026', 'August 2026 - September 2026'); a December start gets
    'december-january-2026-2027' so the year of each half is explicit."""
    label = build_month_label(start_month, start_year)
    m2 = start_month % 12 + 1
    first, second = MONTH_NAMES[start_month - 1].lower(), MONTH_NAMES[m2 - 1].lower()
    key = (f"{first}-{second}-{start_year}" if start_month != 12
           else f"{first}-{second}-{start_year}-{start_year + 1}")
    return key, label


def default_dates(start_month: int, start_year: int):
    """21st of the first month to the 20th of the next (the existing convention)."""
    m2 = start_month % 12 + 1
    y2 = start_year + (1 if start_month == 12 else 0)
    return date(start_year, start_month, 21).isoformat(), date(y2, m2, 20).isoformat()


def _iso(value: Optional[str], name: str, required: bool = False) -> Optional[str]:
    if value in (None, ""):
        if required:
            raise HTTPException(status_code=400, detail=f"{name} is required")
        return None
    if not _ISO.match(str(value)):
        raise HTTPException(status_code=400, detail=f"{name} must be a date (YYYY-MM-DD)")
    try:
        date.fromisoformat(str(value))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} is not a valid date")
    return str(value)


async def ensure_defaults() -> None:
    coll = db()[COLL]
    if await coll.count_documents({}) > 0:
        return
    now = now_utc()
    for key, display, start, end, sub, appr in DEFAULTS:
        try:
            await coll.insert_one({"key": key, "display": display, "start": start, "end": end,
                                   "submit_deadline": sub, "approve_deadline": appr, "visible": True,
                                   "created_at": now, "created_by": "system (initial months)"})
        except DuplicateKeyError:
            pass


def to_api(d: dict) -> dict:
    return {"key": d["key"], "display": d["display"], "start": d["start"], "end": d["end"],
            "submit_deadline": d.get("submit_deadline"), "approve_deadline": d.get("approve_deadline"),
            "visible": bool(d.get("visible")), "updated_by": d.get("updated_by") or d.get("created_by"),
            "updated_at_ist": fmt_ist(d.get("updated_at") or d.get("created_at"))}


async def month_open(label: str) -> bool:
    """May employees submit for this payroll month? True when it is shown to them.
    (If the list was never configured, nothing is restricted.)"""
    coll = db()[COLL]
    if await coll.count_documents({}) == 0:
        return True
    d = await coll.find_one({"display": label})
    return bool(d and d.get("visible"))


class MonthBody(BaseModel):
    start_month: int = Field(ge=1, le=12)
    start_year: int = Field(ge=2000, le=2100)
    start: Optional[str] = None
    end: Optional[str] = None
    submit_deadline: Optional[str] = None
    approve_deadline: Optional[str] = None
    visible: bool = True


class MonthUpdate(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    submit_deadline: Optional[str] = None
    approve_deadline: Optional[str] = None
    visible: Optional[bool] = None
    clear_submit_deadline: bool = False
    clear_approve_deadline: bool = False


def _check_order(start, end, sub, appr):
    if start and end and end < start:
        raise HTTPException(status_code=400, detail="End date cannot be before the start date")
    if sub and start and sub < start:
        raise HTTPException(status_code=400, detail="Submit-by date cannot be before the start date")
    if appr and sub and appr < sub:
        raise HTTPException(status_code=400, detail="Approve-by date cannot be before the submit-by date")


def build_router(get_current_user) -> APIRouter:
    r = APIRouter()

    def code(u) -> str:
        return str(u["employee_code"]).strip().upper()

    @r.get("/api/ope/payroll-months")
    async def visible_months(u=Depends(get_current_user)):
        """The months the OPE form offers (any logged-in user)."""
        await ensure_defaults()
        items = [to_api(d) async for d in db()[COLL].find({"visible": True}).sort("start", 1)]
        return {"configured": True, "months": items}

    @r.get("/api/admin/payroll-months")
    async def all_months(u=Depends(get_current_user)):
        await require_admin(code(u))
        await ensure_defaults()
        items = [to_api(d) async for d in db()[COLL].find({}).sort("start", -1)]
        return {"months": items}

    @r.post("/api/admin/payroll-months")
    async def create_month(body: MonthBody, u=Depends(get_current_user)):
        await require_admin(code(u))
        await ensure_defaults()
        key, label = key_and_label(body.start_month, body.start_year)
        d_start, d_end = default_dates(body.start_month, body.start_year)
        start = _iso(body.start, "Start date") or d_start
        end = _iso(body.end, "End date") or d_end
        sub = _iso(body.submit_deadline, "Submit-by date")
        appr = _iso(body.approve_deadline, "Approve-by date")
        _check_order(start, end, sub, appr)
        doc = {"key": key, "display": label, "start": start, "end": end, "submit_deadline": sub,
               "approve_deadline": appr, "visible": body.visible, "created_at": now_utc(),
               "created_by": code(u)}
        try:
            await db()[COLL].insert_one(doc)
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail=f"{label} already exists")
        await write_audit(employeeId="*", payroll_month=label, action="payroll_month_added", stage="Admin",
                          actor_id=code(u), actor_name=code(u), actor_role="Admin",
                          remark=f"{start} to {end}; {'shown' if body.visible else 'hidden'} to employees")
        return to_api(doc)

    @r.put("/api/admin/payroll-months/{key}")
    async def update_month(key: str, body: MonthUpdate, u=Depends(get_current_user)):
        await require_admin(code(u))
        cur = await db()[COLL].find_one({"key": key})
        if not cur:
            raise HTTPException(status_code=404, detail="Payroll month not found")
        upd = {}
        start = _iso(body.start, "Start date") or cur["start"]
        end = _iso(body.end, "End date") or cur["end"]
        sub = cur.get("submit_deadline")
        appr = cur.get("approve_deadline")
        if body.clear_submit_deadline:
            sub = None
        elif body.submit_deadline not in (None, ""):
            sub = _iso(body.submit_deadline, "Submit-by date")
        if body.clear_approve_deadline:
            appr = None
        elif body.approve_deadline not in (None, ""):
            appr = _iso(body.approve_deadline, "Approve-by date")
        _check_order(start, end, sub, appr)
        upd.update(start=start, end=end, submit_deadline=sub, approve_deadline=appr)
        if body.visible is not None:
            upd["visible"] = body.visible
        upd.update(updated_at=now_utc(), updated_by=code(u))
        await db()[COLL].update_one({"key": key}, {"$set": upd})
        new = await db()[COLL].find_one({"key": key})
        await write_audit(employeeId="*", payroll_month=cur["display"], action="payroll_month_changed",
                          stage="Admin", actor_id=code(u), actor_name=code(u), actor_role="Admin",
                          remark=("; ".join(f"{k}: {cur.get(k)} -> {new.get(k)}"
                                            for k in ("start", "end", "submit_deadline", "approve_deadline", "visible")
                                            if cur.get(k) != new.get(k)) or "no change"))
        return to_api(new)

    return r
