"""One-off: months of team managers who report to another manager (JHS1089, JHS490) were routed to the
partner as "Reporting_Manager" submissions, although their own reporting manager had already approved
every entry. Corrects the Status month (and the Pending lists) to match those approvals. Entries untouched.

    python repair_manager_submitter_months.py            # dry run
    python repair_manager_submitter_months.py --apply    # writes it (backup saved first)
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
TARGETS = [("JHS1089", "July 2026 - August 2026"), ("JHS490", "July 2026 - August 2026")]
HR = "JHS729"


async def main(apply: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URI"])[os.environ["MONGO_DB"]]
    backup = []
    for emp_code, month in TARGETS:
        emp = await db["Employee_details"].find_one({"EmpID": emp_code})
        st = await db["Status"].find_one({"employeeId": emp_code})
        i = next(k for k, p in enumerate(st["approval_status"]) if p["payroll_month"] == month)
        ps = st["approval_status"][i]
        ope = await db["OPE_data"].find_one({"employeeId": emp_code})
        rows = next(r for b in ope["Data"] for k, r in b.items() if k == month)
        rm = emp["ReportingEmpCode"].strip().upper()
        if not all(e.get("status") == "approved" and e.get("L1_approved") and e.get("L1_approver_code") == rm for e in rows):
            print("skip", emp_code, month, "- entries are not all approved by", rm)
            continue
        limit = float(emp.get("OPE Limit") or emp.get("OPE LIMIT") or 1500)
        total = sum(float(e["amount"]) for e in rows)
        levels = 3 if total > limit else 2
        now = datetime.utcnow().isoformat()
        l1 = dict(ps["L1"], status=True, approver_code=rm, approver_name=emp.get("ReportingEmpName", rm),
                  level_name="Reporting Manager", approved_date=ps["L1"].get("approved_date") or now,
                  approved_count=len(rows), pending_count=0)
        upd = {"submitter_type": "Employee", "ope_label": "Greater" if levels == 3 else "Less", "limit": limit,
               "total_levels": levels, "total_amount": total, "L1": l1, "current_level": "L2", "overall_status": "pending"}
        if levels == 3:
            upd["L2"] = {"status": False, "approver_name": emp.get("Partner", ""), "approver_code": emp["PartnerEmpCode"],
                         "approved_date": None, "level_name": "Partner", "approved_count": len(rows), "pending_count": len(rows), "rejected_count": 0}
            upd["L3"] = {"status": False, "approver_name": "HR", "approver_code": HR, "approved_date": None, "level_name": "HR"}
        else:
            upd["L2"] = {"status": False, "approver_name": "HR", "approver_code": HR, "approved_date": None, "level_name": "HR",
                         "approved_count": len(rows), "pending_count": len(rows), "rejected_count": 0}
        print(("apply  " if apply else "would  "), emp_code, month, f"total={total} limit={limit} -> {levels} levels, L1 {rm} approved, now L2",
              "(Partner " + emp["PartnerEmpCode"] + ")" if levels == 3 else "(HR)")
        backup.append({"employeeId": emp_code, "index": i, "approval_status_item": ps})
        if apply:
            await db["Status"].update_one({"_id": st["_id"]}, {"$set": {f"approval_status.{i}.{k}": v for k, v in upd.items()}})
            partner = emp["PartnerEmpCode"].strip().upper()
            if levels == 3:
                await db["Pending"].update_one({"ReportingEmpCode": partner}, {"$addToSet": {"EmployeesCodes": emp_code}}, upsert=True)
            else:
                await db["Pending"].update_one({"ReportingEmpCode": partner}, {"$pull": {"EmployeesCodes": emp_code}})
                await db["HR_Pending"].update_one({"HR_Code": HR}, {"$addToSet": {"EmployeesCodes": emp_code}}, upsert=True)
    if apply and backup:
        name = f"repair_backup_manager_submitter_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(name, "w", encoding="utf-8") as f:
            json.dump(backup, f, default=str, indent=1)
        print("backup:", name)


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
