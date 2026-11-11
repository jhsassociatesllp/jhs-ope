# OPE Portal — User & Testing Guide

For: **Employee · Reporting Manager · Partner · HR · Admin**
Covers everything in the current release, including the features added in this update.

---

## 0. What is new in this release

| Area | What changed |
|---|---|
| **One submission per month** | After you submit a payroll month you cannot submit it again. Only HR (or an Admin) can allow **one** employee to resubmit **one** month, once. |
| **Monthly eligibility & limits** | Admin uploads an Excel file per payroll month. It decides who may submit, each person's OPE limit for that month, and any **fixed OPE amount**. |
| **Fixed-amount employees** | They do not fill the form. Their fixed amount goes straight to HR to approve or reject. |
| **Amounts at every stage** | Every submission shows: original amount submitted, amount approved by Reporting Manager, by Partner, by HR. The original amount is never overwritten. |
| **Full history in IST** | Every submit / approve / reject / reopen is recorded and shown in Indian Standard Time (e.g. `18 Oct 2026, 03:45 PM IST`). |
| **Details in Pending / Approved / Rejected / Status** | A new **Amounts & Timeline** button opens the full record. |
| **HR Report** | HR can pick a month, see counts and amounts on screen, and download the same data as Excel. |
| **Security** | Managers/Partners can act only on their own reportees; approved entries can no longer be edited or deleted by the employee; registration only for known employees; login throttling; debug endpoints are admin-only. |

> **Not in this release:** e-mail notifications (skipped by decision). Approval e-mails are not sent.

---

## 1. Signing in

1. Open the portal URL → **Register** (first time only) with your **Employee Code** and a password. Your code must exist in Employee Details, otherwise registration is refused — contact HR.
2. **Login** with the same code and password.
3. After 8 wrong passwords in 10 minutes the code is locked for the rest of that window (“Too many failed login attempts”). Wait and retry.
4. The sidebar shows only what your role allows:

| Role | Sidebar |
|---|---|
| Employee | OPE · History · Status |
| Reporting Manager / Partner | + Pending · Approve · Reject |
| HR | + HR Report · Resubmission |
| Admin | HR Report · Resubmission in the portal, plus the **Admin Panel** (button “Switch to Control Panel” on the OPE page) |

Roles are decided by the server, not by the screen. Hiding or showing a button is only convenience.

---

## 2. Employee

### 2.1 Submit OPE for a month
1. **OPE** → pick the **Month Range**.
2. A banner may appear above the form:
   * *“Your OPE limit for … is ₹X (set by HR for this month)”* — the limit that applies to that month.
   * *“You are not in the eligible employee list for …”* — you cannot submit that month. Contact HR.
   * *“Your OPE amount for … is fixed at ₹X by HR”* — you do **not** fill the form. HR reviews it for you.
   * *“OPE for … has already been submitted. You cannot submit again. Please contact HR if you need to resubmit.”* — month is locked.
3. Fill the entries → **Save Entry** for each → **Submit All Entries** → confirm.
4. If the total is within your limit: 2-level approval (Reporting Manager → HR). Above the limit: 3 levels (Reporting Manager → Partner → HR). *(Unchanged.)*

### 2.2 Check your status
**Status** shows every month you submitted: total, overall status, the L1/L2/L3 tracker, and **the OPE limit for that month**.
Click **Amounts & timeline** on a month to see:
* **Original amount submitted by you** and **current total** (after any reviewer edit)
* For each stage: *Approved / Rejected / Pending / Not reached*, **the amount approved at that stage** (shows *Not reviewed yet* until that stage decides — never a fake ₹0), reviewer remark / rejection reason, who and when (IST)
* Every expense entry, with its own status and ticket PDF
* The full history, oldest first (including “approved, then later rejected”)
* Whether **resubmission is locked or allowed**. If locked: *contact HR*.

### 2.3 Need to resubmit?
You cannot do it yourself. Ask HR. When HR allows it you will see a green banner on the OPE form for that month: *“HR has allowed you to resubmit … You can submit once more.”* It works **once**, for that month only. Your earlier entries and history stay.

### 2.4 Things you can no longer do
* Edit or delete an entry that a reviewer has already **approved** (“Contact HR”).
* View another employee’s data.

### 2.5 Restricted employees
If you are on HR’s restricted list you can still log in and view everything, but you **cannot fill, edit or submit** your own OPE (a banner explains this). For every payroll month a record is created for you automatically and the **Status** page shows **PENDING HR APPROVAL**; when HR approves it, it changes to **APPROVED**.
HR: those records are in **Pending**; approve them like any other. They appear in the HR Report only after approval.
Admin: manage the list with `python seed_restricted_employees.py` or the API `GET/POST /api/admin/restricted-employees`.

---

## 3. Reporting Manager

Only employees **assigned to you** appear; actions on anyone else are refused (403).

1. **Pending** → click an employee → their entries are grouped by month.
2. Per entry: approve / reject. Per month: **Approve Month / Reject Month**. All-in-one: **Approve / Reject** on the employee row. A reason is requested on reject. *(Unchanged.)*
3. **Edit Total / edit entry amount**: allowed as before, for your own reportees only. The employee’s **original amount is preserved** and the edit is logged.
4. **Amounts & Timeline** (month header) shows original vs. approved amounts and the full IST history.
5. **Approve** and **Reject** tabs list what you decided; the same **Amounts & Timeline** button is on each month there.

What you cannot do: see HR Report, Resubmission, uploads, or act on employees outside your team.

---

## 4. Partner

Same screens as the Reporting Manager, for employees whose partner you are (3-level cases, and Reporting Managers’ own submissions). Your approved amount is recorded separately from the Reporting Manager’s.
You cannot access uploads, the HR report or resubmission permissions.

---

## 5. HR (JHS729)

### 5.1 Approve / reject (existing stage)
**Pending** shows employees waiting for HR (including **fixed-amount** employees). Approve/Reject works as before; HR’s approved amount and remark are recorded.

### 5.2 HR Report (new)
**HR Report** in the sidebar:
1. Choose the **payroll month**.
2. Cards: Total records · Approved · Pending · Rejected · Partially approved · Submitted amount · HR approved amount (and, when an upload is active: Eligible employees / Eligible but not submitted).
3. Filter chips (All / Pending / Approved / Rejected / Partial) and search by name or ID. Click a row for the full details.
4. **Download Excel** — a *Summary* sheet and a *Records* sheet (employee, limit, submitted, Reporting Manager / Partner / HR approved, status, stage, IST timestamps, remarks). The file is generated by the server from the same data as the screen, so counts and amounts match.

Counting rule: each employee-month is counted **once, by its current status**. Status changes are kept in the audit history, not counted twice.

### 5.3 Allow an employee to resubmit (new)
**Resubmission** in the sidebar:
1. Enter the **Employee ID** → **Find employee**. Their submitted months are listed.
2. **Allow resubmission** next to the month → type a **reason** → **Allow once**.
3. The employee can now submit that month one more time. Every other month and every other employee stays locked.
4. Changed your mind? **Revoke** on the same row (reason required). Used and revoked permissions stay in **Permission history**.

Permissions have no automatic expiry; HR revokes them.

---

## 6. Admin

Admins have all HR screens plus the **Admin Panel** (“Switch to Control Panel”).

### 6.1 Monthly Uploads (new) — Admin Panel → *Monthly Uploads*
File format (the same columns as Employee Details):

| Column | Required | Notes |
|---|---|---|
| `EmpID` | Yes | Must exist in Employee Details |
| `Emp Name` | No | A different spelling only gives a warning |
| `OPE LIMIT` | Yes | Number ≥ 0 |
| `Fixed OPE Amount` | No | If filled (> 0), that employee cannot use the form for the month; the amount goes to HR |

`.xlsx` or `.csv`, up to 5 MB.

1. Choose the **starting month** and **year** (the screen shows the payroll month it applies to, e.g. *September 2026 – October 2026*).
2. Choose the file → **Validate & upload**.
3. Read the result:
   * **Failed** — row-by-row errors (unknown EmpID, duplicate, bad number…). Nothing changes; the previous active data stays. Fix the file and upload again.
   * **Passed** — preview of the first rows. Still **not active**.
4. **Activate this version…** → read the confirmation → **Activate**.
   * From now on, for that month only: people not in the file cannot submit; limits come from the file; fixed-amount employees are placed in HR’s Pending list.
   * Employees who **already submitted** that month are not touched (listed as “skipped”).
5. **Month-wise upload history**: click a month to see every version (time in IST, uploader, file, rows, fixed count, validation result, which one is active). **View** shows the stored rows; **Activate** can switch the active version.

Rules to remember:
* A month with **no active upload** behaves exactly as before (Employee Details limit, anyone may submit).
* Uploading September never changes August. August still shows August’s limit, forever.
* If two admins activate at the same time, the second gets *“Another activation happened…Reload and retry.”*

### 6.1b Payroll Months (new) — Admin Panel → *Payroll Months*
Controls the **Month Range** list employees see on the OPE form.
1. **Add a month**: pick the starting month and year (dates default to the 21st → 20th; change them if needed), optional *submit-by* / *approve-by* dates, tick *Show to employees now*, **Add month**.
2. **Edit** changes the period dates and the two deadlines (leave empty for the standard 7 / 5 days).
3. **Hide / Show** controls whether employees see the month. Hidden months keep all data and reports, but employees cannot start a new submission for them.
Employees see the change the next time they open or refresh the portal.

### 6.1c Team Reports (new) — Admin Panel → *Team Reports*
Download OPE data **Partner wise** or **Reporting Manager wise**, with the supporting details.
1. Choose **Partner wise** or **Reporting Manager wise**.
2. Pick a **Partner** (or *All partners*). The **Reporting Manager** list then shows only the managers whose employees are under that partner (e.g. choose *Huzefa kaka* and only his reporting managers appear); pick one or leave *All*. Then choose a **payroll month** (or *All months*) and optionally a **status**. Partner and Reporting Manager can be combined; the Excel, the ZIP and their file names use exactly these filters.
3. The “What you will get” cards show how many employees, records, expense entries and ticket PDFs match.
4. **Download Excel report** — three sheets: *Summary* (per partner / manager), *Employee Months* (limit, submitted and approved amounts, status, IST times, remarks) and *Entries (supporting)* (every expense entry with approver, remarks, rejection reason and the ticket file name).
5. **Download supporting tickets (ZIP)** — the ticket PDFs in folders *Partner or Manager / Employee / Month*. Each file name matches the “Ticket file (in ZIP)” column of the Excel. One ZIP holds up to 600 tickets; pick one person or month to get more.

### 6.2 Resubmission Access and HR Report
Same screens as HR (tabs *Resubmission Access* and *HR Report* in the Admin Panel).

### 6.3 Existing Admin reports
Dashboard, client analysis, advanced analysis, Excel downloads — unchanged.

---

## 7. Testing checklist (UAT)

Use test employees and a **non-production** database. Suggested people: `E1` (employee), `E2` (another employee of the same manager), `E3` (employee of a different manager), `RM1` (E1/E2’s manager), `RM2`, `P1` (partner), `HR` (JHS729), `AD` (admin).
Payroll months below: **M1** = August–September 2026, **M2** = September–October 2026.

### A. Submission lock & reopen
| # | Steps | Expected |
|---|---|---|
| A1 | E1 saves 2 entries for M1 and submits | Success; Status shows M1 *Pending at Reporting Manager* |
| A2 | E1 selects M1 on the OPE form | Banner: already submitted, contact HR |
| A3 | E1 tries to save/submit another M1 entry | Refused with the “contact HR” message |
| A4 | E1 submits M2 | Allowed (different month) |
| A5 | HR → Resubmission → E1 → *Allow resubmission* for M1 with a reason | Row shows *Allowed once* |
| A6 | E1: M2 still locked, E2: M1 still locked | Both refused |
| A7 | E1 adds an entry to M1 and submits | Works; detail shows **version 2**; earlier entries and history intact |
| A8 | E1 tries M1 again | Locked again (permission used) |
| A9 | Employee/RM/Partner try the reopen API/screen | No access (403) |
| A10 | HR allows, then **Revoke** | E1 locked again; history shows both events |

### B. Approval, amounts, history
| # | Steps | Expected |
|---|---|---|
| B1 | RM2 (not E1’s manager) tries to approve E1 | Refused (403) |
| B2 | RM1 approves E1’s M1 with a remark | Detail: *Reporting Manager — Approved*, amount approved = full amount, remark, IST time |
| B3 | Partner/HR stage not yet reached | Shows *Not reviewed yet* (not ₹0) |
| B4 | RM1 edits an entry amount | Original still shown as “Submitted”; current differs; edit logged |
| B5 | For a 3-level case: RM approves, Partner **rejects** | History keeps **both** events; RM’s approved amount still shown; status Rejected |
| B6 | Open the same employee’s M2 | Unaffected by M1 actions (own status, amounts, history) |
| B7 | E1 tries to edit/delete an approved entry | Refused: already approved |
| B8 | Pending, Approve and Reject tabs → **Amounts & Timeline** | Same full detail for each month |
| B10 | 3-level case: RM approves; open Partner’s and HR’s **Approve** tab | Entry is **only in Pending** for the next stage, not in their Approve tab |
| B11 | Partner approves | Entry now appears in Partner’s Approve tab (still not in HR’s) |
| B9 | Try the same approve twice quickly (double click) | Only one decision recorded |

### C. Monthly uploads & limits
| # | Steps | Expected |
|---|---|---|
| C1 | Admin uploads a valid file for M1 (E1 limit 1500) and activates | History: v1 *Active* |
| C2 | Upload M2 with E1 limit 2000, activate | M1 still 1500, M2 2000 |
| C3 | E1 submits 1900 in M2 | 2-level approval (within 2000) |
| C4 | Upload a file with an unknown EmpID, a duplicate row and a text limit | *Failed*, row errors listed, active version unchanged, Activate not offered |
| C5 | Employee not in the active M1 file selects M1 | Banner “not in the eligible list”; save refused |
| C6 | Employee with a Fixed OPE Amount selects the month | Banner “fixed at ₹X by HR”; save refused |
| C7 | HR → Pending | The fixed-amount employee is listed with the fixed amount; HR approves/rejects |
| C8 | Re-upload M2 (v2) and activate | v1 stays in history as inactive; M1 unchanged |
| C9 | Non-admin opens the upload screen / calls the API | No access (403) |

### D. HR Report
| # | Steps | Expected |
|---|---|---|
| D1 | HR Report → M1 | Counts + amounts shown |
| D2 | Download Excel | Summary sheet counts = on-screen cards; Records rows = table rows; amounts equal |
| D3 | Switch to M2 | Different numbers; nothing from M1 |
| D4 | Employee/RM opens the report API | 403 |
| D5 | Month with no data | “No records” message, Download disabled |

### E. Time display
| # | Steps | Expected |
|---|---|---|
| E1 | Approve something and note your clock | Timestamps everywhere show **IST** with the `IST` label, regardless of your computer’s timezone |

### F. Devices
Open the HR Report, Status detail and Admin upload page on **desktop, tablet and phone**: tables become cards on a phone, no sideways scrolling of the page, all buttons usable.

### G. Security spot-checks
| # | Check | Expected |
|---|---|---|
| G1 | Register an employee code that is not in Employee Details | Refused |
| G2 | 9 wrong passwords in a row | “Too many failed login attempts” |
| G3 | An employee opens another employee’s Status/History/detail | 403 |
| G4 | `/api/debug/...` without login / as non-admin | 401 / 403 |

---

## 8. Troubleshooting

| Message / symptom | Meaning / action |
|---|---|
| “OPE for … has already been submitted … contact HR” | Month is locked. Ask HR to allow resubmission. |
| “You are not in the eligible employee list for …” | Admin’s active upload for that month doesn’t contain you. Contact HR/Admin. |
| “Your OPE amount … is fixed …” | You are a fixed-amount employee; nothing to fill. |
| “You are not the assigned approver for this employee” | The employee is not in your team per Employee Details. HR/Admin must fix the assignment. |
| “This entry has already been approved and can no longer be changed” | Approved entries are locked. Contact HR. |
| “Another activation happened at the same time…” | Reload the Monthly Uploads page and retry. |
| “A submission for this month is already in progress” | A double-click; wait a moment and check Status. |
| HR Report / Resubmission not visible | Only HR and Admin see them. |
| New screens look stale after a release | Hard-refresh (Ctrl+F5). |

---

## 9. Technical notes for the person deploying/testing

* Start (existing): `uvicorn main:app --reload` (needs `MONGO_URI`, `MONGO_DB`, `JWT_SECRET`, `JWT_ALGORITHM` in `.env`).
* Install: `pip install -r requirements.txt` (now includes `tzdata`).
* Automated tests: `pip install -r requirements-dev.txt` then `python -m pytest` (34 tests, in-memory Mongo).
* React screens live in `frontend/`; the built files are committed in `static/react/`. After changing them: `cd frontend && npm install && npm run build`.
* Indexes are created automatically at start-up. No data migration is required; existing months keep working and show a history rebuilt from their status record.
* More detail: see `IMPLEMENTATION_NOTES.md`.
