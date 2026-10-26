# Deadline Rescue — College Project Demonstration Checklist & Evaluator Q&A

**Project Title**: Deadline Rescue — Smart Assignment & Deadline Management System  
**Release Version**: 1.0.0 (Release Ready)
**Target Audience**: Academic Evaluators, Professors, and Student Developers  
**Execution Environment**: Localhost (`http://127.0.0.1:5000/`) on Python 3.11+ / Windows PowerShell  

---

## Part 1: Step-by-Step Demonstration Sequence

This sequence provides a deterministic, repeatable 10-minute walkthrough demonstrating all core capabilities of Deadline Rescue from start to finish.

> **Pre-Demonstration Note:**  
> The application starts with existing coursework records in `instance/deadline_rescue.db`:
> 1. `Distributed Systems Lab 2 (Raft Consensus)` — CS 420 (Overdue)
> 2. `Web Security Essay` — SEC 301 (Upcoming)  
> *Do not delete or clear these pre-existing records during the demo.*

---

### Step 1: Open Academic Command Center Dashboard
- **Action**: Navigate to `http://127.0.0.1:5000/` in the browser.
- **Explain to Evaluator**:
  - The dashboard delivers high-level visibility across coursework deliverables.
  - Show the **6 Summary Cards**: Total (2), Pending (2), Completed (0), Overdue (1 with red alert indicator), Due Today (0), Due Soon (0).
  - Point out that completed tasks are never counted as actively overdue.
- **Expected Visual**: Summary cards render with clean badges; Semester Completion shows `0.0%` (`0 of 2 tasks completed`).

---

### Step 2: Explain Subject Workload & Upcoming Deadlines
- **Action**: Scroll to the two-column analytic section on the dashboard.
- **Explain to Evaluator**:
  - **Workload by Subject**: Displays remaining study/lab hours for **Pending tasks only**. Point out `CS 420` (4.5 hrs) and `SEC 301` (4.0 hrs), with `8.5 hrs` total. Mention CSS-based horizontal workload bars (zero external charting dependencies).
  - **Upcoming Deadlines Pipeline**: Displays nearest deliverables due today or future (`Web Security Essay`). Point out that overdue work (`Distributed Systems Lab 2`) is intentionally excluded from "Upcoming" to prevent false planning.
- **Expected Visual**: Two-column layout with horizontal progress bars and action buttons.

---

### Step 3: Navigate to Tasks Management View
- **Action**: Click the **Tasks** link in the navbar or **Manage Tasks** button.
- **Explain to Evaluator**:
  - The `/tasks` page is dedicated to detailed coursework management, filtering, and sorting.
  - Point out the **Recommended Next Task** banner prominently displaying `Distributed Systems Lab 2` (Critical, Priority Score 100.00). Explain why: it is overdue with maximum urgency ($U=100$) and high importance ($I=5$).
- **Expected Visual**: Recommendation card at the top, followed by the search/filter panel and the deliverables table.

---

### Step 4: Add a Sample Demonstration Task
- **Action**: Click **Add Task** (`/tasks/new`).
- **Enter Demonstration Data**:
  - **Task Title**: `Cloud Microservices Architecture Lab`
  - **Subject / Course Code**: `CS 480`
  - **Task Type**: `Lab`
  - **Due Date**: Select a date 5 days from today (e.g. `2026-10-29`)
  - **Importance**: `4` (High)
  - **Estimated Hours**: `6.0`
  - **Description**: `Deploy distributed microservices on Kubernetes`
- **Click**: **Save Task**.
- **Expected Result**: Redirects to `/tasks` with green flash alert: `Task 'Cloud Microservices Architecture Lab' created successfully!`.

---

### Step 5: Explain the Priority Score & Deadline Badge
- **Action**: Locate the newly created task in the table.
- **Explain to Evaluator**:
  - **Days Remaining**: 5 days $\rightarrow$ Urgency score $U = 50$ (falls in the 4–7 days threshold).
  - **Importance**: 4 out of 5 $\rightarrow$ Normalized component $0.25 \times (4 / 5 \times 100) = 20.0$.
  - **Effort**: 6.0 hours $\rightarrow$ Effort component $0.15 \times (6 / 8 \times 100) = 11.25$.
  - **Urgency**: $0.60 \times 50 = 30.0$.
  - **Total Priority Score**: $30.0 + 20.0 + 11.25 = 61.25$ $\rightarrow$ Categorical label **High** (badge rendered in gold).
- **Expected Visual**: Priority badge displays `High (61.25)`, deadline badge shows `Due in 5 days`.

---

### Step 6: Demonstrate Search Functionality
- **Action**: In the search input on `/tasks`, type `Microservices` and click **Apply**.
- **Explain to Evaluator**:
  - Search performs dual-field case-insensitive partial substring matching across title and subject.
  - Notice the table isolates the matching deliverable while the global **Recommended Next Task** banner remains visible above.
- **Expected Visual**: Table shows only `Cloud Microservices Architecture Lab`. Filter badge shows `Showing 1 of 3 tasks | Filters Active`.

---

### Step 7: Demonstrate Multi-Criteria Filtering (AND Logic)
- **Action**:
  - Clear the search box.
  - Select **Status**: `Pending`.
  - Select **Subject**: `CS 480`.
  - Select **Priority**: `High`.
  - Click **Apply**.
- **Explain to Evaluator**:
  - Multi-criteria filtering applies strict **AND logic** in memory over retrieved database rows.
- **Expected Visual**: Displays only tasks matching all criteria simultaneously.

---

### Step 8: Demonstrate Sorting Options
- **Action**:
  - Click **Clear Filters** to restore all 3 tasks.
  - Select **Sort By**: `Deadline: Earliest First` $\rightarrow$ Click **Apply**.
  - Show table ordering: Overdue task (earliest past date) first, followed by upcoming tasks.
  - Select **Sort By**: `Title: A–Z` $\rightarrow$ Click **Apply**.
  - Show table ordering: `Cloud Microservices Architecture Lab`, `Distributed Systems Lab 2`, `Web Security Essay`.
- **Expected Visual**: Table immediately rearranges according to the selected sorting algorithm.

---

### Step 9: Edit the Demonstration Task
- **Action**: Click **Edit** next to `Cloud Microservices Architecture Lab`.
- **Modify**:
  - Change Title to: `Cloud Microservices Architecture Lab (Phase 1)`
  - Change Estimated Hours to: `8.0`
- **Click**: **Save Changes**.
- **Expected Result**: Task is updated. Task ID and original creation timestamp remain strictly preserved.

---

### Step 10: Complete the Demonstration Task & Verify Dashboard Update
- **Action**: Click the green **Complete** button on `Cloud Microservices Architecture Lab (Phase 1)`.
- **Explain to Evaluator**:
  - The task transitions to `Completed` with strike-through styling.
  - Now click **Dashboard** in the navbar:
    - Total Tasks: `3`
    - Completed Tasks: `1`
    - Pending Tasks: `2`
    - Completion Percentage: `33.3%` (`1 of 3 tasks completed`).
    - Subject workload for `CS 480`: Drops to `0.0 hrs` because completed tasks do not consume active study hours!
- **Expected Visual**: Dashboard statistics reflect the completion instantly and accurately.

---

### Step 11: Reopen the Demonstration Task
- **Action**: Navigate back to `/tasks` and click **Reopen** on the task.
- **Expected Result**: Status returns to `Pending`. Green badge changes back to Pending badge.

---

### Step 12: Delete ONLY the Demonstration Task (Clean-Up)
- **Action**: Click **Delete** on `Cloud Microservices Architecture Lab (Phase 1)`.
- **Confirm**: Accept the browser confirmation dialog.
- **Explain to Evaluator**:
  - State-changing deletion uses HTTP POST with confirmation safeguards.
  - Only the demo task created in Step 4 is deleted.
  - The 2 pre-existing database records remain completely intact.
- **Expected Visual**: Task is removed from SQLite; table shows 2 remaining tasks.

---

### Step 13: Explain Software Architecture & Database Design
- **Key Points for Evaluator**:
  - **Backend**: Flask application factory (`create_app()`) with blueprint-like structure.
  - **Database**: SQLite3 with parameterized queries to prevent SQL injection.
  - **Decoupled Architecture**:
    - `database.py`: CRUD operations, connection lifecycle, and schema initialization.
    - `priority.py`: Pure-Python priority engine and deterministic sorting.
    - `analytics.py`: Pure-Python statistical aggregation with date-injection support for tests.
  - **Frontend**: Responsive semantic HTML5, Bootstrap 5.3, Bootstrap Icons, custom SaaS CSS design tokens. No heavy external charting libraries.

---

### Step 14: Demonstrate Automated Test Suite
- **Action**: Run the complete automated test suite in terminal:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
  ```
- **Explain to Evaluator**:
  - Shows 148 automated tests across 6 test modules covering unit calculations, date boundaries, CRUD operations, filters, sorting, dashboard analytics, and security regressions.
  - 100% pass rate with zero failures.

---

## Part 2: Anticipated Evaluator Questions & Answers

### Q1: What is the exact Priority Engine formula and why is it weighted this way?
> **Answer**:  
> The formula is:  
> $$\text{Priority} = 0.60 \times U + 0.25 \times \left(\frac{I}{5} \times 100\right) + 0.15 \times \min\left(\frac{H}{8}, 1.0\right) \times 100$$  
> - **60% Urgency ($U$)**: The primary driver of deadline rescue. An overdue or due-today task scores 100 on urgency, ensuring impending deadlines rise to the top.  
> - **25% Importance ($I$)**: Weights semester impact (course credits, exam weight) on a 1–5 scale.  
> - **15% Effort ($H$)**: Workload estimated in hours, normalized and capped at 8 hours. Prevents massive multi-week projects from completely drowning out quick urgent submissions.

---

### Q2: How does the application prevent SQL injection and Cross-Site Scripting (XSS)?
> **Answer**:  
> - **SQL Injection**: All database interactions in `database.py` use parameterized queries with `?` placeholders. User input is never concatenated into SQL strings.  
> - **XSS**: All user-provided fields (titles, subjects, descriptions) are rendered through Jinja2 with default autoescaping enabled. Malicious `<script>` tags are escaped as HTML entities (`&lt;script&gt;`).

---

### Q3: Why is CSRF protection documented as a limitation rather than being enabled with an external library?
> **Answer**:  
> To maintain zero external network dependency stability in an academic evaluation environment, external package installation (such as `Flask-WTF`) was omitted. In accordance with the project specification, Deadline Rescue is designed and documented as a **local academic prototype** running on `127.0.0.1`. For production multi-user web deployment, CSRF protection via Flask-WTF is documented as an essential production enhancement.

---

### Q4: How are completed tasks handled across the application?
> **Answer**:  
> Completed tasks are treated with strict academic logic:  
> 1. They are **never** counted in Overdue, Due Today, or Due Soon summary cards.  
> 2. They **never** contribute to remaining subject workload hours.  
> 3. They are **never** recommended as the Recommended Next Task.  
> 4. In the task list, they display with strike-through text, lightened background, and a "Reopen" action.

---

### Q5: How does the application handle legacy or corrupted dates in the database?
> **Answer**:  
> The date parser `priority.parse_due_date()` safely catches `ValueError` and `TypeError`, returning `None`. Tasks with invalid dates are safely excluded from deadline boundaries and sorted deterministically to the end of deadline-sorted lists without throwing HTTP 500 errors.

---

### Q6: How does the sorting algorithm break ties between tasks?
> **Answer**:  
> All 8 sorting modes use deterministic tie-breaking hierarchies:  
> - **Recommended**: Priority score ($\downarrow$) $\rightarrow$ Due date ($\uparrow$) $\rightarrow$ Task ID ($\uparrow$).  
> - **Deadline Ascending**: Valid dates first $\rightarrow$ Due date ($\uparrow$) $\rightarrow$ Priority score ($\downarrow$) $\rightarrow$ Task ID ($\uparrow$).  
> - **Title A–Z**: Title lowercase ($\uparrow$) $\rightarrow$ Task ID ($\uparrow$).  
> - Deterministic tie-breaking guarantees reproducible list rendering across all client sessions.
