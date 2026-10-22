"""Test harness: the real FastAPI app wired to an in-memory Mongo (mongomock-motor)."""
import os
import sys

os.environ.setdefault("MONGO_URI", "mongodb://localhost:1")
os.environ.setdefault("MONGO_DB", "ope_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient

import main  # noqa: E402
import ope_features  # noqa: E402
from ope_features.common import ctx  # noqa: E402

MONTH_A = "august-september-2026"
MONTH_B = "september-october-2026"
LABEL_A = "August 2026 - September 2026"
LABEL_B = "September 2026 - October 2026"

EMPLOYEES = [
    # EmpID, name, reporting mgr, partner, limit
    ("EMP001", "Asha Rao", "RM001", "PT001", 1500),
    ("EMP002", "Bala Iyer", "RM001", "PT001", 1500),
    ("EMP003", "Chitra Nair", "RM002", "PT001", 2000),
    ("RM001", "Ravi Mehta", "PT001", "PT001", 0),
    ("RM002", "Rina Shah", "PT001", "PT001", 0),
    ("PT001", "Priya Partner", "", "", 0),
    ("PT002", "Other Partner", "", "", 0),
    ("JHS729", "HR Dept", "", "", 0),
    ("ADM01", "Admin One", "", "", 0),
]


@pytest_asyncio.fixture
async def db():
    client = AsyncMongoMockClient()
    mdb = client["ope_test"]
    main.db = mdb
    main.user_collection = mdb["user"]
    ctx.db = mdb
    for emp_id, name, rm, pt, limit in EMPLOYEES:
        await mdb["Employee_details"].insert_one({
            "EmpID": emp_id, "Emp Name": name, "ReportingEmpCode": rm, "ReportingEmpName": f"mgr {rm}",
            "PartnerEmpCode": pt, "Partner": "Priya Partner", "OPE LIMIT": limit,
            "Designation Name": "Consultant", "Gender": "F"})
        await mdb["user"].insert_one({"employee_code": emp_id, "password_hash": "x"})
    await mdb["Reporting_managers"].insert_many([
        {"ReportingEmpCode": "RM001", "ReportingEmpName": "Ravi Mehta"},
        {"ReportingEmpCode": "RM002", "ReportingEmpName": "Rina Shah"}])
    await mdb["Partner"].insert_many([
        {"PartnerEmpCode": "PT001", "Partner_Name": "Priya Partner"},
        {"PartnerEmpCode": "PT002", "Partner_Name": "Other Partner"}])
    await mdb["Admin"].insert_one({"employee_codes": ["ADM01"]})
    await ope_features.ensure_indexes()
    return mdb


def token(code: str) -> dict:
    return {"Authorization": f"Bearer {main.create_access_token({'sub': code})}"}


@pytest_asyncio.fixture
async def client(db):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def save_entry(client, code, month=MONTH_A, amount=500, day="2026-09-01", project="P1"):
    return await client.post("/api/ope/save-temp", headers=token(code), data={
        "date": day, "client": "ACME", "project_id": project, "project_name": "Proj",
        "project_type": "Billable", "location_from": "A", "location_to": "B",
        "travel_mode": "Cab", "amount": str(amount), "remarks": "trip", "month_range": month})


async def submit(client, code, month=MONTH_A):
    return await client.post("/api/ope/submit-final", headers=token(code), json={"month_range": month})


async def save_and_submit(client, code, month=MONTH_A, amounts=(500, 400)):
    for n, a in enumerate(amounts):
        r = await save_entry(client, code, month, a, project=f"P{n}")
        assert r.status_code == 200, r.text
    return await submit(client, code, month)
