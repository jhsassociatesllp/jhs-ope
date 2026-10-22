# Implementation Notes — OPE Update

Companion to `OPE_Payroll_AI_Implementation_Requirements.md` and `USER_AND_TESTING_GUIDE.md`.

## 1. Decisions taken with you
| Question | Decision |
|---|---|
| React migration | Build **new features as React components** and plug them into the existing pages. The 490 KB `script.js` / 8,400-line `main.py` flows were **not** rewritten (lowest regression risk). |
| Upload format | Employee Details columns: `EmpID`, `Emp Name`, `OPE LIMIT`, optional `Fixed OPE Amount`. (The app had no upload before; `OPE LIMIT` lived only in `Employee_details`.) |
| Resubmission | **New version**: the earlier entries/history stay; new entries are stamped `submission_version = n+1`. |
| E-mail (§16) | **Skipped for now.** Nothing is sent and no half-built mail code was added. |

## 1b. Restricted employees (added 19 Oct 2026)
* Collection `ope_restricted_employees` (`employee_id` unique, `employee_name`, `ope_limit`, `active`, audit fields). Loaded with `python seed_restricted_employees.py` (21 employees; `--dry-run` to preview). Admin API: `GET/POST /api/admin/restricted-employees` (add, change limit, deactivate).
* **Login is never blocked.** The backend refuses save/submit/edit for a restricted employee (403 “You are not allowed to fill your own OPE…”); the OPE page shows the same message straight after login.
* **Monthly record**: one per employee per payroll month, created automatically (app start-up, every 30 min, on login and on Status view). Guard collection `ope_restricted_months` (unique employee+month) prevents duplicates. Payroll month = 21st → 20th (IST), same as the OPE form.
* **Amount** = the employee’s `ope_limit` in the collection (the “OPE Limit” of your list) — assumption; tell me if a different amount is intended.
* Goes straight to HR (Reporting-Manager level marked “System”), same mechanism as fixed-amount employees. Status page shows **PENDING HR APPROVAL**, then **APPROVED** after HR approves that month (a rejection shows REJECTED).
* **HR report / Excel**: restricted records are listed only when HR-approved for that month; pending or rejected ones are excluded from rows, counts and the file. Other existing admin exports were not changed.
* Employees already submitted for a month are skipped (nothing overwritten).

## 1c. Admin-managed payroll months (added 19 Oct 2026)
* Collection `ope_payroll_months` (`key`, `display`, `start`, `end`, optional `submit_deadline` / `approve_deadline`, `visible`). The four months that were typed into the code are inserted once at first start; after that the Admin panel (**Payroll Months** tab) is the only place to change them. Months are never deleted, only hidden.
* The OPE "Month Range" list and the deadline banners now load from `GET /api/ope/payroll-months`; the old list in `script.js` is only a fallback if the server is unreachable.
* Hidden (or unlisted) months cannot be submitted for - enforced on the server (403 "not open"); existing data, approvals and reports are unaffected, and an HR-reopened resubmission still works.
* A month starting in December uses key `december-january-2026-2027` and label "December 2026 - January 2027" (the form's old month parser was extended to understand the 4-part key).

## 1d. Dashboard theme (added 19 Oct 2026)
Visual only. `static/theme.css` (loaded after the existing styles by `index.html` and `admin.html`) restyles the sidebar (navy, coloured icon tiles, gradient active item), cards, tables, buttons, the Pending/Approved/Rejected tiles (colour gradient cards) and the admin KPI cards; the React top bar (`TopBar.jsx`: date in IST, role chips, signed-in user) sits above the page content. No markup, behaviour or API was changed; remove the `theme.css` link to go back to the old look.

## 2. Requirement status
| § | Requirement | Status |
|---|---|---|
| 2/17 | React frontend | **Partial (by decision).** New screens are React (Vite build → `static/react/`): HR Report, Resubmission, Monthly Uploads, Submission detail/timeline, lock banner. Legacy portal pages remain HTML/JS. |
| 4 | Server-side role/ownership/scope checks | **Done** for approve/reject (18 endpoints), edit-amount, edit-total, detail, report, uploads, reopen, status/approved/rejected/employee reads. |
| 5 | Monthly eligibility + fixed amount | **Done.** Fixed-amount employees are blocked from the form and placed in HR’s queue on activation. |
| 6 | HR report + Excel | **Done**; one builder feeds screen and export. |
| 7 | Audit trail, UTC storage, IST display | **Done.** `OPE_audit_log` is append-only (no mutation routes). Existing UI timestamps now go through `formatIST()`. |
| 8 | Stage tracker, no duplicate actions | **Done**: tracker in detail modal; per-employee lock serialises concurrent actions. Approval order untouched. |
| 9 | Details in Approved/Rejected | **Done** (button on every month header in Pending, Approved, Rejected). |
| 10 | Amount tracking | **Done**: `original_amount` per entry, per-stage approved amounts, `None` = not reviewed. **No “final payable” formula was invented** — the existing `total_amount` is shown as “Current total”. |
| 11 | Employee status page | **Done** (limit per month, amounts, timeline, lock state). The page reloads from the server on each visit; **no auto-polling** was added. |
| 12 | One submission/month + HR reopen | **Done** (HR **and** Admin may grant, per §4 which names both; RM/Partner/Employee cannot). No auto-expiry. |
| 13 | Admin upload history | **Done.** |
| 14 | Historical limits | **Done**: limit snapshot on the month’s Status item + upload version. |
| 15 | Month isolation | **Done**; regression tests with adjacent months. |
| 16 | E-mail | **Not implemented (your decision).** |
| 18 | Indexes/atomicity | **Done** (see §5). |
| 19 | Tests | Backend automated (34). UI verified manually in the browser (desktop + phone); no automated UI tests. |

## 3. Behaviour changes you should know about
1. **Resubmitting after a rejection now needs HR’s permission** (previously employees could add entries to a month any time). This is §12 of the spec.
2. **Approved entries can’t be edited/deleted by the employee** (the UI already promised this; the API allowed it).
3. A Reporting Manager/Partner can act **only on assigned employees** (previously any manager could act on anyone). Assignment = current `Employee_details`, or an approver recorded on the employee’s Status, or the routing lists the app already keeps.
4. `/api/register` only accepts codes present in `Employee_details`; login is throttled (8 failures / 10 min / code).
5. `/api/debug/*` endpoints now require an Admin.
6. Months **with** an active upload enforce eligibility/limit/fixed amount; months **without** one behave exactly as before.
7. Fixed-amount records go **directly to HR** (Reporting Manager level is marked “System (fixed amount)”) because the spec says HR approves/rejects them. If you want them to also pass the Reporting Manager, tell me and I will route them to L1.
9. **Approve / Reject tabs are stage-strict**: an entry shows in a person’s Approve tab only after *that* stage approved it (Partner/HR no longer see entries that were merely forwarded from the previous stage), and the Reject tab shows only what that person rejected. Implemented with `?stage=manager|partner|hr` on `/api/ope/approved|rejected/{emp}`; without the parameter the old behaviour is kept.
8. “Partially approved” (an existing state) is its own column in the HR report; the four buckets always add up to the total.

## 4. Files
**New:** `ope_features/` (`common.py`, `audit.py`, `access.py`, `uploads.py`, `detail.py`, `reports.py`, `__init__.py`), `frontend/` (React source), `static/react/` (built bundle), `tests/`, `pytest.ini`, `requirements-dev.txt`, `.dockerignore`, the two guides.
**Edited:** `main.py` (imports; 18 approve/reject routes + submit-final/save-temp/update/delete wrapped by decorators; per-month limit lookup in save-temp/submit-final; `original_amount` + validation + audit in the two edit-amount routes; scope on reads; register/login hardening; security headers; `ope_features.install(...)`), `static/index.html`, `static/admin.html`, `static/script.js` (IST helper, detail buttons, per-month limit), `requirements.txt` (`tzdata`), `.gitignore`.
**Not changed:** `main2.py`, `script2.js`, `index2/admin2/*2.*` (old copies, not served by the Dockerfile), the deploy workflows, the Dockerfile.

## 5. Database
New collections (created on first write; nothing existing is altered or deleted):

| Collection | Purpose |
|---|---|
| `OPE_audit_log` | Append-only events (employee, month, version, action, stage, actor, prev/new status, amounts, remark, `at` UTC) |
| `OPE_reopen_permissions` | One row per grant: `active` → `used` / `revoked` |
| `OPE_submission_inflight` | Short-lived marker against double submits (stale after 2 min) |
| `OPE_monthly_versions` / `OPE_monthly_rows` / `OPE_monthly_active` | Upload versions, their rows, and the single active pointer per month |

New fields on existing documents (all optional; older data keeps working): entry `original_amount`, `submission_version`, `is_fixed_amount`; Status month `submission_version`, `stage_amounts`, `limit_upload_version`, `fixed_amount`.

Indexes (auto-created at start-up, safe to repeat): audit `(employeeId, payroll_month, at)` and `(payroll_month, action, at)`; reopen unique partial `(employeeId, payroll_month)` where `status=active`; inflight unique; versions unique `(payroll_month, version)`; rows unique `(version_id, emp_id)`; active unique `payroll_month`; plus `employeeId` on `Status`, `OPE_data`, `Reject_OPE_data`, `Temp_OPE_data` and `Status.approval_status.payroll_month`.

Time: new timestamps are stored as UTC datetimes; legacy fields stay naive-UTC ISO strings. Both are converted with `zoneinfo("Asia/Kolkata")` for display and Excel.

**Migration:** none required. **Rollback:** deploy the previous image. The new collections/fields are ignored by the old code; drop the new collections only if you want to discard the audit history.

## 6. Run / build
```bash
pip install -r requirements.txt            # app (adds tzdata)
uvicorn main:app --reload                  # as before; env: MONGO_URI, MONGO_DB, JWT_SECRET, JWT_ALGORITHM
pip install -r requirements-dev.txt && python -m pytest      # 34 tests
cd frontend && npm install && npm run build                   # rebuilds static/react/ (committed)
```
No new environment variables. No secret is read by or exposed to the React code (it only sends the user’s own JWT).

## 7. Test results
`python -m pytest` → **34 passed** (in-memory MongoDB via mongomock). Covers: IST conversion; first submission stamps/audit; duplicate-month block; other month allowed; HR/Admin-only reopen; reason required; reopen scoped to one employee+month, single use, history kept; revoke; failed submit doesn’t burn a permission; manager/partner scope; audit events with amounts; reject-after-approve keeps both events and stage amounts; adjacent-month isolation; detail visibility matrix; approved entries locked; edit-amount keeps original + validation + scope; read ownership; debug endpoints; concurrent double submit; upload admin-only, validation, failed upload leaves active data intact, stale-activation guard, month-independent limits, eligibility, fixed-amount flow to HR and approval; HR report counts = Excel; formula-injection escaping; register/login hardening; security headers.
UI checked manually in the built-in browser against a seeded in-memory server: HR Report (desktop + 375 px phone, no horizontal page scroll), detail modal, Status page buttons, lock banner, Admin Monthly Uploads tab.

## 8. Known limitations / please verify in staging
* Tests ran on **mongomock**, not a real MongoDB. Run section 7 of the user guide once against a staging database (especially the partial unique index and concurrent actions).
* Concurrency protection for approvals is an **in-process** lock + the in-flight marker; it assumes the current single uvicorn worker. With several workers, add a database-level guard.
* `GET /api/ope/pdf/{id}` still lets any logged-in user fetch a ticket PDF if they know its (unguessable) id; not changed.
* Still as before: CORS `*`, 10-day JWT lifetime, HR identity hard-coded as `JHS729`, no password-strength rule. Recommend a follow-up.
* Months submitted before this release have no audit events; their history is **rebuilt from the Status record** (labelled as such) and their “submitted” amount may equal the current amount if it was edited before this release.
* Fixed-amount records are created at **activation**; employees who already submitted that month are skipped and reported.
* Payroll month label for Dec→Jan is generated as “December 2026 - January 2027”; the old form uses its own year config for such months.
* No e-mail (see §1).
