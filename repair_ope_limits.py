"""Bring the OPE limit stored on payroll months in line with Employee_details.

Background: Employee_details keeps the limit in the field "OPE Limit", but the submit code only looked
at "OPE LIMIT", so every month was stored with the 1,500 default. This script corrects the months that
are still safe to change.

SAFE to change (only these are touched): the employee's own submission, still pending at the first
approval level with nothing approved or rejected yet, no fixed amount. For those the limit is set from
Employee_details and the approval chain is recomputed with the normal rule (total above the limit = 3
levels: Reporting Manager, Partner, HR; otherwise 2 levels: Reporting Manager, HR).

NOT touched (listed for review): months already approved/rejected, or already past the first level -
their history stays exactly as it happened.

    python repair_ope_limits.py            # dry run: shows what would change, writes nothing
    python repair_ope_limits.py --apply    # writes; first saves a backup file next to this script
"""
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

HR_CODE = "JHS729"


def master_limit(emp: dict):
    """Employee_details limit whichever way the column is spelled ('OPE Limit', 'OPE LIMIT', ...)."""
    for key in ("OPE LIMIT", "OPE Limit"):
        if emp.get(key) not in (None, ""):
            raw = emp[key]
            break
    else:
        raw = next((v for k, v in emp.items() if k.strip().lower().replace("_", " ") == "ope limit"), None)
    try:
        return float(str(raw).replace(",", "")) if raw not in (None, "") else None
    except ValueError:
        return None


def bucket(doc, month):
    for item in (doc or {}).get("Data", []):
        if month in item:
            return item[month]
    return []


def main() -> int:
    apply = "--apply" in sys.argv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    db = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=20000)[os.environ["MONGO_DB"]]

    employees = {e["EmpID"]: e for e in db["Employee_details"].find({})}
    changes, skipped = [], []
    for st in db["Status"].find({}):
        eid = st["employeeId"]
        emp = employees.get(eid)
        el = master_limit(emp) if emp else None
        if el is None:
            continue
        ope = db["OPE_data"].find_one({"employeeId": eid})
        rej = db["Reject_OPE_data"].find_one({"employeeId": eid})
        for i, ps in enumerate(st.get("approval_status", [])):
            if ps.get("submitter_type") != "Employee" or ps.get("fixed_amount"):
                continue
            try:
                stored = float(ps.get("limit") or 0)
            except (TypeError, ValueError):
                continue
            if stored == el:
                continue
            month = ps["payroll_month"]
            l1 = ps.get("L1") or {}
            entries = bucket(ope, month)
            untouched = (
                ps.get("current_level") == "L1" and ps.get("overall_status") == "pending"
                and not l1.get("status") and not l1.get("approved_count") and not l1.get("rejected_count")
                and entries and all((e.get("status") or "").lower() == "pending" and not e.get("L1_approved") for e in entries)
                and not bucket(rej, month)
            )
            row = {"employee": eid, "month": month, "stored_limit": stored, "master_limit": el,
                   "total": ps.get("total_amount"), "levels_now": ps.get("total_levels"),
                   "status": f'{ps.get("overall_status")}@{ps.get("current_level")}'}
            if not untouched:
                skipped.append(row)
                continue
            total = float(ps.get("total_amount") or 0)
            new_levels = 3 if total > el else 2
            row["levels_new"] = new_levels
            row["_index"] = i
            row["_before"] = json.loads(json.dumps(ps, default=str))
            changes.append(row)

    print(f"Employees read: {len(employees)}   months to correct: {len(changes)}   left as history / needs review: {len(skipped)}")
    for r in changes:
        print(f'  FIX  {r["employee"]:9} {r["month"]:30} limit {r["stored_limit"]:.0f} -> {r["master_limit"]:.0f}   '
              f'total {r["total"]}   levels {r["levels_now"]} -> {r["levels_new"]}')
    if skipped:
        print("Not changed (already decided or past level 1):")
        for r in skipped[:40]:
            print(f'  keep {r["employee"]:9} {r["month"]:30} stored {r["stored_limit"]:.0f} / master {r["master_limit"]:.0f}   {r["status"]}')
        if len(skipped) > 40:
            print(f"  ... and {len(skipped) - 40} more")
    if not apply:
        print("\nDRY RUN - nothing written. Run with --apply to save these changes.")
        return 0
    if not changes:
        print("Nothing to apply.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"repair_backup_{stamp}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in r.items() if k in ("employee", "month", "_before")} for r in changes], f, indent=1)
    print("Backup written:", backup)

    now = datetime.now(timezone.utc)
    for r in changes:
        eid, month, i, el, levels = r["employee"], r["month"], r["_index"], r["master_limit"], r["levels_new"]
        ps = r["_before"]
        emp = employees[eid]
        sets = {f"approval_status.{i}.limit": el,
                f"approval_status.{i}.ope_label": "Greater" if levels == 3 else "Less"}
        unsets = {}
        if levels != ps.get("total_levels"):
            sets[f"approval_status.{i}.total_levels"] = levels
            hr = {"status": False, "approver_name": "HR", "approver_code": HR_CODE, "approved_date": None, "level_name": "HR"}
            if levels == 2:
                sets[f"approval_status.{i}.L2"] = hr
                unsets[f"approval_status.{i}.L3"] = ""
            else:
                sets[f"approval_status.{i}.L2"] = {
                    "status": False, "approver_name": emp.get("Partner", ""),
                    "approver_code": str(emp.get("PartnerEmpCode") or "").strip().upper(),
                    "approved_date": None, "level_name": "Partner"}
                sets[f"approval_status.{i}.L3"] = hr
        update = {"$set": sets}
        if unsets:
            update["$unset"] = unsets
        res = db["Status"].update_one({"employeeId": eid, f"approval_status.{i}.payroll_month": month}, update)
        db["OPE_audit_log"].insert_one({
            "employeeId": eid, "payroll_month": month, "action": "limit_corrected", "stage": "System",
            "actor_id": "repair_ope_limits", "actor_name": "repair script", "actor_role": "System",
            "remark": f"OPE limit {r['stored_limit']:.0f} -> {el:.0f} from Employee Details; levels {r['levels_now']} -> {levels}",
            "at": now})
        print(f"  updated {eid} {month}: matched={res.matched_count} modified={res.modified_count}")
    print("Done. Restart is not required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
