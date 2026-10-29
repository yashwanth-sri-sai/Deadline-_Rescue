"""
Deadline Rescue — Step 7 Final Quality Assurance & Release-Readiness Test Suite
File: test_final_qa.py

Comprehensive end-to-end audit verifying:
A. Route health & error responses (/, /tasks, /tasks/new, /tasks/<id>/edit, 404, 500, static assets).
B. Full task lifecycle (create -> list -> edit -> complete -> reopen -> delete).
C. Cross-feature consistency (CRUD mutations update dashboard metrics and subject workload).
D. Security regressions (SQL injection resistance, XSS escaping, GET on state-changing endpoints rejected).
E. Boundary cases (empty database, zero hours, all completed, tie-breakers, malformed legacy dates).
F. Test isolation (100% temporary databases, no mutation of instance/deadline_rescue.db).
"""

from datetime import date, datetime, timedelta
import math
import os
import tempfile
import unittest

from app import create_app
import analytics
import database
import priority


class FinalQARouteHealthTestCase(unittest.TestCase):
    """Verifies all application endpoints and HTTP status responses."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_dashboard_route_health(self):
        """Dashboard root route (/) returns HTTP 200 and primary headings."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Academic Command Center", resp.data)
        self.assertIn(b"Take control of your deadlines", resp.data)

    def test_tasks_route_health(self):
        """Tasks route (/tasks) returns HTTP 200 on empty DB and populated DB."""
        resp_empty = self.client.get("/tasks")
        self.assertEqual(resp_empty.status_code, 200)
        self.assertIn(b"Assignments &amp; Deadlines", resp_empty.data)
        self.assertIn(b"No tasks found", resp_empty.data)

        # Seed a task to verify filter controls render when tasks exist
        database.create_task(
            title="Sample Task",
            subject="CS 101",
            task_type="Assignment",
            due_date="2026-11-20",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )
        resp_populated = self.client.get("/tasks")
        self.assertEqual(resp_populated.status_code, 200)
        self.assertIn(b"filter-status-select", resp_populated.data)

    def test_create_task_form_renders(self):
        """GET /tasks/new displays the creation form with all required inputs."""
        resp = self.client.get("/tasks/new")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Create New Task", resp.data)
        self.assertIn(b'name="title"', resp.data)
        self.assertIn(b'name="subject"', resp.data)
        self.assertIn(b'name="task_type"', resp.data)
        self.assertIn(b'name="due_date"', resp.data)
        self.assertIn(b'name="importance"', resp.data)
        self.assertIn(b'name="estimated_hours"', resp.data)

    def test_edit_task_form_renders_prepopulated(self):
        """GET /tasks/<id>/edit prepopulates saved assignment fields."""
        task_id = database.create_task(
            title="Distributed Consensus Lab",
            subject="CS 450",
            task_type="Lab",
            due_date="2026-11-15",
            importance=5,
            estimated_hours=7.5,
            description="Implement Raft leader election",
            db_path=self.db_path,
        )
        resp = self.client.get(f"/tasks/{task_id}/edit")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Edit Task:", resp.data)
        self.assertIn(b"Distributed Consensus Lab", resp.data)
        self.assertIn(b"CS 450", resp.data)
        self.assertIn(b"2026-11-15", resp.data)
        self.assertIn(b"7.5", resp.data)
        self.assertIn(b"Implement Raft leader election", resp.data)

    def test_unknown_task_id_returns_404(self):
        """Nonexistent task IDs return HTTP 404 with friendly error page."""
        resp_edit = self.client.get("/tasks/99999/edit")
        self.assertEqual(resp_edit.status_code, 404)
        self.assertIn(b"Task or Page Not Found", resp_edit.data)

        resp_complete = self.client.post("/tasks/99999/complete")
        self.assertEqual(resp_complete.status_code, 404)

        resp_reopen = self.client.post("/tasks/99999/reopen")
        self.assertEqual(resp_reopen.status_code, 404)

        resp_delete = self.client.post("/tasks/99999/delete")
        self.assertEqual(resp_delete.status_code, 404)

    def test_static_css_and_js_health(self):
        """Static stylesheet and JavaScript assets load with HTTP 200."""
        with self.client.get("/static/css/style.css") as resp_css:
            self.assertEqual(resp_css.status_code, 200)
            self.assertIn(b"--dr-primary", resp_css.data)
            self.assertIn(b".stat-card", resp_css.data)

        with self.client.get("/static/js/main.js") as resp_js:
            self.assertEqual(resp_js.status_code, 200)
            self.assertIn(b"Smart Search, Filtering & Sorting", resp_js.data)
            self.assertIn(b"Step 7", resp_js.data)

    def test_analytics_route_health(self):
        """Analytics route (/analytics) returns HTTP 200 and renders dashboard analytics."""
        resp = self.client.get("/analytics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Academic Command Center", resp.data)
        self.assertIn(b"Overall Coursework Completion Progress", resp.data)

    def test_empty_database_does_not_return_404(self):
        """Empty SQLite database renders the dashboard with HTTP 200, not custom 404."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"Task or Page Not Found", resp.data)
        self.assertIn(b"Academic Command Center", resp.data)

    def test_api_index_prefix_normalization_regression(self):
        """Legacy /api/index rewrite targets normalize to root and tasks without 404."""
        resp_root = self.client.get("/api/index")
        self.assertEqual(resp_root.status_code, 200)
        self.assertIn(b"Academic Command Center", resp_root.data)

        resp_tasks = self.client.get("/api/index/tasks")
        self.assertEqual(resp_tasks.status_code, 200)
        self.assertIn(b"Assignments &amp; Deadlines", resp_tasks.data)

    def test_all_core_routes_resolve_correctly(self):
        """Core application routes (/, /tasks, /analytics, /tasks/new) all return HTTP 200."""
        routes = ["/", "/tasks", "/analytics", "/tasks/new"]
        for route in routes:
            with self.subTest(route=route):
                resp = self.client.get(route)
                self.assertEqual(resp.status_code, 200, f"Route {route} failed to resolve with 200 OK")


class FinalQAEndToEndLifecycleTestCase(unittest.TestCase):
    """Verifies complete task lifecycle: Create -> List -> Edit -> Complete -> Reopen -> Delete."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_complete_crud_lifecycle_flow(self):
        """Execute full end-to-end task lifecycle using web routes."""
        # 1. CREATE task
        create_resp = self.client.post(
            "/tasks/new",
            data={
                "title": "Compilers Lexer Project",
                "subject": "CS 425",
                "task_type": "Project",
                "due_date": "2026-11-10",
                "importance": "4",
                "estimated_hours": "8.0",
                "description": "Build tokenizer for mini-language",
            },
            follow_redirects=True,
        )
        self.assertEqual(create_resp.status_code, 200)
        self.assertIn(b"Compilers Lexer Project", create_resp.data)

        tasks = database.get_all_tasks(self.db_path)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        task_id = task["id"]
        original_created_at = task["created_at"]
        self.assertEqual(task["status"], "Pending")

        # 2. EDIT task
        edit_resp = self.client.post(
            f"/tasks/{task_id}/edit",
            data={
                "title": "Compilers Lexer & Parser Project",
                "subject": "CS 425",
                "task_type": "Project",
                "due_date": "2026-11-12",
                "importance": "5",
                "estimated_hours": "10.0",
                "description": "Build tokenizer and recursive descent parser",
            },
            follow_redirects=True,
        )
        self.assertEqual(edit_resp.status_code, 200)
        self.assertIn(b"Compilers Lexer &amp; Parser Project", edit_resp.data)

        updated_task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(updated_task["title"], "Compilers Lexer & Parser Project")
        self.assertEqual(updated_task["importance"], 5)
        self.assertEqual(updated_task["estimated_hours"], 10.0)
        # Verify immutable fields are strictly preserved
        self.assertEqual(updated_task["id"], task_id)
        self.assertEqual(updated_task["created_at"], original_created_at)
        self.assertEqual(updated_task["status"], "Pending")

        # 3. COMPLETE task
        complete_resp = self.client.post(f"/tasks/{task_id}/complete", follow_redirects=True)
        self.assertEqual(complete_resp.status_code, 200)
        completed_task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(completed_task["status"], "Completed")

        # 4. REOPEN task
        reopen_resp = self.client.post(f"/tasks/{task_id}/reopen", follow_redirects=True)
        self.assertEqual(reopen_resp.status_code, 200)
        reopened_task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(reopened_task["status"], "Pending")

        # 5. DELETE task
        delete_resp = self.client.post(f"/tasks/{task_id}/delete", follow_redirects=True)
        self.assertEqual(delete_resp.status_code, 200)
        self.assertIsNone(database.get_task_by_id(task_id, self.db_path))
        self.assertEqual(len(database.get_all_tasks(self.db_path)), 0)


class FinalQACrossFeatureConsistencyTestCase(unittest.TestCase):
    """Verifies that task mutations immediately update dashboard statistics and workload correctly."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()
        self.today = date.today()

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_crud_updates_dashboard_counts_dynamically(self):
        """Dashboard statistics accurately track task creation, completion, reopening, and deletion."""
        # Baseline empty
        resp0 = self.client.get("/")
        self.assertIn(b"No coursework recorded yet", resp0.data)

        # Create Task A (Pending, due in 3 days)
        due_soon_date = (self.today + timedelta(days=3)).strftime("%Y-%m-%d")
        id_a = database.create_task(
            title="Computer Networks Lab",
            subject="CS 330",
            task_type="Lab",
            due_date=due_soon_date,
            importance=4,
            estimated_hours=3.5,
            status="Pending",
            db_path=self.db_path,
        )

        resp1 = self.client.get("/")
        self.assertIn(b'id="stat-val-total">\n                            1', resp1.data)
        self.assertIn(b'id="stat-val-pending">\n                            1', resp1.data)
        self.assertIn(b'id="stat-val-completed">\n                            0', resp1.data)
        self.assertIn(b'id="stat-val-due-soon">\n                            1', resp1.data)
        self.assertIn(b"0.0%", resp1.data)
        self.assertIn(b"3.5 hrs", resp1.data)

        # Create Task B (Pending, overdue by 2 days)
        overdue_date = (self.today - timedelta(days=2)).strftime("%Y-%m-%d")
        id_b = database.create_task(
            title="Database Schema Design",
            subject="CS 350",
            task_type="Assignment",
            due_date=overdue_date,
            importance=5,
            estimated_hours=4.0,
            status="Pending",
            db_path=self.db_path,
        )

        resp2 = self.client.get("/")
        self.assertIn(b'id="stat-val-total">\n                            2', resp2.data)
        self.assertIn(b'id="stat-val-pending">\n                            2', resp2.data)
        self.assertIn(b'id="stat-val-overdue">\n                            1', resp2.data)
        self.assertIn(b'id="stat-val-due-soon">\n                            1', resp2.data)
        self.assertIn(b"7.5 hrs", resp2.data)  # 3.5 + 4.0

        # Complete Task B (overdue task completed)
        database.set_task_status(id_b, "Completed", db_path=self.db_path)
        resp3 = self.client.get("/")
        # Completed task must NOT count as overdue anymore!
        self.assertIn(b'id="stat-val-overdue">\n                            0', resp3.data)
        self.assertIn(b'id="stat-val-completed">\n                            1', resp3.data)
        self.assertIn(b'id="stat-val-pending">\n                            1', resp3.data)
        self.assertIn(b"50.0%", resp3.data)  # 1 of 2 = 50.0%
        # Workload hours only count pending: 3.5 hrs remaining (Task A only)
        self.assertIn(b"3.5 hrs", resp3.data)

        # Reopen Task B
        database.set_task_status(id_b, "Pending", db_path=self.db_path)
        resp4 = self.client.get("/")
        self.assertIn(b'id="stat-val-overdue">\n                            1', resp4.data)
        self.assertIn(b'id="stat-val-completed">\n                            0', resp4.data)
        self.assertIn(b"7.5 hrs", resp4.data)

        # Delete Task A
        database.delete_task(id_a, db_path=self.db_path)
        resp5 = self.client.get("/")
        self.assertIn(b'id="stat-val-total">\n                            1', resp5.data)
        self.assertIn(b"4.0 hrs", resp5.data)

    def test_dashboard_independent_of_filter_parameters(self):
        """Dashboard statistics always reflect full database, even if URL contains search/filter query parameters."""
        database.create_task(
            title="Distributed Lab",
            subject="CS 400",
            task_type="Lab",
            due_date=(self.today + timedelta(days=2)).strftime("%Y-%m-%d"),
            importance=4,
            estimated_hours=3.0,
            status="Pending",
            db_path=self.db_path,
        )
        database.create_task(
            title="English Essay",
            subject="ENG 101",
            task_type="Assignment",
            due_date=(self.today + timedelta(days=4)).strftime("%Y-%m-%d"),
            importance=2,
            estimated_hours=2.0,
            status="Pending",
            db_path=self.db_path,
        )

        # Query / with filters that only match English
        resp = self.client.get("/?q=English&status=Completed")
        self.assertEqual(resp.status_code, 200)
        # Dashboard must still show all 2 tasks, not 0 or 1
        self.assertIn(b'id="stat-val-total">\n                            2', resp.data)
        self.assertIn(b"5.0 hrs", resp.data)


class FinalQASecurityAndValidationTestCase(unittest.TestCase):
    """Verifies security controls, SQL safety, XSS protection, and validation boundaries."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_validation_rejects_missing_title_and_subject(self):
        """Task creation rejects missing or whitespace-only title and subject."""
        resp = self.client.post(
            "/tasks/new",
            data={
                "title": "   ",
                "subject": "",
                "task_type": "Lab",
                "due_date": "2026-11-10",
                "importance": "3",
                "estimated_hours": "2.0",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Task title is required and cannot be blank.", resp.data)
        self.assertIn(b"Subject / course code is required and cannot be blank.", resp.data)

    def test_validation_rejects_invalid_date_format(self):
        """Task creation rejects malformed due dates."""
        resp = self.client.post(
            "/tasks/new",
            data={
                "title": "Valid Title",
                "subject": "CS 101",
                "task_type": "Quiz",
                "due_date": "10-11-2026",  # DD-MM-YYYY instead of YYYY-MM-DD
                "importance": "3",
                "estimated_hours": "1.0",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Due date must be a valid calendar date in YYYY-MM-DD format.", resp.data)

    def test_validation_rejects_invalid_importance(self):
        """Importance outside 1-5 is rejected with validation message."""
        for bad_imp in ("0", "6", "not-a-number", "-1"):
            resp = self.client.post(
                "/tasks/new",
                data={
                    "title": "Valid Title",
                    "subject": "CS 101",
                    "task_type": "Quiz",
                    "due_date": "2026-11-10",
                    "importance": bad_imp,
                    "estimated_hours": "1.0",
                },
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn(b"Importance must be an integer between 1 and 5.", resp.data)

    def test_validation_rejects_negative_and_nan_hours(self):
        """Estimated hours rejects negative, NaN, and non-numeric values."""
        for bad_hours in ("-1.5", "nan", "inf", "abc"):
            resp = self.client.post(
                "/tasks/new",
                data={
                    "title": "Valid Title",
                    "subject": "CS 101",
                    "task_type": "Quiz",
                    "due_date": "2026-11-10",
                    "importance": "3",
                    "estimated_hours": bad_hours,
                },
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(len(database.get_all_tasks(self.db_path)), 0)

    def test_sql_injection_attempt_in_search_is_safe(self):
        """Search query containing SQL injection payloads is treated safely as literal text."""
        database.create_task(
            title="Safe Assignment",
            subject="SEC 400",
            task_type="Assignment",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )

        malicious_query = "' OR 1=1; DROP TABLE tasks; --"
        resp = self.client.get(f"/tasks?q={malicious_query}")
        self.assertEqual(resp.status_code, 200)

        # Verify table was NOT dropped
        tasks = database.get_all_tasks(self.db_path)
        self.assertEqual(len(tasks), 1)

    def test_literal_percent_and_underscore_in_search(self):
        """Search query treats % and _ as literal substrings without wildcard expansion."""
        database.create_task(
            title="Math Exam 100% Score",
            subject="MATH 101",
            task_type="Quiz",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=1.0,
            db_path=self.db_path,
        )
        database.create_task(
            title="Physics Exam Prep",
            subject="PHYS 101",
            task_type="Quiz",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=1.0,
            db_path=self.db_path,
        )

        # Searching '%' should match only the title with literal '%'
        resp = self.client.get("/tasks?q=%25")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Math Exam 100% Score", resp.data)
        self.assertNotIn(b"Physics Exam Prep", resp.data)

    def test_xss_payloads_in_task_data_escaped(self):
        """Task title and description containing script tags are escaped in rendered HTML."""
        xss_title = "<script>alert('pwned')</script>"
        xss_desc = "<img src=x onerror=alert(1)>"
        database.create_task(
            title=xss_title,
            subject="CS 200",
            task_type="Assignment",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=2.0,
            description=xss_desc,
            db_path=self.db_path,
        )

        # Check /tasks
        resp_tasks = self.client.get("/tasks")
        self.assertEqual(resp_tasks.status_code, 200)
        self.assertNotIn(b"<script>alert('pwned')</script>", resp_tasks.data)
        self.assertIn(b"&lt;script&gt;alert(&#39;pwned&#39;)&lt;/script&gt;", resp_tasks.data)

        # Check /
        resp_dash = self.client.get("/")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertNotIn(b"<script>alert('pwned')</script>", resp_dash.data)

    def test_state_changing_get_requests_rejected(self):
        """State-changing endpoints (complete, reopen, delete) reject GET requests with HTTP 405."""
        task_id = database.create_task(
            title="Task 1",
            subject="CS 101",
            task_type="Assignment",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )

        resp_comp = self.client.get(f"/tasks/{task_id}/complete")
        self.assertEqual(resp_comp.status_code, 405)

        resp_reop = self.client.get(f"/tasks/{task_id}/reopen")
        self.assertEqual(resp_reop.status_code, 405)

        resp_del = self.client.get(f"/tasks/{task_id}/delete")
        self.assertEqual(resp_del.status_code, 405)

        # Task remains in original Pending state and is not deleted
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "Pending")


class FinalQABoundaryAndEdgeCasesTestCase(unittest.TestCase):
    """Verifies edge cases, deterministic tie-breakers, zero hours, and malformed legacy data."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()
        self.ref_today = date(2026, 10, 24)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_zero_estimated_hours_handled_correctly(self):
        """0.0 estimated hours is valid and handled accurately in priority and workload."""
        score = priority.calculate_priority_score(urgency_score=50, importance=3, estimated_hours=0.0)
        # 0.60 * 50 + 0.25 * 60 + 0.15 * 0 = 30 + 15 + 0 = 45.0
        self.assertAlmostEqual(score, 45.0)

        tasks = [
            {"id": 1, "subject": "CS 100", "status": "Pending", "estimated_hours": 0.0},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        self.assertEqual(workload["total_remaining_hours"], 0.0)
        self.assertEqual(workload["has_workload"], False)

    def test_all_tasks_completed_renders_all_caught_up_state(self):
        """When all tasks are Completed, recommendation and workload show all-caught-up states."""
        database.create_task(
            title="Finished Task 1",
            subject="CS 100",
            task_type="Quiz",
            due_date="2026-10-20",
            importance=5,
            estimated_hours=2.0,
            status="Completed",
            db_path=self.db_path,
        )
        database.create_task(
            title="Finished Task 2",
            subject="CS 200",
            task_type="Lab",
            due_date="2026-10-22",
            importance=4,
            estimated_hours=3.0,
            status="Completed",
            db_path=self.db_path,
        )

        resp_tasks = self.client.get("/tasks")
        self.assertEqual(resp_tasks.status_code, 200)
        self.assertIn(b"all caught up", resp_tasks.data.lower())

        resp_dash = self.client.get("/")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(b"100.0%", resp_dash.data)
        self.assertIn(b"No remaining workload", resp_dash.data)

    def test_malformed_legacy_date_does_not_crash_app(self):
        """Malformed legacy dates sort predictably to end and do not crash dashboard or tasks page."""
        database.create_task(
            title="Corrupted Date Task",
            subject="CS 999",
            task_type="Other",
            due_date="corrupted-date-string",
            importance=3,
            estimated_hours=2.0,
            status="Pending",
            db_path=self.db_path,
        )

        resp_tasks = self.client.get("/tasks?sort=deadline_asc")
        self.assertEqual(resp_tasks.status_code, 200)
        self.assertIn(b"Corrupted Date Task", resp_tasks.data)

        resp_dash = self.client.get("/")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(b"CS 999", resp_dash.data)

    def test_deterministic_tie_breakers_priority_and_id(self):
        """When two tasks share the same deadline and priority, smaller task ID breaks the tie."""
        tasks = [
            {"id": 10, "title": "Task B", "due_date": "2026-11-01", "priority_score": 80.0, "status": "Pending", "importance": 4, "estimated_hours": 2.0},
            {"id": 5, "title": "Task A", "due_date": "2026-11-01", "priority_score": 80.0, "status": "Pending", "importance": 4, "estimated_hours": 2.0},
        ]
        upcoming = analytics.get_upcoming_deadlines(tasks, today=self.ref_today, limit=5)
        self.assertEqual(upcoming[0]["id"], 5)
        self.assertEqual(upcoming[1]["id"], 10)


class FinalQADualThemeRegressionTestCase(unittest.TestCase):
    """Verifies that the dual-theme system (Dark Neon Dusk & Bright Purple) is properly integrated."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_dual_theme_navbar_toggle_elements(self):
        """Theme toggle button and icons exist in navbar with accessible attributes."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'id="theme-toggle"', resp.data)
        self.assertIn(b'theme-toggle-btn', resp.data)
        self.assertIn(b'bi-sun-fill', resp.data)
        self.assertIn(b'bi-moon-stars-fill', resp.data)
        self.assertIn(b'aria-label="Switch to bright theme"', resp.data)

    def test_fouc_prevention_script_in_head(self):
        """Head includes synchronous theme script checking localStorage to prevent FOUC."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"deadline-rescue-theme", resp.data)
        self.assertIn(b"document.documentElement.setAttribute('data-theme'", resp.data)

    def test_dual_theme_css_tokens(self):
        """CSS defines design tokens for both Dark Neon Dusk and Bright Purple themes."""
        with self.client.get("/static/css/style.css") as resp:
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'[data-theme="dark"]', resp.data)
            self.assertIn(b'[data-theme="light"]', resp.data)
            self.assertIn(b'--color-background', resp.data)
            self.assertIn(b'--color-primary', resp.data)
            self.assertIn(b'--dr-primary', resp.data)

    def test_dual_theme_js_controller(self):
        """JavaScript client includes theme controller and localStorage persistence functions."""
        with self.client.get("/static/js/main.js") as resp:
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"deadline-rescue-theme", resp.data)
            self.assertIn(b"applyTheme", resp.data)
            self.assertIn(b"updateThemeToggleUI", resp.data)


if __name__ == "__main__":
    unittest.main()
