# Deadline Rescue — Smart Assignment & Deadline Management System

Deadline Rescue is an academic productivity web application designed to help college students organize coursework deliverables, calculate urgency-weighted priority scores, track completion milestones, and eliminate submission panic.

Built with Python (Flask) and SQLite, the system provides a clean command center dashboard, full task CRUD lifecycle, smart search and filtering, and a deterministic priority scoring engine.

---

## 1. Features

### Academic Command Center Dashboard (`/`)
- **6 Real-Time Metric Cards**: Total Tasks, Pending Tasks, Completed Tasks, Overdue Tasks, Due Today, and Due Soon (1–7 days out).
- **Semester Completion Progress Bar**: Displays overall completion percentage ($\frac{\text{Completed}}{\text{Total}} \times 100\%$) with accessible markup.
- **Workload by Course Subject**: Aggregates remaining study and lab hours for **Pending tasks only**, with CSS-based proportional horizontal progress bars (zero external charting dependencies).
- **Upcoming Deadlines Pipeline**: Displays the nearest active deliverables due today or in the future, excluding overdue and completed tasks.

### Coursework Deliverables Management (`/tasks`, `/tasks/new`, `/tasks/<id>/edit`)
- **Task Lifecycle CRUD**: Create, view, edit, complete, reopen, and delete coursework items.
- **Form Prepopulation & Safe Edits**: Edit coursework details with full form prepopulation while strictly preserving task IDs and creation timestamps.
- **Status Toggling**: One-click completion marking and reopening with distinct visual treatments.
- **Safe Deletion**: Deletion requires HTTP POST confirmation to prevent accidental loss.

### Priority Engine & Deadline Awareness (`priority.py`)
- **Continuous Priority Scoring**: Dynamically calculates a composite score from $0.0$ to $100.0$ combining urgency, importance, and estimated effort.
- **Categorical Badges**: Maps scores into 4 distinct priority tiers: **Critical** (75–100), **High** (50–74.99), **Medium** (25–49.99), and **Low** (0–24.99).
- **Human-Friendly Relative Dates**: Computes dynamic relative deadline labels (`Overdue by X days`, `Due today`, `Due tomorrow`, `Due in X days`).
- **Recommended Next Task**: Highlights the single most urgent pending deliverable across the entire database, independent of active table filters.

### Search, Filtering & Deterministic Sorting (`/tasks`)
- **Search**: Case-insensitive substring search matching across Task Title and Course Subject.
- **Multi-Criteria Filtering**: Combine Status (`Pending`, `Completed`), Subject, and Priority tier using strict AND logic.
- **8 Deterministic Sorting Modes**:
  1. `Recommended Priority` (Priority score $\downarrow$, Due date $\uparrow$, Task ID $\uparrow$)
  2. `Deadline: Earliest First` (Due date $\uparrow$, Priority score $\downarrow$, Task ID $\uparrow$)
  3. `Deadline: Latest First` (Due date $\downarrow$, Priority score $\downarrow$, Task ID $\uparrow$)
  4. `Priority: Highest First` (Priority score $\downarrow$, Due date $\uparrow$, Task ID $\uparrow$)
  5. `Priority: Lowest First` (Priority score $\uparrow$, Due date $\uparrow$, Task ID $\uparrow$)
  6. `Title: A–Z` (Alphabetical $\uparrow$, Task ID $\uparrow$)
  7. `Title: Z–A` (Reverse alphabetical $\downarrow$, Task ID $\uparrow$)
  8. `Newest First` (Creation timestamp $\downarrow$, Task ID $\downarrow$)

---

## 2. Priority Scoring Formula

The priority engine computes an exact priority score between $0.0$ and $100.0$:

$$\text{Priority Score} = 0.60 \times U + 0.25 \times \left(\frac{I}{5} \times 100\right) + 0.15 \times \min\left(\frac{H}{8}, 1.0\right) \times 100$$

### Components:
1. **Urgency ($U$, 60% Weight)**: Evaluated from calendar days remaining ($\text{due\_date} - \text{today}$):
   - $\text{Overdue} (< 0 \text{ days}) \rightarrow U = 100$
   - $\text{Due Today} (0 \text{ days}) \rightarrow U = 100$
   - $\text{Due Tomorrow} (1 \text{ day}) \rightarrow U = 90$
   - $\text{Due in } 2–3 \text{ days} \rightarrow U = 75$
   - $\text{Due in } 4–7 \text{ days} \rightarrow U = 50$
   - $\text{Due in } 8–14 \text{ days} \rightarrow U = 30$
   - $\text{Due in } > 14 \text{ days} \rightarrow U = 10$
2. **Importance ($I$, 25% Weight)**: User rating on a 1–5 scale, normalized to 100.
3. **Effort ($H$, 15% Weight)**: Estimated workload in hours, normalized and capped at 8 hours (100).

---

## 3. Technology Stack

- **Backend**: Python 3.11+, Flask 3.1
- **Database**: SQLite3 (via Python standard library `sqlite3` with parameterized statements)
- **Frontend**: HTML5, Vanilla CSS design tokens (`static/css/style.css`), Bootstrap 5.3.3 & Bootstrap Icons 1.11.3 (via CDN)
- **Themes**: Dual-theme system (Dark Neon Dusk default, Bright Purple alternative) with `localStorage` persistence
- **Security**: Synchronizer Token Pattern CSRF protection via `csrf.py`, autoescaped Jinja templates, parameterized SQL
- **Client Scripting**: Vanilla JavaScript (`static/js/main.js`)
- **Testing**: Python standard library `unittest` (185 automated tests)

---

## 4. Project Structure

```text
Deadline-_Rescue/
├── app.py                      # Flask application factory, routes, and error handlers
├── database.py                 # SQLite connection manager, schema initialization, CRUD functions
├── priority.py                 # Priority calculation, urgency thresholds, filtering and sorting
├── analytics.py                # Dashboard statistical aggregation and workload calculations
├── csrf.py                     # Session-bound CSRF token generation and validation
├── requirements.txt            # Python package dependencies (Flask)
├── .gitignore                  # Git ignore rules for virtualenvs, caches, and databases
├── README.md                   # Project documentation
├── instance/
│   └── deadline_rescue.db      # Local SQLite database (auto-created on startup, git-ignored)
├── templates/
│   ├── base.html               # Master layout with navigation and footer
│   ├── dashboard.html          # Academic Command Center dashboard view
│   ├── tasks.html              # Coursework management view with filter bar and task table
│   ├── task_form.html          # Form for creating and editing tasks
│   ├── 404.html                # Friendly 404 Not Found error template
│   └── 500.html                # Friendly 500 Internal Error error template
├── static/
│   ├── css/
│   │   └── style.css           # Custom CSS stylesheet with design tokens and cards
│   └── js/
│       └── main.js             # Client interactivity, theme toggle, and filters
├── test_priority.py            # Priority engine and urgency calculations (28 tests)
├── test_analytics.py           # Dashboard metrics and workload aggregation (27 tests)
├── test_task_filters.py        # Search, multi-criteria filters, and sorting modes (33 tests)
├── test_step2.py               # Database initialization & validation (12 tests)
├── test_step3.py               # Task CRUD lifecycle operations (27 tests)
├── test_csrf.py                # CSRF protection and token validation (29 tests)
└── test_final_qa.py            # End-to-end workflows and security regression (29 tests)
```

---

## 5. Installation & Setup

### Prerequisites
- Python 3.11 or higher
- PowerShell (Windows) or terminal (macOS/Linux)

### 1. Create a Virtual Environment
```powershell
python -m venv .venv
```

### 2. Activate the Virtual Environment
- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

*(If script execution is restricted on Windows PowerShell, you can invoke the virtual environment Python binary directly: `.\.venv\Scripts\python.exe`)*

### 3. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

---

## 6. How to Run the Application

Start the local Flask development server:

```powershell
python app.py
```

Open your browser to:
- **Dashboard**: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- **Tasks Management**: [http://127.0.0.1:5000/tasks](http://127.0.0.1:5000/tasks)
- **Add New Task**: [http://127.0.0.1:5000/tasks/new](http://127.0.0.1:5000/tasks/new)

---

## 7. How to Run Tests

The project includes **185 automated unit and integration tests** built using Python's standard `unittest` framework.

### Run All 185 Tests
```powershell
python -m unittest discover -s . -p "test_*.py" -v
```

### Run Individual Test Suites
```powershell
python -m unittest test_priority.py -v       # Priority scoring & urgency (28 tests)
python -m unittest test_analytics.py -v      # Dashboard analytics & workload (27 tests)
python -m unittest test_task_filters.py -v   # Search, filter, and sort (33 tests)
python -m unittest test_step2.py -v          # Database initialization & validation (12 tests)
python -m unittest test_step3.py -v          # Task CRUD lifecycle (27 tests)
python -m unittest test_csrf.py -v           # CSRF token security & session isolation (29 tests)
python -m unittest test_final_qa.py -v       # End-to-end workflows & security regression (29 tests)
```

All test cases use isolated temporary SQLite databases (`tempfile.mkstemp()`), ensuring that running the test suite never modifies or deletes your actual local data.

---

## 8. Database Behavior & Persistence

- **Database Engine**: SQLite3
- **File Location**: `instance/deadline_rescue.db` (created automatically within the instance folder on first run).
- **Schema Management**: Tables are created automatically on startup via `CREATE TABLE IF NOT EXISTS tasks (...)` inside `database.init_app()`.
- **Data Persistence**: Records persist permanently across application restarts. Existing records are never overwritten or deleted on server start.
- **Git Ignore**: The `instance/` folder and `*.db` files are excluded by [.gitignore](file:///.gitignore) to keep personal coursework databases out of version control.

### Vercel SQLite limitation — college demonstration

Deadline Rescue currently uses SQLite. The deployed Vercel configuration stores its temporary database under `/tmp`.

- Data in `/tmp` is not guaranteed to persist between runtime instances or deployments.
- Different serverless instances may have separate database files.
- Task records and analytics may disappear or differ between requests.
- The local database at `instance/deadline_rescue.db` is separate from the deployed temporary database.
- This setup is for a college demonstration only, not permanent academic record keeping.
- Before real-world use, the application will need suitable persistent storage and a verified backup/recovery plan.

---

## 9. Security & Project Limitations

1. **Academic Prototype Context**: Deadline Rescue is designed and tested as a local, single-user academic tool running on `127.0.0.1`.
2. **SQL Injection Protection**: All database queries in `database.py` use parameterized statements (`?` placeholders). Raw user input is never concatenated into SQL queries.
3. **Cross-Site Scripting (XSS) Prevention**: All user-provided fields (titles, subjects, descriptions) are rendered through Jinja2 with autoescaping enabled.
4. **CSRF Protection**: Comprehensive Synchronizer Token Pattern (STP) protection is implemented via `csrf.py` using Python standard library cryptography (`secrets.token_hex(32)` and `hmac.compare_digest`). All state-changing form submissions (create, edit, complete, reopen, delete) require a valid session-bound token. Requests with missing, invalid, or cross-session tokens are rejected with HTTP 400.
5. **Authentication**: User accounts, login sessions, and multi-user access control are not part of this prototype scope.

---

## 10. Future Improvements

- Multi-user authentication and role-based course access.
- Calendar export and synchronization (iCalendar / Google Calendar `.ics` feeds).
- Reminders and desktop notifications for impending deadlines.
- Interactive historical completion trend charts using client-side SVG or Canvas.
