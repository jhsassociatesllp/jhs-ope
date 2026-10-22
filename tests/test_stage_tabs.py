"""Approve / Reject tabs show an entry only after THAT stage decided it."""
from conftest import LABEL_A, MONTH_A, save_and_submit, token


async def approved_ids(client, who, stage, emp="EMP001"):
    r = await client.get(f"/api/ope/approved/{emp}", params={"stage": stage}, headers=token(who))
    assert r.status_code == 200, r.text
    return r.json()["approved"]


async def rejected_ids(client, who, stage, emp="EMP001"):
    r = await client.get(f"/api/ope/rejected/{emp}", params={"stage": stage}, headers=token(who))
    assert r.status_code == 200, r.text
    return r.json()["rejected"]


async def test_three_level_entry_appears_in_approve_tab_only_after_own_stage(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))  # 1600 > 1500 -> RM, Partner, HR
    assert await approved_ids(client, "RM001", "manager") == []
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "okay"})
    assert len(await approved_ids(client, "RM001", "manager")) == 2
    # forwarded to the partner but not decided yet: NOT in the partner's or HR's Approve tab
    assert await approved_ids(client, "PT001", "partner") == []
    assert await approved_ids(client, "JHS729", "hr") == []
    await client.post("/api/ope/partner/approve-month", headers=token("PT001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "fine"})
    assert len(await approved_ids(client, "PT001", "partner")) == 2
    assert await approved_ids(client, "JHS729", "hr") == []
    assert len(await approved_ids(client, "RM001", "manager")) == 2  # manager keeps its own approvals
    await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert len(await approved_ids(client, "JHS729", "hr")) == 2


async def test_reject_tab_shows_only_own_rejections(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/partner/reject-month", headers=token("PT001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "no"})
    assert len(await rejected_ids(client, "PT001", "partner")) == 2
    assert await rejected_ids(client, "RM001", "manager") == []      # manager did not reject it
    assert await rejected_ids(client, "JHS729", "hr") == []
    assert len(await approved_ids(client, "RM001", "manager")) == 0   # entries left the active set


async def test_without_stage_behaviour_is_unchanged_and_bad_stage_rejected(client, db):
    await save_and_submit(client, "EMP001")
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    r = await client.get("/api/ope/approved/EMP001", headers=token("EMP001"))
    assert len(r.json()["approved"]) == 2
    r = await client.get("/api/ope/approved/EMP001", params={"stage": "bogus"}, headers=token("RM001"))
    assert r.status_code == 400


async def test_stage_amount_uses_edited_total_and_keeps_earlier_stage(client, db):
    await save_and_submit(client, "EMP001", amounts=(1600,))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    r = await client.put("/api/ope/manager/edit-total-amount", headers=token("PT001"),
                         json={"employee_id": "EMP001", "month_range": LABEL_A, "new_total": 1400})
    assert r.status_code == 200, r.text
    await client.post("/api/ope/partner/approve-month", headers=token("PT001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "only 1400"})
    d = (await client.get("/api/ope/submission/EMP001/detail", params={"month": MONTH_A},
                          headers=token("EMP001"))).json()
    stages = {s["stage"]: s for s in d["amounts"]["stages"]}
    assert stages["Reporting Manager"]["approved_amount"] == 1600.0   # decided before the edit
    assert stages["Partner"]["approved_amount"] == 1400.0              # decided on the edited total
    assert d["amounts"]["original_submitted"] == 1600.0 and d["amounts"]["current_total"] == 1400
    ev = [e for e in d["timeline"] if e["action"] == "approved" and e["stage"] == "Partner"][0]
    assert ev["stage_amount"] == 1400.0


async def test_status_page_total_is_the_original_submitted_amount(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))
    await client.put("/api/ope/manager/edit-total-amount", headers=token("RM001"),
                     json={"employee_id": "EMP001", "month_range": LABEL_A, "new_total": 1200})
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(doc["Data"][0][LABEL_A][0]["_id"])
    await client.put("/api/ope/manager/edit-amount", headers=token("RM001"),
                     json={"employee_id": "EMP001", "entry_id": eid, "new_amount": 700})
    row = (await client.get("/api/ope/status/EMP001", headers=token("EMP001"))).json()["status_entries"][0]
    assert row["submitted_amount"] == 1600.0          # what the employee filled, not 1200 / edited values


async def test_hr_rejection_remark_is_shown_on_the_stage_card(client, db):
    await save_and_submit(client, "EMP001", amounts=(100,))   # single entry: the in-memory test DB cannot
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),   # do partial array pulls
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "okay"})
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    first = str(doc["Data"][0][LABEL_A][0]["_id"])
    r = await client.post("/api/ope/hr/reject-single", headers=token("JHS729"),
                          json={"employee_id": "EMP001", "entry_id": first, "reason": "Duplicate claim"})
    assert r.status_code == 200, r.text
    d = (await client.get("/api/ope/submission/EMP001/detail", params={"month": MONTH_A},
                          headers=token("EMP001"))).json()
    hr = next(s for s in d["amounts"]["stages"] if s["stage"] == "HR")
    assert hr["rejection_reason"] == "Duplicate claim"
    assert hr["rejected_count"] == 1


async def _status(client, who="EMP001"):
    return (await client.get(f"/api/ope/status/{who}", headers=token(who))).json()["status_entries"][0]


async def test_hr_overriding_a_rejected_month_updates_the_employee_tracker(client, db):
    await save_and_submit(client, "EMP001", amounts=(100,))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/hr/reject-month", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "no"})
    s = await _status(client)
    assert s["overall_status"] == "rejected" and s["total_amount"] == 0
    rej = await db["Reject_OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(rej["Data"][0][LABEL_A][0]["_id"])
    r = await client.post("/api/ope/hr/approve-single", headers=token("JHS729"),
                          json={"employee_id": "EMP001", "entry_id": eid, "remark": "ok"})
    assert r.status_code == 200, r.text
    s = await _status(client)
    assert s["overall_status"] == "approved" and s["total_amount"] == 100
    assert s["L2"]["status"] is True and s["L2"]["approved_count"] == 1 and s["L2"]["rejected_count"] == 0


async def test_manager_overriding_own_rejection_sends_entry_on_and_tracker_shows_it(client, db):
    await save_and_submit(client, "EMP001", amounts=(100,))
    await client.post("/api/ope/manager/reject-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "no"})
    assert (await _status(client))["overall_status"] == "rejected"
    rej = await db["Reject_OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(rej["Data"][0][LABEL_A][0]["_id"])
    r = await client.post("/api/ope/manager/approve-single", headers=token("RM001"),
                          json={"employee_id": "EMP001", "entry_id": eid, "remark": "ok"})
    assert r.status_code == 200, r.text
    s = await _status(client)
    assert s["overall_status"] == "pending" and s["current_level"] == "L2" and s["L1"]["status"] is True
    hr = (await client.get("/api/ope/hr/pending-employees", headers=token("JHS729"))).json()["pending_employees"]
    assert [x["employeeId"] for x in hr] == ["EMP001"]
    # and HR can then approve it normally
    await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert (await _status(client))["overall_status"] == "approved"


async def test_entry_approved_from_reject_tab_shows_in_approve_tab(client, db):
    await save_and_submit(client, "EMP001", amounts=(100, 50))
    await client.post("/api/ope/manager/reject-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "no"})
    rej = await db["Reject_OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(rej["Data"][0][LABEL_A][0]["_id"])
    r = await client.post("/api/ope/manager/approve-single", headers=token("RM001"),
                          json={"employee_id": "EMP001", "entry_id": eid, "remark": "ok"})
    assert r.status_code == 200, r.text
    # the employee list the Approve tab starts from now includes them ...
    lst = (await client.get("/api/ope/manager/approved-list", headers=token("RM001"))).json()
    assert "EMP001" in lst["employee_codes"]
    # ... and the entry is returned for that stage
    got = await approved_ids(client, "RM001", "manager")
    assert len(got) == 1 and got[0]["_id"] == eid


async def test_hr_and_partner_approvals_from_reject_tab_are_listed_too(client, db):
    await save_and_submit(client, "EMP001", amounts=(100,))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/hr/reject-month", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A, "reason": "no"})
    assert "EMP001" in (await client.get("/api/ope/hr/rejected-employees", headers=token("JHS729"))).json()["employee_codes"]
    rej = await db["Reject_OPE_data"].find_one({"employeeId": "EMP001"})
    eid = str(rej["Data"][0][LABEL_A][0]["_id"])
    await client.post("/api/ope/hr/approve-single", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "entry_id": eid, "remark": "ok"})
    assert "EMP001" in (await client.get("/api/ope/hr/approved-employees", headers=token("JHS729"))).json()["employee_codes"]
    assert len(await approved_ids(client, "JHS729", "hr")) == 1


async def test_catch_up_adds_earlier_decisions_to_the_lists(client, db):
    from ope_features import repair_decision_lists
    await save_and_submit(client, "EMP001", amounts=(100,))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    await db["Approved"].delete_many({})                     # simulate a decision made before the fix
    assert (await client.get("/api/ope/manager/approved-list", headers=token("RM001"))).json()["employee_codes"] == []
    await repair_decision_lists()
    await repair_decision_lists()                             # idempotent
    assert (await client.get("/api/ope/manager/approved-list", headers=token("RM001"))).json()["employee_codes"] == ["EMP001"]


async def _batch(client, who, kind, stage):
    r = await client.get("/api/ope/stage-entries", params={"kind": kind, "stage": stage}, headers=token(who))
    assert r.status_code == 200, r.text
    return r.json()["entries"]


async def test_batch_endpoint_matches_per_employee_endpoints(client, db):
    for emp, amts in (("EMP001", (100, 50)), ("EMP002", (70,)), ("EMP003", (200,))):
        await save_and_submit(client, emp, amounts=amts)
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP002", "month_range": LABEL_A})
    await client.post("/api/ope/manager/reject-month", headers=token("RM002"),
                      json={"employee_id": "EMP003", "month_range": LABEL_A, "reason": "no"})
    # approved tab (manager RM001)
    fast = await _batch(client, "RM001", "approved", "manager")
    slow = []
    for emp in (await client.get("/api/ope/manager/approved-list", headers=token("RM001"))).json()["employee_codes"]:
        slow += await approved_ids(client, "RM001", "manager", emp)
    assert sorted(e["_id"] for e in fast) == sorted(e["_id"] for e in slow) and len(fast) == 3
    assert set(fast[0]) == set(slow[0])                       # identical fields, so the UI needs no change
    # reject tab (manager RM002)
    fast = await _batch(client, "RM002", "rejected", "manager")
    slow = await rejected_ids(client, "RM002", "manager", "EMP003")
    assert sorted(e["_id"] for e in fast) == sorted(e["_id"] for e in slow) and len(fast) == 1
    assert set(fast[0]) == set(slow[0])


async def test_batch_endpoint_respects_role_and_stage(client, db):
    await save_and_submit(client, "EMP001", amounts=(100,))
    assert (await client.get("/api/ope/stage-entries", params={"kind": "approved", "stage": "hr"},
                             headers=token("RM001"))).status_code == 403
    assert (await client.get("/api/ope/stage-entries", params={"kind": "approved", "stage": "partner"},
                             headers=token("EMP001"))).status_code == 403
    assert (await client.get("/api/ope/stage-entries", params={"kind": "x", "stage": "hr"},
                             headers=token("JHS729"))).status_code == 400
    # forwarded-but-undecided entries are not listed for HR
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert await _batch(client, "JHS729", "approved", "hr") == []
