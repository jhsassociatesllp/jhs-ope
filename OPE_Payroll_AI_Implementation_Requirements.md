# OPE Payroll Management System --- Strict AI Implementation Requirements

**Document purpose:** This file is the authoritative requirement and
implementation contract for updating the existing OPE web application.
Give this file to the coding AI together with the existing repository.
The AI must inspect the repository first and implement only the
requirements written here.

## 1. Non-negotiable rules

1.  **Preserve the existing business logic.** The current application
    uses HTML, CSS, JavaScript, FastAPI, and MongoDB. The frontend must
    be migrated to React, but existing workflows, calculations,
    validation rules, API behavior, database meaning, roles, and
    business logic must remain unchanged unless a change is explicitly
    required below.
2.  **Do not redesign or rewrite the backend unnecessarily.** Reuse
    existing FastAPI routes, services, MongoDB collections, fields,
    authentication, and validation wherever possible. Make only the
    smallest backend changes needed for the specified additions.
3.  **Do not invent features.** Do not add unrequested modules, workflow
    stages, calculations, roles, permissions, UI sections, or business
    rules.
4.  **Do not silently change requirements.** If a requirement conflicts
    with existing code or cannot be implemented safely without a
    business decision, stop and report the exact conflict and options.
    Do not guess.
5.  **Do not replace existing data formats.** The monthly employee
    eligibility/OPE-limit upload must accept the same file format and
    structure currently used by the application. Preserve existing
    column names, field meanings, and required values.
6.  **Do not delete or overwrite existing production data during
    migration.** Use safe, reversible migrations if required. Back up
    data before any destructive operation. Never clear a collection to
    make the new implementation easier.
7.  **Do not claim completion based only on a successful build.** Verify
    the workflow, permissions, amounts, month isolation, timestamps,
    emails, exports, and regression behavior.
8.  **Keep the application fast and maintainable.** Use reusable React
    components, avoid duplicate API calls and unnecessary re-renders,
    add suitable database indexes where needed, and paginate/filter
    large lists instead of loading everything without limits.
9.  **No placeholder implementations.** Do not leave buttons that do
    nothing, mock data in production flows, TODO-only features, or
    hard-coded employee/reporting data.
10. **Keep secrets secure.** Do not expose database credentials, SMTP
    credentials, API keys, or private configuration in React or
    client-side environment variables.

## 2. Existing technology and migration scope

-   **Current frontend:** HTML, CSS, JavaScript.
-   **Target frontend:** React. Use the repository's existing
    build/tooling where practical; inspect it before selecting or
    replacing tooling.
-   **Backend:** FastAPI.
-   **Database:** MongoDB.
-   **Reference UI:** The attached Jewellery Billing Software dashboard
    image is a visual reference for a clean, information-dense admin
    dashboard: fixed/clear navigation, compact summary cards,
    charts/tables, strong hierarchy, and consistent spacing. It is a
    visual direction only; do not copy jewellery-specific labels,
    metrics, or business functionality.
-   **Responsive behavior:** The application must work properly on
    desktop, tablet, and mobile. Desktop should use a structured
    dashboard/sidebar and readable tables. Mobile should use responsive
    navigation, stacked cards, scrollable or appropriately transformed
    tables, accessible forms, and usable action buttons. Do not merely
    shrink the desktop layout.
-   **Scope:** Migrate the existing frontend to React and implement only
    the OPE requirements in this document. Keep the FastAPI + MongoDB
    architecture unless repository inspection demonstrates a necessary,
    clearly explained reason to change a small part.

## 3. Mandatory first step: repository audit

Before editing any code, inspect the full existing project and produce a
concise audit covering:

-   Current frontend entry points, pages, components, CSS, JavaScript,
    API calls, and build process.
-   FastAPI routers, models/schemas, services, authentication, role
    checks, approval logic, and email configuration.
-   MongoDB database/collection names and relevant document structures
    for employee details, OPE submissions, approvals, statuses,
    eligibility lists, and limits.
-   Existing status values and how reporting manager, partner, HR, and
    admin are currently authorized.
-   Existing Excel import/export implementation and exact current upload
    format.
-   Existing tests and deployment assumptions.

Create a mapping from each existing page/workflow to its React
replacement. Do not start a broad rewrite before this audit. Preserve
current behavior and identify any missing facts rather than assuming
them.

## 4. Roles and access control

Preserve the existing role definitions and hierarchy. The required
access boundaries are:

### Employee

-   Can view their own OPE submissions, applicable limit, amount
    breakdown, workflow history, status, and remarks.
-   Can submit OPE only when eligible for that specific month and when
    the submission is allowed by the existing rules.
-   Cannot grant themselves permission to resubmit a month.
-   Cannot view another employee's private OPE data.

### Reporting Manager

-   Can review and act only on submissions assigned to them under the
    existing reporting structure and permissions.
-   Can approve or reject at their permitted workflow stage.
-   Cannot access admin-only employee data upload, global reports, or
    permission controls.

### Partner

-   Can review and act only on submissions they are authorized to handle
    under the existing workflow.
-   Cannot access admin-only employee data upload, global reports, or
    permission controls.

### HR

-   Can approve/reject at the existing HR stage.
-   Can grant or deny an employee permission to reopen a specific month
    for resubmission.
-   Can download the monthly HR report from the application without
    manually querying MongoDB or preparing an Excel file.
-   Must not receive admin-only powers unless the existing system
    already explicitly grants them.

### Admin

-   Has access to all OPE records and the admin functions specified
    here.
-   Can download reports, view month-wise history, manage monthly
    eligible employee/limit uploads, and control which employees are
    permitted to submit or resubmit data for a month.
-   Can manage employee submission access for a month. No reporting
    manager or partner may receive this access.
-   Admin-only operations must be enforced by the backend, not just
    hidden in the frontend.

**Security rule:** Every protected API must verify identity, role,
ownership, assigned approval scope, and month scope on the server.
Hiding a button is not authorization.

## 5. Monthly employee eligibility and fixed OPE amount

Some employees are assigned a fixed OPE amount each month.

-   These fixed-amount employees must **not be able to fill or submit
    the normal OPE form** for that month.
-   Their records must still appear in the system and be visible in the
    relevant approval workflow so HR can approve or reject them.
-   The amount for these employees must come from the approved monthly
    eligibility/employee data supplied by HR, not from employee-entered
    values.
-   Only employees included in the active eligible list for a particular
    month may use the relevant monthly submission flow, subject to the
    existing rules.
-   Preserve the current monthly upload file format and column
    structure.
-   If a fixed amount or eligibility field already exists, reuse it. Do
    not introduce a conflicting duplicate field without first explaining
    why it is necessary.
-   Validate uploaded rows and report row-level errors. Do not partially
    replace the active list silently.
-   After validation, make the monthly import atomic: either the valid
    upload is activated successfully as a complete month-specific
    version, or the previous active version remains intact.
-   Do not mix eligibility, fixed amounts, or limits between months.

## 6. Monthly HR report and Excel download

Add a report/export section to the HR admin panel so HR can download the
report directly.

For the selected month, show and export at least the following counts
and details, using the actual existing workflow stages and statuses:

-   Total employees/records in scope.
-   Approved records.
-   Pending records.
-   Rejected records.
-   Employee name and identifier, month, submitted amount, amount
    approved at each applicable stage, final/current status, and
    relevant timestamps/remarks where available.
-   Counts and amounts must be consistent between the on-screen summary
    and the downloaded Excel file.
-   Provide month selection and clear loading/error/empty states.
-   Export must be generated from authorized backend data, not by
    trusting totals calculated only in the browser.
-   Avoid double-counting a submission that has changed status. Define
    counts using the current state for the selected month, while
    retaining the full historical status-change log separately.
-   Use the existing Excel library/format if present. Do not change
    unrelated exports.

## 7. Complete audit trail with Indian time

Maintain a reliable, month-specific history for each OPE submission.
Record events for:

-   Employee submission.
-   Reporting Manager approval or rejection.
-   Partner approval or rejection.
-   HR approval or rejection.
-   Any later status change, including approval followed by rejection.
-   Admin/HR reopening permission changes, where applicable.
-   Relevant changes to approved amounts and remarks.

Each event should include, where applicable:

-   Submission ID and employee identifier.
-   OPE month/period.
-   Actor ID and role.
-   Action (`submitted`, `approved`, `rejected`, `reopened`, or a
    clearly defined existing equivalent).
-   Previous status and new status.
-   Original submitted amount and the amount approved at that
    action/stage.
-   Remark/reason.
-   Timestamp.

**Time handling:** Store timestamps consistently in UTC in the database,
and display them in Indian Standard Time (Asia/Kolkata, UTC+05:30). Use
a proper timezone-aware conversion; do not manually add 5 hours 30
minutes to stored values in multiple places. Display an unambiguous date
and time in the UI and exports.

Audit history must be append-only for ordinary workflow actions. Do not
overwrite earlier events when a later action occurs. Protect audit
records from unauthorized edits/deletion.

## 8. Approval/rejection workflow and tracker

-   Preserve the existing approval order and rules. Do not add or remove
    an approval stage.
-   Track the reporting manager, partner, and HR stages independently
    for each submission and month.
-   If a submission is approved at a stage and later rejected or
    otherwise changed, retain both events in history and show the
    current state clearly.
-   Each stage must show its current status, actor, action time, amount
    approved at that stage, and remark when applicable.
-   An earlier stage's approval must not be erased from the audit
    history when a later stage rejects the submission.
-   Keep current status separate from event history. The current status
    answers "what is the state now?"; the history answers "what
    happened, and when?"
-   Prevent duplicate or conflicting approval actions caused by repeated
    clicks, stale screens, or concurrent requests. Use backend
    validation and safe state transitions.
-   Display stage-level history in a clear timeline/tracker for
    employees and authorized reviewers.

## 9. Employee details in Pending, Approved, and Rejected sections

Currently, selecting an employee in Pending shows their submitted
details. Extend equivalent detail viewing to the Approved and Rejected
sections.

When an authorized user opens a record, show:

-   Employee details relevant to the existing OPE form.
-   The selected OPE month/period.
-   Original amount submitted by the employee.
-   Reporting Manager approved amount and remark, if applicable.
-   Partner approved amount and remark, if applicable.
-   HR approved amount and remark, if applicable.
-   Current/final status.
-   Complete approval/rejection timeline with timestamps in IST.
-   Any existing line items or expense entries, preserving their current
    meaning and formatting.

Do not show an approved amount as if it were the original submitted
amount. Label each amount clearly. Do not expose one employee's details
to another employee.

## 10. Amount-level tracking

For every submission, maintain distinct values for:

1.  Original employee-submitted amount.
2.  Reporting Manager approved amount.
3.  Partner approved amount.
4.  HR approved amount.
5.  Final payable/approved amount, only if the existing business rules
    define one.

Rules:

-   Do not overwrite the original submitted amount when a reviewer
    adjusts an amount.
-   Store stage-level decisions and their amounts in the
    submission/audit data model in a way that preserves historical
    decisions.
-   Validate amounts on the backend: numeric, finite, non-negative
    unless the existing business rules explicitly allow otherwise, and
    subject to existing limits.
-   Do not invent a formula to calculate the final amount. Follow the
    existing business rules. If they do not define how stage amounts
    combine, stop and ask for a decision before implementing that
    calculation.
-   Show amounts in the employee view, reviewer detail view, reports,
    exports, and notification emails with clear labels.
-   Handle zero amounts and missing/not-yet-reviewed stage amounts
    explicitly; do not silently display them as an approved zero.

## 11. Employee status page

Employees must be able to see the real status of their own OPE
submission for each month.

Show: - The current overall status. - Each applicable approval stage and
its status. - Reviewer remarks/rejection reasons. - Amount submitted and
each stage's approved amount. - Submission and decision timestamps in
IST. - A chronological history of changes, including approval followed
by rejection. - Whether resubmission is locked or allowed, and how to
contact HR when locked.

The UI must refresh status from the backend and reflect saved server
state. Do not display a success state before the API confirms the
action. Use polling or the existing refresh pattern if real-time push
infrastructure does not already exist; do not add complex infrastructure
without need. Avoid showing stale status as current.

## 12. One submission per employee per month and HR-controlled reopening

-   After an employee submits OPE data for a month, block another
    submission for the same employee and month by default.
-   The restriction must be enforced by the backend and backed by a
    suitable uniqueness/idempotency strategy where compatible with the
    existing data model.
-   Show a clear message instructing the employee to contact HR if they
    need to resubmit.
-   Only HR may authorize reopening/resubmission for a specific employee
    and specific month. If the existing role model makes this a separate
    admin-only operation, preserve that boundary and flag the conflict
    instead of silently granting access.
-   A reopening permission must be scoped to the exact employee and
    month, have an actor, timestamp, reason/remark if required by
    existing policy, and an audit event.
-   Reopening one month must not unlock any other month.
-   Once permission is granted, allow the existing form/process to be
    used again according to the established rules. Do not erase the
    previous submission or its audit history. Follow the existing policy
    for whether resubmission updates a record or creates a new version;
    if this is not defined, ask before implementing.
-   HR must be able to revoke or close the permission if required by the
    existing workflow; do not invent automatic expiry rules without a
    business decision.

## 13. Admin month-wise upload/version history

Add an admin-only section to manage the monthly eligible employee/limit
file.

Required behavior: - Upload a new monthly employee data file using the
exact existing format. - Select or identify the month to which the
upload applies. - Show a month-wise list/history of uploaded data. -
Each version should show month, upload time in IST, uploader,
file/version identifier, row count, validation result, and whether it is
active. - Clicking a month shows the list/details for that month's
upload. - The currently active data for a month determines which
employees are eligible and what limits/fixed amounts apply for that
month. - Preserve prior upload versions so admins can review which data
applied to a past month. - Do not let a new month's upload modify a
previous month's employee limits or submission history. - Provide
validation preview and clear errors before activation. - Prevent
accidental duplicate activation or concurrent overwrite. - Make
activation atomic and auditable. If a file fails validation, keep the
previously active version unchanged. - Do not change the existing file
format, column names, or field meanings to suit the new UI.

## 14. Historical OPE limit handling

An employee's OPE limit may change from month to month.

Example: - May limit: ₹1,500. - June limit: ₹2,000.

The system must show ₹1,500 for May and ₹2,000 for June. The June upload
must not rewrite the historical May limit or make a May report display
₹2,000.

Implementation requirements: - Associate eligibility and limit values
with a specific month and upload version. - Snapshot the applicable
limit/eligibility onto the submission or preserve a durable reference to
the exact monthly version used at submission time. - Historical reports
and audit views must use the limit applicable to that month, not the
latest employee master value. - Display the applicable limit clearly to
employees and reviewers. - Validate amount-versus-limit according to
existing business rules; do not invent whether an exception/override is
allowed.

## 15. Strict month isolation

This is a critical correctness requirement.

-   Every submission, status, approval event, remark, amount,
    eligibility record, limit, reopen permission, email, and report must
    be scoped to the correct OPE month/period and employee.
-   Use a canonical month/period identifier consistent with the existing
    application's definition of an OPE month. Do not assume calendar
    months if the existing system uses a payroll period such as
    May--June.
-   Never identify a submission using employee ID alone when multiple
    months are possible.
-   All database queries and updates must filter by the correct
    submission ID and month/period, and validate that the submission
    belongs to that period.
-   An action for May--June must never update or display as an action
    for June--July.
-   Approval lists, counts, totals, exports, status timelines, and
    emails must use the same month-scoping rules.
-   Add regression tests for adjacent periods and for the same employee
    having records in multiple periods.
-   Do not copy the latest status/amount into another month.
-   Use appropriate compound indexes for common employee/month,
    status/month, and reviewer/month queries after inspecting the actual
    schema.

## 16. Email notifications

Send an email to the relevant employee whenever a Reporting Manager,
Partner, or HR approves or rejects an OPE submission.

-   Resolve the recipient using that employee's email address in the
    existing Employee Details database record.
-   Do not hard-code employee email addresses or use the reviewer's
    email as the recipient.
-   Include the OPE month/period, actioning stage/role, action
    (approved/rejected), current status, reviewer remark/reason,
    original submitted amount, relevant stage-approved amount, other
    stage amounts when available, and counts/amounts of approved and
    rejected entries where the existing data model supports entry-level
    detail.
-   Clearly distinguish "amount submitted," "amount approved at this
    stage," and "current/final amount" so the email cannot mislead the
    employee.
-   Include the action timestamp in IST.
-   If the system stores multiple line items/entries, report approved
    and rejected entry counts and their amounts accurately. If it stores
    only one aggregate submission, do not invent entry-level counts.
-   Send notifications after the database action commits successfully. A
    failed email must not roll back or falsely reverse a successful
    approval/rejection.
-   Log email delivery attempts and failures without logging credentials
    or unnecessary personal data. Provide retry-safe behavior so a retry
    does not unintentionally create duplicate approval actions.
-   Reuse the existing email provider/configuration if available. Keep
    credentials in server-side environment variables/secrets and
    document required configuration. Do not send email from the React
    frontend.
-   Show an appropriate warning/log state if notification delivery
    fails; do not claim an email was sent if it was not.

## 17. React UI and dashboard requirements

-   Use reusable React components for navigation, dashboard cards,
    filters, data tables, detail views, status timelines, forms, modals,
    and alerts.
-   Match the attached reference's professional dashboard feel without
    copying irrelevant jewellery content.
-   Build separate role-appropriate views using the existing roles:
    Employee, Reporting Manager, Partner, HR, and Admin.
-   Use consistent typography, spacing, status indicators, amount
    formatting (INR), date formatting (IST), and accessible contrast.
-   Provide loading, empty, success, validation-error, API-error, and
    permission-denied states.
-   Use clear confirmation for irreversible or high-impact actions such
    as rejecting a submission, activating a new monthly upload, or
    granting reopening access.
-   Prevent accidental double submission by disabling relevant actions
    while a request is in flight, while still enforcing correctness on
    the backend.
-   Keep mobile interactions usable. Wide tables should become
    responsive cards or use a deliberate horizontal-scroll layout with
    visible key columns.
-   Do not add charts or dashboard metrics unless they are useful for
    existing data and required by this specification. Do not introduce
    decorative complexity that slows the application.

## 18. Data model and API implementation rules

-   Inspect the current MongoDB schema before choosing changes. Existing
    MongoDB documents may be flexible, but the implementation must use
    consistent validated structures.
-   Prefer minimal, backward-compatible additions over wholesale
    collection/schema replacement.
-   If new fields/collections are necessary, document the purpose,
    indexes, compatibility behavior, and migration/rollback plan.
-   Keep workflow state transitions in FastAPI, not only in React.
-   Validate input types, amount values, role access, submission
    ownership, month identity, and transition legality on the server.
-   Make approval/rejection operations safe against duplicate requests
    and concurrent updates.
-   Use atomic MongoDB updates or transactions where supported and
    appropriate. If multi-document atomicity is required but unavailable
    in the deployment configuration, design a safe alternative and
    document it.
-   Add indexes based on actual query patterns; do not add speculative
    indexes blindly.
-   Keep API responses backward-compatible where feasible. Update
    frontend API usage consistently if a response must change.
-   Do not expose MongoDB internal credentials or secrets in logs or API
    responses.
-   Preserve existing authentication/session behavior unless a specific
    change is required for security or this specification.

## 19. Testing and acceptance criteria

Do not mark the work complete until these scenarios pass.

### Regression

-   Existing OPE workflow still works as before for users who are
    eligible.
-   Existing calculations, validations, role rules, and approval order
    remain unchanged except for explicitly requested features.
-   Existing data remains readable and valid after the frontend
    migration.

### Monthly limits and uploads

-   Upload a valid monthly file in the existing format.
-   Invalid upload shows actionable errors and does not replace active
    data.
-   May and June have different limits; each month continues to show its
    own limit.
-   Historical upload versions remain visible.
-   A fixed-amount employee cannot submit the regular form but appears
    in the HR workflow with the configured fixed amount.

### Approval workflow

-   Reporting Manager, Partner, and HR can only act at their authorized
    stage.
-   Pending, Approved, and Rejected detail views all show the correct
    employee data and stage amounts.
-   Approval/rejection history remains intact after subsequent actions.
-   Remarks and timestamps are correctly attributed to the actor and
    stage.
-   Amounts at each stage remain separate from the original submitted
    amount.

### Submission locking

-   Employee submits for a month; a second submission for that same
    month is blocked.
-   A submission for a different permitted month follows the existing
    rules.
-   HR reopening for one employee/month permits only that
    employee/month.
-   Another employee or month remains locked.
-   Earlier submissions and their audit events remain available after
    resubmission.

### Reporting and email

-   HR can select a month and download an Excel report without database
    access.
-   On-screen counts, Excel counts, and amounts match.
-   Approval/rejection emails go to the employee email stored in
    Employee Details.
-   Email content correctly distinguishes original and approved amounts
    and includes the correct month, status, remark, and IST timestamp.
-   Email failure is logged and does not corrupt the workflow state.

### Month isolation

-   Create records for two adjacent payroll periods for the same
    employee.
-   Approve/reject the first period and confirm that the second period's
    status, amount, history, and report remain unchanged.
-   Confirm all dashboard counts, detail views, exports, and emails use
    the correct period.

### Responsive UI and performance

-   Verify desktop, tablet, and mobile layouts.
-   Verify large lists use pagination or appropriate filtering.
-   Verify common pages do not make unnecessary repeated requests.
-   Verify all buttons and actions work and all errors are visible to
    the user.

## 20. Required implementation process and deliverables

The coding AI must follow this sequence:

1.  Audit the repository and report the current architecture and
    existing business rules.
2.  List the exact files/components/routes/collections expected to
    change and why.
3.  Identify ambiguities or conflicts. Ask concise questions before
    implementing any behavior that cannot be derived safely from the
    existing code.
4.  Implement the React migration while preserving existing behavior.
5.  Implement the specified backend changes, access controls, month
    isolation, audit history, reports, uploads, and email notifications.
6.  Add or update tests for regression, authorization, amounts, month
    isolation, upload validation, reopening, and notifications.
7.  Run available backend tests, frontend lint/type checks, and
    production builds. Fix regressions caused by the changes.
8.  Provide a final report listing files changed, new dependencies,
    environment variables, database/index/migration changes, test
    results, known limitations, and deployment steps.

### Final response from the coding AI must include

-   What was changed and what was deliberately left unchanged.
-   Exact commands to install dependencies and run frontend/backend
    locally.
-   Any environment variables required, with example variable names only
    (never real secrets).
-   Database migration/index steps and rollback instructions.
-   Test cases executed and their actual results.
-   Any requirement that remains incomplete, with the reason. Never
    claim an untested feature is complete.

## 21. Strict instruction to the coding AI

Treat this document as the scope boundary. **Do not make unrelated
improvements, redesign business logic, rename or remove existing fields,
change the monthly file format, add new approval stages, change the
approval order, change calculations, or alter role permissions unless
explicitly required here or necessary to preserve existing behavior.**
If the current repository contradicts an assumption in this document,
inspect the implementation and ask for clarification instead of silently
choosing a new rule. Make the smallest safe change that satisfies the
requirement, and prove it with tests.
