"""Shared helpers for the OPE feature package: DB context, time (UTC storage /
IST display), payroll-month normalisation, role lookups and approval scope."""
import asyncio
import math
import re
import weakref
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

HR_CODE = "JHS729"  # existing hard-coded HR identity used throughout main.py
IST = ZoneInfo("Asia/Kolkata")

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]
_ABBR = {m[:3].lower(): m[:3] for m in MONTH_NAMES}
_FULL = {m.lower(): m for m in MONTH_NAMES}

# canonical payroll month label, e.g. "August 2026 - September 2026"
_MONTH_LABEL_RE = re.compile(r"^[A-Za-z]{3,9} \d{4} - [A-Za-z]{3,9} \d{4}$")


class Ctx:
    """Holds the Mongo database handle. main.py assigns `ctx.db` at start-up
    (tests assign a mock), so nothing in this package imports main."""
    db = None


ctx = Ctx()


def db():
    if ctx.db is None:
        raise RuntimeError("ope_features not initialised")
    return ctx.db


# ------------------------------------------------------------------ time
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(value: Any) -> Optional[datetime]:
    """Accept datetime / ISO string (naive values are UTC, as main.py stores
    `datetime.utcnow().isoformat()`) and return an aware UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            s = str(value).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(value: Any) -> Optional[str]:
    dt = to_utc(value)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def fmt_ist(value: Any) -> Optional[str]:
    """Unambiguous IST display, e.g. '18 Oct 2026, 03:45 PM IST'."""
    dt = to_utc(value)
    if not dt:
        return None
    return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


# ------------------------------------------------------------ payroll month
def normalize_month(value: Any) -> str:
    """Return the canonical payroll-month key used as Status.payroll_month and
    as the OPE_data bucket key. Mirrors main.py's format_month_range for UI
    values such as 'august-september-2026' and passes canonical labels through."""
    s = str(value or "").strip()
    if not s:
        raise HTTPException(status_code=400, detail="Payroll month is required")
    if " - " in s:
        out = re.sub(r"\s+", " ", s)
    else:
        parts = s.lower().split("-")
        if len(parts) == 3:
            m1 = _ABBR.get(parts[0]) or parts[0].capitalize()
            m2 = _ABBR.get(parts[1]) or parts[1].capitalize()
            out = f"{m1} {parts[2]} - {m2} {parts[2]}"
        elif len(parts) == 4:  # year-crossing period, e.g. december-january-2026-2027
            m1 = _ABBR.get(parts[0]) or parts[0].capitalize()
            m2 = _ABBR.get(parts[1]) or parts[1].capitalize()
            out = f"{m1} {parts[2]} - {m2} {parts[3]}"
        else:
            out = s
    if not _MONTH_LABEL_RE.match(out):
        raise HTTPException(status_code=400, detail=f"Invalid payroll month: {s[:60]}")
    return out


def build_month_label(start_month: int, start_year: int) -> str:
    """'August 2026 - September 2026' from (8, 2026); Dec rolls into next year."""
    if not (1 <= int(start_month) <= 12) or not (2000 <= int(start_year) <= 2100):
        raise HTTPException(status_code=400, detail="Invalid month or year")
    m2 = int(start_month) % 12 + 1
    y2 = int(start_year) + (1 if int(start_month) == 12 else 0)
    return (f"{MONTH_NAMES[int(start_month) - 1]} {int(start_year)} - "
            f"{MONTH_NAMES[m2 - 1]} {y2}")


# --------------------------------------------------------------- amounts
def parse_amount(value: Any, *, allow_zero: bool = True) -> float:
    """Strict numeric parsing: finite, non-negative (existing rules never allow
    negative OPE amounts)."""
    if isinstance(value, bool):
        raise ValueError("Amount must be a number")
    try:
        f = float(str(value).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        raise ValueError("Amount must be a number")
    if math.isnan(f) or math.isinf(f):
        raise ValueError("Amount must be a finite number")
    if f < 0 or (f == 0 and not allow_zero):
        raise ValueError("Amount must be greater than 0" if not allow_zero else "Amount cannot be negative")
    return round(f, 2)


def safe_num(value: Any) -> float:
    try:
        f = float(value)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return 0.0


# -------------------------------------------------------------- locking
_locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()


def employee_lock(employee_id: str) -> asyncio.Lock:
    """Per-employee mutex: serialises approve/reject/submit calls for one
    employee inside this process so repeated clicks / concurrent requests
    cannot interleave. (The app runs as a single uvicorn process.)"""
    key = str(employee_id).strip().upper()
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


# ------------------------------------------------------------ restrictions
RESTRICTED = "ope_restricted_employees"


async def is_restricted(employee_id: str):
    """Active restriction document for this employee, else None."""
    return await db()[RESTRICTED].find_one({"employee_id": str(employee_id).strip().upper(), "active": True})


def employee_ope_limit(emp):
    """OPE limit from an Employee_details document, whichever way the column is spelled
    ("OPE LIMIT", "OPE Limit", "ope_limit"...). None when the employee has no usable limit."""
    if not emp:
        return None
    raw = None
    for key in ("OPE LIMIT", "OPE Limit"):
        if emp.get(key) not in (None, ""):
            raw = emp[key]
            break
    if raw is None:
        for k, v in emp.items():
            if str(k).strip().lower().replace("_", " ") == "ope limit" and v not in (None, ""):
                raw = v
                break
    try:
        return float(str(raw).replace(",", "").strip()) if raw is not None else None
    except ValueError:
        return None


# ----------------------------------------------------------------- roles
async def is_admin(code: str) -> bool:
    doc = await db()["Admin"].find_one({})
    if not doc:
        return False
    return code.strip().upper() in [str(c).upper() for c in doc.get("employee_codes", [])]


async def get_roles(code: str) -> dict:
    code = code.strip().upper()
    return {
        "is_hr": code == HR_CODE,
        "is_admin": await is_admin(code),
        "is_manager": await db()["Reporting_managers"].find_one({"ReportingEmpCode": code}) is not None,
        "is_partner": await db()["Partner"].find_one({"PartnerEmpCode": code}) is not None,
    }


async def require_hr_or_admin(code: str) -> dict:
    roles = await get_roles(code)
    if not (roles["is_hr"] or roles["is_admin"]):
        raise HTTPException(status_code=403, detail="Only HR or Admin can perform this action")
    return roles


async def require_admin(code: str) -> None:
    if not await is_admin(code):
        raise HTTPException(status_code=403, detail="Admin access required")


# ----------------------------------------------------------------- scope
async def approver_in_scope(actor: str, role: str, employee_id: str) -> bool:
    """True when `actor` is an assigned approver (role 'manager' | 'partner') of
    `employee_id` - by current Employee_details, by an approver recorded on the
    employee's Status months, or by the routing lists the app already keeps."""
    actor = actor.strip().upper()
    employee_id = employee_id.strip().upper()
    d = db()
    emp = await d["Employee_details"].find_one({"EmpID": employee_id})
    if emp:
        rm = str(emp.get("ReportingEmpCode") or "").strip().upper()
        pt = str(emp.get("PartnerEmpCode") or "").strip().upper()
        if role == "manager" and rm == actor:
            return True
        if role == "partner" and pt == actor:
            return True
    wanted = "Reporting Manager" if role == "manager" else "Partner"
    st = await d["Status"].find_one({"employeeId": employee_id})
    if st:
        for ps in st.get("approval_status", []):
            for lvl in ("L1", "L2", "L3"):
                info = ps.get(lvl) or {}
                if info.get("level_name") == wanted and str(info.get("approver_code") or "").upper() == actor:
                    return True
    lists = (("Pending", "ReportingEmpCode"), ("Approved", "ReportingEmpCode"), ("Rejected", "ReportingEmpCode")) \
        if role == "manager" else \
        (("Pending", "ReportingEmpCode"), ("Partner_Approved", "PartnerEmpCode"), ("Partner_Rejected", "PartnerEmpCode"))
    for coll, key in lists:
        if await d[coll].find_one({key: actor, "EmployeesCodes": employee_id}):
            return True
    return False


async def can_view_employee(actor: str, employee_id: str) -> bool:
    """Read access to one employee's OPE records: self, HR, Admin, or an
    assigned Reporting Manager / Partner."""
    actor = actor.strip().upper()
    employee_id = employee_id.strip().upper()
    if actor == employee_id:
        return True
    roles = await get_roles(actor)
    if roles["is_hr"] or roles["is_admin"]:
        return True
    if roles["is_manager"] and await approver_in_scope(actor, "manager", employee_id):
        return True
    if roles["is_partner"] and await approver_in_scope(actor, "partner", employee_id):
        return True
    return False


# ------------------------------------------------------------- month data
def find_bucket(doc: Optional[dict], month: str) -> list:
    if not doc:
        return []
    for item in doc.get("Data", []):
        if month in item:
            return item[month]
    return []


async def month_entries(employee_id: str, month: str) -> tuple:
    """(active_entries, rejected_entries) for one employee and one month only."""
    active = find_bucket(await db()["OPE_data"].find_one({"employeeId": employee_id}), month)
    rejected = find_bucket(await db()["Reject_OPE_data"].find_one({"employeeId": employee_id}), month)
    return list(active), list(rejected)


def find_month_status(status_doc: Optional[dict], month: str) -> tuple:
    """(index, approval_status item) or (None, None)."""
    if not status_doc:
        return None, None
    for i, ps in enumerate(status_doc.get("approval_status", [])):
        if ps.get("payroll_month") == month:
            return i, ps
    return None, None


LEVEL_MARKERS = {"Reporting Manager": "L1_approved", "Partner": "L2_approved", "HR": "hr_approved"}


def _marked(e: dict, marker: str) -> bool:
    if marker == "L2_approved":
        return bool(e.get("L2_approved") or e.get("partner_approved"))
    return bool(e.get(marker))


def stage_amounts_for(ps: dict, active: list, rejected: list) -> dict:
    """Per-level amounts computed from the entries themselves.

    approved_amount is None (not 0) while a level has made no decision, so a
    not-yet-reviewed stage is never shown as an approved zero."""
    out = {}
    for lvl in ("L1", "L2", "L3"):
        info = ps.get(lvl)
        if not info:
            continue
        name = info.get("level_name") or ""
        marker = LEVEL_MARKERS.get(name)
        # An earlier stage's approval survives a later rejection: rejected entries
        # keep their marker, except at the level that rejected them.
        appr = [e for e in active + rejected
                if marker and _marked(e, marker) and e.get("rejected_level") != lvl]
        rej = [e for e in rejected if e.get("rejected_level") == lvl]
        decided = bool(appr or rej)
        out[lvl] = {
            "stage": name,
            "approver_code": info.get("approver_code"),
            "approver_name": info.get("approver_name"),
            "approved_amount": round(sum(safe_num(e.get("amount")) for e in appr), 2) if decided else None,
            "rejected_amount": round(sum(safe_num(e.get("amount")) for e in rej), 2) if rej else 0.0,
            "approved_count": len(appr),
            "rejected_count": len(rej),
        }
    return out
