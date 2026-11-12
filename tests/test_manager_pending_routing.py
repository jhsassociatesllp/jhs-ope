"""Manager Pending screen vs the Pending collection."""
from conftest import LABEL_A, MONTH_A, save_and_submit, token


async def pending_codes(client, who):
    r = await client.get("/api/ope/manager/pending", headers=token(who))
    assert r.status_code == 200, r.text
    return [e["employeeId"] for e in r.json()["employees"]]


async def test_employee_routed_through_pending_list_is_shown_even_if_manager_changed(client, db):
    await save_and_submit(client, "EMP001", amounts=(500, 400))
    assert await pending_codes(client, "RM001") == ["EMP001"]
    # the employee's reporting manager changes in Employee_details after submission,
    # but the Pending collection still routes them to RM001
    await db["Employee_details"].update_one({"EmpID": "EMP001"}, {"$set": {"ReportingEmpCode": "RM002"}})
    assert "EMP001" in await pending_codes(client, "RM001")
    assert "EMP001" in await pending_codes(client, "RM002")


async def test_pending_list_name_without_pending_entries_stays_hidden(client, db):
    await db["Pending"].insert_one({"ReportingEmpCode": "RM001", "EmployeesCodes": ["GHOST"]})
    assert await pending_codes(client, "RM001") == []


async def test_deleting_last_pending_entry_removes_employee_from_pending_list(client, db):
    await save_and_submit(client, "EMP001", amounts=(500,))
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    row = next(iter(doc["Data"][0].values()))[0]
    r = await client.request("DELETE", f"/api/ope/delete/{row['_id']}", headers=token("EMP001"),
                             json={"month_range": LABEL_A})
    assert r.status_code == 200, r.text
    pend = await db["Pending"].find_one({"ReportingEmpCode": "RM001"})
    assert "EMP001" not in (pend or {}).get("EmployeesCodes", [])



async def test_team_manager_with_own_reporting_manager_goes_to_that_manager_first(client, db):
    # EMP001 manages a team (listed in Reporting_managers) but reports to RM002, not to the partner
    await db["Reporting_managers"].insert_one({"ReportingEmpCode": "EMP001", "ReportingEmpName": "Asha Rao"})
    await db["Employee_details"].update_one({"EmpID": "EMP001"}, {"$set": {"ReportingEmpCode": "RM002"}})
    await save_and_submit(client, "EMP001", amounts=(500, 400))
    ps = (await db["Status"].find_one({"employeeId": "EMP001"}))["approval_status"][0]
    assert ps["submitter_type"] == "Employee" and ps["L1"]["approver_code"] == "RM002"
    assert "EMP001" in await pending_codes(client, "RM002")
    assert "EMP001" not in await pending_codes(client, "PT001")


async def test_manager_reporting_straight_to_partner_still_goes_to_partner(client, db):
    await save_and_submit(client, "RM001", amounts=(500, 400))   # RM001 reports to PT001
    ps = (await db["Status"].find_one({"employeeId": "RM001"}))["approval_status"][0]
    assert ps["submitter_type"] == "Reporting_Manager" and ps["L1"]["approver_code"] == "PT001"
