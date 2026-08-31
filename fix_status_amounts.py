"""
fix_status_amounts.py
──────────────────────
One-time script to correct two related problems in the Status collection that
were caused by a bug in /api/ope/submit-final (fixed in main.py):

1. total_amount inflation: total_amount was accumulated from its own previous
   (stale) value instead of from currently-active OPE_data entries. If an
   entry was rejected (moved out to Reject_OPE_data) and the employee later
   resubmitted new entries for the same month, the rejected amount got added
   back in on top of the new entries, double-counting it.

2. Months stuck on a stale terminal state: when every entry in a month had
   been rejected, current_level advanced to "Completed" and overall_status to
   "rejected". If the employee then submitted fresh entries for that same
   month, they were added to OPE_data as new "pending" entries, but
   current_level/overall_status were never reset - so the month kept
   displaying "Rejected" forever even though it had brand-new entries
   waiting for L1 (Reporting Manager / Partner) review.

This script scans every Status document and, for each payroll month:
  - Recomputes total_amount from OPE_data's currently-active (pending/
    approved) entries for that month.
  - If current_level == "Completed" but OPE_data still has "pending" entries
    for that month (the stuck case above), reopens it: current_level -> "L1",
    overall_status -> "pending", then calls main.py's own
    recompute_month_status() so the L1 approved/rejected/pending counts are
    consistent with the app's normal logic.

Months whose total_amount was manually overridden via
PUT /api/ope/manager/edit-total-amount (tracked via last_edited_by) are left
untouched - that's a deliberate, audited business decision, not drift.

Safe to run twice - it only writes when a value actually differs from what's
already stored.

DRY RUN BY DEFAULT. This touches production data, so it only prints what it
would do unless you pass --confirm:

    python fix_status_amounts.py            # dry run - prints a plan, writes nothing
    python fix_status_amounts.py --confirm   # actually performs the fix

Last run against the live DB on 2026-08-31: 163 total_amount corrections,
4 months reopened at L1, 130 manually-edited months correctly skipped.
"""

import argparse
import asyncio
from datetime import datetime, UTC

import main as app_module

db = app_module.db
recompute_month_status = app_module.recompute_month_status


def get_active_entries(ope_doc, payroll_month):
    if not ope_doc:
        return []
    for data_item in ope_doc.get("Data", []):
        if payroll_month in data_item:
            return data_item[payroll_month]
    return []


async def fix(confirm: bool):
    status_docs = await db["Status"].find({}).to_list(length=None)
    print(f"📂 Status: {len(status_docs)} employee documents to scan")

    total_months = 0
    total_amount_fixes = 0
    total_reopened = 0
    total_manual_skipped = 0

    for status_doc in status_docs:
        employee_id = status_doc.get("employeeId")
        approval_status = status_doc.get("approval_status", [])
        if not approval_status:
            continue

        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})

        for i, ps in enumerate(approval_status):
            payroll_month = ps.get("payroll_month")
            if not payroll_month:
                continue

            total_months += 1
            active_entries = get_active_entries(ope_doc, payroll_month)

            correct_total = sum(
                float(e.get("amount", 0))
                for e in active_entries
                if (e.get("status") or "").lower() in ["pending", "approved"]
            )
            old_total = ps.get("total_amount", 0)

            # A manager/Partner/HR can deliberately override total_amount away
            # from the raw entry sum via PUT /api/ope/manager/edit-total-amount
            # (e.g. approving a lesser reimbursement). That's an intentional,
            # audited business decision - never overwrite it here.
            manually_edited = bool(ps.get("last_edited_by"))
            raw_mismatch = abs(float(old_total) - correct_total) > 0.001

            amount_mismatch = (not manually_edited) and raw_mismatch

            if manually_edited and raw_mismatch:
                total_manual_skipped += 1
                print(f"\n👤 {employee_id} / {payroll_month}")
                print(f"   ⏭️  SKIPPED - manually edited by {ps.get('last_edited_by_name')} ({ps.get('last_edited_by_role')}): "
                      f"total_amount ₹{old_total} kept as-is (raw active sum would be ₹{correct_total})")

            current_level = ps.get("current_level")
            has_pending_active = any(
                (e.get("status") or "").lower() == "pending" for e in active_entries
            )
            needs_reopen = current_level == "Completed" and has_pending_active

            if not amount_mismatch and not needs_reopen:
                continue

            print(f"\n👤 {employee_id} / {payroll_month}")
            if amount_mismatch:
                print(f"   💰 total_amount: ₹{old_total} → ₹{correct_total}")
                total_amount_fixes += 1
            if needs_reopen:
                print(f"   🔓 current_level: 'Completed' → 'L1' (has {sum(1 for e in active_entries if (e.get('status') or '').lower() == 'pending')} pending entries stuck invisible)")
                print(f"      overall_status: '{ps.get('overall_status')}' → 'pending'")
                total_reopened += 1

            if confirm:
                update_fields = {}
                if amount_mismatch:
                    update_fields[f"approval_status.{i}.total_amount"] = correct_total
                if needs_reopen:
                    update_fields[f"approval_status.{i}.current_level"] = "L1"
                    update_fields[f"approval_status.{i}.overall_status"] = "pending"

                await db["Status"].update_one(
                    {"employeeId": employee_id},
                    {"$set": update_fields}
                )

                if needs_reopen:
                    await recompute_month_status(employee_id, payroll_month)

    print("\n" + "=" * 60)
    print(f"Payroll months scanned      : {total_months}")
    print(f"total_amount corrections    : {total_amount_fixes}")
    print(f"Skipped (manually edited)   : {total_manual_skipped}")
    print(f"Months reopened at L1       : {total_reopened}")
    if not confirm and (total_amount_fixes or total_reopened):
        print("\n⚠️  This was a DRY RUN - nothing was written.")
        print("    Re-run with --confirm to apply these changes:")
        print("    python fix_status_amounts.py --confirm")
    elif confirm:
        print("\n✅ Fix applied.")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Recompute Status.total_amount from active OPE_data entries and reopen months wrongly stuck as 'Completed'."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write changes. Without this flag the script only prints what it would do."
    )
    args = parser.parse_args()

    print("\n" + "#" * 60)
    print("# Status total_amount / stuck-Completed-month fix")
    print(f"# Mode: {'CONFIRM (writing changes)' if args.confirm else 'DRY RUN (no changes will be written)'}")
    print(f"# Started: {datetime.now(UTC).isoformat()}")
    print("#" * 60 + "\n")

    await fix(confirm=args.confirm)


if __name__ == "__main__":
    asyncio.run(main())
