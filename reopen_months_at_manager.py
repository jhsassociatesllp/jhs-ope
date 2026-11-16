"""Send chosen (employee, month) pairs back to the reporting manager's Pending for a fresh approval.

Entries -> status "pending" (manager / partner / HR approval fields cleared); Status month -> L1 pending
at the employee's manager (L1/L2/L3 flags cleared, counts reset); the employee is added to the manager's
Pending list and dropped from the partner / HR lists if no other month of theirs still waits there.

    python reopen_months_at_manager.py            # dry run
    python reopen_months_at_manager.py --apply    # writes it (backup saved first)
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
TARGETS = [("JHS1089", "July 2026 - August 2026"), ("JHS1316", "August 2026 - September 2026"),
           ("JHS413", "September 2026 - October 2026")]
CLEAR = ["approved_by", "approved_date", "approver_name", "approval_remark", "L1_approved", "L1_approver_code",
         "L1_approver_name", "L2_approved", "L2_approver_code", "L2_approver_name", "partner_approved",
         "partner_approved_by", "partner_approved_date", "partner_name", "hr_approved", "hr_approved_by",
         "hr_approved_date"]


async def main(apply: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URI"])[os.environ["MONGO_DB"]]
    backup = []
    for code, month in TARGETS:
        emp = await db["Employee_details"].find_one({"EmpID": code})
        rm = emp["ReportingEmpCode"].strip().upper()
        ope = await db["OPE_data"].find_one({"employeeId": code})
        bi = next(i for i, b in enumerate(ope["Data"]) if month in b)
        rows = ope["Data"][bi][month]
        st = await db["Status"].find_one({"employeeId": code})
        si = next(i for i, p in enumerate(st["approval_status"]) if p["payroll_month"] == month)
        ps = st["approval_status"][si]
        print(("apply  " if apply else "would  "), code, month, f"{len(rows)} entries -> pending at {rm} (was {ps['current_level']}, {ps['total_levels']} levels)")
        backup.append({"employeeId": code, "month": month, "block": bi, "entries": rows, "status_index": si, "status_item": ps})
        if not apply:
            continue
        sets = {f"Data.{bi}.{month}.{j}.status": "pending" for j in range(len(rows))}
        unsets = {f"Data.{bi}.{month}.{j}.{k}": "" for j in range(len(rows)) for k in CLEAR}
        await db["OPE_data"].update_one({"_id": ope["_id"]}, {"$set": sets, "$unset": unsets})
        p = f"approval_status.{si}"
        upd = {f"{p}.current_level": "L1", f"{p}.overall_status": "pending", f"{p}.L1.status": False,
               f"{p}.L1.approved_date": None, f"{p}.L1.approved_count": 0, f"{p}.L1.pending_count": len(rows),
               f"{p}.L1.rejected_count": 0, f"{p}.L2.status": False, f"{p}.L2.approved_date": None}
        if "L3" in ps:
            upd[f"{p}.L3.status"] = False
            upd[f"{p}.L3.approved_date"] = None
        await db["Status"].update_one({"_id": st["_id"]}, {"$set": upd})
        await db["Pending"].update_one({"ReportingEmpCode": rm}, {"$addToSet": {"EmployeesCodes": code}}, upsert=True)
        st = await db["Status"].find_one({"_id": st["_id"]})
        at = lambda a: any(q.get("overall_status") == "pending" and (q.get(q.get("current_level")) or {}).get("approver_code") == a
                           and q.get("current_level") != "L1" for q in st["approval_status"])
        partner = emp["PartnerEmpCode"].strip().upper()
        if not at(partner):
            await db["Pending"].update_one({"ReportingEmpCode": partner}, {"$pull": {"EmployeesCodes": code}})
        if not at("JHS729"):
            await db["HR_Pending"].update_one({"HR_Code": "JHS729"}, {"$pull": {"EmployeesCodes": code}})
    if apply:
        name = f"repair_backup_reopen_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(name, "w", encoding="utf-8") as f:
            json.dump(backup, f, default=str, indent=1)
        print("backup:", name)


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
