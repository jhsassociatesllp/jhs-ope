from conftest import LABEL_A, save_and_submit, token
from ope_features.reports import build_report


async def _row():
    rep = await build_report(LABEL_A)
    return next(r for r in rep["rows"] if r["employee_id"] == "EMP001")


async def test_hr_action_after_partial_pending_approve(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))
    body = {"employee_id": "EMP001", "payroll_month": LABEL_A, "remark": "ok by hr"}
    assert (await client.post("/api/ope/hr/partial-pending/approve", headers=token("JHS729"), json=body)).status_code == 200
    r = await _row()
    assert r["hr_action_at"] and "IST" in r["hr_action_at"]
    assert "ok by hr" in r["hr_remark"]


async def test_hr_action_after_partial_pending_reject(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))
    body = {"employee_id": "EMP001", "month_range": LABEL_A, "reason": "Not valid"}
    assert (await client.post("/api/ope/hr/partial-pending/reject", headers=token("JHS729"), json=body)).status_code == 200
    r = await _row()
    assert r["hr_action_at"]
    assert "Not valid" in r["hr_remark"]


async def test_hr_action_after_normal_pending_approve(client, db):
    await save_and_submit(client, "EMP001", amounts=(1000, 600))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"), json={"employee_id": "EMP001", "month_range": LABEL_A})
    await client.post("/api/ope/partner/approve-month", headers=token("PT001"), json={"employee_id": "EMP001", "month_range": LABEL_A})
    res = await client.post("/api/ope/hr/approve-month", headers=token("JHS729"),
                            json={"employee_id": "EMP001", "month_range": LABEL_A, "remark": "final ok"})
    assert res.status_code == 200, res.text
    r = await _row()
    assert r["hr_action_at"]
    assert "final ok" in r["hr_remark"]
