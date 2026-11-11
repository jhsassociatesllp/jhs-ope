"""One-off repair: months reopened at L1 (new entries submitted after the month had finished)
still show L1 / L2 as approved in Status.approval_status.

Only months with current_level == "L1", overall_status == "pending" and at least one entry still
pending are touched; only L1.status / L2.status are set to False. Entries are never changed.

    python repair_status_levels.py            # dry run: lists what would change
    python repair_status_levels.py --apply    # writes it (backup saved first)
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def main(apply: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URI"])[os.environ["MONGO_DB"]]
    pending = set()
    async for doc in db["OPE_data"].find({}, {"employeeId": 1, "Data": 1}):
        for block in doc.get("Data", []):
            for month, rows in block.items():
                if any((e.get("status") or "").lower() == "pending" for e in rows):
                    pending.add((doc["employeeId"], month))
    fixes, backup = [], []
    async for st in db["Status"].find({}):
        for i, ps in enumerate(st.get("approval_status", [])):
            key = (st["employeeId"], ps.get("payroll_month"))
            stale = [lv for lv in ("L1", "L2") if (ps.get(lv) or {}).get("status") is True]
            if ps.get("current_level") == "L1" and ps.get("overall_status") == "pending" and stale and key in pending:
                fixes.append((st["_id"], i, key, stale))
                backup.append({"employeeId": key[0], "payroll_month": key[1], "L1": ps.get("L1"), "L2": ps.get("L2")})
    for _id, i, key, stale in fixes:
        print(("fix " if apply else "would fix "), key, "->", ", ".join(f"{lv}.status=False" for lv in stale))
    if apply and fixes:
        name = f"repair_backup_status_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(name, "w", encoding="utf-8") as f:
            json.dump(backup, f, default=str, indent=1)
        for _id, i, key, stale in fixes:
            await db["Status"].update_one({"_id": _id}, {"$set": {f"approval_status.{i}.{lv}.status": False for lv in stale}})
        print("backup:", name)
    print(f"{len(fixes)} month(s) {'repaired' if apply else 'need repair'}")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
