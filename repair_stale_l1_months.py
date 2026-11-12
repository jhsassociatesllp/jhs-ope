"""One-off repair for Status months stuck at "L1 pending" although nothing is left for L1 to approve
(an entry was submitted on a finished month, reopening it at L1, then deleted again).
Such months leave the employee in the manager's Pending collection and the manager screen empty.

A month is touched only when Status says current_level L1 / overall pending / L1.status False
AND no OPE_data entry of that month has status "pending". Then:
  - no entries at all, none rejected  -> the Status month is removed
  - no entries at all, some rejected  -> Completed / "rejected"
  - entries still unsigned by HR      -> L1.status True, current_level L2 (waiting for HR), HR_Pending
  - every entry signed by HR          -> Completed / "approved"
The employee is then removed from the L1 approver's Pending list if no other L1-pending month remains.

    python repair_stale_l1_months.py                 # dry run
    python repair_stale_l1_months.py --apply         # writes it (backup saved first)

By default only the clear-cut "no entries left" cases (remove / mark_rejected) are repaired. The
"to_hr" / "complete" cases (entries already approved past the manager) are listed as REVIEW only;
add --include-hr-cases to repair them too.
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


def entries_of(doc, month):
    for block in (doc or {}).get("Data", []):
        if month in block:
            return block[month]
    return []


async def main(apply: bool, include_hr: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URI"])[os.environ["MONGO_DB"]]
    plans, backup = [], []
    async for st in db["Status"].find({}):
        emp = st["employeeId"]
        ope = rej = None
        for ps in st.get("approval_status", []):
            if not (ps.get("current_level") == "L1" and ps.get("overall_status") == "pending"
                    and not (ps.get("L1") or {}).get("status")):
                continue
            if ope is None:
                ope = await db["OPE_data"].find_one({"employeeId": emp}) or {}
                rej = await db["Reject_OPE_data"].find_one({"employeeId": emp}) or {}
            month = ps.get("payroll_month")
            rows = entries_of(ope, month)
            if any((e.get("status") or "").lower() == "pending" for e in rows):
                continue  # genuinely waiting for the manager
            if not rows:
                action = "mark_rejected" if entries_of(rej, month) else "remove"
            elif all(e.get("hr_approved") for e in rows):
                action = "complete"
            else:
                action = "to_hr"
            plans.append((st["_id"], emp, month, action, (ps.get("L1") or {}).get("approver_code"), len(rows)))
            backup.append({"employeeId": emp, "approval_status_item": ps})
    skipped = [p for p in plans if p[3] in ("to_hr", "complete") and not include_hr]
    plans = [p for p in plans if p not in skipped]
    backup = [b for b in backup if any(b["employeeId"] == p[1] and b["approval_status_item"].get("payroll_month") == p[2] for p in plans)]
    for _, emp, month, action, _, n in plans:
        print(("apply  " if apply else "would  "), f"{emp:9} {month:32} entries={n:<3} -> {action}")
    for _, emp, month, action, _, n in skipped:
        print("REVIEW ", f"{emp:9} {month:32} entries={n:<3} -> {action} (not changed)")
    if apply and plans:
        name = f"repair_backup_stale_l1_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(name, "w", encoding="utf-8") as f:
            json.dump(backup, f, default=str, indent=1)
        print("backup:", name)
        for _id, emp, month, action, l1code, _ in plans:
            if action == "remove":
                await db["Status"].update_one({"_id": _id}, {"$pull": {"approval_status": {"payroll_month": month}}})
                continue
            st = await db["Status"].find_one({"_id": _id})
            i = next(k for k, p in enumerate(st["approval_status"]) if p.get("payroll_month") == month)
            if action == "mark_rejected":
                upd = {"current_level": "Completed", "overall_status": "rejected"}
            elif action == "complete":
                upd = {"current_level": "Completed", "overall_status": "approved", "L1.status": True, "L2.status": True}
            else:
                upd = {"current_level": "L2", "L1.status": True}
            await db["Status"].update_one({"_id": _id}, {"$set": {f"approval_status.{i}.{k}": v for k, v in upd.items()}})
            if action == "to_hr":
                await db["HR_Pending"].update_one({"HR_Code": "JHS729"}, {"$addToSet": {"EmployeesCodes": emp}}, upsert=True)
        for emp, l1code in {(p[1], p[4]) for p in plans if p[4]}:
            st = await db["Status"].find_one({"employeeId": emp}) or {}
            still = any(p.get("current_level") == "L1" and p.get("overall_status") == "pending"
                        for p in st.get("approval_status", []))
            if not still:
                await db["Pending"].update_one({"ReportingEmpCode": l1code}, {"$pull": {"EmployeesCodes": emp}})
    print(f"{len(plans)} month(s) {'repaired' if apply else 'need repair'}")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv, "--include-hr-cases" in sys.argv))
