from conftest import LABEL_A, save_and_submit, token


async def rows(client, who="JHS729"):
    r = await client.get("/api/ope/hr/partial-pending", headers=token(who))
    return r


async def test_access_and_direct_approval_flow(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))  # 3-level
    assert (await rows(client, "EMP001")).status_code == 403
    assert (await rows(client, "RM001")).status_code == 403
    assert len((await rows(client)).json()["rows"]) == 1
    body = {"employee_id": "EMP001", "payroll_month": LABEL_A, "remark": "ok"}
    assert (await client.post("/api/ope/hr/partial-pending/approve", headers=token("RM001"), json=body)).status_code == 403
    assert (await client.post("/api/ope/hr/partial-pending/approve", headers=token("JHS729"), json=body)).status_code == 200
    assert (await client.post("/api/ope/hr/partial-pending/approve", headers=token("JHS729"), json=body)).status_code == 409
    assert (await rows(client)).json()["rows"] == []
    # HR Approved tab shows it; HR Pending does not
    r = await client.get("/api/ope/stage-entries", params={"kind": "approved", "stage": "hr"}, headers=token("JHS729"))
    assert len(r.json()["entries"]) == 2
    # RM then Partner approve: status completes, never lands in HR pending
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"), json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/partner/approve-month", headers=token("PT001"), json={"employee_id": "EMP001", "month_range": LABEL_A})
    ps = (await db["Status"].find_one({"employeeId": "EMP001"}))["approval_status"][0]
    assert ps["current_level"] == "Completed" and ps["overall_status"] == "approved"
    assert ps["L1"]["status"] and ps["L2"]["status"] and ps["L3"]["status"]
    pend = await client.get("/api/ope/hr/pending-employees", headers=token("JHS729"))
    assert pend.json()["pending_employees"] == []
    assert (await rows(client)).json()["rows"] == []


async def test_hr_reject_from_partial_pending(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))
    url = "/api/ope/hr/partial-pending/reject"
    body = {"employee_id": "EMP001", "month_range": LABEL_A, "reason": "Not valid"}
    assert (await client.post(url, headers=token("RM001"), json=body)).status_code == 403
    assert (await client.post(url, headers=token("JHS729"), json={**body, "reason": ""})).status_code == 400
    assert (await client.post(url, headers=token("JHS729"), json=body)).status_code == 200
    assert (await client.post(url, headers=token("JHS729"), json=body)).status_code == 409
    assert (await rows(client)).json()["rows"] == []
    r = await client.get("/api/ope/stage-entries", params={"kind": "rejected", "stage": "hr"}, headers=token("JHS729"))
    assert len(r.json()["entries"]) == 2
    ps = (await db["Status"].find_one({"employeeId": "EMP001"}))["approval_status"][0]
    assert ps["overall_status"] == "rejected" and ps["current_level"] == "Completed"
    r = await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                          json={"employee_id": "EMP001", "month_range": LABEL_A})
    assert r.status_code >= 400
    assert (await client.get("/api/ope/hr/pending-employees", headers=token("JHS729"))).json()["pending_employees"] == []
