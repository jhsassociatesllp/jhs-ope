"""Local demo: real app on an in-memory database with sample data. Password for every user: Test@1234"""
import asyncio, io, os, sys
os.environ.update(MONGO_URI="mongodb://localhost:1", MONGO_DB="dev", JWT_SECRET="dev", JWT_ALGORITHM="HS256")
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + r"\tests")
import httpx, uvicorn, openpyxl
from mongomock_motor import AsyncMongoMockClient
import main, ope_features
from ope_features.common import ctx
import conftest as C

async def seed():
    mdb = AsyncMongoMockClient()["dev"]
    main.db = mdb; main.user_collection = mdb["user"]; ctx.db = mdb
    for emp_id, name, rm, pt, limit in C.EMPLOYEES:
        await mdb["Employee_details"].insert_one({"EmpID": emp_id, "Emp Name": name, "ReportingEmpCode": rm, "ReportingEmpName": "Ravi Mehta" if rm=="RM001" else "Rina Shah", "PartnerEmpCode": pt, "Partner": "Priya Partner", "OPE LIMIT": limit, "Designation Name": "Consultant", "Gender": "F"})
        await mdb["user"].insert_one({"employee_code": emp_id, "password_hash": main.get_password_hash("Test@1234")})
    await mdb["Reporting_managers"].insert_many([{"ReportingEmpCode": "RM001", "ReportingEmpName": "Ravi Mehta"}, {"ReportingEmpCode": "RM002", "ReportingEmpName": "Rina Shah"}])
    await mdb["Partner"].insert_many([{"PartnerEmpCode": "PT001", "Partner_Name": "Priya Partner"}])
    await mdb["Admin"].insert_one({"employee_codes": ["ADM01"]})
    await ope_features.ensure_indexes()
    t = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=t, base_url="http://x") as c:
        T = C.token
        await C.save_and_submit(c, "EMP001", C.MONTH_A, (500, 400))
        await C.save_and_submit(c, "EMP002", C.MONTH_A, (300,))
        await C.save_and_submit(c, "EMP003", C.MONTH_A, (1200, 1100))
        await C.save_and_submit(c, "EMP001", C.MONTH_B, (250,))
        await c.post("/api/ope/manager/approve-month", headers=T("RM001"), json={"employee_id": "EMP001", "month_range": C.LABEL_A, "remark": "Looks fine"})
        await c.post("/api/ope/manager/reject-month", headers=T("RM002"), json={"employee_id": "EMP003", "month_range": C.LABEL_A, "reason": "Personal travel"})
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["EmpID", "Emp Name", "OPE LIMIT", "Fixed OPE Amount"])
        ws.append(["EMP001", "Asha Rao", 1500, None]); ws.append(["EMP002", "Bala Iyer", 3000, None]); ws.append(["EMP003", "Chitra Nair", 2000, 1800])
        b = io.BytesIO(); wb.save(b)
        r = await c.post("/api/admin/monthly-upload", headers=T("ADM01"), data={"start_month": "9", "start_year": "2026"}, files={"file": ("sep.xlsx", b.getvalue(), "application/octet-stream")})
        await c.post(f"/api/admin/monthly-upload/{r.json()['id']}/activate", headers=T("ADM01"), json={"confirm": True, "expected_active_id": ""})
        await c.post("/api/ope/access/reopen", headers=T("JHS729"), json={"employee_id": "EMP002", "payroll_month": C.LABEL_A, "reason": "Missing ticket"})
    for who in ("EMP001", "EMP002", "RM001", "PT001", "JHS729", "ADM01"):
        print(who, C.token(who)["Authorization"].split()[1])

async def run():
    await seed()
    cfg = uvicorn.Config(main.app, host="127.0.0.1", port=8765, log_level="warning")
    await uvicorn.Server(cfg).serve()
asyncio.run(run())
