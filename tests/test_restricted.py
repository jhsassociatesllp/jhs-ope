"""Restricted employees: cannot fill own OPE, monthly HR record, report only after HR approval."""
import asyncio
import io
from datetime import datetime, timezone

import openpyxl

from conftest import LABEL_A, LABEL_B, MONTH_A, save_and_submit, save_entry, submit, token
from ope_features import restricted
from ope_features.common import IST


async def add(client, emp="EMP003", limit=None, active=True, who="ADM01"):
    body = {"employee_id": emp, "active": active}
    if limit is not None:
        body["ope_limit"] = limit
    return await client.post("/api/admin/restricted-employees", headers=token(who), json=body)


def at(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=IST).astimezone(timezone.utc)


async def test_payroll_period_label_follows_21st_to_20th_cycle():
    assert restricted.current_period_label(at(2026, 10, 19)) == "September 2026 - October 2026"
    assert restricted.current_period_label(at(2026, 10, 21)) == "October 2026 - November 2026"
    assert restricted.current_period_label(at(2026, 12, 25)) == "December 2026 - January 2027"
    assert restricted.current_period_label(at(2027, 1, 5)) == "December 2026 - January 2027"


async def test_only_admin_manages_restrictions(client, db):
    for who in ("JHS729", "EMP001", "RM001"):
        assert (await add(client, who=who)).status_code == 403
    assert (await client.get("/api/admin/restricted-employees", headers=token("EMP001"))).status_code == 403
    assert (await add(client, emp="NOPE")).status_code == 404
    r = await add(client, limit=1500)
    assert r.status_code == 200 and r.json()["active"] is True and r.json()["current_month_record"] == "created"
    assert (await client.get("/api/admin/restricted-employees", headers=token("ADM01"))).json()["total"] == 1


async def test_restricted_employee_cannot_fill_edit_or_submit(client, db):
    await add(client, limit=1500)
    r = await save_entry(client, "EMP003", MONTH_A)
    assert r.status_code == 403 and "not allowed to fill your own OPE" in r.json()["detail"]
    assert (await submit(client, "EMP003", MONTH_A)).status_code == 403
    s = await client.get("/api/ope/access/status", params={"month": MONTH_A}, headers=token("EMP003"))
    assert s.json()["locked"] and s.json()["reason"] == "restricted"
    # their system-created entry cannot be edited either
    doc = await db["OPE_data"].find_one({"employeeId": "EMP003"})
    month = restricted.current_period_label()
    eid = str(next(i[month] for i in doc["Data"] if month in i)[0]["_id"])
    r = await client.put(f"/api/ope/update/{eid}", headers=token("EMP003"), json={"month_range": month, "amount": 9})
    assert r.status_code == 409
    me = await client.get("/api/ope/my-restriction", headers=token("EMP003"))
    assert me.json()["restricted"] is True
    assert (await client.get("/api/ope/my-restriction", headers=token("EMP001"))).json() == {"restricted": False}
    # login-level data still works (status page loads)
    assert (await client.get("/api/ope/status/EMP003", headers=token("EMP003"))).status_code == 200


async def test_unrestricted_employees_unaffected(client, db):
    await add(client, limit=1500)
    assert (await save_and_submit(client, "EMP001")).status_code == 200
    assert (await save_and_submit(client, "EMP002")).status_code == 200


async def test_monthly_record_pending_then_approved_and_visible_on_status(client, db):
    await add(client, limit=1500)
    month = restricted.current_period_label()
    st = (await client.get("/api/ope/status/EMP003", headers=token("EMP003"))).json()["status_entries"]
    assert len(st) == 1 and st[0]["payroll_month"] == month
    assert st[0]["restricted"] is True and st[0]["overall_status"] == "pending"
    assert st[0]["total_amount"] == 1500
    hr = (await client.get("/api/ope/hr/pending-employees", headers=token("JHS729"))).json()["pending_employees"]
    assert [(x["employeeId"], x["payroll_month"]) for x in hr] == [("EMP003", month)]
    # only HR may approve; the month-specific record becomes Approved
    r = await client.post("/api/ope/hr/approve-month", headers=token("RM002"),
                          json={"employee_id": "EMP003", "month_range": month})
    assert r.status_code == 403
    r = await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                          json={"employee_id": "EMP003", "month_range": month, "remark": "ok"})
    assert r.status_code == 200, r.text
    st = (await client.get("/api/ope/status/EMP003", headers=token("EMP003"))).json()["status_entries"][0]
    assert st["overall_status"] == "approved" and st["restricted"] is True


async def test_no_duplicate_monthly_records(client, db):
    await add(client, limit=1500)
    month = restricted.current_period_label()
    outs = await asyncio.gather(*[restricted.ensure_month_record("EMP003", month) for _ in range(5)])
    assert set(outs) <= {"exists", "created"}
    for _ in range(3):
        await client.get("/api/ope/status/EMP003", headers=token("EMP003"))
    st = await db["Status"].find_one({"employeeId": "EMP003"})
    assert len(st["approval_status"]) == 1
    doc = await db["OPE_data"].find_one({"employeeId": "EMP003"})
    assert len(next(i[month] for i in doc["Data"] if month in i)) == 1
    assert await db["ope_restricted_months"].count_documents({"employee_id": "EMP003", "payroll_month": month}) == 1


async def test_new_month_creates_a_separate_record_and_approval_is_month_specific(client, db):
    await add(client, limit=1500)
    m1 = restricted.current_period_label()
    m2 = "October 2026 - November 2026" if m1 != "October 2026 - November 2026" else LABEL_B
    assert await restricted.ensure_month_record("EMP003", m2) == "created"
    await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                      json={"employee_id": "EMP003", "month_range": m1})
    st = await db["Status"].find_one({"employeeId": "EMP003"})
    by = {p["payroll_month"]: p["overall_status"] for p in st["approval_status"]}
    assert by[m1] == "approved" and by[m2] == "pending"


async def test_hr_report_lists_restricted_only_after_hr_approval(client, db):
    await add(client, limit=1500)
    await save_and_submit(client, "EMP001", amounts=(100,))          # normal employee, pending
    month = restricted.current_period_label()
    # put the normal employee's submission in the same month as the restricted record
    await db["Status"].update_one({"employeeId": "EMP001"}, {"$set": {"approval_status.0.payroll_month": month}})
    rep = (await client.get("/api/hr/report", headers=token("JHS729"), params={"month": month})).json()
    ids = [r["employee_id"] for r in rep["rows"]]
    assert ids == ["EMP001"]                                          # pending restricted record hidden
    assert rep["summary"]["total_records"] == 1 and rep["summary"]["counts"]["pending"] == 1
    x = await client.get("/api/hr/report/export", headers=token("JHS729"), params={"month": month})
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    assert [r[0] for r in wb["Records"].iter_rows(min_row=2, values_only=True)] == ["EMP001"]

    await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                      json={"employee_id": "EMP003", "month_range": month})
    rep = (await client.get("/api/hr/report", headers=token("JHS729"), params={"month": month})).json()
    assert sorted(r["employee_id"] for r in rep["rows"]) == ["EMP001", "EMP003"]
    row = next(r for r in rep["rows"] if r["employee_id"] == "EMP003")
    assert row["status"] == "approved" and row["hr_approved_amount"] == 1500 and row["restricted"] is True
    x = await client.get("/api/hr/report/export", headers=token("JHS729"), params={"month": month})
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    assert sorted(r[0] for r in wb["Records"].iter_rows(min_row=2, values_only=True)) == ["EMP001", "EMP003"]


async def test_rejected_restricted_record_stays_out_of_report(client, db):
    await add(client, limit=1500)
    month = restricted.current_period_label()
    r = await client.post("/api/ope/hr/reject-month", headers=token("JHS729"),
                          json={"employee_id": "EMP003", "month_range": month, "reason": "check amount"})
    assert r.status_code == 200, r.text
    rep = (await client.get("/api/hr/report", headers=token("JHS729"), params={"month": month})).json()
    assert rep["rows"] == []


async def test_deactivating_restores_normal_submission(client, db):
    await add(client, limit=1500)
    assert (await save_entry(client, "EMP003", MONTH_A)).status_code == 403
    await add(client, active=False)
    assert (await save_entry(client, "EMP003", MONTH_A)).status_code == 200
    # no new record is created for a deactivated employee
    assert await restricted.ensure_month_record("EMP003", LABEL_B) == "not_restricted"


async def test_employee_already_submitted_month_is_not_overwritten(client, db):
    await save_and_submit(client, "EMP003", MONTH_A, amounts=(300,))
    await add(client, limit=1500)
    out = await restricted.ensure_month_record("EMP003", LABEL_A)
    assert out == "already has a submission for this month"
    doc = await db["OPE_data"].find_one({"employeeId": "EMP003"})
    assert len(next(i[LABEL_A] for i in doc["Data"] if LABEL_A in i)) == 1
