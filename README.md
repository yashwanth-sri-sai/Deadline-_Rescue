# Deadline Rescue — Smart Assignment & Deadline Management System

**Deadline Rescue** is an academic productivity web application designed to help college students organize coursework deliverables, calculate urgency-weighted priority scores, track completion milestones, and eliminate submission panic.

This repository represents **Step 7: Final QA, Security Audit, Documentation & Release Readiness**, providing a verified, fully tested, and demonstrable coursework management system with 148 automated tests passing at a 100% success rate.

---

## 1. Project Overview

- **Project Name**: Deadline Rescue
- **Target Users**: College and university students managing multiple course deadlines.
- **Problem Solved**: Students frequently experience cognitive overload when juggling multiple assignments, quizzes, labs, and projects across diverse courses. Traditional to-do lists treat all items equally, ignoring deadlines, coursework importance, and estimated effort.
- **Core Objectives**:
  1. Eliminate eleventh-hour submission panic through deadline-aware priority scoring.
  2. Surface a single, unambiguous **Recommended Next Task** to eliminate decision fatigue.
  3. Provide an **Academic Command Center Dashboard** with real-time progress metrics and study workload distribution.
  4. Deliver instant search, multi-criteria filtering, and 8 deterministic sorting modes.
  5. Ensure rock-solid stability with an isolated, parameterized SQLite database layer and 100% test coverage.

---

## 2. Feature Summary

### A. Academic Command Center Dashboard (`/`)
- **6 Real-Time Metric Cards**: Total Tasks, Pending Tasks, Completed Tasks, Overdue Tasks, Due Today, and Due Soon (1–7 days out).
- **Semester Completion Progress Bar**: Displays exact completion percentage ($\frac{\text{Completed}}{\text{Total}} \times 100\%$) with accessible markup (`role="progressbar"`).
- **Workload by Course Subject**: Aggregates remaining study/lab hours for **Pending tasks only**, with CSS-based proportional horizontal progress bars (zero external charting dependencies).
- **Upcoming Deadlines Pipeline**: Curates up to 5 nearest active deliverables due today or in the future, excluding overdue and completed tasks.

### B. Full Task Lifecycle CRUD (`/tasks`, `/tasks/new`, `/tasks/<id>/edit`)
- **Create**: Add coursework with title, course code, task type (`Assignment`, `Quiz`, `Lab`, `Project`, `Other`), due date (`YYYY-MM-DD`), importance (`1` to `5`), estimated hours, and optional notes.
- **Edit**: Update deliverable details with full form prepopulation while strictly preserving task ID, status, and creation timestamps.
- **Complete & Reopen**: One-click status toggling with visual strike-through treatment.
- **Delete**: Safe deletion using HTTP POST and browser confirmation dialogs.

### C. Priority Engine & Deadline Awareness (`priority.py`)
- Evaluates urgency, course importance, and estimated effort into an exact continuous score ($0.0$ to $100.0$).
- Maps scores to 4 color-coded categorical badges: **Critical** (75–100), **High** (50–74.99), **Medium** (25–49.99), and **Low** (0–24.99).
- Generates human-friendly deadline messages (`Overdue by X days`, `Due today`, `Due tomorrow`, `Due in X days`).

### D. Recommended Next Task Banner
- Automatically highlights the single most urgent `Pending` task across the entire database.
- Completely decoupled and independent of active search queries, table filters, or table sorting modes.
- Never recommends a completed task; displays an *"All caught up!"* celebration banner when all work is finished.

### E. Smart Search, Filtering & 8 Sorting Modes (`/tasks`)
- **Search**: Dual-field case-insensitive partial substring search across Title and Subject.
- **Filters**: Status (`Pending`, `Completed`), Subject (dynamically populated and deduplicated), and Priority (`Critical`, `High`, `Medium`, `Low`) combined via strict **AND logic**.
- **8 Deterministic Sorting Modes**:
  1. `Recommended Priority` (Priority score $\downarrow$, Due date $\uparrow$, Task ID $\uparrow$)
  2. `Deadline: Earliest First` (Due date $\uparrow$, Priority score $\downarrow$, Task ID $\uparrow$)
  3. `Deadline: Latest First` (Due date $\downarrow$, Priority score $\downarrow$, Task ID $\uparrow$)
  4. `Priority: Highest First` (Priority score $\downarrow$, Due date $\uparrow$, Task ID $\uparrow$)
  5. `Priority: Lowest First` (Priority score $\uparrow$, Due date $\uparrow$, Task ID $\uparrow$)
  6. `Title: A–Z` (Title alphabetical $\uparrow$, Task ID $\uparrow$)
  7. `Title: Z–A` (Title reverse alphabetical $\downarrow$, Task ID $\uparrow$)
  8. `Newest First` (Creation timestamp $\downarrow$, Task ID $\downarrow$)

---

## 3. Technology Stack

- **Python**: Version 3.11+
- **Backend Framework**: Flask 3.1.3 (WSGI web framework)
- **Database**: SQLite3 (Python standard library `sqlite3` with parameterized statements)
- **Frontend Framework**: Bootstrap 5.3.3 (Official CDN) & Bootstrap Icons 1.11.3
- **Design System**: Colorful Premium Claymorphism (Soft 3D pastel surfaces, multi-layered ambient and inset depth shadows, friendly 26px card radii, tactile pill buttons, and responsive controls in `static/css/style.css`)
- **Scripting**: Vanilla JavaScript for accessible link protection and client diagnostics (`static/js/main.js`)
- **Testing**: Python standard library `unittest` (148 tests across 6 test suites)

---

## 4. Priority Formula & Urgency Thresholds

$$\text{Priority Score} = 0.60 \times U + 0.25 \times \left(\frac{I}{5} \times 100\right) + 0.15 \times \min\left(\frac{H}{8}, 1.0\right) \times 100$$

### Parameter Weights:
1. **Urgency ($U$, 60% Weight)**: Evaluated from calendar days remaining ($\text{due\_date} - \text{today}$):
   - $\text{Overdue} \le 0 \text{ days} \rightarrow U = 100$
   - $\text{Due today} (0 \text{ days}) \rightarrow U = 100$
   - $\text{Due tomorrow} (1 \text{ day}) \rightarrow U = 90$
   - $\text{Due in } 2–3 \text{ days} \rightarrow U = 75$
   - $\text{Due in } 4–7 \text{ days} \rightarrow U = 50$
   - $\text{Due in } 8–14 \text{ days} \rightarrow U = 30$
   - $\text{Due in } > 14 \text{ days} \rightarrow U = 10$
2. **Importance ($I$, 25% Weight)**: User rating on a 1–5 scale, normalized to $100$.
3. **Effort ($H$, 15% Weight)**: Estimated study/lab hours, normalized and capped at 8 hours ($100$).

---

## 5. Project Directory Structure

```text
deadline-rescue/
├── app.py                      # Flask application factory, route handlers, validation, error handlers
├── database.py                 # SQLite connection manager, schema initialization, parameterized CRUD
├── priority.py                 # Priority scoring engine, urgency tables, filter & sort algorithms
├── analytics.py                # Pure-Python analytics engine: summary counts, boundaries, workload
├── requirements.txt            # Minimal project dependencies (Flask 3.x)
├── README.md                   # Complete architectural and execution documentation
├── PROJECT_DEMO_CHECKLIST.md   # Step-by-step evaluator demonstration script and anticipated Q&A
├── step_6_verification_report.md # Step 6 QA verification report
├── step_7_verification_report.md # Final Step 7 release-readiness verification report
├── test_step2.py               # Step 2 Database foundation test suite (12 tests)
├── test_step3.py               # Step 3 Task CRUD lifecycle test suite (27 tests)
├── test_priority.py            # Step 4 Priority engine & recommendation test suite (28 tests)
├── test_task_filters.py        # Step 5 Search, filtering & 8 sorting modes test suite (33 tests)
├── test_analytics.py           # Step 6 Dashboard & workload analytics test suite (27 tests)
├── test_final_qa.py            # Step 7 Final QA & security regression test suite (21 tests)
├── instance/
│   └── deadline_rescue.db      # Local SQLite database file (auto-initialized, git-ignored)
├── templates/
│   ├── base.html               # Master layout with navigation, system status pill, and footer
│   ├── dashboard.html          # Academic Command Center dashboard with summary cards & workload
│   ├── tasks.html              # Coursework task list with filter panel, table, and empty states
│   ├── task_form.html          # Unified form for creating and editing coursework deliverables
│   ├── 404.html                # Friendly 404 Not Found template
│   └── 500.html                # Friendly 500 Internal Error template
└── static/
    ├── css/
    │   └── style.css           # Custom SaaS stylesheet, cards, badges, and progress components
    └── js/
        └── main.js             # Accessible link safeguards and runtime diagnostics
```

---

## 6. Setup & Running the Application (Windows PowerShell)

Follow these steps from the project root directory (`a:\Python Project`):

### Step 1: Create a Virtual Environment (if not already present)
```powershell
python -m venv .venv
```

### Step 2: Activate the Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

> **PowerShell Execution Policy Tip:**  
> If script execution is restricted on your machine, you can run commands directly using the virtual environment's Python executable without changing system policies:
> ```powershell
> .\.venv\Scripts\python.exe -m pip install -r requirements.txt
> .\.venv\Scripts\python.exe app.py
> ```

### Step 3: Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 4: Run the Local Development Server
```powershell
python app.py
```

### Step 5: Open in Web Browser
- **Academic Command Center (Dashboard)**: `http://127.0.0.1:5000/`
- **Coursework Management (Tasks)**: `http://127.0.0.1:5000/tasks`
- **Create New Task**: `http://127.0.0.1:5000/tasks/new`

---

## 7. Database Information

- **Storage Location**: `instance/deadline_rescue.db` (auto-created inside the application instance directory).
- **Schema Initialization**: Automatically invoked on application startup via `database.init_app(app)` and `CREATE TABLE IF NOT EXISTS tasks (...)`.
- **Data Persistence**: All created, updated, and completed tasks persist permanently across server restarts.
- **Safety Rule**: Existing database records are never dropped, reset, or overwritten by the application.

---

## 8. Running Automated Tests

Deadline Rescue includes a comprehensive test suite of **148 automated tests** across 6 test modules:

```powershell
# Run all 148 automated tests across the entire application:
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v

# Or run individual test modules:
.\.venv\Scripts\python.exe test_final_qa.py -v       # Step 7 Final QA & Security (21 tests)
.\.venv\Scripts\python.exe test_analytics.py -v      # Step 6 Dashboard Analytics (27 tests)
.\.venv\Scripts\python.exe test_task_filters.py -v   # Step 5 Search & Filters (33 tests)
.\.venv\Scripts\python.exe test_priority.py -v       # Step 4 Priority Engine (28 tests)
.\.venv\Scripts\python.exe test_step3.py -v          # Step 3 Task CRUD (27 tests)
.\.venv\Scripts\python.exe test_step2.py -v          # Step 2 Database Foundation (12 tests)
```

### Test Coverage Summary:
| Test Suite | Module | Test Count | Status |
| :--- | :--- | :---: | :---: |
| **Final QA & Security** | `test_final_qa.py` | 21 | **21/21 PASSED** |
| **Dashboard Analytics** | `test_analytics.py` | 27 | **27/27 PASSED** |
| **Search, Filters & Sorting** | `test_task_filters.py` | 33 | **33/33 PASSED** |
| **Priority Engine** | `test_priority.py` | 28 | **28/28 PASSED** |
| **Task CRUD Operations** | `test_step3.py` | 27 | **27/27 PASSED** |
| **Database Foundation** | `test_step2.py` | 12 | **12/12 PASSED** |
| **Full Project Test Suite** | **All 6 Suites** | **148** | **148/148 PASSED (100%)** |

---

## 9. Security & Known Limitations

1. **Local Prototype Context**: Deadline Rescue is engineered as a local single-user academic companion running on `127.0.0.1:5000`.
2. **CSRF Protection**: State-changing POST requests do not currently require a CSRF token. In accordance with the Step 7 audit, external packages (such as Flask-WTF) are not installed to maintain zero-network dependency stability. For multi-user public internet deployment, CSRF protection via Flask-WTF is an essential enhancement.
3. **Authentication**: User accounts, login sessions, and role-based permissions are intentionally omitted from this step.
4. **Calendar Synchronization**: External Google Calendar or iCal sync is not implemented.
