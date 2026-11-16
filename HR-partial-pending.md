# COMPLETE SYSTEM ENHANCEMENT PROMPT
## HR Portal – Partial Pending, HR Approval, Rejection & Status Management

### 1. Main Objective

I want to enhance the existing application's HR Portal approval workflow by introducing a new **Partial Pending** section and improving the existing HR Pending, HR Approved, HR Rejected, and Status sections.

The enhancement must work with the existing application, existing database, employee records, approval hierarchy, backend APIs, frontend components, and business logic.

**IMPORTANT: This is an UPDATE to my existing application, NOT a new application or redesign.**

Before making any changes, analyse the complete existing project and understand its current architecture, database structure, APIs, authentication, role permissions, approval logic, and UI.

Make only the necessary changes. Do not modify unrelated functionality.

---

### 2. Analyse Existing Application and Database

Before implementation:

1. Analyse the complete frontend and backend code.
2. Identify the existing HR Portal components and sidebar navigation.
3. Understand the current Employee → Reporting Manager → Partner → HR approval workflow.
4. Identify how the application calculates 2-level and 3-level approval requirements.
5. Inspect the existing MongoDB collections and actual employee submission documents.
6. Identify the existing approval status fields, employee IDs, submission IDs, and approval history.
7. Understand the existing HR Pending, HR Approved, HR Rejected, and Status sections, if available.
8. Identify the APIs responsible for fetching and updating employee approval records.

Do not assume database fields or collection names. Use the actual existing database schema and code.

---

### 3. Existing Approval-Level Logic – Must Remain Unchanged

The existing approval-level calculation and amount limits must remain exactly as they are.

**Scenario A: Employee Amount Below the Configured Limit**

1. Employee fills in their details.
2. Employee saves and submits their data.
3. Submission follows the existing 2-level approval workflow.
4. Reporting Manager and Partner approvals are handled according to the existing configuration.

**Scenario B: Employee Amount Above the Configured Limit**

1. Employee fills in their details.
2. Employee saves and submits their data.
3. Submission follows the existing 3-level approval workflow.
4. Reporting Manager, Partner, and HR approvals are handled according to the existing configuration.

Do not modify:
- Existing approval amount limits.
- Existing approval hierarchy.
- Existing approval-level calculation.
- Existing Employee, Reporting Manager, Partner, or HR permissions outside the required enhancement.

Use the actual existing approval configuration to determine which approval stages are mandatory.

---

### 4. Introduce New Section – Partial Pending

Add a new section named **Partial Pending** inside the existing HR Portal.

This section will provide HR with visibility into employee submissions that have been submitted but have not yet completed the required Reporting Manager and Partner approvals.

#### Partial Pending Display Conditions

Display employee submissions when:

- Employee has submitted their data.
- Reporting Manager approval is pending, OR
- Reporting Manager has approved but Partner approval is pending.
- The required approval workflow is not yet complete.

#### Information to Display

Show the existing employee submission information, including:

- Employee Name.
- Employee ID.
- Designation.
- Department.
- Reporting Manager.
- Submitted Amount.
- Submission Date.
- Reporting Manager Approval Status.
- Partner Approval Status.
- HR Approval Status, wherever applicable.
- Current Approval Stage.

Reuse the existing table structure and employee details components.

#### Partial Pending Actions

HR must be able to:

- View employee submission details.
- Review the submitted information.
- Approve the submission where the existing HR workflow permits.
- Reject the submission where the existing HR workflow permits.
- View the current approval history.

Do not allow HR actions to bypass mandatory Reporting Manager or Partner approvals.

---

### 5. Partial Pending Must Be Accessible Only to HR

This is a mandatory requirement.

Add a **Partial Pending** navigation button inside the existing HR Portal sidebar.

Requirements:

1. Display the Partial Pending button only when an authenticated HR user logs in.
2. When HR clicks the button, open the Partial Pending section.
3. Do not display this button to Employees.
4. Do not display this button to Reporting Managers.
5. Do not display this button to Partners.
6. Do not display this button to any other unauthorized user.
7. Prevent unauthorized users from accessing the section through a direct URL.
8. Protect the corresponding backend APIs with existing role-based authentication and authorization.
9. Maintain the existing sidebar design, layout, colours, and navigation behaviour.

Do not create a separate HR Portal or change the existing navigation structure unnecessarily.

---

### 6. HR Approval and Rejection from Partial Pending

HR must be able to perform the permitted approval or rejection action from Partial Pending.

#### Scenario A: HR Approves Employee Submission

When HR approves an eligible employee submission:

1. Validate the employee submission ID.
2. Validate the authenticated user's HR role.
3. Check the latest approval state in MongoDB.
4. Ensure the action is permitted by the existing approval hierarchy.
5. Update the HR approval status to Approved.
6. Record the HR approver's details.
7. Record the approval timestamp.
8. Preserve all previous Reporting Manager and Partner approval history.
9. Immediately remove the submission from Partial Pending.
10. Move the submission to the existing HR Approved section.
11. Ensure the submission does not appear in HR Pending.
12. Prevent HR from approving the same submission again.

#### Scenario B: HR Rejects Employee Submission

When HR rejects an eligible employee submission:

1. Validate the employee submission ID.
2. Validate the authenticated user's HR role.
3. Check the latest approval state in MongoDB.
4. Update the HR approval status to Rejected.
5. Record the HR approver's details.
6. Record the rejection timestamp.
7. Save rejection remarks using the existing schema or extend it minimally if required.
8. Preserve previous Reporting Manager and Partner approval history.
9. Immediately remove the submission from Partial Pending.
10. Move the submission to the existing HR Rejected section.
11. Ensure the submission does not appear in HR Pending.
12. Prevent another HR approval or rejection action on the same submission unless an existing authorized reopening or resubmission process permits it.

**Important:** HR Approved and HR Rejected must be treated as final HR decision states for that submission.

---

### 7. Update Existing HR Pending Section

Modify the existing HR Pending section.

HR Pending must show only employee submissions that are genuinely eligible for HR approval.

#### Display Conditions

Show a submission in HR Pending only when:

- Employee has submitted the data.
- All mandatory Reporting Manager approvals are completed.
- All mandatory Partner approvals are completed.
- HR approval is required by the existing approval configuration.
- HR approval is still Pending.

#### Restrictions

- Do not show records awaiting Reporting Manager approval.
- Do not show records awaiting Partner approval.
- Do not show records already approved by HR.
- Do not show records already rejected by HR.
- Do not show duplicate submissions.
- Do not allow an already HR-approved or HR-rejected submission to return to HR Pending.

When HR approves or rejects a submission, immediately remove it from HR Pending if it was previously displayed there.

---

### 8. HR Approved Section

Use the existing HR Approved section if available.

If it does not exist, introduce it within the existing HR Portal using the existing UI structure.

Display submissions where HR has successfully approved the record.

Show:

- Employee details.
- Submission amount.
- Reporting Manager approval status.
- Partner approval status.
- HR approval status.
- HR approver details.
- HR approval date and time.
- Existing approval history.

Once HR approves a submission:

- It must appear in HR Approved.
- It must disappear from Partial Pending.
- It must disappear from HR Pending.
- It must not be available for another HR approval action.
- Its completed approval history must remain accessible.

---

### 9. HR Rejected Section

Use the existing HR Rejected section if available.

If it does not exist, add it within the existing HR Portal without redesigning the application.

Display submissions rejected by HR.

Show:

- Employee details.
- Submission amount.
- Reporting Manager approval status.
- Partner approval status.
- HR rejection status.
- HR approver details.
- Rejection date and time.
- Rejection remarks.
- Existing approval history.

Once HR rejects a submission:

- It must appear in HR Rejected.
- It must disappear from Partial Pending.
- It must disappear from HR Pending.
- It must not remain available for another approval or rejection action.
- Preserve the earlier approval history.

---

### 10. Update Existing Status Section

Maintain the existing Status section and its current purpose.

The Status section must reflect the latest actual approval status from MongoDB.

Requirements:

- Display the existing employee approval records.
- Show Reporting Manager approval status.
- Show Partner approval status.
- Show HR approval status.
- Show the current approval stage.
- Show HR approval or rejection details when applicable.
- Preserve the existing status-history information.

HR must be able to access eligible submissions and perform approval actions only where the existing workflow permits.

**Critical Restriction:**

HR must approve or reject each eligible employee submission only once.

After HR approves or rejects a submission:

- Update its database status.
- Disable the relevant HR approval/rejection actions.
- Do not create another HR approval opportunity.
- Do not show the same submission again in pending sections.
- Preserve the completed decision and audit history.

The Status section must not create duplicate approval opportunities simply because an employee record is visible there.

---

### 11. Centralized Data Visibility Rules

Implement a centralized, database-driven filtering mechanism.

The following visibility rules must be enforced:

| Submission condition | Partial Pending | HR Pending | HR Approved | HR Rejected |
|---|---|---|---|---|
| Employee has not submitted | Hide | Hide | Hide | Hide |
| Reporting Manager approval pending | Show | Hide | Hide | Hide |
| Reporting Manager approved, Partner pending | Show | Hide | Hide | Hide |
| All mandatory manager/partner approvals completed, HR pending | Hide | Show | Hide | Hide |
| HR approved | Hide | Hide | Show | Hide |
| HR rejected | Hide | Hide | Hide | Show |

For submissions that require only two approval levels and do not require HR approval, maintain the existing workflow. Do not force them into HR Pending or introduce an unnecessary HR approval.

The same submission must never appear simultaneously in Partial Pending and HR Pending.

Approved and rejected submissions must never reappear in either pending section.

---

### 12. Apply Changes to All Existing Employees

The enhancement must work for all existing employee records already stored in MongoDB, not only new submissions.

Requirements:

1. Fetch existing employee submission records dynamically.
2. Evaluate their actual current approval statuses.
3. Identify records awaiting Reporting Manager approval.
4. Identify records awaiting Partner approval.
5. Identify records eligible for HR approval.
6. Identify records already approved by HR.
7. Identify records already rejected by HR.
8. Display each submission in the correct section.
9. Support historical employee submissions.
10. Prevent duplicate employee submissions from appearing due to incorrect queries.
11. Do not delete or overwrite existing employee records.
12. Do not reset existing approval statuses.

If historical records have missing or inconsistent approval fields, identify them and handle them safely.

Do not automatically approve, reject, or modify historical records based on assumptions.

---

### 13. Real-Time Data Synchronization

All sections must display the latest database state.

When Reporting Manager approves a submission:

- Update MongoDB.
- Refresh the relevant approval status.
- Keep the record in Partial Pending if Partner approval is still pending.
- Move it to HR Pending only after all mandatory previous approvals are completed and HR approval is required.

When Partner approves a submission:

- Update MongoDB.
- Remove the record from Partial Pending.
- Move it to HR Pending if HR approval is required.
- Otherwise, follow the existing completion workflow.

When HR approves:

- Update MongoDB.
- Remove the record from Partial Pending or HR Pending.
- Display it in HR Approved.
- Update the Status section.

When HR rejects:

- Update MongoDB.
- Remove the record from Partial Pending or HR Pending.
- Display it in HR Rejected.
- Update the Status section.

Use the existing application's API, state management, and refresh mechanisms wherever possible.

Do not rely on manual browser refresh to maintain correct section visibility.

---

### 14. Backend and MongoDB Requirements

Implement the required changes using the existing FastAPI/backend architecture and MongoDB database.

Requirements:

- Reuse existing database collections.
- Reuse existing employee submission documents.
- Reuse existing API endpoints wherever practical.
- Modify existing endpoints only where required.
- Use actual approval status fields as the source of truth.
- Implement backend-side filtering.
- Validate every approval and rejection action against the latest database state.
- Validate HR permissions on the backend.
- Prevent duplicate approval and rejection operations.
- Use atomic MongoDB updates or equivalent concurrency-safe operations.
- Preserve existing employee IDs and submission IDs.
- Preserve existing approval history.
- Record approver identity and timestamps.
- Prevent simultaneous HR users from approving or rejecting the same submission.
- Maintain compatibility with existing employee records.

Do not rely exclusively on frontend filtering for security or approval validation.

---

### 15. Frontend UI/UX Requirements

Maintain the existing application's complete design system.

Do not redesign the HR Portal.

Only implement the following changes:

1. Add Partial Pending to the HR sidebar.
2. Make Partial Pending visible only to HR.
3. Create the Partial Pending section using the existing table and components.
4. Add HR Approve and Reject actions where permitted.
5. Update HR Pending filtering.
6. Update HR Approved filtering and display.
7. Update HR Rejected filtering and display.
8. Update Status section approval information.
9. Display clear status indicators.
10. Refresh relevant sections after approval/rejection actions.

Maintain existing:

- Colours.
- Fonts.
- Sidebar layout.
- Tables.
- Buttons.
- Cards.
- Modal/dialogue styles.
- Responsive design.
- Existing navigation.
- Reusable components.

---

### 16. Testing and Validation

Before completing the implementation, test all the following scenarios.

**Approval workflow tests:**

1. Employee submits an amount below the configured limit.
2. Employee submits an amount above the configured limit.
3. Reporting Manager has not approved.
4. Reporting Manager approves but Partner has not approved.
5. Reporting Manager and Partner both approve.
6. HR approval becomes eligible.
7. HR approves a submission from Partial Pending where permitted.
8. HR rejects a submission from Partial Pending where permitted.
9. HR approves a submission from HR Pending.
10. HR rejects a submission from HR Pending.
11. HR attempts to approve an already approved submission.
12. HR attempts to reject an already rejected submission.
13. Multiple HR users attempt to process the same submission simultaneously.
**Access-control tests:**

14. HR can see Partial Pending in the sidebar.
15. Employee cannot see Partial Pending.
16. Reporting Manager cannot see Partial Pending.
17. Partner cannot see Partial Pending.
18. Unauthorized users cannot access Partial Pending through a direct URL.
19. Unauthorized users cannot call HR-only backend endpoints.

**Database and existing-record tests:**

20. Existing employee records load correctly.
21. Historical approved records do not appear in pending sections.
22. Historical rejected records do not appear in pending sections.
23. Partially approved historical records appear in the correct section.
24. New submissions appear in the correct section.
25. Refreshing the application does not cause duplicate records.
26. Existing approval history remains intact.
27. HR approval/rejection immediately updates the appropriate sections.
28. Two-level submissions do not receive unnecessary HR approval.

---

### 17. Strict Development Instructions

**DO NOT:**

- Rebuild the existing application.
- Create a separate HR Portal.
- Change existing approval amount limits.
- Change existing approval hierarchy.
- Modify unrelated modules.
- Rename existing database collections unnecessarily.
- Rename existing fields unnecessarily.
- Delete existing employee data.
- Reset existing approval statuses.
- Create duplicate approval records.
- Allow HR to approve or reject the same submission twice.
- Allow unauthorized users to access Partial Pending.
- Bypass mandatory Reporting Manager or Partner approvals.
- Break existing Employee, Reporting Manager, Partner, or HR functionality.

**DO:**

- Analyse the existing code before implementation.
- Inspect actual MongoDB data.
- Reuse existing APIs, models, components, and business logic.
- Make minimal and targeted changes.
- Implement backend-side validation.
- Implement role-based access control.
- Ensure backward compatibility.
- Preserve approval history.
- Test the complete workflow using existing and new employee submissions.

---

### 18. Final Expected Result

The existing HR Portal must have the following functional sections:

**1. Partial Pending**
- Accessible only to HR.
- Available through the HR sidebar.
- Displays submissions awaiting mandatory Reporting Manager or Partner approvals.
- Allows HR to view and perform permitted approval/rejection actions.
- Removes records after an HR decision.

**2. HR Pending**
- Displays only submissions eligible for HR approval.
- Requires all mandatory previous approvals to be completed.
- Does not display partially approved, already approved, or rejected submissions.

**3. HR Approved**
- Displays submissions approved by HR.
- Maintains approval history.
- Prevents duplicate HR approvals.

**4. HR Rejected**
- Displays submissions rejected by HR.
- Maintains rejection remarks and history.
- Prevents duplicate HR decisions.

**5. Status**
- Displays the latest actual approval status.
- Shows the complete approval progress.
- Does not create duplicate HR approval opportunities.

### FINAL IMPLEMENTATION INSTRUCTION

First analyse the entire existing application and MongoDB database. Understand the actual workflow and existing employee records before modifying anything.

Then implement this enhancement in the existing application using minimal, targeted, backward-compatible changes.

Do not make assumptions about the database structure. Do not modify unrelated functionality.

After implementation, provide:

1. Files modified.
2. APIs modified or added.
3. MongoDB fields used or added.
4. Approval workflow changes.
5. HR sidebar changes.
6. Existing employee record compatibility details.
7. Test results for all approval scenarios.
8. Any identified historical data inconsistencies.

**The most important requirement is that the existing application must continue working exactly as before, except for the requested HR Portal enhancements.**

