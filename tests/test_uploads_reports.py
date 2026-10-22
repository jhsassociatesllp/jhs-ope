"""Monthly eligibility/limit uploads, fixed-amount employees, HR report + export."""
import io

import openpyxl

from conftest import LABEL_A, LABEL_B, MONTH_A, MONTH_B, save_and_submit, save_entry, submit, token

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_xlsx(rows, header=("EmpID", "Emp Name", "OPE LIMIT", "Fixed OPE Amount")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def upload(client, who, rows, start_month="8", start_year="2026", name="m.xlsx", header=None):
    data = make_xlsx(rows, header) if header else make_xlsx(rows)
    return await client.post("/api/admin/monthly-upload", headers=token(who),
                             data={"start_month": start_month, "start_year": start_year},
                             files={"file": (name, data, XLSX)})


async def activate(client, who, vid, expected=""):
    return await client.post(f"/api/admin/monthly-upload/{vid}/activate", headers=token(who),
                             json={"confirm": True, "expected_active_id": expected})


GOOD = [("EMP001", "Asha Rao", 1500, None), ("EMP002", "Bala Iyer", 3000, None),
        ("EMP003", "Chitra Nair", 2000, 1800)]


async def test_upload_is_admin_only(client, db):
    for who in ("JHS729", "EMP001", "RM001", "PT001"):
        r = await upload(client, who, GOOD)
        assert r.status_code == 403, who
    assert (await upload(client, "ADM01", GOOD)).status_code == 200


async def test_valid_upload_preview_and_activation(client, db):
    r = await upload(client, "ADM01", GOOD)
    body = r.json()
    assert body["payroll_month"] == LABEL_A and body["version"] == 1
    assert body["validation"] == "passed" and body["row_count"] == 3 and body["fixed_count"] == 1
    assert body["is_active"] is False and len(body["preview"]) == 3
    assert body["uploaded_at_ist"].endswith("IST")
    r = await activate(client, "ADM01", body["id"])
    assert r.status_code == 200, r.text
    assert r.json()["fixed_submissions_created"] == 1
    versions = (await client.get("/api/admin/monthly-upload/versions", headers=token("ADM01"),
                                 params={"month": LABEL_A})).json()["versions"]
    assert versions[0]["is_active"] is True
    # activating the same version twice is refused
    assert (await activate(client, "ADM01", body["id"], expected=body["id"])).status_code == 409


async def test_invalid_upload_reports_rows_and_keeps_active_version(client, db):
    good = (await upload(client, "ADM01", GOOD)).json()
    await activate(client, "ADM01", good["id"])
    bad_rows = [("EMP001", "Asha Rao", 1500, None), ("NOPE99", "Ghost", 1000, None),
                ("EMP001", "Asha Rao", 1500, None), ("EMP002", "Bala Iyer", "abc", None),
                ("EMP003", "Chitra Nair", -5, None), ("RM001", "Ravi Mehta", 100, "x")]
    bad = (await upload(client, "ADM01", bad_rows)).json()
    assert bad["validation"] == "failed" and bad["error_count"] >= 5
    msgs = " | ".join(e["message"] for e in bad["errors"])
    assert "not found" in msgs and "Duplicate" in msgs and "OPE LIMIT" in msgs and "Fixed OPE Amount" in msgs
    assert (await activate(client, "ADM01", bad["id"], expected=good["id"])).status_code == 400
    # active version unchanged, and no rows were stored for the failed one
    ptr = await db["OPE_monthly_active"].find_one({"payroll_month": LABEL_A})
    assert str(ptr["version_id"]) == good["id"]
    from bson import ObjectId
    assert await db["OPE_monthly_rows"].count_documents({"version_id": ObjectId(bad["id"])}) == 0


async def test_wrong_headers_and_file_types_rejected(client, db):
    r = await upload(client, "ADM01", [("EMP001", 5)], header=("Foo", "Bar"))
    assert r.status_code == 200 and r.json()["validation"] == "failed" and r.json()["header_error"]
    r = await client.post("/api/admin/monthly-upload", headers=token("ADM01"),
                          data={"start_month": "8", "start_year": "2026"},
                          files={"file": ("x.exe", b"MZ....", "application/octet-stream")})
    assert r.status_code == 400
    r = await client.post("/api/admin/monthly-upload", headers=token("ADM01"),
                          data={"start_month": "8", "start_year": "2026"},
                          files={"file": ("x.xlsx", b"not a zip", XLSX)})
    assert r.status_code == 400


async def test_stale_activation_is_refused(client, db):
    v1 = (await upload(client, "ADM01", GOOD)).json()
    v2 = (await upload(client, "ADM01", GOOD[:2])).json()
    assert (await activate(client, "ADM01", v1["id"])).status_code == 200
    r = await activate(client, "ADM01", v2["id"], expected="")  # page loaded before v1 was activated
    assert r.status_code == 409
    assert (await activate(client, "ADM01", v2["id"], expected=v1["id"])).status_code == 200
    versions = (await client.get("/api/admin/monthly-upload/versions", headers=token("ADM01"),
                                 params={"month": LABEL_A})).json()["versions"]
    assert [v["version"] for v in versions] == [2, 1]
    assert [v["is_active"] for v in versions] == [True, False]  # history preserved


async def test_months_have_independent_limits(client, db):
    may = (await upload(client, "ADM01", [("EMP001", "Asha Rao", 1500, None)], "8", "2026")).json()
    jun = (await upload(client, "ADM01", [("EMP001", "Asha Rao", 2000, None)], "9", "2026")).json()
    await activate(client, "ADM01", may["id"])
    await activate(client, "ADM01", jun["id"])
    assert (await save_and_submit(client, "EMP001", MONTH_A, amounts=(1400,))).status_code == 200
    assert (await save_and_submit(client, "EMP001", MONTH_B, amounts=(1900,))).status_code == 200
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    by = {p["payroll_month"]: p for p in st["approval_status"]}
    assert by[LABEL_A]["limit"] == 1500 and by[LABEL_B]["limit"] == 2000
    # 1900 is within June's 2000 -> 2 levels; the master Employee_details limit (1500) was not used
    assert by[LABEL_B]["total_levels"] == 2
    # a later re-upload for June does not touch August-September history
    jun2 = (await upload(client, "ADM01", [("EMP001", "Asha Rao", 5000, None)], "9", "2026")).json()
    await activate(client, "ADM01", jun2["id"], expected=jun["id"])
    st = await db["Status"].find_one({"employeeId": "EMP001"})
    assert {p["payroll_month"]: p["limit"] for p in st["approval_status"]}[LABEL_A] == 1500
    d = await client.get("/api/ope/submission/EMP001/detail", params={"month": MONTH_A}, headers=token("EMP001"))
    assert d.json()["limit"]["amount"] == 1500


async def test_not_in_eligible_list_cannot_submit(client, db):
    v = (await upload(client, "ADM01", [("EMP001", "Asha Rao", 1500, None)])).json()
    await activate(client, "ADM01", v["id"])
    r = await save_entry(client, "EMP002", MONTH_A)
    assert r.status_code == 403 and "eligible" in r.json()["detail"]
    assert (await save_entry(client, "EMP001", MONTH_A)).status_code == 200
    # months with no active upload keep the legacy behaviour
    assert (await save_entry(client, "EMP002", MONTH_B)).status_code == 200
    s = await client.get("/api/ope/access/status", params={"month": MONTH_A}, headers=token("EMP002"))
    assert s.json()["locked"] is True and s.json()["reason"] == "not_eligible"


async def test_fixed_amount_employee_goes_to_hr_not_the_form(client, db):
    v = (await upload(client, "ADM01", GOOD)).json()
    await activate(client, "ADM01", v["id"])
    r = await save_entry(client, "EMP003", MONTH_A)
    assert r.status_code == 403 and "fixed" in r.json()["detail"]
    assert (await submit(client, "EMP003", MONTH_A)).status_code == 403
    # but the record exists and HR can see + act on it
    hr_pending = await client.get("/api/ope/hr/pending-employees", headers=token("JHS729"))
    rows = hr_pending.json()["pending_employees"]
    assert [(x["employeeId"], x["total_amount"]) for x in rows] == [("EMP003", 1800)]
    d = await client.get("/api/ope/submission/EMP003/detail", params={"month": MONTH_A}, headers=token("EMP003"))
    body = d.json()
    assert body["status"]["is_fixed_amount"] is True and body["amounts"]["original_submitted"] == 1800.0
    assert body["entries"][0]["is_fixed_amount"] is True
    # a non-HR user cannot approve it
    r = await client.post("/api/ope/hr/approve-month", headers=token("RM001"),
                          json={"employee_id": "EMP003", "month_range": LABEL_A})
    assert r.status_code == 403
    r = await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                          json={"employee_id": "EMP003", "month_range": LABEL_A, "remark": "ok"})
    assert r.status_code == 200, r.text
    st = await db["Status"].find_one({"employeeId": "EMP003"})
    ps = st["approval_status"][0]
    assert ps["overall_status"] == "approved" and ps["stage_amounts"]["L2"]["approved_amount"] == 1800.0
    actions = [(e["action"], e["stage"]) async for e in db["OPE_audit_log"].find(
        {"employeeId": "EMP003"}).sort("at", 1)]
    assert actions == [("fixed_amount_assigned", "System"), ("approved", "HR")]
    # re-activating an identical new version does not duplicate the record
    v2 = (await upload(client, "ADM01", GOOD)).json()
    r = await activate(client, "ADM01", v2["id"], expected=v["id"])
    assert r.json()["fixed_submissions_created"] == 0 and r.json()["fixed_skipped"][0]["emp_id"] == "EMP003"


async def test_hr_report_counts_match_export(client, db):
    await save_and_submit(client, "EMP001", amounts=(500, 400))                  # will be approved by RM
    await save_and_submit(client, "EMP002", amounts=(300,))                      # stays pending
    await save_and_submit(client, "EMP003", amounts=(700,))                      # will be rejected
    await save_and_submit(client, "EMP001", MONTH_B, amounts=(100,))             # other month, must not leak
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/manager/reject-month", headers=token("RM002"),
                      json={"employee_id": "EMP003", "month_range": LABEL_A, "reason": "personal"})
    assert (await client.get("/api/hr/report", headers=token("EMP001"), params={"month": MONTH_A})).status_code == 403
    assert (await client.get("/api/hr/report", headers=token("RM001"), params={"month": MONTH_A})).status_code == 403
    r = await client.get("/api/hr/report", headers=token("JHS729"), params={"month": MONTH_A})
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["total_records"] == 3 and s["payroll_month"] == LABEL_A
    assert s["counts"] == {"approved": 0, "pending": 2, "rejected": 1, "partial": 0}
    assert s["total_submitted_amount"] == 1900.0
    rows = {x["employee_id"]: x for x in r.json()["rows"]}
    assert rows["EMP001"]["submitted_amount"] == 900.0 and rows["EMP001"]["rm_approved_amount"] == 900.0
    assert rows["EMP001"]["hr_approved_amount"] is None and rows["EMP001"]["stage"] == "Pending at HR"
    assert rows["EMP003"]["status"] == "rejected" and "personal" in rows["EMP003"]["remarks"]
    assert rows["EMP001"]["rm_action_at"].endswith("IST")

    x = await client.get("/api/hr/report/export", headers=token("ADM01"), params={"month": MONTH_A})
    assert x.status_code == 200 and x.headers["content-type"].startswith(XLSX)
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    summ = {row[0].value: row[1].value for row in wb["Summary"].iter_rows(min_row=4) if row[0].value}
    assert summ["Total records"] == 3 and summ["Pending"] == 2 and summ["Rejected"] == 1
    assert summ["Total submitted amount (INR)"] == 1900.0
    rec = list(wb["Records"].iter_rows(min_row=2, values_only=True))
    assert len(rec) == 3 and sum(r[5] for r in rec) == 1900.0
    assert x.content != b""
    # filter + pagination
    r = await client.get("/api/hr/report", headers=token("JHS729"),
                         params={"month": MONTH_A, "status": "pending", "page_size": 1})
    assert r.json()["total_rows"] == 2 and len(r.json()["rows"]) == 1


async def test_report_export_escapes_formulas(client, db):
    await save_and_submit(client, "EMP002", amounts=(300,))
    await db["Status"].update_one({"employeeId": "EMP002"}, {"$set": {"employeeName": "=HYPERLINK(\"x\")"}})
    x = await client.get("/api/hr/report/export", headers=token("JHS729"), params={"month": MONTH_A})
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    assert wb["Records"]["B2"].value.startswith("'=")


async def test_access_listing_and_employee_lookup(client, db):
    await save_and_submit(client, "EMP001")
    await client.post("/api/ope/access/reopen", headers=token("JHS729"),
                      json={"employee_id": "EMP001", "payroll_month": LABEL_A, "reason": "need fix"})
    r = await client.get("/api/ope/access/permissions", headers=token("ADM01"), params={"status": "active"})
    assert r.json()["total"] == 1 and r.json()["items"][0]["granted_at_ist"].endswith("IST")
    assert (await client.get("/api/ope/access/permissions", headers=token("EMP001"))).status_code == 403
    e = await client.get("/api/ope/access/employee/EMP001", headers=token("JHS729"))
    assert e.json()["months"][0]["reopen_permitted"] is True
    assert (await client.get("/api/ope/access/employee/NOPE", headers=token("JHS729"))).status_code == 404
    # an employee can check only their own lock state
    ok = await client.get("/api/ope/access/status", params={"month": MONTH_A}, headers=token("EMP001"))
    assert ok.status_code == 200 and ok.json()["reopen_permitted"] is True and ok.json()["locked"] is False
    other = await client.get("/api/ope/access/status", params={"month": MONTH_A, "employee_id": "EMP001"},
                             headers=token("EMP002"))
    assert other.status_code == 403
