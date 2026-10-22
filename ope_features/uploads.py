"""Admin month-wise eligibility / OPE-limit / fixed-amount uploads.

Upload columns follow the Employee_details sheet the HR team already maintains:
  EmpID (required) | Emp Name (optional) | OPE LIMIT (required) | Fixed OPE Amount (optional)

Each upload is stored as an immutable *version* (OPE_monthly_versions) with its
rows in OPE_monthly_rows. Exactly one version per month is active, tracked by a
single pointer document in OPE_monthly_active that is flipped atomically with
optimistic concurrency. Nothing is ever deleted or overwritten, so past months
keep the limits that applied to them."""
import csv
import hashlib
import io
import logging
import zipfile
from datetime import date

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from .access import month_is_submitted
from .audit import write_audit
from .common import (
    HR_CODE, MONTH_NAMES, db, employee_lock, fmt_ist, iso_utc, normalize_month, now_utc,
    parse_amount, safe_num,
)

log = logging.getLogger("ope.uploads")
VERSIONS, ROWS, ACTIVE = "OPE_monthly_versions", "OPE_monthly_rows", "OPE_monthly_active"
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000
MAX_REPORTED = 200

_HEADERS = {
    "emp_id": {"empid", "employeeid", "empcode", "employeecode"},
    "emp_name": {"empname", "employeename", "name"},
    "ope_limit": {"opelimit", "limit"},
    "fixed_amount": {"fixedopeamount", "fixedamount", "fixedope", "fixedopeamountrs"},
}


def _norm(h) -> str:
    return "".join(ch for ch in str(h or "").lower() if ch.isalnum())


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def parse_upload(filename: str, content: bytes):
    """-> (rows, header_error). rows = [(excel_row_number, {emp_id, emp_name, ope_limit, fixed_amount})]"""
    name = (filename or "").lower()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 5 MB)")
    if name.endswith((".xlsx", ".xlsm")):
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise HTTPException(status_code=400, detail="File is not a valid .xlsx workbook")
        import openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the Excel file")
        grid = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
        wb.close()
    elif name.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")
        grid = list(csv.reader(io.StringIO(text)))
    else:
        raise HTTPException(status_code=400, detail="Only .xlsx or .csv files are accepted")

    header_idx, colmap = None, {}
    for i, row in enumerate(grid[:15]):
        cand = {}
        for ci, h in enumerate(row):
            for key, names in _HEADERS.items():
                if _norm(h) in names and key not in cand:
                    cand[key] = ci
        if "emp_id" in cand and "ope_limit" in cand:
            header_idx, colmap = i, cand
            break
    if header_idx is None:
        return [], "Header row not found. The file must have the columns 'EmpID' and 'OPE LIMIT' " \
                   "(optional: 'Emp Name', 'Fixed OPE Amount')."
    rows = []
    for ri in range(header_idx + 1, len(grid)):
        raw = grid[ri]
        if not any(_cell(c) for c in raw):
            continue
        rec = {k: (_cell(raw[ci]) if ci < len(raw) else "") for k, ci in colmap.items()}
        rows.append((ri + 1, rec))
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"Too many rows (max {MAX_ROWS})")
    return rows, None


async def validate_rows(rows):
    """-> (valid_rows, errors, warnings). Any error makes the whole upload unusable."""
    valid, errors, warnings, seen = [], [], [], {}
    ids = sorted({r["emp_id"].strip().upper() for _n, r in rows if r.get("emp_id")})
    known = {}
    for i in range(0, len(ids), 500):
        async for e in db()["Employee_details"].find({"EmpID": {"$in": ids[i:i + 500]}}, {"EmpID": 1, "Emp Name": 1}):
            known[str(e["EmpID"]).upper()] = e.get("Emp Name") or ""
    for n, r in rows:
        emp_id = (r.get("emp_id") or "").strip().upper()
        problems = []
        if not emp_id:
            problems.append("EmpID is empty")
        elif emp_id in seen:
            problems.append(f"Duplicate EmpID (also on row {seen[emp_id]})")
        elif emp_id not in known:
            problems.append("EmpID not found in Employee Details")
        if emp_id:
            seen.setdefault(emp_id, n)
        limit = fixed = None
        try:
            limit = parse_amount(r.get("ope_limit"))
        except ValueError as ex:
            problems.append(f"OPE LIMIT: {ex}")
        if r.get("fixed_amount", "") != "":
            try:
                fixed = parse_amount(r["fixed_amount"], allow_zero=False)
            except ValueError as ex:
                problems.append(f"Fixed OPE Amount: {ex}")
        if problems:
            for p in problems:
                errors.append({"row": n, "emp_id": emp_id, "message": p})
            continue
        nm = (r.get("emp_name") or "").strip()
        if nm and known.get(emp_id) and nm.lower() != known[emp_id].strip().lower():
            warnings.append({"row": n, "emp_id": emp_id,
                             "message": f"Name '{nm}' differs from Employee Details '{known[emp_id]}'"})
        valid.append({"emp_id": emp_id, "emp_name": known.get(emp_id) or nm,
                      "ope_limit": limit, "fixed_amount": fixed})
    return valid, errors, warnings


def version_to_api(v: dict, active_id=None) -> dict:
    return {
        "id": str(v["_id"]), "payroll_month": v["payroll_month"], "version": v["version"],
        "filename": v.get("filename"), "uploaded_by": v.get("uploaded_by"),
        "uploaded_at_ist": fmt_ist(v.get("uploaded_at")), "uploaded_at_utc": iso_utc(v.get("uploaded_at")),
        "row_count": v.get("row_count", 0), "valid_rows": v.get("valid_rows", 0),
        "fixed_count": v.get("fixed_count", 0), "error_count": v.get("error_count", 0),
        "warning_count": v.get("warning_count", 0),
        "validation": "passed" if v.get("status") == "validated" else "failed",
        "errors": v.get("errors", []), "warnings": v.get("warnings", []),
        "header_error": v.get("header_error"),
        "is_active": active_id is not None and v["_id"] == active_id,
        "activated_at_ist": fmt_ist(v.get("activated_at")), "activated_by": v.get("activated_by"),
        "superseded_at_ist": fmt_ist(v.get("superseded_at")),
        "sha256": v.get("sha256"),
    }


async def create_version(month: str, filename: str, content: bytes, actor: str) -> dict:
    month = normalize_month(month)
    rows, header_error = parse_upload(filename, content)
    valid, errors, warnings = ([], [], []) if header_error else await validate_rows(rows)
    if not rows and not header_error:
        header_error = "The file contains no data rows"
    ok = not errors and not header_error and bool(valid)
    d = db()
    for _ in range(5):  # version number is per month; unique index arbitrates races
        last = await d[VERSIONS].find({"payroll_month": month}).sort("version", -1).limit(1).to_list(1)
        version = (last[0]["version"] + 1) if last else 1
        doc = {
            "_id": ObjectId(), "payroll_month": month, "version": version, "filename": (filename or "")[:200],
            "sha256": hashlib.sha256(content).hexdigest(), "uploaded_by": actor, "uploaded_at": now_utc(),
            "row_count": len(rows), "valid_rows": len(valid),
            "fixed_count": sum(1 for r in valid if r["fixed_amount"] is not None),
            "error_count": len(errors), "warning_count": len(warnings),
            "errors": errors[:MAX_REPORTED], "warnings": warnings[:MAX_REPORTED],
            "header_error": header_error, "status": "validated" if ok else "failed",
            "rows_complete": False,
        }
        try:
            await d[VERSIONS].insert_one(doc)
            break
        except DuplicateKeyError:
            continue
    else:
        raise HTTPException(status_code=409, detail="Could not allocate a version number, please retry")
    if ok:
        try:
            for i in range(0, len(valid), 1000):
                await d[ROWS].insert_many([{**r, "version_id": doc["_id"], "payroll_month": month}
                                           for r in valid[i:i + 1000]])
            await d[VERSIONS].update_one({"_id": doc["_id"]}, {"$set": {"rows_complete": True}})
            doc["rows_complete"] = True
        except Exception:
            log.exception("row insert failed for version %s", doc["_id"])
            await d[ROWS].delete_many({"version_id": doc["_id"]})
            await d[VERSIONS].update_one({"_id": doc["_id"]}, {"$set": {
                "status": "failed", "error_count": 1,
                "errors": [{"row": 0, "emp_id": "", "message": "Storing the rows failed; please upload again"}]}})
            raise HTTPException(status_code=500, detail="Storing the upload failed; nothing was activated")
    active = await d[ACTIVE].find_one({"payroll_month": month})
    api = version_to_api(doc, active["version_id"] if active else None)
    api["preview"] = [{"emp_id": r["emp_id"], "emp_name": r["emp_name"], "ope_limit": r["ope_limit"],
                       "fixed_amount": r["fixed_amount"]} for r in valid[:25]]
    return api


def _period_start(month: str) -> str:
    first = month.split(" - ")[0].split()
    try:
        return date(int(first[1]), MONTH_NAMES.index(first[0]) + 1, 21).isoformat()
    except Exception:
        return date.today().isoformat()


async def create_fixed_submission(emp_id: str, month: str, fixed: float, ope_limit: float, version: dict,
                                  restricted: bool = False) -> str:
    """Put a fixed-amount employee straight into the HR queue. Returns 'created' or a skip reason."""
    d = db()
    emp = await d["Employee_details"].find_one({"EmpID": emp_id})
    if not emp:
        return "employee not found"
    async with employee_lock(emp_id):
        if await month_is_submitted(emp_id, month):
            return "already has a submission for this month"
        now = now_utc()
        iso = now.replace(tzinfo=None).isoformat()  # same naive-UTC string form main.py stores
        entry = {
            "_id": ObjectId(), "date": _period_start(month), "client": "-", "project_id": "-",
            "project_name": "Fixed monthly OPE", "project_type": "Fixed", "location_from": "-",
            "location_to": "-", "travel_mode": "-", "amount": fixed, "original_amount": fixed,
            "remarks": ("Monthly OPE for restricted employee, prepared for HR approval" if restricted
                        else f"Fixed monthly OPE amount set by HR (upload v{version['version']})"),
            "ticket_pdf": None, "created_time": iso, "updated_time": iso, "submitted_time": iso,
            "status": "approved", "payroll_month": month, "is_fixed_amount": True,
            "is_restricted_employee": restricted,
            "submission_version": 1, "approved_by": "SYSTEM", "approver_name": "System (fixed amount)",
            "approved_date": iso, "approval_remark": "Fixed monthly OPE amount - no employee entry required",
            "L1_approved": True, "L1_approver_code": "SYSTEM", "L1_approver_name": "System (fixed amount)",
            "rejected_by": None, "rejected_date": None, "rejection_reason": None,
        }
        ps = {
            "payroll_month": month, "ope_label": "Fixed", "submitter_type": "Employee", "total_levels": 2,
            "limit": ope_limit, "total_amount": fixed, "original_total": fixed,
            "L1": {"status": True, "approver_name": "System (fixed amount)", "approver_code": "SYSTEM",
                   "approved_date": iso, "level_name": "Reporting Manager",
                   "approval_remark": "Fixed monthly OPE amount", "approved_count": 1,
                   "rejected_count": 0, "pending_count": 0},
            "L2": {"status": False, "approver_name": "HR", "approver_code": HR_CODE, "approved_date": None,
                   "level_name": "HR", "approved_count": 0, "rejected_count": 0, "pending_count": 1},
            "current_level": "L2", "overall_status": "pending", "submission_date": iso,
            "fixed_amount": True, "submission_version": 1, "limit_upload_version": version.get("version"),
            "restricted": restricted,
        }
        st = await d["Status"].find_one({"employeeId": emp_id})
        if st:
            await d["Status"].update_one({"employeeId": emp_id}, {"$push": {"approval_status": ps}})
            status_id = str(st["_id"])
        else:
            res = await d["Status"].insert_one({
                "employeeId": emp_id, "employeeName": emp.get("Emp Name", ""),
                "ReportingEmpCode": str(emp.get("ReportingEmpCode") or "").strip().upper(),
                "PartnerEmpCode": str(emp.get("PartnerEmpCode") or "").strip().upper(),
                "HREmpCode": HR_CODE, "approval_status": [ps]})
            status_id = str(res.inserted_id)
        entry["status_doc_id"] = status_id
        doc = await d["OPE_data"].find_one({"employeeId": emp_id})
        if not doc:
            await d["OPE_data"].insert_one({
                "employeeId": emp_id, "employeeName": emp.get("Emp Name", ""),
                "designation": emp.get("Designation Name", ""), "gender": emp.get("Gender", ""),
                "partner": emp.get("Partner", ""), "reportingManager": emp.get("ReportingEmpName", ""),
                "department": "", "Data": [{month: [entry]}]})
        else:
            for i, item in enumerate(doc.get("Data", [])):
                if month in item:
                    await d["OPE_data"].update_one({"employeeId": emp_id}, {"$push": {f"Data.{i}.{month}": entry}})
                    break
            else:
                await d["OPE_data"].update_one({"employeeId": emp_id}, {"$push": {"Data": {month: [entry]}}})
        await d["HR_Pending"].update_one(
            {"HR_Code": HR_CODE},
            {"$addToSet": {"EmployeesCodes": emp_id}, "$set": {"last_updated": now.replace(tzinfo=None)}},
            upsert=True)
    await write_audit(
        employeeId=emp_id, payroll_month=month, submission_version=1, action="fixed_amount_assigned",
        stage="System", actor_id="SYSTEM", actor_name="System", actor_role="System",
        prev_status=None, new_status="pending", original_amount=fixed, entry_count=1,
        remark=("Restricted employee: monthly OPE record created; sent to HR for approval" if restricted
                else f"Fixed monthly OPE amount from upload v{version['version']}; sent to HR for review"))
    return "created"


async def activate_version(version_id: str, actor: str, expected_active_id: str = None) -> dict:
    d = db()
    try:
        vid = ObjectId(version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid version id")
    v = await d[VERSIONS].find_one({"_id": vid})
    if not v:
        raise HTTPException(status_code=404, detail="Upload version not found")
    if v.get("status") != "validated" or not v.get("rows_complete"):
        raise HTTPException(status_code=400, detail="Only a fully validated upload can be activated")
    month = v["payroll_month"]
    ptr = await d[ACTIVE].find_one({"payroll_month": month})
    if ptr and ptr["version_id"] == vid:
        raise HTTPException(status_code=409, detail="This version is already the active one for the month")
    if expected_active_id is not None and (str(ptr["version_id"]) if ptr else "") != expected_active_id:
        raise HTTPException(status_code=409,
                            detail="The active version changed since you opened this page. Reload and try again.")
    if await d[ROWS].count_documents({"version_id": vid}) != v.get("valid_rows"):
        raise HTTPException(status_code=409, detail="Stored rows do not match the validated file; upload again")
    now = now_utc()
    new_ptr = {"version_id": vid, "version": v["version"], "activated_at": now, "activated_by": actor}
    if ptr:
        res = await d[ACTIVE].update_one({"payroll_month": month, "rev": ptr.get("rev", 1)},
                                         {"$set": new_ptr, "$inc": {"rev": 1}})
        if res.modified_count != 1:
            raise HTTPException(status_code=409, detail="Another activation happened at the same time. Reload and retry.")
        await d[VERSIONS].update_one({"_id": ptr["version_id"]}, {"$set": {"superseded_at": now}})
    else:
        try:
            await d[ACTIVE].insert_one({"payroll_month": month, "rev": 1, **new_ptr})
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="Another activation happened at the same time. Reload and retry.")
    await d[VERSIONS].update_one({"_id": vid}, {"$set": {"activated_at": now, "activated_by": actor},
                                                 "$unset": {"superseded_at": ""}})
    await write_audit(
        employeeId="*", payroll_month=month, action="upload_activated", stage="Admin", actor_id=actor,
        actor_name=actor, actor_role="Admin", remark=f"Version {v['version']} ({v.get('filename')}) activated; "
                                                    f"{v['valid_rows']} employees, {v.get('fixed_count', 0)} fixed-amount")
    created, skipped = 0, []
    async for r in d[ROWS].find({"version_id": vid, "fixed_amount": {"$ne": None}}):
        outcome = await create_fixed_submission(r["emp_id"], month, r["fixed_amount"], r["ope_limit"], v)
        if outcome == "created":
            created += 1
        else:
            skipped.append({"emp_id": r["emp_id"], "reason": outcome})
    return {"payroll_month": month, "version": v["version"], "fixed_submissions_created": created,
            "fixed_skipped": skipped[:MAX_REPORTED]}


async def list_versions(month: str = None) -> list:
    d = db()
    q = {"payroll_month": normalize_month(month)} if month else {}
    ptrs = {p["payroll_month"]: p["version_id"] async for p in d[ACTIVE].find({})}
    out = []
    async for v in d[VERSIONS].find(q).sort([("payroll_month", -1), ("version", -1)]):
        api = version_to_api(v, ptrs.get(v["payroll_month"]))
        api["errors"], api["warnings"] = [], []  # keep the list light; details load per version
        out.append(api)
    return out


async def months_summary() -> list:
    """One row per month that has uploads, with the active version info."""
    versions = await list_versions()
    months = {}
    for v in versions:
        m = months.setdefault(v["payroll_month"], {"payroll_month": v["payroll_month"], "versions": 0, "active": None})
        m["versions"] += 1
        if v["is_active"]:
            m["active"] = v
    return list(months.values())


async def version_detail(version_id: str, page: int, page_size: int, q: str = "") -> dict:
    d = db()
    try:
        vid = ObjectId(version_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid version id")
    v = await d[VERSIONS].find_one({"_id": vid})
    if not v:
        raise HTTPException(status_code=404, detail="Upload version not found")
    ptr = await d[ACTIVE].find_one({"payroll_month": v["payroll_month"]})
    page, page_size = max(1, page), min(max(1, page_size), 200)
    flt = {"version_id": vid}
    if q:
        import re
        flt["$or"] = [{"emp_id": {"$regex": re.escape(q.upper())}},
                      {"emp_name": {"$regex": re.escape(q), "$options": "i"}}]
    total = await d[ROWS].count_documents(flt)
    rows = [{"emp_id": r["emp_id"], "emp_name": r.get("emp_name"), "ope_limit": r.get("ope_limit"),
             "fixed_amount": r.get("fixed_amount")}
            async for r in d[ROWS].find(flt).sort("emp_id", 1).skip((page - 1) * page_size).limit(page_size)]
    api = version_to_api(v, ptr["version_id"] if ptr else None)
    return {**api, "rows": rows, "page": page, "page_size": page_size, "total_rows": total}
