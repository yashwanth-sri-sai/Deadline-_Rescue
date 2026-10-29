"""
Deadline Rescue — Step 6 Test Suite: Dashboard & Progress Analytics
Verifies:
1. Summary counts: Total, Pending, Completed, Overdue, Due Today, Due Soon.
2. Deadline boundaries: Overdue (past), Due Today (0), Due Soon (1-7 days),
   Completed tasks excluded, legacy/malformed dates excluded safely.
3. Completion percentage: 0 tasks -> 0%, division by zero protection, accurate rounding.
4. Workload by subject: Pending tasks only, case-insensitive subject deduplication,
   fallback to "Unspecified Subject", decimal hours, sum consistency.
5. Upcoming deadlines: up to 5 tasks, due today/future only, overdue/completed excluded,
   sorting by earliest deadline -> priority -> task ID tie-breaker.
6. Dashboard HTTP integration: GET / returns 200, summary cards, progress bar,
   upcoming deadlines table, workload section, empty database state, XSS escaping,
   and static assets.
7. Step 1-5 regression safety.
"""

from datetime import date, datetime, timedelta
import os
import tempfile
import unittest

from app import create_app
import analytics
import database
import priority


class AnalyticsUnitTestCase(unittest.TestCase):
    """Unit tests for analytics.py functions using fixed reference dates."""

    def setUp(self):
        self.ref_today = date(2026, 10, 24)

    def test_summary_empty_tasks(self):
        """Empty task list produces all zeros and 0.0% completion."""
        summary = analytics.get_summary_stats([], today=self.ref_today)
        self.assertEqual(summary["total_tasks"], 0)
        self.assertEqual(summary["pending_tasks"], 0)
        self.assertEqual(summary["completed_tasks"], 0)
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["due_soon_tasks"], 0)
        self.assertEqual(summary["completion_percentage"], 0.0)

    def test_summary_all_pending(self):
        """All pending tasks produce 0.0% completion percentage."""
        tasks = [
            {"id": 1, "title": "T1", "status": "Pending", "due_date": "2026-10-30", "importance": 3, "estimated_hours": 2.0},
            {"id": 2, "title": "T2", "status": "Pending", "due_date": "2026-11-05", "importance": 4, "estimated_hours": 4.0},
        ]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["total_tasks"], 2)
        self.assertEqual(summary["pending_tasks"], 2)
        self.assertEqual(summary["completed_tasks"], 0)
        self.assertEqual(summary["completion_percentage"], 0.0)

    def test_summary_all_completed(self):
        """All completed tasks produce 100.0% completion percentage."""
        tasks = [
            {"id": 1, "title": "T1", "status": "Completed", "due_date": "2026-10-20", "importance": 3, "estimated_hours": 2.0},
            {"id": 2, "title": "T2", "status": "Completed", "due_date": "2026-10-24", "importance": 4, "estimated_hours": 4.0},
        ]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["total_tasks"], 2)
        self.assertEqual(summary["pending_tasks"], 0)
        self.assertEqual(summary["completed_tasks"], 2)
        self.assertEqual(summary["completion_percentage"], 100.0)
        # Completed tasks must never count as overdue or due today
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 0)

    def test_summary_mixed_counts(self):
        """Mixed tasks correctly count total, pending, completed, and completion %."""
        tasks = [
            {"id": 1, "title": "T1", "status": "Completed", "due_date": "2026-10-20"},
            {"id": 2, "title": "T2", "status": "Pending", "due_date": "2026-10-26"},
            {"id": 3, "title": "T3", "status": "Pending", "due_date": "2026-10-28"},
            {"id": 4, "title": "T4", "status": "Completed", "due_date": "2026-10-22"},
        ]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["total_tasks"], 4)
        self.assertEqual(summary["pending_tasks"], 2)
        self.assertEqual(summary["completed_tasks"], 2)
        self.assertEqual(summary["completion_percentage"], 50.0)

    def test_boundary_overdue_one_day(self):
        """Task due yesterday (1 day overdue) is counted as overdue."""
        yesterday = (self.ref_today - timedelta(days=1)).strftime("%Y-%m-%d")
        tasks = [{"id": 1, "title": "T1", "status": "Pending", "due_date": yesterday}]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["overdue_tasks"], 1)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["due_soon_tasks"], 0)

    def test_boundary_overdue_multiple_days(self):
        """Task due 7 days ago is counted as overdue."""
        past = (self.ref_today - timedelta(days=7)).strftime("%Y-%m-%d")
        tasks = [{"id": 1, "title": "T1", "status": "Pending", "due_date": past}]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["overdue_tasks"], 1)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["due_soon_tasks"], 0)

    def test_boundary_due_today(self):
        """Task due today is counted in due_today, NOT overdue or due soon."""
        today_str = self.ref_today.strftime("%Y-%m-%d")
        tasks = [{"id": 1, "title": "T1", "status": "Pending", "due_date": today_str}]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 1)
        self.assertEqual(summary["due_soon_tasks"], 0)

    def test_boundary_due_tomorrow(self):
        """Task due tomorrow (days_remaining = 1) is counted in due_soon."""
        tomorrow_str = (self.ref_today + timedelta(days=1)).strftime("%Y-%m-%d")
        tasks = [{"id": 1, "title": "T1", "status": "Pending", "due_date": tomorrow_str}]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["due_soon_tasks"], 1)

    def test_boundary_due_in_seven_days(self):
        """Task due exactly 7 days from today (days_remaining = 7) is counted in due_soon."""
        day7_str = (self.ref_today + timedelta(days=7)).strftime("%Y-%m-%d")
        tasks = [{"id": 1, "title": "T1", "status": "Pending", "due_date": day7_str}]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["due_soon_tasks"], 1)

    def test_boundary_due_in_eight_days(self):
        """Task due 8 days from today (days_remaining = 8) is NOT counted in due_soon."""
        day8_str = (self.ref_today + timedelta(days=8)).strftime("%Y-%m-%d")
        tasks = [{"id": 1, "title": "T1", "status": "Pending", "due_date": day8_str}]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["due_soon_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["overdue_tasks"], 0)

    def test_completed_tasks_excluded_from_deadlines(self):
        """Completed tasks are strictly excluded from overdue, due today, and due soon."""
        past_str = (self.ref_today - timedelta(days=3)).strftime("%Y-%m-%d")
        today_str = self.ref_today.strftime("%Y-%m-%d")
        future_str = (self.ref_today + timedelta(days=2)).strftime("%Y-%m-%d")
        tasks = [
            {"id": 1, "title": "T1", "status": "Completed", "due_date": past_str},
            {"id": 2, "title": "T2", "status": "Completed", "due_date": today_str},
            {"id": 3, "title": "T3", "status": "Completed", "due_date": future_str},
        ]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["due_soon_tasks"], 0)
        self.assertEqual(summary["completed_tasks"], 3)

    def test_invalid_or_missing_deadline(self):
        """Tasks with invalid or missing deadlines are handled safely and not counted in boundaries."""
        tasks = [
            {"id": 1, "title": "T1", "status": "Pending", "due_date": "not-a-date"},
            {"id": 2, "title": "T2", "status": "Pending", "due_date": ""},
            {"id": 3, "title": "T3", "status": "Pending", "due_date": None},
        ]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertEqual(summary["total_tasks"], 3)
        self.assertEqual(summary["pending_tasks"], 3)
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["due_today_tasks"], 0)
        self.assertEqual(summary["due_soon_tasks"], 0)

    def test_completion_percentage_fractional(self):
        """Fractional completion percentage is accurately calculated."""
        tasks = [
            {"id": 1, "status": "Completed"},
            {"id": 2, "status": "Pending"},
            {"id": 3, "status": "Pending"},
        ]
        summary = analytics.get_summary_stats(tasks, today=self.ref_today)
        self.assertAlmostEqual(summary["completion_percentage"], 33.333333333333336, places=5)

    def test_workload_by_subject_pending_only(self):
        """Workload only counts Pending tasks towards remaining hours."""
        tasks = [
            {"id": 1, "subject": "CS 420", "status": "Pending", "estimated_hours": 3.5},
            {"id": 2, "subject": "CS 420", "status": "Completed", "estimated_hours": 5.0},
            {"id": 3, "subject": "CS 420", "status": "Pending", "estimated_hours": 2.0},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        self.assertEqual(len(workload["subjects"]), 1)
        subj = workload["subjects"][0]
        self.assertEqual(subj["subject"], "CS 420")
        self.assertEqual(subj["pending_tasks"], 2)
        self.assertEqual(subj["completed_tasks"], 1)
        self.assertEqual(subj["remaining_hours"], 5.5)
        self.assertEqual(workload["total_remaining_hours"], 5.5)

    def test_workload_different_subjects_sorted(self):
        """Workload returns subjects sorted alphabetically."""
        tasks = [
            {"id": 1, "subject": "Web Security", "status": "Pending", "estimated_hours": 2.0},
            {"id": 2, "subject": "Algorithms", "status": "Pending", "estimated_hours": 4.0},
            {"id": 3, "subject": "Data Mining", "status": "Pending", "estimated_hours": 1.5},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        subjects = [s["subject"] for s in workload["subjects"]]
        self.assertEqual(subjects, ["Algorithms", "Data Mining", "Web Security"])
        self.assertEqual(workload["total_remaining_hours"], 7.5)

    def test_workload_case_insensitivity(self):
        """Subjects differing only in capitalization are grouped together without duplication."""
        tasks = [
            {"id": 1, "subject": "cs 101", "status": "Pending", "estimated_hours": 2.0},
            {"id": 2, "subject": "CS 101", "status": "Pending", "estimated_hours": 3.0},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        self.assertEqual(len(workload["subjects"]), 1)
        self.assertEqual(workload["subjects"][0]["pending_tasks"], 2)
        self.assertEqual(workload["subjects"][0]["remaining_hours"], 5.0)

    def test_workload_empty_subject_fallback(self):
        """Blank or missing subjects fall back to 'Unspecified Subject'."""
        tasks = [
            {"id": 1, "subject": "", "status": "Pending", "estimated_hours": 2.0},
            {"id": 2, "subject": None, "status": "Pending", "estimated_hours": 1.5},
            {"id": 3, "subject": "   ", "status": "Pending", "estimated_hours": 0.5},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        self.assertEqual(len(workload["subjects"]), 1)
        self.assertEqual(workload["subjects"][0]["subject"], "Unspecified Subject")
        self.assertEqual(workload["subjects"][0]["pending_tasks"], 3)
        self.assertEqual(workload["subjects"][0]["remaining_hours"], 4.0)

    def test_workload_zero_and_decimal_hours(self):
        """Zero-hour tasks and decimal hours are safely accumulated."""
        tasks = [
            {"id": 1, "subject": "Math", "status": "Pending", "estimated_hours": 0.0},
            {"id": 2, "subject": "Math", "status": "Pending", "estimated_hours": 1.25},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        self.assertEqual(workload["subjects"][0]["remaining_hours"], 1.25)
        self.assertEqual(workload["total_remaining_hours"], 1.25)

    def test_workload_malformed_estimated_hours(self):
        """Non-numeric or malformed estimated_hours falls back safely to 0.0."""
        tasks = [
            {"id": 1, "subject": "Bio", "status": "Pending", "estimated_hours": "invalid"},
            {"id": 2, "subject": "Bio", "status": "Pending", "estimated_hours": -5.0},
            {"id": 3, "subject": "Bio", "status": "Pending", "estimated_hours": 3.0},
        ]
        workload = analytics.get_workload_by_subject(tasks)
        self.assertEqual(workload["subjects"][0]["remaining_hours"], 3.0)

    def test_upcoming_deadlines_selection(self):
        """Upcoming deadlines include only Pending tasks due today or future, capped at 5."""
        tasks = [
            {"id": 1, "title": "Overdue Task", "status": "Pending", "due_date": "2026-10-20", "importance": 5, "estimated_hours": 2.0},
            {"id": 2, "title": "Due Today Task", "status": "Pending", "due_date": "2026-10-24", "importance": 4, "estimated_hours": 2.0},
            {"id": 3, "title": "Completed Task", "status": "Completed", "due_date": "2026-10-25", "importance": 5, "estimated_hours": 2.0},
            {"id": 4, "title": "Tomorrow Task", "status": "Pending", "due_date": "2026-10-25", "importance": 3, "estimated_hours": 2.0},
            {"id": 5, "title": "Next Week Task", "status": "Pending", "due_date": "2026-10-31", "importance": 2, "estimated_hours": 2.0},
            {"id": 6, "title": "Next Month Task 1", "status": "Pending", "due_date": "2026-11-10", "importance": 1, "estimated_hours": 2.0},
            {"id": 7, "title": "Next Month Task 2", "status": "Pending", "due_date": "2026-11-15", "importance": 1, "estimated_hours": 2.0},
            {"id": 8, "title": "Next Month Task 3", "status": "Pending", "due_date": "2026-11-20", "importance": 1, "estimated_hours": 2.0},
        ]
        upcoming = analytics.get_upcoming_deadlines(tasks, today=self.ref_today, limit=5)
        self.assertEqual(len(upcoming), 5)
        # Verify overdue and completed are excluded
        upcoming_titles = [t["title"] for t in upcoming]
        self.assertNotIn("Overdue Task", upcoming_titles)
        self.assertNotIn("Completed Task", upcoming_titles)
        # Verify Due Today is first
        self.assertEqual(upcoming[0]["title"], "Due Today Task")
        self.assertEqual(upcoming[1]["title"], "Tomorrow Task")

    def test_upcoming_deadlines_priority_and_id_tie_breakers(self):
        """Same due date orders by higher priority score, then lowest task ID."""
        tasks = [
            # Same due date (2026-10-26):
            {"id": 10, "title": "Same Date Low Priority", "status": "Pending", "due_date": "2026-10-26", "importance": 1, "estimated_hours": 1.0},
            {"id": 5, "title": "Same Date High Priority", "status": "Pending", "due_date": "2026-10-26", "importance": 5, "estimated_hours": 10.0},
            {"id": 2, "title": "Same Date High Priority Lower ID", "status": "Pending", "due_date": "2026-10-26", "importance": 5, "estimated_hours": 10.0},
        ]
        upcoming = analytics.get_upcoming_deadlines(tasks, today=self.ref_today, limit=5)
        self.assertEqual(len(upcoming), 3)
        # ID 2 and ID 5 have same date and same priority score; ID 2 has smaller ID
        self.assertEqual(upcoming[0]["id"], 2)
        self.assertEqual(upcoming[1]["id"], 5)
        self.assertEqual(upcoming[2]["id"], 10)


class DashboardIntegrationTestCase(unittest.TestCase):
    """Integration tests for the Flask dashboard route, templates, and full app stack."""

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

    def test_dashboard_empty_db_returns_200(self):
        """GET / on empty database returns HTTP 200 and renders empty state."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Academic Command Center", response.data)
        self.assertIn(b"No coursework recorded yet", response.data)
        self.assertIn(b"Add Your First Task", response.data)

    def test_dashboard_renders_summary_cards_and_progress(self):
        """GET / with populated database displays all 6 metric cards and progress percentage."""
        # Seed 1 completed, 1 pending due today, 1 pending overdue, 1 pending due soon
        today_str = date.today().strftime("%Y-%m-%d")
        past_str = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        soon_str = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")

        database.create_task(
            title="Completed Task",
            subject="CS 101",
            task_type="Assignment",
            due_date=past_str,
            importance=3,
            estimated_hours=2.0,
            status="Completed",
            db_path=self.db_path,
        )
        database.create_task(
            title="Overdue Task",
            subject="CS 101",
            task_type="Lab",
            due_date=past_str,
            importance=4,
            estimated_hours=3.0,
            status="Pending",
            db_path=self.db_path,
        )
        database.create_task(
            title="Due Today Task",
            subject="MATH 201",
            task_type="Quiz",
            due_date=today_str,
            importance=5,
            estimated_hours=1.5,
            status="Pending",
            db_path=self.db_path,
        )
        database.create_task(
            title="Due Soon Task",
            subject="MATH 201",
            task_type="Assignment",
            due_date=soon_str,
            importance=2,
            estimated_hours=2.5,
            status="Pending",
            db_path=self.db_path,
        )

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # Total: 4, Pending: 3, Completed: 1, Overdue: 1, Due Today: 1, Due Soon: 1
        # Completion: 1 / 4 * 100 = 25.0%
        self.assertIn(b"stat-card-total", response.data)
        self.assertIn(b"stat-card-pending", response.data)
        self.assertIn(b"stat-card-completed", response.data)
        self.assertIn(b"stat-card-overdue", response.data)
        self.assertIn(b"stat-card-due-today", response.data)
        self.assertIn(b"stat-card-due-soon", response.data)

        # Completion percentage badge & progress bar
        self.assertIn(b"25.0%", response.data)
        self.assertIn(b"1</strong> of <strong class=\"text-slate-900\">4</strong> tasks completed", response.data)

        # Workload section: CS 101: 3.0 hrs, MATH 201: 4.0 hrs, Total: 7.0 hrs
        self.assertIn(b"CS 101", response.data)
        self.assertIn(b"MATH 201", response.data)
        self.assertIn(b"7.0 hrs", response.data)

        # Upcoming deadlines: Due Today Task and Due Soon Task are present; Overdue is excluded
        self.assertIn(b"Due Today Task", response.data)
        self.assertIn(b"Due Soon Task", response.data)
        self.assertNotIn(b"upcoming-row-2", response.data)  # Task 2 is overdue

    def test_dashboard_malformed_legacy_date_resilience(self):
        """Dashboard does not crash when database contains legacy malformed date strings."""
        database.create_task(
            title="Malformed Date Task",
            subject="CS 999",
            task_type="Other",
            due_date="not-a-valid-date",
            importance=3,
            estimated_hours=2.0,
            status="Pending",
            db_path=self.db_path,
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CS 999", response.data)
        self.assertIn(b"1 Total Tasks", response.data)

    def test_dashboard_xss_escaping(self):
        """Task titles and subjects containing HTML tags are escaped in the dashboard template."""
        database.create_task(
            title="<script>alert('xss')</script>",
            subject="<b>Security</b>",
            task_type="Assignment",
            due_date=date.today().strftime("%Y-%m-%d"),
            importance=5,
            estimated_hours=1.0,
            status="Pending",
            db_path=self.db_path,
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<script>alert('xss')</script>", response.data)
        self.assertIn(b"&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;", response.data)

    def test_dashboard_static_assets_return_200(self):
        """Static CSS and JavaScript assets are accessible and return HTTP 200."""
        with self.client.get("/static/css/style.css") as css_resp:
            self.assertEqual(css_resp.status_code, 200)
            self.assertIn(b".stat-card", css_resp.data)

        with self.client.get("/static/js/main.js") as js_resp:
            self.assertEqual(js_resp.status_code, 200)
            self.assertIn(b"Step 6", js_resp.data)


class Step6RegressionTestCase(unittest.TestCase):
    """Verifies that all Step 1-5 features continue to work flawlessly."""

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

    def test_crud_and_filters_regression(self):
        """Verify task creation, editing, completion, search, and sorting remain 100% functional."""
        # 1. Create a task via POST
        create_resp = self.client.post(
            "/tasks/new",
            data={
                "title": "Regression Verification Task",
                "subject": "CS 500",
                "task_type": "Project",
                "due_date": "2026-11-01",
                "importance": "5",
                "estimated_hours": "6.5",
            },
            follow_redirects=True,
        )
        self.assertEqual(create_resp.status_code, 200)
        self.assertIn(b"Regression Verification Task", create_resp.data)

        # 2. Complete task
        tasks = database.get_all_tasks(self.db_path)
        self.assertEqual(len(tasks), 1)
        task_id = tasks[0]["id"]

        comp_resp = self.client.post(f"/tasks/{task_id}/complete", follow_redirects=True)
        self.assertEqual(comp_resp.status_code, 200)

        completed_task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(completed_task["status"], "Completed")

        # 3. Reopen task
        reopen_resp = self.client.post(f"/tasks/{task_id}/reopen", follow_redirects=True)
        self.assertEqual(reopen_resp.status_code, 200)

        reopened_task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(reopened_task["status"], "Pending")

        # 4. Search and filter on /tasks
        filter_resp = self.client.get("/tasks?q=Regression&status=Pending&sort=deadline_asc")
        self.assertEqual(filter_resp.status_code, 200)
        self.assertIn(b"Regression Verification Task", filter_resp.data)

        # 5. Delete task
        del_resp = self.client.post(f"/tasks/{task_id}/delete", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(len(database.get_all_tasks(self.db_path)), 0)


if __name__ == "__main__":
    unittest.main()
