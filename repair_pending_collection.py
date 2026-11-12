"""Remove stale names from the Pending collection (names with nothing for that approver to act on).

  - Reporting-manager lists: an employee is removed when they have NO entry with status "pending"
    (any employee who does have one is shown on the manager's screen, whoever their manager is).
  - Partner lists: an employee is removed when no Status month is currently waiting on that partner
    (overall pending, current level's approver_code == partner) AND they have no pending entry.
Nothing else is touched (entries / Status stay as they are).

    python repair_pending_collection.py            # dry run
    python repair_pending_collection.py --apply    # writes it (backup saved first)
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


def has_pending_entry(ope):
    return any((e.get("status") or "").lower() == "pending"
               for b in (ope or {}).get("Data", []) for rows in b.values() for e in rows)


async def main(apply: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URI"])[os.environ["MONGO_DB"]]
    partners = {p["PartnerEmpCode"] async for p in db["Partner"].find({})}
    removals, backup = {}, []
    async for pd in db["Pending"].find({}):
        rm = pd["ReportingEmpCode"]
        stale = []
        for code in pd.get("EmployeesCodes", []):
            ope = await db["OPE_data"].find_one({"employeeId": code})
            if has_pending_entry(ope):
                continue
            if rm in partners:
                st = await db["Status"].find_one({"employeeId": code}) or {}
                if any(p.get("overall_status") == "pending" and (p.get(p.get("current_level")) or {}).get("approver_code") == rm
                       for p in st.get("approval_status", [])):
                    continue
            stale.append(code)
        if stale:
            removals[rm] = stale
            backup.append({"ReportingEmpCode": rm, "EmployeesCodes": pd.get("EmployeesCodes", [])})
    for rm, codes in sorted(removals.items()):
        print(("remove " if apply else "would remove "), rm, codes)
    if apply and removals:
        name = f"repair_backup_pending_collection_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(name, "w", encoding="utf-8") as f:
            json.dump(backup, f, default=str, indent=1)
        for rm, codes in removals.items():
            await db["Pending"].update_one({"ReportingEmpCode": rm}, {"$pull": {"EmployeesCodes": {"$in": codes}}})
        print("backup:", name)
    print(f"{sum(map(len, removals.values()))} stale name(s) in {len(removals)} list(s)")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
