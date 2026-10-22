"""Admin-managed payroll months shown to employees."""
from conftest import LABEL_A, LABEL_B, MONTH_A, MONTH_B, save_and_submit, save_entry, token
from ope_features import payroll_months
from ope_features.common import normalize_month


async def get_visible(client, who="EMP001"):
    r = await client.get("/api/ope/payroll-months", headers=token(who))
    assert r.status_code == 200, r.text
    return r.json()


async def test_defaults_are_seeded_once_with_the_four_existing_months(client, db):
    d = await get_visible(client)
    assert [m["key"] for m in d["months"]] == [
        "june-july-2026", "july-august-2026", "august-september-2026", "september-october-2026"]
    aug = next(m for m in d["months"] if m["key"] == "august-september-2026")
    assert aug["start"] == "2026-08-21" and aug["end"] == "2026-09-20" and aug["submit_deadline"] == "2026-09-26"
    await get_visible(client)  # second call must not duplicate
    assert await db["ope_payroll_months"].count_documents({}) == 4


async def test_only_admin_can_manage_months(client, db):
    body = {"start_month": 10, "start_year": 2026}
    for who in ("JHS729", "EMP001", "RM001", "PT001"):
        assert (await client.post("/api/admin/payroll-months", headers=token(who), json=body)).status_code == 403
        assert (await client.get("/api/admin/payroll-months", headers=token(who))).status_code == 403
        assert (await client.put("/api/admin/payroll-months/june-july-2026", headers=token(who),
                                 json={"visible": False})).status_code == 403


async def test_admin_adds_month_and_employees_see_it(client, db):
    r = await client.post("/api/admin/payroll-months", headers=token("ADM01"),
                          json={"start_month": 10, "start_year": 2026, "submit_deadline": "2026-11-27"})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["key"] == "october-november-2026" and m["display"] == "October 2026 - November 2026"
    assert m["start"] == "2026-10-21" and m["end"] == "2026-11-20" and m["visible"] is True
    keys = [x["key"] for x in (await get_visible(client))["months"]]
    assert keys[-1] == "october-november-2026"
    # duplicate refused
    r = await client.post("/api/admin/payroll-months", headers=token("ADM01"), json={"start_month": 10, "start_year": 2026})
    assert r.status_code == 409
    # the new month works end to end for an employee
    assert (await save_and_submit(client, "EMP001", "october-november-2026")).status_code == 200


async def test_year_crossing_month_key_and_label_match_what_the_form_stores(client, db):
    r = await client.post("/api/admin/payroll-months", headers=token("ADM01"),
                          json={"start_month": 12, "start_year": 2026})
    m = r.json()
    assert m["key"] == "december-january-2026-2027" and m["display"] == "December 2026 - January 2027"
    assert m["end"] == "2027-01-20"
    assert normalize_month(m["key"]) == m["display"]
    assert (await save_and_submit(client, "EMP001", m["key"])).status_code == 200
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    assert st["approval_status"][0]["payroll_month"] == "December 2026 - January 2027"


async def test_hidden_month_is_not_offered_and_cannot_be_submitted(client, db):
    await get_visible(client)
    r = await client.put("/api/admin/payroll-months/september-october-2026", headers=token("ADM01"),
                         json={"visible": False})
    assert r.status_code == 200 and r.json()["visible"] is False
    keys = [x["key"] for x in (await get_visible(client))["months"]]
    assert "september-october-2026" not in keys and "august-september-2026" in keys
    r = await save_entry(client, "EMP001", MONTH_B)
    assert r.status_code == 403 and "not open" in r.json()["detail"]
    s = await client.get("/api/ope/access/status", params={"month": MONTH_B}, headers=token("EMP001"))
    assert s.json()["locked"] and s.json()["reason"] == "month_closed"
    # an open month is unaffected; showing it again restores access
    assert (await save_entry(client, "EMP001", MONTH_A)).status_code == 200
    await client.put("/api/admin/payroll-months/september-october-2026", headers=token("ADM01"), json={"visible": True})
    assert (await save_entry(client, "EMP001", MONTH_B)).status_code == 200


async def test_hiding_a_month_keeps_existing_submission_and_reports(client, db):
    await get_visible(client)
    await save_and_submit(client, "EMP001", MONTH_A)
    await client.put("/api/admin/payroll-months/august-september-2026", headers=token("ADM01"), json={"visible": False})
    d = await client.get("/api/ope/submission/EMP001/detail", params={"month": MONTH_A}, headers=token("EMP001"))
    assert d.status_code == 200
    rep = await client.get("/api/hr/report", headers=token("JHS729"), params={"month": MONTH_A})
    assert rep.json()["summary"]["total_records"] == 1


async def test_hr_reopened_month_still_works_when_hidden(client, db):
    await get_visible(client)
    await save_and_submit(client, "EMP001", MONTH_A)
    await client.put("/api/admin/payroll-months/august-september-2026", headers=token("ADM01"), json={"visible": False})
    await client.post("/api/ope/access/reopen", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "late ticket"})
    assert (await save_entry(client, "EMP001", MONTH_A, 50, project="LATE")).status_code == 200


async def test_validation_of_dates_and_audit(client, db):
    bad = [{"start_month": 13, "start_year": 2026},
           {"start_month": 3, "start_year": 2026, "start": "2026-03-21", "end": "2026-03-01"},
           {"start_month": 3, "start_year": 2026, "start": "21/03/2026"},
           {"start_month": 3, "start_year": 2026, "submit_deadline": "2026-01-01"},
           {"start_month": 3, "start_year": 2026, "submit_deadline": "2026-04-10", "approve_deadline": "2026-04-01"}]
    for b in bad:
        assert (await client.post("/api/admin/payroll-months", headers=token("ADM01"), json=b)).status_code in (400, 422), b
    r = await client.put("/api/admin/payroll-months/june-july-2026", headers=token("ADM01"),
                         json={"submit_deadline": "2026-08-01", "approve_deadline": "2026-08-05"})
    assert r.status_code == 200 and r.json()["submit_deadline"] == "2026-08-01"
    r = await client.put("/api/admin/payroll-months/june-july-2026", headers=token("ADM01"),
                         json={"clear_submit_deadline": True, "clear_approve_deadline": True})
    assert r.json()["submit_deadline"] is None
    assert (await client.put("/api/admin/payroll-months/nope", headers=token("ADM01"), json={"visible": False})).status_code == 404
    acts = [e["action"] async for e in db["OPE_audit_log"].find({"employeeId": "*"}).sort("at", 1)]
    assert "payroll_month_changed" in acts


async def test_unconfigured_list_keeps_legacy_behaviour(client, db):
    # no call has seeded the collection yet: nothing is restricted
    assert await db["ope_payroll_months"].count_documents({}) == 0
    assert await payroll_months.month_open("Anything 2026 - Else 2026") is True
    assert (await save_entry(client, "EMP001", MONTH_A)).status_code == 200
