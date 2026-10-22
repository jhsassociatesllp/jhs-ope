"""Append-only audit trail + decorators that wrap the existing approve/reject
endpoints without changing their bodies.

Audit rows live in `OPE_audit_log`. The package exposes no update/delete route
for them and only ever calls insert_one / insert_many on that collection."""
import functools
import logging
from typing import Optional

from fastapi import HTTPException

from .common import (
    HR_CODE, approver_in_scope, db, employee_lock, find_bucket, find_month_status,
    fmt_ist, iso_utc, normalize_month, now_utc, safe_num, stage_amounts_for,
)

log = logging.getLogger("ope.audit")
AUDIT = "OPE_audit_log"

ROLE_LABEL = {"manager": "Reporting Manager", "partner": "Partner", "hr": "HR"}
ROLE_MARKER = {"manager": "L1_approved", "partner": "L2_approved", "hr": "hr_approved"}


async def write_audit(**fields) -> None:
    """Insert one audit event. Never raises: the workflow action it describes has
    already been committed, so a logging failure must not turn it into an error."""
    try:
        doc = {k: v for k, v in fields.items() if v is not None}
        doc["at"] = now_utc()
        await db()[AUDIT].insert_one(doc)
    except Exception:  # pragma: no cover - defensive
        log.exception("failed to write audit event %s", fields.get("action"))


def event_to_api(ev: dict) -> dict:
    return {
        "id": str(ev.get("_id")),
        "action": ev.get("action"),
        "stage": ev.get("stage"),
        "level": ev.get("level"),
        "actor_id": ev.get("actor_id"),
        "actor_name": ev.get("actor_name"),
        "actor_role": ev.get("actor_role"),
        "prev_status": ev.get("prev_status"),
        "new_status": ev.get("new_status"),
        "original_amount": ev.get("original_amount"),
        "stage_amount": ev.get("stage_amount"),
        "rejected_amount": ev.get("rejected_amount"),
        "entry_count": ev.get("entry_count"),
        "remark": ev.get("remark"),
        "submission_version": ev.get("submission_version"),
        "at_utc": iso_utc(ev.get("at")),
        "at_ist": fmt_ist(ev.get("at")),
        "source": "audit_log",
    }


# ------------------------------------------------------------- snapshots
async def _snapshot_entries(employee_id: str) -> dict:
    snap = {}
    for coll, tag in (("Reject_OPE_data", "rejected"), ("OPE_data", "active")):  # active wins if an id is in both
        doc = await db()[coll].find_one({"employeeId": employee_id})
        if not doc:
            continue
        for item in doc.get("Data", []):
            for month, entries in item.items():
                for e in entries:
                    snap[(month, str(e.get("_id")))] = {
                        "where": tag,
                        "status": (e.get("status") or "").lower(),
                        "amount": safe_num(e.get("amount")),
                        "original_amount": safe_num(e.get("original_amount", e.get("amount"))),
                        "L1_approved": bool(e.get("L1_approved")),
                        "L2_approved": bool(e.get("L2_approved") or e.get("partner_approved")),
                        "hr_approved": bool(e.get("hr_approved")),
                        "rejected_level": e.get("rejected_level"),
                        "rejected_by": e.get("rejected_by"),
                        "rejected_date": e.get("rejected_date"),
                        "rejection_reason": e.get("rejection_reason"),
                        "approval_remark": e.get("approval_remark"),
                        "version": e.get("submission_version", 1),
                    }
    return snap


async def _snapshot_status(employee_id: str) -> dict:
    doc = await db()["Status"].find_one({"employeeId": employee_id})
    out = {}
    if doc:
        for ps in doc.get("approval_status", []):
            out[ps.get("payroll_month")] = {
                "overall_status": ps.get("overall_status"),
                "current_level": ps.get("current_level"),
                "version": ps.get("submission_version", 1),
                "total_amount": ps.get("total_amount"),
                "overridden": bool(ps.get("last_edited_by")),
            }
    return out


async def _actor_name(role: str, code: str) -> str:
    d = db()
    if role == "hr":
        return "HR"
    if role == "partner":
        p = await d["Partner"].find_one({"PartnerEmpCode": code})
        return (p or {}).get("Partner_Name") or code
    m = await d["Reporting_managers"].find_one({"ReportingEmpCode": code})
    return (m or {}).get("ReportingEmpName") or code


def _derive_events(role: str, before: dict, after: dict, status_before: dict, status_after: dict,
                   employee_id: str, actor: str, actor_name: str, remark: Optional[str]) -> list:
    marker = ROLE_MARKER[role]
    acted: dict = {}  # (month, action) -> list[(entry_key, after_entry, before_entry)]
    for key, a in after.items():
        b = before.get(key)
        month = key[0]
        if a["where"] == "active" and a["status"] == "approved" and a.get(marker):
            if not (b and b["where"] == "active" and b.get(marker)):
                acted.setdefault((month, "approved"), []).append((key, a, b))
        elif a["where"] == "rejected":
            newly = (b is None or b["where"] == "active"
                     or b.get("rejected_by") != a.get("rejected_by")
                     or b.get("rejected_date") != a.get("rejected_date"))
            if newly and a.get("rejected_by") and str(a["rejected_by"]).upper() == actor:
                acted.setdefault((month, "rejected"), []).append((key, a, b))
    events = []
    for (month, action), items in acted.items():
        sa = status_after.get(month, {})
        sb = status_before.get(month, {})
        total_orig = sum(a["original_amount"] for _, a, _b in items)
        total_amt = sum(a["amount"] for _, a, _b in items)
        # "Edit Total" changes the month total but not the entry amounts. When a stage
        # approves everything under such an edited total, the amount it approved is
        # that edited total, not the (unchanged) sum of the entry amounts.
        active_n = sum(1 for k, v in after.items() if k[0] == month and v["where"] == "active")
        overridden = (action == "approved" and sa.get("overridden") and len(items) == active_n
                      and sa.get("total_amount") is not None)
        if overridden:
            total_amt = safe_num(sa["total_amount"])
        reason = remark
        if not reason:
            reason = items[0][1].get("rejection_reason" if action == "rejected" else "approval_remark")
        events.append({
            "employeeId": employee_id,
            "payroll_month": month,
            "submission_version": sa.get("version", 1),
            "action": action,
            "stage": ROLE_LABEL[role],
            "actor_id": actor,
            "actor_name": actor_name,
            "actor_role": ROLE_LABEL[role],
            "prev_status": sb.get("overall_status"),
            "new_status": sa.get("overall_status"),
            "original_amount": round(total_orig, 2),
            "stage_amount": round(total_amt, 2) if action == "approved" else 0.0,
            "rejected_amount": round(total_amt, 2) if action == "rejected" else 0.0,
            "entry_count": len(items),
            "entry_ids": [k[1] for k, _a, _b in items][:500],
            "amount_from_edited_total": bool(overridden),
            "remark": reason,
        })
    return events


async def _persist_stage_amounts(employee_id: str, acted: dict) -> None:
    """acted: {month: role}. Only the acting stage is recomputed; every other stage
    keeps the amount recorded when it decided (a later edit or rejection must not
    rewrite an earlier stage's decision)."""
    for month, role in acted.items():
        st = await db()["Status"].find_one({"employeeId": employee_id})
        idx, ps = find_month_status(st, month)
        if ps is None:
            continue
        active = find_bucket(await db()["OPE_data"].find_one({"employeeId": employee_id}), month)
        rejected = find_bucket(await db()["Reject_OPE_data"].find_one({"employeeId": employee_id}), month)
        fresh = stage_amounts_for(ps, active, rejected)
        stored = ps.get("stage_amounts") or {}
        merged = {}
        for lvl, vals in fresh.items():
            keep = stored.get(lvl)
            if keep and keep.get("approved_amount") is not None and (ps.get(lvl) or {}).get("level_name") != ROLE_LABEL[role]:
                merged[lvl] = keep
            else:
                merged[lvl] = vals
        for lvl, info in ((l, ps.get(l) or {}) for l in ("L1", "L2", "L3")):
            if info.get("level_name") == ROLE_LABEL[role] and lvl in merged:
                v = merged[lvl]
                if (ps.get("last_edited_by") and v.get("approved_amount") is not None
                        and v.get("approved_count") == len(active) and ps.get("total_amount") is not None):
                    v["approved_amount"] = round(safe_num(ps["total_amount"]), 2)
                    v["from_edited_total"] = True
        await db()["Status"].update_one(
            {"employeeId": employee_id},
            {"$set": {f"approval_status.{idx}.stage_amounts": merged,
                      f"approval_status.{idx}.stage_amounts_updated_at": now_utc()}},
        )


# Routing lists the Approve / Reject tabs read to know WHICH employees to show.
_DECISION_LISTS = {
    "manager": {"approved": ("Approved", "ReportingEmpCode"), "rejected": ("Rejected", "ReportingEmpCode")},
    "partner": {"approved": ("Partner_Approved", "PartnerEmpCode"), "rejected": ("Partner_Rejected", "PartnerEmpCode")},
    "hr": {"approved": ("HR_Approved", "HR_Code"), "rejected": ("HR_Rejected", "HR_Code")},
}


async def _list_decision(role: str, actor: str, employee_id: str, action: str) -> None:
    """Make sure the employee is listed in the acting person's Approved / Rejected list.
    The original endpoints only add them when ALL of the employee's entries ended up on that side,
    so an entry approved from the Reject tab (others still rejected) never reached the Approve tab."""
    coll, key = _DECISION_LISTS[role][action]
    await db()[coll].update_one({key: actor}, {"$addToSet": {"EmployeesCodes": employee_id}}, upsert=True)


async def repair_decision_lists() -> dict:
    """Idempotent catch-up for decisions made before _list_decision existed: add every employee to the
    Approved / Rejected list of each person who actually approved / rejected one of their entries.
    Only adds (addToSet); nothing is removed or rewritten."""
    d = db()
    managers = {m["ReportingEmpCode"] async for m in d["Reporting_managers"].find({}, {"ReportingEmpCode": 1})}
    partners = {p["PartnerEmpCode"] async for p in d["Partner"].find({}, {"PartnerEmpCode": 1})}
    adds: dict = {}

    def add(coll, key, code, emp):
        if code:
            adds.setdefault((coll, key, str(code).upper()), set()).add(emp)

    async for doc in d["OPE_data"].find({}):
        emp = doc.get("employeeId")
        for item in doc.get("Data", []):
            for entries in item.values():
                for e in entries:
                    if (e.get("status") or "").lower() != "approved":
                        continue
                    if e.get("L1_approved") and str(e.get("L1_approver_code") or "").upper() != "SYSTEM":
                        add("Approved", "ReportingEmpCode", e.get("L1_approver_code"), emp)
                    if e.get("partner_approved") or e.get("L2_approved"):
                        add("Partner_Approved", "PartnerEmpCode",
                            e.get("partner_approved_by") or e.get("L2_approver_code"), emp)
                    if e.get("hr_approved"):
                        add("HR_Approved", "HR_Code", e.get("hr_approved_by"), emp)
    async for doc in d["Reject_OPE_data"].find({}):
        emp = doc.get("employeeId")
        for item in doc.get("Data", []):
            for entries in item.values():
                for e in entries:
                    who = str(e.get("rejected_by") or "").upper()
                    if who == HR_CODE:
                        add("HR_Rejected", "HR_Code", who, emp)
                    else:
                        if who in managers:
                            add("Rejected", "ReportingEmpCode", who, emp)
                        if who in partners:
                            add("Partner_Rejected", "PartnerEmpCode", who, emp)
    for (coll, key, code), emps in adds.items():
        await d[coll].update_one({key: code}, {"$addToSet": {"EmployeesCodes": {"$each": sorted(emps)}}}, upsert=True)
    return {"lists_touched": len(adds)}


async def _reconcile_completed_month(employee_id: str, month: str) -> None:
    """A month that finished ("Completed") can be changed again when a reviewer overrides a
    rejection (rejected entries come back as approved) - e.g. from the Reject tab. The existing
    endpoints move the entries but leave the month frozen on its old terminal state, so the
    employee's tracker kept showing "Rejected". Bring the Status item back in line with the entries:
      * every active entry has passed the final stage  -> Approved (Partially approved if some stay rejected)
      * some entries still need a later stage          -> reopened at that stage and routed to its approver
    """
    st = await db()["Status"].find_one({"employeeId": employee_id})
    idx, ps = find_month_status(st, month)
    if ps is None or ps.get("current_level") != "Completed":
        return
    active, rejected = (find_bucket(await db()["OPE_data"].find_one({"employeeId": employee_id}), month),
                        find_bucket(await db()["Reject_OPE_data"].find_one({"employeeId": employee_id}), month))
    active = [e for e in active if (e.get("status") or "").lower() == "approved"]
    levels = [l for l in ("L1", "L2", "L3") if ps.get(l)]
    if not active or not levels:
        return
    from .common import LEVEL_MARKERS, _marked
    import main as _m  # existing routing helpers live in main.py (loaded long before any request)

    def passed(e):
        top = -1
        for i, l in enumerate(levels):
            marker = LEVEL_MARKERS.get((ps.get(l) or {}).get("level_name"))
            if marker and _marked(e, marker):
                top = i
        return top

    reached = min(passed(e) for e in active)
    last = len(levels) - 1
    if reached >= last:
        lvl = levels[last]
        final = "partial" if rejected else "approved"
        await db()["Status"].update_one({"employeeId": employee_id}, {"$set": {
            f"approval_status.{idx}.overall_status": final,
            f"approval_status.{idx}.{lvl}.status": True,
            f"approval_status.{idx}.{lvl}.approved_count": len(active),
            f"approval_status.{idx}.{lvl}.rejected_count": sum(1 for e in rejected if e.get("rejected_level") == lvl),
            f"approval_status.{idx}.{lvl}.pending_count": 0,
        }})
    else:
        nxt = levels[reached + 1]
        upd = {
            f"approval_status.{idx}.current_level": nxt,
            f"approval_status.{idx}.overall_status": "pending",
            f"approval_status.{idx}.{nxt}.status": False,
        }
        for done in levels[:reached + 1]:  # stages the entries have already cleared
            upd[f"approval_status.{idx}.{done}.status"] = True
            upd[f"approval_status.{idx}.{done}.approved_count"] = len(active)
            upd[f"approval_status.{idx}.{done}.pending_count"] = 0
            upd[f"approval_status.{idx}.{done}.rejected_count"] = sum(
                1 for e in rejected if e.get("rejected_level") == done)
        await db()["Status"].update_one({"employeeId": employee_id}, {"$set": upd})
        await _m.recompute_month_status(employee_id, month)
        await _m.route_employee_to_next_level(employee_id, month, nxt)
    await _m.recompute_total_amount(employee_id, month)


def audited_action(role: str, action: str):
    """Decorator for the manager / partner / HR approve & reject endpoints.

    * enforces assignment scope (a manager/partner may only act on employees
      they are assigned to) before the original endpoint runs;
    * serialises concurrent calls per employee;
    * diffs the employee's entries before/after the original endpoint and
      appends one audit event per (month, action), then persists the
      per-stage approved amounts on the month's Status item.
    """
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            user = kwargs.get("current_user")
            if request is None or user is None:
                return await fn(*args, **kwargs)
            actor = str(user["employee_code"]).strip().upper()
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    body = {}
            except Exception:
                body = {}
            employee_id = kwargs.get("employee_code") or body.get("employee_id")
            employee_id = str(employee_id or "").strip().upper()
            if not employee_id:
                return await fn(*args, **kwargs)

            if role in ("manager", "partner"):
                # the original endpoint rejects non-managers/partners; scope is only
                # meaningful for those who hold the role
                holds = await db()["Reporting_managers" if role == "manager" else "Partner"].find_one(
                    {"ReportingEmpCode" if role == "manager" else "PartnerEmpCode": actor})
                if holds and not await approver_in_scope(actor, role, employee_id):
                    log.warning("scope denied: %s tried %s/%s on %s", actor, role, action, employee_id)
                    raise HTTPException(status_code=403,
                                        detail="You are not the assigned approver for this employee")
            elif actor != HR_CODE:
                return await fn(*args, **kwargs)  # endpoint itself returns 403

            async with employee_lock(employee_id):
                before = await _snapshot_entries(employee_id)
                status_before = await _snapshot_status(employee_id)
                result = await fn(*args, **kwargs)
                after = await _snapshot_entries(employee_id)
                status_after = await _snapshot_status(employee_id)
                try:
                    remark = body.get("remark") or body.get("reason")
                    actor_name = await _actor_name(role, actor)
                    events = _derive_events(role, before, after, status_before, status_after,
                                            employee_id, actor, actor_name, remark)
                    at = now_utc()
                    for ev in events:
                        ev["at"] = at
                    if events:
                        await db()[AUDIT].insert_many(events)
                        for _action in {e["action"] for e in events if e["action"] in ("approved", "rejected")}:
                            await _list_decision(role, actor, employee_id, _action)
                        for _month in {e["payroll_month"] for e in events if e["action"] == "approved"}:
                            await _reconcile_completed_month(employee_id, _month)
                        await _persist_stage_amounts(employee_id, {e["payroll_month"]: role for e in events})
                except Exception:  # pragma: no cover - action already committed
                    log.exception("audit failed for %s %s %s", role, action, employee_id)
                return result
        return wrapper
    return deco


# --------------------------------------------- employee-side entry changes
def guard_entry_change(kind: str):
    """Wrap PUT /api/ope/update and DELETE /api/ope/delete.

    Approved entries are part of the audited record and may no longer be edited
    or deleted by the employee. Edits/deletes of still-pending entries are
    allowed as before but are recorded in the audit log."""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("current_user")
            entry_id = kwargs.get("entry_id")
            payload = kwargs.get("update_data") if kind == "update" else kwargs.get("delete_data")
            if user is None or not entry_id or not isinstance(payload, dict) or not payload.get("month_range"):
                return await fn(*args, **kwargs)
            emp = str(user["employee_code"]).strip().upper()
            month = str(payload["month_range"]).strip()
            doc = await db()["OPE_data"].find_one({"employeeId": user["employee_code"]}) \
                or await db()["OPE_data"].find_one({"employeeId": emp})
            entry = next((e for e in find_bucket(doc, month) if str(e.get("_id")) == str(entry_id)), None)
            if entry is not None and (entry.get("status") or "").lower() == "approved":
                raise HTTPException(
                    status_code=409,
                    detail="This entry has already been approved and can no longer be changed. Contact HR.")
            old_amount = safe_num(entry.get("amount")) if entry else None
            result = await fn(*args, **kwargs)
            if entry is not None:  # only entries that sit in OPE_data (submitted) are audited
                st = await db()["Status"].find_one({"employeeId": emp})
                _i, ps = find_month_status(st, month)
                await write_audit(
                    employeeId=emp, payroll_month=month,
                    submission_version=(ps or {}).get("submission_version", 1),
                    action="entry_updated" if kind == "update" else "entry_deleted",
                    stage="Employee", actor_id=emp, actor_name=emp, actor_role="Employee",
                    prev_status=(entry.get("status") or None),
                    original_amount=old_amount,
                    new_status=(ps or {}).get("overall_status"),
                    remark=("Entry %s %s" % (entry_id, "edited" if kind == "update" else "deleted")),
                )
            return result
        return wrapper
    return deco
