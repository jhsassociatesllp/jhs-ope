# OPE Application — Testing Guide for the New Approval Workflow

This guide covers the features added in this update:

1. Remarks/rejection reasons visible to the employee for every approval level, including a new "Partially Approved" state.
2. Rejected OPE data is now physically moved to its own collection (`Reject_OPE_data`) so a resubmission for the same month never merges with old rejected data.
3. Reporting Managers (RM), Partners, and HR can now approve or reject **individual entries** or **a single month**, not just "Approve All / Reject All" for an employee.
4. Pending / Approved / Rejected count tiles on the RM/Partner/HR dashboard.
5. Employee History now includes rejected entries (with the rejection reason, who rejected it, and the PDF).
6. Informational "Submit by" / "Approve by" deadline banners (nothing is blocked by these — display only).

**Before you start:** confirm which MongoDB database your `.env` points at (`MONGO_DB`). If it's your production database, do these tests with a **throwaway test employee code** you can clean up afterward, not with real employee data — several of the actions below (reject, delete) are destructive to the test data they touch.

---

## 0. One-time setup: migrate existing rejected entries

Before this update, a rejected entry stayed inside `OPE_data` with `status: "rejected"`. Going forward, rejections physically move to a new `Reject_OPE_data` collection. Any entries that were already rejected *before* this update need to be moved once so they still show up correctly in the "Rejected" views and employee History.

```bash
pip install motor python-dotenv
python migrate_rejected_entries.py
```

This is a **dry run by default** — it only prints what it would move, it writes nothing. Review the printed list, then actually apply it:

```bash
python migrate_rejected_entries.py --confirm
```

It's safe to run more than once (already-migrated entries are skipped, not duplicated).

---

## 1. Start the app

```bash
uvicorn main:app --reload
```

Open the portal (`index.html`) in a browser for each role you're testing (employee, RM, Partner, HR) — you can use separate browser profiles/incognito windows to be logged in as multiple roles at once, which makes the approval-chain tests much easier to follow.

---

## 2. Employee: submit OPE entries

1. Log in as a test employee.
2. Go to **OPE** → note the new **"Submit by"** banner near the month selector (informational date reminder — confirm it shows a date, nothing should be blocked by it).
3. Add 4–6 entries for one payroll period (e.g. "May 2026 - June 2026"), mixing amounts so the total crosses your `Employee_details."OPE LIMIT"` if you want to exercise the 3-level (RM → Partner → HR) path, or stays under it for the 2-level (RM → HR) path.
4. Click **Save Entry** for each, then **Submit All Entries**.
5. Go to **Status** — you should see the new submission with an "Approval Tracker" showing L1 (Reporting Manager) as the active step.

---

## 3. RM: granular approve/reject

Log in as the employee's RM.

1. Go to **Pending** — confirm the new **Pending / Approved / Rejected** stat tiles appear at the top and the **"Approve by"** banner shows a date.
2. Open the pending employee's row to see their entries grouped by month.
3. **Per-entry test:** click the new per-entry Approve button on one entry, and the per-entry Reject button on a different entry (enter a reason when prompted). Confirm:
   - The approved entry disappears from Pending and shows as approved.
   - The rejected entry disappears from Pending and OPE_data (check via the Rejected tab, or the employee's Status tab).
4. **Per-month test:** for a *different* month (submit a second period as the employee first if needed), use the month-level **"Approve Month"** / **"Reject Month"** buttons instead of per-entry ones. Confirm the whole month moves as a unit and any *other* pending month for the same employee is unaffected (this is the "approve June-July but reject May-June" scenario from the requirements).
5. **Bulk test:** confirm the original **Approve All / Reject All** buttons on the employee's row still work as before, for a third month/employee.
6. Check the **Dashboard tiles** update correctly after each action (pending count decreases, approved/rejected increase).

---

## 4. Employee: verify status, remarks, and rejection are visible

Log back in as the employee.

1. Go to **Status**. For the month(s) touched above, confirm:
   - The approved level shows the RM's **approval remark** (not just a checkmark — this is new).
   - The rejected entry's month shows a clear **Rejected** state with the RM's **rejection reason** and name.
   - If a month had a mix of approved-and-forwarded plus rejected entries, confirm it shows the new **"Partial"** status (not plainly "Pending" or "Approved"), with counts like "3 Approved · 2 Rejected".
2. Go to **History**. Confirm the rejected entry now appears here too (previously it would only show if it stayed in `OPE_data` — now it's fetched from the new collection), tagged as rejected, with its reason and its PDF still viewable.
3. **Resubmission test (core requirement):** for the month that had a rejected entry, add and submit a *new* entry for the same month. Confirm:
   - The new entry does **not** get merged with the old rejected one — it starts a clean pending cycle.
   - The old rejected entry is still visible in History (audit trail preserved) but does not affect the new submission's amount/status.

---

## 5. Partner flow (only if the test submission was 3-level / over the OPE limit)

Repeat the RM steps as the Partner:

1. **Pending** tab shows the entries RM forwarded, with the new dashboard tiles.
2. Test per-entry approve, per-entry reject, per-month approve, per-month reject, and the original bulk Approve All/Reject All.
3. Confirm approved entries route to **HR's Pending** afterward, and this happens correctly even if the employee has another, unrelated month still pending at this same Partner (this is the specific bug this update fixed — routing must not get stuck behind unrelated months).

---

## 6. HR flow

Log in as HR (`JHS729`).

1. Confirm entries approved by the Partner (or RM directly, for 2-level submissions) appear in HR's **Pending**, with dashboard tiles.
2. Test per-entry approve/reject, per-month approve/reject (new — HR did not have these before), and bulk Approve All/Reject All.
3. Confirm HR approval is terminal — after HR approves everything in a month, the employee's Status tab shows it fully "Completed"/"Approved".

---

## 7. Regression checks (confirm nothing existing broke)

- [ ] Login/logout and role detection (RM/Partner/HR/plain employee nav visibility) still work.
- [ ] Save / Update / Delete a **draft** entry (before submission) still works.
- [ ] PDF upload on a new entry, and PDF viewing from Pending/Approved/Rejected/History, still works.
- [ ] Deleting a still-**pending** submitted entry as the employee still works, and correctly clears it from the RM's pending count.
- [ ] The Admin Control Panel (`admin.html`) dashboard/charts still load — this update intentionally did not touch that page.
- [ ] Existing month-range dropdown options are unaffected (this update did not change how month ranges are added each payroll cycle).

---

## 8. Known, intentionally out-of-scope items

These were found during review but are **not** part of this update — flagging them so they don't get mistaken for new bugs:

- The legacy `/api/ope/submit` endpoint and a second, unreachable copy of the delete endpoint near the end of `main.py` are pre-existing, unrelated issues in the codebase that this update deliberately left untouched.

Two smaller items originally deferred here (`edit-amount` not reaching rejected entries, and the dashboard-summary endpoints doing full collection scans) have since been fixed as a follow-up pass — `edit-amount` now searches `Reject_OPE_data` as a fallback, and all three dashboard-summary endpoints now compute their counts with a MongoDB aggregation / batched queries instead of pulling entire collections into Python.
