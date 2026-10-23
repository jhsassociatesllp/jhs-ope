"""Submission lock, reopen, audit trail, scope, amounts and month isolation."""
import pytest

from conftest import LABEL_A, LABEL_B, MONTH_A, MONTH_B, save_and_submit, save_entry, submit, token
from ope_features.common import fmt_ist


async def audit(db, emp, month=None):
    q = {"employeeId": emp}
    if month:
        q["payroll_month"] = month
    return [e async for e in db["OPE_audit_log"].find(q).sort("at", 1)]


async def test_ist_conversion_is_timezone_aware():
    assert fmt_ist("2026-10-18T10:15:00") == "18 Oct 2026, 03:45 PM IST"
    assert fmt_ist("2026-10-18T10:15:00Z") == "18 Oct 2026, 03:45 PM IST"
    assert fmt_ist(None) is None


async def test_first_submission_stamps_original_amount_and_audit(client, db):
    r = await save_and_submit(client, "EMP001")
    assert r.status_code == 200, r.text
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    ps = st["approval_status"][0]
    assert ps["payroll_month"] == LABEL_A and ps["submission_version"] == 1 and ps["limit"] == 1500
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    entries = doc["Data"][0][LABEL_A]
    assert {e["original_amount"] for e in entries} == {500.0, 400.0}
    assert all(e["submission_version"] == 1 for e in entries)
    ev = await audit(db, "EMP001")
    assert [e["action"] for e in ev] == ["submitted"]
    assert ev[0]["original_amount"] == 900.0 and ev[0]["at"] is not None


async def test_second_submission_for_same_month_is_blocked(client, db):
    assert (await save_and_submit(client, "EMP001")).status_code == 200
    r = await save_entry(client, "EMP001", amount=100, project="PX")
    assert r.status_code == 409 and "contact HR" in r.json()["detail"]
    r = await submit(client, "EMP001")
    assert r.status_code == 409 and "contact HR" in r.json()["detail"]


async def test_other_month_still_allowed(client, db):
    assert (await save_and_submit(client, "EMP001", MONTH_A)).status_code == 200
    assert (await save_and_submit(client, "EMP001", MONTH_B)).status_code == 200
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    assert {p["payroll_month"] for p in st["approval_status"]} == {LABEL_A, LABEL_B}


async def test_only_hr_or_admin_can_reopen(client, db):
    await save_and_submit(client, "EMP001")
    body = {"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "wrong project"}
    for who in ("EMP001", "RM001", "PT001"):
        r = await client.post("/api/ope/access/reopen", headers=token(who), json=body)
        assert r.status_code == 403, who
    r = await client.post("/api/ope/access/reopen", headers=token("JHS729"), json=body)
    assert r.status_code == 200 and r.json()["status"] == "active"
    r = await client.post("/api/ope/access/reopen", headers=token("ADM01"), json=body)
    assert r.status_code == 409  # already active


async def test_reopen_needs_reason_and_a_submission(client, db):
    r = await client.post("/api/ope/access/reopen", headers=token("JHS729"),
                          json={"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "x"})
    assert r.status_code == 400
    r = await client.post("/api/ope/access/reopen", headers=token("JHS729"),
                          json={"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "valid reason"})
    assert r.status_code == 400  # nothing submitted, so nothing to reopen


async def test_reopen_is_scoped_single_use_and_keeps_history(client, db):
    await save_and_submit(client, "EMP001", MONTH_A)
    await save_and_submit(client, "EMP001", MONTH_B)
    await save_and_submit(client, "EMP002", MONTH_A)
    body = {"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "add missing ticket"}
    assert (await client.post("/api/ope/access/reopen", headers=token("JHS729"), json=body)).status_code == 200

    # other month and other employee stay locked
    assert (await save_entry(client, "EMP001", MONTH_B, 50, project="Z")).status_code == 409
    assert (await save_entry(client, "EMP002", MONTH_A, 50, project="Z")).status_code == 409

    # reopened month accepts one more submission
    assert (await save_entry(client, "EMP001", MONTH_A, 200, project="NEW")).status_code == 200
    r = await submit(client, "EMP001", MONTH_A)
    assert r.status_code == 200, r.text
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    ps = next(p for p in st["approval_status"] if p["payroll_month"] == LABEL_A)
    assert ps["submission_version"] == 2
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    entries = next(i[LABEL_A] for i in doc["Data"] if LABEL_A in i)
    assert sorted(e["submission_version"] for e in entries) == [1, 1, 2]  # earlier entries preserved

    # permission is spent: locked again
    assert (await save_entry(client, "EMP001", MONTH_A, 10, project="AGAIN")).status_code == 409
    perm = await db["OPE_reopen_permissions"].find_one({"employeeId": "EMP001"})
    assert perm["status"] == "used"
    actions = [e["action"] for e in await audit(db, "EMP001", LABEL_A)]
    assert actions == ["submitted", "reopened", "resubmitted"]


async def test_revoke_permission_locks_again(client, db):
    await save_and_submit(client, "EMP001")
    body = {"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "oops"}
    await client.post("/api/ope/access/reopen", headers=token("JHS729"), json=body)
    r = await client.post("/api/ope/access/revoke", headers=token("JHS729"), json=body)
    assert r.status_code == 200 and r.json()["status"] == "revoked"
    assert (await save_entry(client, "EMP001", MONTH_A, 10, project="Q")).status_code == 409


async def test_failed_resubmission_does_not_burn_permission(client, db):
    await save_and_submit(client, "EMP001")
    body = {"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "retry please"}
    await client.post("/api/ope/access/reopen", headers=token("JHS729"), json=body)
    r = await submit(client, "EMP001")  # no temp entries saved -> original endpoint 404s
    assert r.status_code == 404
    perm = await db["OPE_reopen_permissions"].find_one({"employeeId": "EMP001"})
    assert perm["status"] == "active"


async def test_manager_scope_enforced_and_audit_written(client, db):
    await save_and_submit(client, "EMP001")
    # RM002 is a manager, but not EMP001's manager
    r = await client.post("/api/ope/manager/approve-month", headers=token("RM002"),
                          json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert r.status_code == 403
    r = await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                          json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "ok"})
    assert r.status_code == 200, r.text
    ev = await audit(db, "EMP001", LABEL_A)
    approved = [e for e in ev if e["action"] == "approved"]
    assert len(approved) == 1
    a = approved[0]
    assert a["actor_id"] == "RM001" and a["stage"] == "Reporting Manager"
    assert a["original_amount"] == 900.0 and a["stage_amount"] == 900.0 and a["remark"] == "ok"
    assert a["entry_count"] == 2
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    sa = st["approval_status"][0]["stage_amounts"]
    assert sa["L1"]["approved_amount"] == 900.0
    assert sa["L2"]["approved_amount"] is None  # HR not reviewed: None, never a fake approved 0


async def test_partner_cannot_use_manager_endpoint_and_wrong_partner_denied(client, db):
    await save_and_submit(client, "EMP001")
    r = await client.post("/api/ope/manager/approve-month", headers=token("PT001"),
                          json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert r.status_code == 403
    r = await client.post("/api/ope/partner/approve-month", headers=token("PT002"),
                          json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert r.status_code == 403


async def test_reject_after_approve_keeps_both_events(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 800))  # 1800 > 1500 -> 3 levels
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "fine"})
    r = await client.post("/api/ope/partner/reject-month", headers=token("PT001"),
                          json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "too high"})
    assert r.status_code == 200, r.text
    ev = await audit(db, "EMP001", LABEL_A)
    assert [(e["action"], e["stage"]) for e in ev] == [
        ("submitted", "Employee"), ("approved", "Reporting Manager"), ("rejected", "Partner")]
    rej = ev[-1]
    assert rej["rejected_amount"] == 1800.0 and rej["stage_amount"] == 0.0 and rej["remark"] == "too high"
    d = await client.get("/api/ope/submission/EMP001/detail", params={"month": MONTH_A}, headers=token("EMP001"))
    assert d.status_code == 200
    body = d.json()
    stages = {s["stage"]: s for s in body["amounts"]["stages"]}
    assert stages["Reporting Manager"]["approved_amount"] == 1800.0
    assert stages["Partner"]["status"] == "rejected" and stages["Partner"]["rejected_amount"] == 1800.0
    assert body["amounts"]["original_submitted"] == 1800.0
    assert [e["action"] for e in body["timeline"]] == ["submitted", "approved", "rejected"]
    assert all(e["at_ist"].endswith("IST") for e in body["timeline"])


async def test_month_isolation_for_same_employee(client, db):
    await save_and_submit(client, "EMP001", MONTH_A)
    await save_and_submit(client, "EMP001", MONTH_B, amounts=(100, 100))
    await client.post("/api/ope/manager/reject-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "no"})
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    by = {p["payroll_month"]: p for p in st["approval_status"]}
    assert by[LABEL_A]["overall_status"] == "rejected"
    assert by[LABEL_B]["overall_status"] == "pending" and by[LABEL_B]["current_level"] == "L1"
    assert [e["action"] for e in await audit(db, "EMP001", LABEL_B)] == ["submitted"]
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    assert all(e["status"] == "pending" for i in doc["Data"] for e in i.get(LABEL_B, []))
    d = await client.get("/api/ope/submission/EMP001/detail", params={"month": MONTH_B}, headers=token("EMP001"))
    assert d.json()["amounts"]["original_submitted"] == 200.0
    assert d.json()["status"]["overall_status"] == "pending"


async def test_detail_visibility(client, db):
    await save_and_submit(client, "EMP001")
    url = "/api/ope/submission/EMP001/detail"
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("EMP001"))).status_code == 200
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("RM001"))).status_code == 200
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("JHS729"))).status_code == 200
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("ADM01"))).status_code == 200
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("EMP002"))).status_code == 403  # peer
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("RM002"))).status_code == 403  # other manager
    assert (await client.get(url, params={"month": MONTH_A}, headers=token("PT002"))).status_code == 403  # other partner
    assert (await client.get(url, params={"month": "bad month"}, headers=token("EMP001"))).status_code == 400


async def test_approved_entries_cannot_be_edited_or_deleted_by_employee(client, db):
    await save_and_submit(client, "EMP001")
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(doc["Data"][0][LABEL_A][0]["_id"])
    r = await client.put(f"/api/ope/update/{eid}", headers=token("EMP001"),
                         json={"month_range": LABEL_A, "amount": 99999})
    assert r.status_code == 409
    r = await client.request("DELETE", f"/api/ope/delete/{eid}", headers=token("EMP001"),
                             json={"month_range": LABEL_A})
    assert r.status_code == 409


async def test_edit_amount_preserves_original_and_is_audited(client, db):
    await save_and_submit(client, "EMP001")
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(doc["Data"][0][LABEL_A][0]["_id"])
    r = await client.put("/api/ope/manager/edit-amount", headers=token("RM001"),
                         json={"employee_id": "EMP001", "entry_id": eid, "new_amount": 300})
    assert r.status_code == 200, r.text
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    e = next(x for x in doc["Data"][0][LABEL_A] if str(x["_id"]) == eid)
    assert e["amount"] == 300 and e["original_amount"] == 500.0
    assert "amount_edited" in [x["action"] for x in await audit(db, "EMP001", LABEL_A)]
    # non-finite / non-numeric amounts are rejected
    for bad in ("12", None, True):
        r = await client.put("/api/ope/manager/edit-amount", headers=token("RM001"),
                             json={"employee_id": "EMP001", "entry_id": eid, "new_amount": bad})
        assert r.status_code in (400,), (bad, r.text)
    # a manager who is not assigned cannot edit
    r = await client.put("/api/ope/manager/edit-amount", headers=token("RM002"),
                         json={"employee_id": "EMP001", "entry_id": eid, "new_amount": 1})
    assert r.status_code == 403


async def test_status_and_history_endpoints_enforce_ownership(client, db):
    await save_and_submit(client, "EMP001")
    r = await client.get("/api/ope/status/EMP001", headers=token("EMP002"))
    assert r.status_code == 403
    assert (await client.get("/api/ope/status/EMP001", headers=token("RM002"))).status_code == 403
    assert (await client.get("/api/ope/status/EMP001", headers=token("RM001"))).status_code == 200
    assert (await client.get("/api/employee/EMP001", headers=token("EMP002"))).status_code == 403
    assert (await client.get("/api/employee/EMP001", headers=token("EMP001"))).status_code == 200
    assert (await client.get("/api/ope/approved/EMP001", headers=token("RM002"))).status_code == 403


async def test_debug_endpoints_require_admin(client, db):
    assert (await client.get("/api/debug/partner-pending/PT001")).status_code == 401
    assert (await client.get("/api/debug/partner-pending/PT001", headers=token("EMP001"))).status_code == 403
    assert (await client.get("/api/debug/check-partner-data/PT001", headers=token("ADM01"))).status_code == 200


async def test_audit_log_has_no_mutation_routes():
    import main
    for route in main.app.routes:
        path = getattr(route, "path", "")
        if "audit" in path:
            assert getattr(route, "methods", {"GET"}) <= {"GET", "HEAD"}, path


async def test_concurrent_double_submit_creates_one_submission(client, db):
    import asyncio
    for n, a in enumerate((500, 400)):
        await save_entry(client, "EMP001", MONTH_A, a, project=f"P{n}")
    r1, r2 = await asyncio.gather(submit(client, "EMP001"), submit(client, "EMP001"))
    assert sorted([r1.status_code, r2.status_code])[0] == 200
    assert sorted([r1.status_code, r2.status_code])[1] in (404, 409)
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    assert len(doc["Data"][0][LABEL_A]) == 2
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    assert len(st["approval_status"]) == 1


async def test_identical_entries_are_refused_on_save_and_submit(client, db):
    from conftest import save_entry
    # identical to one already waiting in the draft -> existing save check
    assert (await save_entry(client, "EMP001", MONTH_A, 100, project="P1")).status_code == 200
    assert (await save_entry(client, "EMP001", MONTH_A, 100, project="P1")).status_code == 400
    # two identical drafts that bypassed the save check are still refused at submit
    doc = await db["Temp_OPE_data"].find_one({"employeeId": "EMP001"})
    bucket = doc["Data"][0][LABEL_A]
    from bson import ObjectId
    twin = dict(bucket[0], _id=ObjectId())
    await db["Temp_OPE_data"].update_one({"employeeId": "EMP001"}, {"$push": {f"Data.0.{LABEL_A}": twin}})
    r = await submit(client, "EMP001", MONTH_A)
    assert r.status_code == 409 and "Duplicate" in r.json()["detail"]
    assert await db["Status"].find_one({"employeeId": "EMP001"}) is None  # nothing was submitted


async def test_entry_identical_to_a_submitted_one_is_refused(client, db):
    await save_and_submit(client, "EMP001", amounts=(500,))
    await db["OPE_reopen_permissions"].insert_one({"employeeId": "EMP001", "payroll_month": LABEL_A,
                                                   "status": "active", "granted_by": "JHS729"})
    r = await save_entry(client, "EMP001", MONTH_A, 500, project="P0")   # same as the submitted P0 / 500
    assert r.status_code == 409 and "Duplicate" in r.json()["detail"]
    assert (await save_entry(client, "EMP001", MONTH_A, 501, project="P0")).status_code == 200  # different amount


async def test_limit_is_read_from_employee_details_whatever_the_column_spelling(client, db):
    """Employee_details in production stores the limit as 'OPE Limit' (not 'OPE LIMIT')."""
    await db["Employee_details"].update_one({"EmpID": "EMP001"}, {"$rename": {"OPE LIMIT": "OPE Limit"}})
    await db["Employee_details"].update_one({"EmpID": "EMP001"}, {"$set": {"OPE Limit": 2000}})
    assert (await save_and_submit(client, "EMP001", amounts=(1000, 774))).status_code == 200   # 1774 <= 2000
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    ps = st["approval_status"][0]
    assert ps["limit"] == 2000 and ps["total_levels"] == 2 and ps["ope_label"] == "Less"
    row = (await client.get("/api/ope/status/EMP001", headers=token("EMP001"))).json()
    assert row["ope_limit"] == 2000 and row["status_entries"][0]["limit"] == 2000


async def test_employee_ope_limit_helper_variants():
    from ope_features.common import employee_ope_limit
    assert employee_ope_limit({"OPE Limit": 2000}) == 2000.0
    assert employee_ope_limit({"OPE LIMIT": "2,500"}) == 2500.0
    assert employee_ope_limit({"ope_limit": 1800}) == 1800.0
    assert employee_ope_limit({"OPE LIMIT": "", "OPE Limit": 900}) == 900.0
    assert employee_ope_limit({"Name": "x"}) is None and employee_ope_limit(None) is None
