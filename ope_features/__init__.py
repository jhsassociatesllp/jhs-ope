"""OPE feature package: audit trail, one-submission-per-month locking with
HR/Admin reopen, monthly eligibility/limit uploads, submission detail view and
the HR monthly report. main.py wires it in with `ope_features.install(...)`."""
import io
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure

import asyncio

from . import access, partial_pending, payroll_months, restricted, stage_lists, team_reports, uploads
from .access import apply_month_policy_limit, guarded_save, guarded_submit  # noqa: F401  (used by main.py)
from .audit import AUDIT, audited_action, repair_decision_lists, event_to_api, guard_entry_change, write_audit  # noqa: F401
from .common import (
    HR_CODE, RESTRICTED, build_month_label, ctx, db, fmt_ist, get_roles, normalize_month, now_utc,
    require_admin, require_hr_or_admin,
)
from .detail import build_detail
from .partial_pending import ensure_hr_stage, months_not_at_hr  # noqa: F401  (used by main.py)
from .reports import BUCKETS, build_report, export_xlsx
from .restricted import ensure_month_record as ensure_restricted_month  # noqa: F401

log = logging.getLogger("ope")


async def ensure_indexes() -> None:
    """Create the indexes the new queries need. Safe to run on every start."""
    d = db()
    specs = [
        (AUDIT, [("employeeId", ASCENDING), ("payroll_month", ASCENDING), ("at", ASCENDING)], {}),
        (AUDIT, [("payroll_month", ASCENDING), ("action", ASCENDING), ("at", DESCENDING)], {}),
        (access.PERMS, [("employeeId", ASCENDING), ("payroll_month", ASCENDING)],
         {"unique": True, "partialFilterExpression": {"status": "active"}, "name": "one_active_reopen"}),
        (access.PERMS, [("payroll_month", ASCENDING), ("status", ASCENDING)], {}),
        (access.INFLIGHT, [("employeeId", ASCENDING), ("payroll_month", ASCENDING)], {"unique": True}),
        (uploads.VERSIONS, [("payroll_month", ASCENDING), ("version", ASCENDING)], {"unique": True}),
        (uploads.ROWS, [("version_id", ASCENDING), ("emp_id", ASCENDING)], {"unique": True}),
        (uploads.ACTIVE, [("payroll_month", ASCENDING)], {"unique": True}),
        (RESTRICTED, [("employee_id", ASCENDING)], {"unique": True}),
        (payroll_months.COLL, [("key", ASCENDING)], {"unique": True}),
        (payroll_months.COLL, [("display", ASCENDING)], {}),
        (restricted.MONTHS_GUARD, [("employee_id", ASCENDING), ("payroll_month", ASCENDING)], {"unique": True}),
        ("Status", [("employeeId", ASCENDING)], {}),
        ("Status", [("approval_status.payroll_month", ASCENDING)], {}),
        ("OPE_data", [("employeeId", ASCENDING)], {}),
        ("Reject_OPE_data", [("employeeId", ASCENDING)], {}),
        ("Temp_OPE_data", [("employeeId", ASCENDING)], {}),
    ]
    for coll, keys, opts in specs:
        try:
            await d[coll].create_index(keys, **opts)
        except ConnectionFailure as ex:  # database unreachable: do not wait once per index
            log.warning("indexes skipped, database unreachable: %s", ex)
            return
        except Exception as ex:  # e.g. pre-existing duplicate data blocks a unique index
            log.warning("index on %s %s not created: %s", coll, keys, ex)


def install(app, database, get_current_user) -> None:
    ctx.db = database
    app.include_router(build_router(get_current_user))
    app.include_router(restricted.build_router(get_current_user))
    app.include_router(stage_lists.build_router(get_current_user))
    app.include_router(partial_pending.build_router(get_current_user))
    app.include_router(team_reports.build_router(get_current_user))
    app.include_router(payroll_months.build_router(get_current_user))

    @app.on_event("startup")
    async def _ope_indexes():  # noqa: D401
        await ensure_indexes()
        try:
            await payroll_months.ensure_defaults()
        except Exception as ex:  # database unreachable at start-up
            log.warning("payroll month defaults not created: %s", ex)
        try:
            await repair_decision_lists()
        except Exception as ex:
            log.warning("decision list catch-up skipped: %s", ex)
        app.state.restricted_watcher = asyncio.create_task(restricted.month_watcher())


class ReopenBody(BaseModel):
    employee_id: str = Field(min_length=1, max_length=40)
    payroll_month: str = Field(min_length=3, max_length=60)
    reason: str = Field(default="", max_length=500)


class ActivateBody(BaseModel):
    expected_active_id: Optional[str] = Field(default=None, max_length=40)
    confirm: bool = False


def build_router(get_current_user) -> APIRouter:
    r = APIRouter()

    def code(u) -> str:
        return str(u["employee_code"]).strip().upper()

    # ------------------------------------------------------------ roles
    @r.get("/api/ope/my-roles")
    async def my_roles(u=Depends(get_current_user)):
        roles = await get_roles(code(u))
        return {"employee_code": code(u), **roles}

    @r.get("/api/ope/months")
    async def known_months(u=Depends(get_current_user)):
        """Payroll months that exist in the data (for selectors)."""
        roles = await get_roles(code(u))
        if not (roles["is_hr"] or roles["is_admin"]):
            raise HTTPException(status_code=403, detail="Only HR or Admin can list months")
        months = set(await db()["Status"].distinct("approval_status.payroll_month"))
        months |= set(await db()[uploads.VERSIONS].distinct("payroll_month"))
        return {"months": sorted(m for m in months if isinstance(m, str))}

    # ----------------------------------------------------------- detail
    @r.get("/api/ope/submission/{employee_id}/detail")
    async def submission_detail(employee_id: str, month: str = Query(...), u=Depends(get_current_user)):
        return await build_detail(code(u), employee_id, month)

    # ------------------------------------------------------ lock / access
    @r.get("/api/ope/access/status")
    async def access_status(month: str = Query(...), employee_id: Optional[str] = None,
                            u=Depends(get_current_user)):
        target = (employee_id or code(u)).strip().upper()
        if target != code(u):
            await require_hr_or_admin(code(u))
        return await access.lock_state(target, month)

    @r.get("/api/ope/access/employee/{employee_id}")
    async def access_employee(employee_id: str, u=Depends(get_current_user)):
        await require_hr_or_admin(code(u))
        eid = employee_id.strip().upper()
        emp = await db()["Employee_details"].find_one({"EmpID": eid})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        st = await db()["Status"].find_one({"employeeId": eid}) or {}
        months = []
        for ps in st.get("approval_status", []):
            m = ps.get("payroll_month")
            perm = await access.active_permission(eid, m)
            months.append({"payroll_month": m, "overall_status": ps.get("overall_status"),
                           "submission_version": ps.get("submission_version", 1),
                           "total_amount": ps.get("total_amount"),
                           "reopen_permitted": perm is not None})
        return {"employee_id": eid, "employee_name": emp.get("Emp Name"), "months": months}

    @r.post("/api/ope/access/reopen")
    async def reopen(body: ReopenBody, u=Depends(get_current_user)):
        roles = await require_hr_or_admin(code(u))
        role = "HR" if roles["is_hr"] else "Admin"
        return await access.grant_reopen(code(u), role, body.employee_id, body.payroll_month, body.reason)

    @r.post("/api/ope/access/revoke")
    async def revoke(body: ReopenBody, u=Depends(get_current_user)):
        roles = await require_hr_or_admin(code(u))
        role = "HR" if roles["is_hr"] else "Admin"
        return await access.revoke_reopen(code(u), role, body.employee_id, body.payroll_month, body.reason)

    @r.get("/api/ope/access/permissions")
    async def permissions(month: Optional[str] = None, status: Optional[str] = None, q: str = "",
                          page: int = 1, page_size: int = 25, u=Depends(get_current_user)):
        await require_hr_or_admin(code(u))
        flt = {}
        if month:
            flt["payroll_month"] = normalize_month(month)
        if status in ("active", "used", "revoked"):
            flt["status"] = status
        if q:
            flt["$or"] = [{"employeeId": {"$regex": re.escape(q.upper())}},
                          {"employee_name": {"$regex": re.escape(q), "$options": "i"}}]
        page, page_size = max(1, page), min(max(1, page_size), 100)
        coll = db()[access.PERMS]
        total = await coll.count_documents(flt)
        items = [access.perm_to_api(p) async for p in coll.find(flt).sort("granted_at", -1)
                 .skip((page - 1) * page_size).limit(page_size)]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ------------------------------------------------------------ report
    async def _report(month: str, u) -> dict:
        await require_hr_or_admin(code(u))
        return await build_report(normalize_month(month))

    @r.get("/api/hr/report")
    async def hr_report(month: str = Query(...), status: Optional[str] = None, q: str = "",
                        page: int = 1, page_size: int = 25, u=Depends(get_current_user)):
        rep = await _report(month, u)
        rows = rep["rows"]
        if status in BUCKETS:
            rows = [x for x in rows if x["status"] == status]
        if q:
            ql = q.lower()
            rows = [x for x in rows if ql in x["employee_id"].lower() or ql in (x["employee_name"] or "").lower()]
        page, page_size = max(1, page), min(max(1, page_size), 200)
        return {"summary": rep["summary"], "rows": rows[(page - 1) * page_size: page * page_size],
                "total_rows": len(rows), "page": page, "page_size": page_size,
                "generated_at_ist": fmt_ist(now_utc())}

    @r.get("/api/hr/report/export")
    async def hr_report_export(month: str = Query(...), u=Depends(get_current_user)):
        rep = await _report(month, u)
        data = export_xlsx(rep, code(u))
        slug = re.sub(r"[^A-Za-z0-9]+", "_", rep["summary"]["payroll_month"]).strip("_")
        await write_audit(employeeId="*", payroll_month=rep["summary"]["payroll_month"], action="report_exported",
                          stage="Report", actor_id=code(u), actor_name=code(u), actor_role="HR/Admin",
                          remark=f"{rep['summary']['total_records']} records")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="OPE_HR_Report_{slug}.xlsx"'})

    # ----------------------------------------------------- monthly uploads
    @r.get("/api/admin/monthly-upload/months")
    async def upload_months(u=Depends(get_current_user)):
        await require_admin(code(u))
        return {"months": await uploads.months_summary()}

    @r.get("/api/admin/monthly-upload/versions")
    async def upload_versions(month: Optional[str] = None, u=Depends(get_current_user)):
        await require_admin(code(u))
        return {"versions": await uploads.list_versions(month)}

    @r.post("/api/admin/monthly-upload")
    async def upload_create(file: UploadFile = File(...), payroll_month: Optional[str] = Form(None),
                            start_month: Optional[int] = Form(None), start_year: Optional[int] = Form(None),
                            u=Depends(get_current_user)):
        await require_admin(code(u))
        if payroll_month:
            month = normalize_month(payroll_month)
        elif start_month and start_year:
            month = build_month_label(start_month, start_year)
        else:
            raise HTTPException(status_code=400, detail="Select the payroll month for this upload")
        content = await file.read(uploads.MAX_BYTES + 1)
        return await uploads.create_version(month, file.filename or "", content, code(u))

    @r.get("/api/admin/monthly-upload/{version_id}")
    async def upload_detail(version_id: str, page: int = 1, page_size: int = 50, q: str = "",
                            u=Depends(get_current_user)):
        await require_admin(code(u))
        return await uploads.version_detail(version_id, page, page_size, q)

    @r.post("/api/admin/monthly-upload/{version_id}/activate")
    async def upload_activate(version_id: str, body: ActivateBody, u=Depends(get_current_user)):
        await require_admin(code(u))
        if not body.confirm:
            raise HTTPException(status_code=400, detail="Activation must be confirmed")
        return await uploads.activate_version(version_id, code(u), body.expected_active_id)

    return r
