"""Load the restricted-employee list into MongoDB (collection: ope_restricted_employees).

Safe to run more than once: employees are upserted by EmpID (no duplicates).
Employees missing from Employee_details are reported and skipped.

    python seed_restricted_employees.py --dry-run     # show what would happen
    python seed_restricted_employees.py                # write

The monthly HR records are created by the app itself (start-up, every 30 minutes,
login and status view), so this script only maintains the list."""
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

EMPLOYEES = [
    ("JHS1303", "Abutalib K.Raza Syed", 1500), ("JHS714", "Aparna Gangaram Wadkar", 1500),
    ("JHS1471", "Asad Afsar ali Baloch", 1500), ("JHS1465", "Dhanashree Sharad Mhaskar", 1500),
    ("JHS1347", "Isha Mehul Parikh", 1500), ("JHS1490", "Fatima Firoz Ansari", 1500),
    ("JHS1284", "Ismail Tajuddin Shaikh", 1500), ("JHS1234", "Mahrin Fatima Abujafar Shaikh", 1500),
    ("JHS1000", "Mohd Zaid Mohd Arif Mudel", 1500), ("JHS1294", "Ritesh Rajesh Pevekar", 1500),
    ("JHS1097", "Muis Mushtaq Inamdar", 2000), ("JHS1424", "Neha Devi Sunil Chavriya", 1500),
    ("JHS1533", "Nikheel Chandrabhan Gupta", 1500), ("JHS1458", "Om Sanjay Dhuri", 1500),
    ("JHS1312", "Siddhesh Govind Iyer", 1500), ("JHS1033", "Prasad Pandurang Danavale", 1500),
    ("JHS1103", "Sowmi Shyamal Santra", 1500), ("JHS293", "Sabhya Shivaprakash Vishwakarma", 1500),
    ("JHS762", "Salman Salim Sayyed", 1500), ("JHS1329", "Shivamangala Mallikarjun Udubal", 1500),
    ("JHS732", "Yash Pravin Gediya", 1500),
]


def main() -> int:
    dry = "--dry-run" in sys.argv
    load_dotenv()
    db = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=15000)[os.environ["MONGO_DB"]]
    coll = db["ope_restricted_employees"]
    if not dry:
        coll.create_index("employee_id", unique=True)
    now = datetime.now(timezone.utc)
    added = updated = 0
    missing = []
    for emp_id, name, limit in EMPLOYEES:
        emp = db["Employee_details"].find_one({"EmpID": emp_id})
        if not emp:
            missing.append(emp_id)
            continue
        exists = coll.find_one({"employee_id": emp_id}) is not None
        if not dry:
            coll.update_one(
                {"employee_id": emp_id},
                {"$set": {"employee_name": emp.get("Emp Name") or name, "ope_limit": float(limit),
                          "active": True, "updated_at": now, "updated_by": "seed_script"},
                 "$setOnInsert": {"created_at": now, "created_by": "seed_script"}},
                upsert=True)
        added, updated = (added, updated + 1) if exists else (added + 1, updated)
    print(("DRY RUN - " if dry else "") + f"new: {added}, already present (refreshed): {updated}, "
          f"total in list: {len(EMPLOYEES)}")
    if missing:
        print("Skipped - not found in Employee_details:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
