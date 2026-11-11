"""Admin Team Reports: Excel + supporting tickets grouped by Partner / Reporting Manager."""
import io
import zipfile

import openpyxl

from conftest import LABEL_A, LABEL_B, MONTH_A, MONTH_B, save_and_submit, token
from ope_features import team_reports

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def seed(client, db):
    await save_and_submit(client, "EMP001", MONTH_A, amounts=(500, 400))   # RM001 / PT001
    await save_and_submit(client, "EMP003", MONTH_A, amounts=(700,))       # RM002 / PT001
    await save_and_submit(client, "EMP001", MONTH_B, amounts=(100,))
    await client.post("/api/ope/manager/approve-month", headers=token("RM001"),
                      json={"employee_id": "EMP001", "month_range": LABEL_A})


async def get(client, who, path, **params):
    return await client.get(path, headers=token(who), params=params)


async def test_only_admin_can_use_team_reports(client, db):
    for who in ("JHS729", "EMP001", "RM001", "PT001"):
        for path in ("options", "preview", "excel", "tickets"):
            r = await get(client, who, f"/api/admin/team-report/{path}", group_by="partner")
            assert r.status_code == 403, (who, path)


async def test_options_list_partners_and_managers(client, db):
    p = (await get(client, "ADM01", "/api/admin/team-report/options", group_by="partner")).json()["people"]
    assert [x["code"] for x in p] == ["PT001"] or "PT001" in [x["code"] for x in p]
    m = (await get(client, "ADM01", "/api/admin/team-report/options", group_by="manager")).json()["people"]
    assert {"RM001", "RM002"} <= {x["code"] for x in m}
    assert (await get(client, "ADM01", "/api/admin/team-report/options", group_by="nope")).status_code == 400


async def test_manager_wise_excel_has_summary_months_and_entries(client, db):
    await seed(client, db)
    r = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="manager", person="RM001", month=LABEL_A)
    assert r.status_code == 200 and r.headers["content-type"].startswith(XLSX)
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Summary", "Employee Months", "Entries (supporting)"]
    rows = list(wb["Employee Months"].iter_rows(min_row=2, values_only=True))
    assert len(rows) == 1 and rows[0][2] == "EMP001" and rows[0][4] == LABEL_A     # only RM001's team, only that month
    assert rows[0][6] == 900 and rows[0][8] == 900                                  # submitted / reporting manager approved
    ent = list(wb["Entries (supporting)"].iter_rows(min_row=2, values_only=True))
    assert len(ent) == 2 and {e[13] for e in ent} == {500, 400} and all(e[16] == "Approved" for e in ent)
    summ = {c.value: wb["Summary"].cell(row=5, column=i).value for i, c in enumerate(wb["Summary"][4], start=1)}
    assert summ["Employees"] == 1 and summ["Records"] == 1 and summ["Submitted amount (INR)"] == 900


async def test_partner_wise_groups_both_managers_teams_and_all_months(client, db):
    await seed(client, db)
    r = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner", person="PT001")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    months = list(wb["Employee Months"].iter_rows(min_row=2, values_only=True))
    assert sorted((m[2], m[4]) for m in months) == sorted([("EMP001", LABEL_A), ("EMP001", LABEL_B), ("EMP003", LABEL_A)])
    # status filter
    r = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner", person="PT001", status="approved")
    assert r.status_code == 404                      # RM-approved only = still pending overall, nothing is fully approved
    r = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner", person="PT001", status="pending")
    assert r.status_code == 200
    # unknown person -> nothing to export
    assert (await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner", person="PT999")).status_code == 404


async def test_preview_counts_and_formula_escape(client, db):
    await seed(client, db)
    await db["Status"].update_one({"employeeId": "EMP003"}, {"$set": {"employeeName": "=SUM(A1)"}})
    pv = (await get(client, "ADM01", "/api/admin/team-report/preview", group_by="partner", person="PT001", month=LABEL_A)).json()
    assert pv["employees"] == 2 and pv["records"] == 2 and pv["entries"] == 3 and pv["tickets"] == 0
    r = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner", person="PT001", month=LABEL_A)
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    names = [row[3] for row in wb["Employee Months"].iter_rows(min_row=2, values_only=True)]
    assert any(str(n).startswith("'=") for n in names)


async def test_tickets_zip_contains_files_named_like_the_excel(client, db, monkeypatch):
    await seed(client, db)
    doc = await db["OPE_data"].find_one({"employeeId": "EMP001"})
    bucket = next(i[LABEL_A] for i in doc["Data"] if LABEL_A in i)
    fake = "64b000000000000000000001"
    await db["OPE_data"].update_one({"employeeId": "EMP001"}, {"$set": {f"Data.0.{LABEL_A}.0.ticket_pdf": fake}})

    async def reader(fid):
        return b"%PDF-1.4 fake" if fid == fake else None
    monkeypatch.setattr(team_reports, "_read_ticket", reader)
    assert (await get(client, "EMP001", "/api/admin/team-report/tickets", group_by="manager")).status_code == 403
    r = await get(client, "ADM01", "/api/admin/team-report/tickets", group_by="manager", person="RM001", month=LABEL_A)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip" and r.headers["x-tickets-included"] == "1"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    pdfs = [n for n in z.namelist() if n.endswith(".pdf")]
    assert len(pdfs) == 1 and pdfs[0].startswith("mgr RM001/EMP001_Asha Rao/")
    assert z.read(pdfs[0]).startswith(b"%PDF") and "README.txt" in z.namelist()
    x = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="manager", person="RM001", month=LABEL_A)
    ent = list(openpyxl.load_workbook(io.BytesIO(x.content))["Entries (supporting)"].iter_rows(min_row=2, values_only=True))
    withfile = [e for e in ent if e[23] == "Yes"]
    assert len(withfile) == 1 and pdfs[0].endswith(withfile[0][24])               # same name in Excel and ZIP
    # no tickets attached in another selection -> clear message
    r = await get(client, "ADM01", "/api/admin/team-report/tickets", group_by="manager", person="RM002", month=LABEL_A)
    assert r.status_code == 404


async def test_managers_list_follows_the_chosen_partner(client, db):
    allm = (await get(client, "ADM01", "/api/admin/team-report/options", group_by="partner")).json()["managers"]
    assert {"RM001", "RM002"} <= {x["code"] for x in allm}
    under = (await get(client, "ADM01", "/api/admin/team-report/options", group_by="partner", partner="PT001")).json()
    assert {"RM001", "RM002"} <= {x["code"] for x in under["managers"]}
    assert "PT001" in {x["code"] for x in under["partners"]}
    none = (await get(client, "ADM01", "/api/admin/team-report/options", group_by="partner", partner="PT002")).json()
    assert none["managers"] == []
    # a manager whose employees all belong to another partner is not offered
    await db["Employee_details"].update_one({"EmpID": "EMP003"}, {"$set": {"PartnerEmpCode": "PT002"}})
    p1 = (await get(client, "ADM01", "/api/admin/team-report/options", partner="PT001")).json()["managers"]
    p2 = (await get(client, "ADM01", "/api/admin/team-report/options", partner="PT002")).json()["managers"]
    assert "RM002" not in {x["code"] for x in p1} and {x["code"] for x in p2} == {"RM002"}


async def test_partner_and_manager_filters_combine(client, db):
    await seed(client, db)
    r = await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner", partner="PT001", manager="RM002")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    months = list(wb["Employee Months"].iter_rows(min_row=2, values_only=True))
    assert [m[2] for m in months] == ["EMP003"]
    assert "RM002" in r.headers["content-disposition"] and "PT001" in r.headers["content-disposition"]
    assert "Reporting Manager: RM002" in wb["Summary"]["A2"].value
    pv = (await get(client, "ADM01", "/api/admin/team-report/preview", group_by="partner", partner="PT001", manager="RM001")).json()
    assert pv["employees"] == 1 and pv["records"] == 2
    await db["Employee_details"].update_one({"EmpID": "EMP003"}, {"$set": {"PartnerEmpCode": "PT002"}})
    assert (await get(client, "ADM01", "/api/admin/team-report/excel", group_by="partner",
                      partner="PT001", manager="RM002")).status_code == 404
