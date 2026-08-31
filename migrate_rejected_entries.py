"""
migrate_rejected_entries.py
────────────────────────────
One-time script to move every entry currently sitting in OPE_data with
status == "rejected" out into the new Reject_OPE_data collection (same
document / Data[] bucket shape as OPE_data), and remove it from OPE_data.

This mirrors what the new move_entries_to_rejected() helper in main.py does
for entries rejected going forward - this script is for entries that were
already rejected (in place, inside OPE_data) BEFORE that change shipped.

Safe to run twice: an entry whose _id is already present in Reject_OPE_data
for that employee is skipped, never duplicated.

DRY RUN BY DEFAULT. This touches production data, so it only prints what it
would do unless you pass --confirm:

    pip install motor pymongo python-dotenv
    python migrate_rejected_entries.py            # dry run - prints a plan, writes nothing
    python migrate_rejected_entries.py --confirm   # actually performs the migration
"""

import argparse
import asyncio
import os
from datetime import datetime, UTC

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

if not MONGO_URI or not MONGO_DB:
    raise ValueError("Missing MongoDB configuration (MONGO_URI / MONGO_DB)")


async def already_in_reject(reject_collection, employee_id: str, entry_id) -> bool:
    """True if this entry_id is already present anywhere in the employee's
    Reject_OPE_data.Data[] buckets (keeps the script idempotent)."""
    reject_doc = await reject_collection.find_one({"employeeId": employee_id})
    if not reject_doc:
        return False
    for data_item in reject_doc.get("Data", []):
        for month_range, entries in data_item.items():
            for entry in entries:
                if str(entry.get("_id")) == str(entry_id):
                    return True
    return False


async def append_to_reject_bucket(db, employee_id: str, month_range: str, entry: dict, source_doc: dict):
    """Upsert one entry into Reject_OPE_data.Data[*][month_range] for
    employee_id, mirroring the bucket-building pattern OPE_data itself uses."""
    reject_collection = db["Reject_OPE_data"]
    reject_doc = await reject_collection.find_one({"employeeId": employee_id})

    if not reject_doc:
        new_doc = {
            "employeeId": employee_id,
            "employeeName": source_doc.get("employeeName", ""),
            "designation": source_doc.get("designation", ""),
            "gender": source_doc.get("gender", ""),
            "partner": source_doc.get("partner", ""),
            "reportingManager": source_doc.get("reportingManager", ""),
            "department": source_doc.get("department", ""),
            "Data": [
                {month_range: [entry]}
            ]
        }
        await reject_collection.insert_one(new_doc)
        return

    reject_data_array = reject_doc.get("Data", [])
    month_exists = False
    for i, data_item in enumerate(reject_data_array):
        if month_range in data_item:
            await reject_collection.update_one(
                {"employeeId": employee_id},
                {"$push": {f"Data.{i}.{month_range}": entry}}
            )
            month_exists = True
            break

    if not month_exists:
        await reject_collection.update_one(
            {"employeeId": employee_id},
            {"$push": {"Data": {month_range: [entry]}}}
        )


async def migrate(db, confirm: bool):
    ope_collection = db["OPE_data"]
    reject_collection = db["Reject_OPE_data"]

    docs = await ope_collection.find({}).to_list(length=None)
    print(f"📂 OPE_data: {len(docs)} employee documents to scan")

    total_found = 0
    total_migrated = 0
    total_skipped_duplicate = 0

    for doc in docs:
        employee_id = doc.get("employeeId", str(doc["_id"]))
        data_array = doc.get("Data", [])

        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                rejected_entries = [e for e in entries if (e.get("status") or "").lower() == "rejected"]

                if not rejected_entries:
                    continue

                for entry in rejected_entries:
                    entry_id = entry.get("_id")
                    total_found += 1

                    if await already_in_reject(reject_collection, employee_id, entry_id):
                        total_skipped_duplicate += 1
                        print(f"  ⏭️  {employee_id} / {month_range} / {entry_id} - already in Reject_OPE_data, skipping")
                        continue

                    print(f"  ❌ {employee_id} / {month_range} / {entry_id} - "
                          f"rejected_by={entry.get('rejected_by')} reason={entry.get('rejection_reason')!r}")

                    if confirm:
                        await append_to_reject_bucket(db, employee_id, month_range, entry, doc)
                        await ope_collection.update_one(
                            {"employeeId": employee_id},
                            {"$pull": {f"Data.{i}.{month_range}": {"_id": entry_id}}}
                        )
                        total_migrated += 1

        if confirm:
            # Clean up any month buckets that are now empty, and drop them
            # from Data[] entirely (consistent with the delete-entry cleanup
            # convention already used elsewhere in the app)
            refreshed = await ope_collection.find_one({"employeeId": employee_id})
            if refreshed:
                cleaned = False
                new_data_array = []
                for data_item in refreshed.get("Data", []):
                    keep_item = {}
                    for month_range, entries in data_item.items():
                        if entries:
                            keep_item[month_range] = entries
                        else:
                            cleaned = True
                    if keep_item:
                        new_data_array.append(keep_item)
                if cleaned:
                    await ope_collection.update_one(
                        {"employeeId": employee_id},
                        {"$set": {"Data": new_data_array}}
                    )
                    print(f"  🧹 {employee_id}: removed emptied month bucket(s)")

    print("\n" + "=" * 60)
    print(f"Rejected entries found      : {total_found}")
    print(f"Already migrated (skipped)  : {total_skipped_duplicate}")
    if confirm:
        print(f"Migrated this run           : {total_migrated}")
    else:
        print(f"Would migrate (dry run)     : {total_found - total_skipped_duplicate}")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Move status=='rejected' entries from OPE_data into Reject_OPE_data."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write changes. Without this flag the script only prints what it would do."
    )
    args = parser.parse_args()

    print("\n" + "#" * 60)
    print("# OPE Rejected-Entries Migration (OPE_data -> Reject_OPE_data)")
    print(f"# Mode: {'CONFIRM (writing changes)' if args.confirm else 'DRY RUN (no changes will be written)'}")
    print(f"# Started: {datetime.now(UTC).isoformat()}")
    print("#" * 60 + "\n")

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    try:
        await migrate(db, confirm=args.confirm)

        if not args.confirm:
            print("\n⚠️  This was a DRY RUN - nothing was written.")
            print("    Review the plan above, then re-run with --confirm to apply it:")
            print("    python migrate_rejected_entries.py --confirm")
        else:
            print(f"\n✅ Migration complete: {datetime.now(UTC).isoformat()}")

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
