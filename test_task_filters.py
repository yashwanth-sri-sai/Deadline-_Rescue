"""
Deadline Rescue — Step 5 Test Suite: Smart Search, Filtering & Sorting
Verifies:
1. Search by full/partial title, subject, case-insensitivity, whitespace trimming, %, _.
2. Status filter (All, Pending, Completed, invalid fallback).
3. Subject filter (dropdown deduplication, alphabetical sorting, safe filtering).
4. Priority filter (Critical, High, Medium, Low, invalid fallback).
5. Combined multi-criteria filtering (search + status + subject + priority).
6. Sorting (recommended, deadline_asc, deadline_desc, priority_desc, priority_asc,
   title_asc, title_desc, created_desc, tie-breakers, malformed date resilience).
7. Step 4 Recommendation Independence (recommendation remains global highest pending task).
8. Empty states distinction (empty DB vs no matching search results).
9. Integration and regression safety.
"""

from datetime import date, datetime, timedelta
import os
import tempfile
import unittest

from app import create_app
import database
import priority


class TaskFiltersTestCase(unittest.TestCase):
    def setUp(self):
        """Set up an isolated temporary SQLite database for each test case."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

        # Fixed reference date for deterministic priority calculation: 2026-10-24
        self.ref_today = date(2026, 10, 24)

    def tearDown(self):
        """Remove the temporary SQLite database file after each test."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def _seed_standard_tasks(self):
        """
        Helper to seed a diverse set of tasks covering various subjects,
        statuses, deadlines, importances, and efforts.
        Reference date: 2026-10-24.
        """
        # 1. Overdue, Pending, Critical (U=100, I=5, H=8 -> 100.0)
        id1 = database.create_task(
            title="Operating Systems Kernel Lab",
            subject="CS 401",
            task_type="Lab",
            due_date="2026-10-20",  # 4 days overdue
            importance=5,
            estimated_hours=8.0,
            status="Pending",
            db_path=self.db_path,
        )

        # 2. Due Tomorrow, Pending, Critical (U=90, I=5, H=6 -> 90.25)
        id2 = database.create_task(
            title="Linear Algebra Homework 4",
            subject="MATH 201",
            task_type="Assignment",
            due_date="2026-10-25",  # due tomorrow
            importance=5,
            estimated_hours=6.0,
            status="Pending",
            db_path=self.db_path,
        )

        # 3. Due in 5 Days, Pending, High (U=50, I=4, H=4 -> 57.5)
        id3 = database.create_task(
            title="Database B-Tree Indexing Project",
            subject="CS 320",
            task_type="Project",
            due_date="2026-10-29",  # due in 5 days
            importance=4,
            estimated_hours=4.0,
            status="Pending",
            db_path=self.db_path,
        )

        # 4. Due in 20 Days, Pending, Medium (U=10, I=3, H=2 -> 24.75)
        id4 = database.create_task(
            title="Ethics in AI Essay",
            subject="PHIL 105",
            task_type="Assignment",
            due_date="2026-11-13",  # due in 20 days
            importance=3,
            estimated_hours=2.0,
            status="Pending",
            db_path=self.db_path,
        )

        # 5. Overdue, Completed, Critical (U=100, I=5, H=4 -> 92.5)
        id5 = database.create_task(
            title="Computer Networks Quiz Review",
            subject="CS 401",
            task_type="Quiz",
            due_date="2026-10-15",
            importance=5,
            estimated_hours=4.0,
            status="Completed",
            db_path=self.db_path,
        )

        # 6. Due in 10 Days, Completed, Medium (U=30, I=2, H=1 -> 29.88)
        id6 = database.create_task(
            title="Physics Lab 3 Report",
            subject="PHY 101",
            task_type="Lab",
            due_date="2026-11-03",
            importance=2,
            estimated_hours=1.0,
            status="Completed",
            db_path=self.db_path,
        )

        return [id1, id2, id3, id4, id5, id6]

    # ----------------------------------------------------------------------
    # A. Search Tests
    # ----------------------------------------------------------------------

    def test_01_search_by_full_title(self):
        """Search matches exact full title case-insensitively."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?q=Ethics in AI Essay")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ethics in AI Essay", resp.data)
        # Operating Systems Kernel Lab is in the global Recommended card, but NOT in the table
        self.assertNotIn(b'id="task-row-1"', resp.data)
        self.assertNotIn(b"Linear Algebra Homework 4", resp.data)

    def test_02_search_by_partial_title(self):
        """Search matches partial words in task title."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?q=kernel")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        self.assertNotIn(b"Linear Algebra", resp.data)

    def test_03_search_by_subject(self):
        """Search matches subject code."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?q=CS 401")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        self.assertIn(b"Computer Networks Quiz Review", resp.data)
        self.assertNotIn(b"Linear Algebra", resp.data)

    def test_04_search_case_insensitivity(self):
        """Search is case-insensitive for both uppercase and lowercase input."""
        self._seed_standard_tasks()
        resp_upper = self.client.get("/tasks?q=MATH")
        resp_lower = self.client.get("/tasks?q=math")
        self.assertIn(b"Linear Algebra Homework 4", resp_upper.data)
        self.assertIn(b"Linear Algebra Homework 4", resp_lower.data)

    def test_05_search_leading_and_trailing_whitespace(self):
        """Search query is trimmed of leading and trailing whitespace."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?q=%20%20B-Tree%20%20")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Database B-Tree Indexing Project", resp.data)

    def test_06_empty_or_whitespace_search_returns_all_tasks(self):
        """Empty or whitespace-only search does not filter tasks."""
        self._seed_standard_tasks()
        resp_empty = self.client.get("/tasks?q=")
        resp_spaces = self.client.get("/tasks?q=%20%20%20")
        self.assertIn(b"Showing <strong>6</strong> of <strong>6</strong> tasks", resp_empty.data)
        self.assertIn(b"Showing <strong>6</strong> of <strong>6</strong> tasks", resp_spaces.data)

    def test_07_search_literal_wildcards_percent_and_underscore(self):
        """Search treats % and _ as literal substrings without wildcard behavior."""
        database.create_task(
            title="100% Completion Goal",
            subject="CS_101",
            task_type="Assignment",
            due_date="2026-11-01",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )
        database.create_task(
            title="Regular Homework",
            subject="CS 101",
            task_type="Assignment",
            due_date="2026-11-01",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )

        # Searching '%' should only match "100% Completion Goal"
        resp_pct = self.client.get("/tasks?q=%25")
        self.assertEqual(resp_pct.status_code, 200)
        self.assertIn(b"100% Completion Goal", resp_pct.data)
        self.assertNotIn(b"Regular Homework", resp_pct.data)

        # Searching '_' should only match "CS_101"
        resp_und = self.client.get("/tasks?q=_")
        self.assertEqual(resp_und.status_code, 200)
        self.assertIn(b"100% Completion Goal", resp_und.data)
        self.assertNotIn(b"Regular Homework", resp_und.data)

    def test_08_search_no_matches_shows_filter_empty_state(self):
        """When search finds 0 matches in populated DB, displays specific empty state."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?q=NonExistentQueryXYZ")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No tasks match your search or filters", resp.data)
        self.assertIn(b"Clear Filters", resp.data)
        self.assertIn(b'value="NonExistentQueryXYZ"', resp.data)

    # ----------------------------------------------------------------------
    # B. Status Filter Tests
    # ----------------------------------------------------------------------

    def test_09_status_filter_pending_only(self):
        """Status filter 'Pending' returns only pending tasks."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?status=Pending")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        self.assertIn(b"Linear Algebra Homework 4", resp.data)
        self.assertIn(b"Database B-Tree Indexing Project", resp.data)
        self.assertIn(b"Ethics in AI Essay", resp.data)
        self.assertNotIn(b"Computer Networks Quiz Review", resp.data)
        self.assertNotIn(b"Physics Lab 3 Report", resp.data)

    def test_10_status_filter_completed_only(self):
        """Status filter 'Completed' returns only completed tasks."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?status=Completed")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Computer Networks Quiz Review", resp.data)
        self.assertIn(b"Physics Lab 3 Report", resp.data)
        # Pending tasks are not in the table
        self.assertNotIn(b'id="task-row-1"', resp.data)
        self.assertNotIn(b"Linear Algebra Homework 4", resp.data)

    def test_11_status_filter_all_or_invalid_normalizes(self):
        """Invalid status parameter safely normalizes to all tasks."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?status=InvalidStatus123")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Showing <strong>6</strong> of <strong>6</strong> tasks", resp.data)

    def test_12_status_combined_with_search(self):
        """Status filter and search query combine with AND logic."""
        self._seed_standard_tasks()
        # Search "CS 401" with Pending status -> only OS Kernel Lab (Computer Networks is Completed)
        resp = self.client.get("/tasks?q=CS+401&status=Pending")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        self.assertNotIn(b"Computer Networks Quiz Review", resp.data)

    # ----------------------------------------------------------------------
    # C. Subject Filter Tests
    # ----------------------------------------------------------------------

    def test_13_subject_filter_matches_exact_subject(self):
        """Subject filter isolates tasks belonging to that specific subject."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?subject=MATH+201")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Linear Algebra Homework 4", resp.data)
        # Non-math tasks are not in the table
        self.assertNotIn(b'id="task-row-1"', resp.data)
        self.assertNotIn(b"Database B-Tree Indexing Project", resp.data)

    def test_14_subject_dropdown_deduplication_and_sorting(self):
        """Subject options in dropdown are unique and sorted alphabetically."""
        self._seed_standard_tasks()
        # CS 401 has 2 tasks; MATH 201, CS 320, PHIL 105, PHY 101 have 1 each
        tasks = database.get_all_tasks(self.db_path)
        subjects = priority.get_distinct_subjects(tasks)
        expected = ["CS 320", "CS 401", "MATH 201", "PHIL 105", "PHY 101"]
        self.assertEqual(subjects, expected)

    def test_15_empty_database_subject_extraction(self):
        """get_distinct_subjects returns empty list for empty database without error."""
        subjects = priority.get_distinct_subjects([])
        self.assertEqual(subjects, [])

    # ----------------------------------------------------------------------
    # D. Priority Filter Tests
    # ----------------------------------------------------------------------

    def test_16_priority_filter_critical(self):
        """Priority filter 'Critical' returns only Critical-labeled tasks."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?priority=Critical")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        self.assertIn(b"Linear Algebra Homework 4", resp.data)
        self.assertNotIn(b"Database B-Tree Indexing Project", resp.data)  # High
        self.assertNotIn(b"Ethics in AI Essay", resp.data)  # Low/Medium

    def test_17_priority_filter_invalid_fallback(self):
        """Invalid priority parameter safely normalizes to all tasks."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?priority=UltraCritical")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Showing <strong>6</strong> of <strong>6</strong> tasks", resp.data)

    def test_18_combined_all_filters_together(self):
        """Search, status, subject, and priority work simultaneously (AND logic)."""
        self._seed_standard_tasks()
        # q="Lab", status="Pending", subject="CS 401", priority="Critical"
        resp = self.client.get("/tasks?q=Lab&status=Pending&subject=CS+401&priority=Critical")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        self.assertIn(b"Showing <strong>1</strong> of <strong>6</strong> tasks", resp.data)

    # ----------------------------------------------------------------------
    # E. Sorting Tests
    # ----------------------------------------------------------------------

    def test_19_sort_recommended_priority(self):
        """Sort by 'recommended' puts highest priority first, with earlier deadline tie-breaker."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?sort=recommended")
        self.assertEqual(resp.status_code, 200)
        tasks = database.get_all_tasks(self.db_path)
        sorted_tasks = priority.filter_and_sort_tasks(tasks, sort_by="recommended", today=self.ref_today)
        # ID 1 (OS Kernel, score 100.0) should be first
        self.assertEqual(sorted_tasks[0]["id"], 1)

    def test_20_sort_deadline_earliest_first(self):
        """Sort by 'deadline_asc' puts earliest deadline first."""
        self._seed_standard_tasks()
        tasks = database.get_all_tasks(self.db_path)
        sorted_tasks = priority.filter_and_sort_tasks(tasks, sort_by="deadline_asc", today=self.ref_today)
        # 2026-10-15 (Networks Quiz, ID 5) is the earliest deadline
        self.assertEqual(sorted_tasks[0]["due_date"], "2026-10-15")
        self.assertEqual(sorted_tasks[-1]["due_date"], "2026-11-13")

    def test_21_sort_deadline_latest_first(self):
        """Sort by 'deadline_desc' puts latest deadline first."""
        self._seed_standard_tasks()
        tasks = database.get_all_tasks(self.db_path)
        sorted_tasks = priority.filter_and_sort_tasks(tasks, sort_by="deadline_desc", today=self.ref_today)
        # 2026-11-13 (Ethics, ID 4) is the latest deadline
        self.assertEqual(sorted_tasks[0]["due_date"], "2026-11-13")
        self.assertEqual(sorted_tasks[-1]["due_date"], "2026-10-15")

    def test_22_sort_priority_highest_and_lowest_first(self):
        """Sort by 'priority_desc' and 'priority_asc' orders by priority score."""
        self._seed_standard_tasks()
        tasks = database.get_all_tasks(self.db_path)
        sorted_desc = priority.filter_and_sort_tasks(tasks, sort_by="priority_desc", today=self.ref_today)
        sorted_asc = priority.filter_and_sort_tasks(tasks, sort_by="priority_asc", today=self.ref_today)

        # Highest score >= second highest
        self.assertGreaterEqual(sorted_desc[0]["priority_score"], sorted_desc[1]["priority_score"])
        # Lowest score <= second lowest
        self.assertLessEqual(sorted_asc[0]["priority_score"], sorted_asc[1]["priority_score"])

    def test_23_sort_title_az_and_za(self):
        """Sort by title A-Z and Z-A case-insensitively."""
        self._seed_standard_tasks()
        tasks = database.get_all_tasks(self.db_path)
        az_tasks = priority.filter_and_sort_tasks(tasks, sort_by="title_asc")
        za_tasks = priority.filter_and_sort_tasks(tasks, sort_by="title_desc")

        self.assertEqual(az_tasks[0]["title"], "Computer Networks Quiz Review")
        self.assertEqual(az_tasks[-1]["title"], "Physics Lab 3 Report")

        self.assertEqual(za_tasks[0]["title"], "Physics Lab 3 Report")
        self.assertEqual(za_tasks[-1]["title"], "Computer Networks Quiz Review")

    def test_24_sort_newest_first(self):
        """Sort by 'created_desc' places most recently created tasks first."""
        self._seed_standard_tasks()
        tasks = database.get_all_tasks(self.db_path)
        newest = priority.filter_and_sort_tasks(tasks, sort_by="created_desc")
        # ID 6 was inserted last
        self.assertEqual(newest[0]["id"], 6)

    def test_25_sort_malformed_legacy_dates_handled_safely(self):
        """Tasks with malformed dates sort predictably to end without crashing."""
        database.create_task(
            title="Corrupted Date Task",
            subject="CS 000",
            task_type="Other",
            due_date="not-a-date",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )
        database.create_task(
            title="Valid Date Task",
            subject="CS 001",
            task_type="Assignment",
            due_date="2026-11-01",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )
        tasks = database.get_all_tasks(self.db_path)
        sorted_asc = priority.filter_and_sort_tasks(tasks, sort_by="deadline_asc")
        # Valid date should come before corrupted date
        self.assertEqual(sorted_asc[0]["title"], "Valid Date Task")
        self.assertEqual(sorted_asc[1]["title"], "Corrupted Date Task")

    def test_26_sort_invalid_fallback_to_recommended(self):
        """Invalid sort option safely falls back to 'recommended'."""
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?sort=hacker_sort")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)

    # ----------------------------------------------------------------------
    # F. Step 4 Recommendation Semantics Preservation Tests
    # ----------------------------------------------------------------------

    def test_27_recommendation_independent_of_status_filter(self):
        """
        Filtering to status=Completed does NOT change recommendation to completed task.
        Recommendation remains the global highest-priority Pending task.
        """
        self._seed_standard_tasks()
        resp = self.client.get("/tasks?status=Completed")
        self.assertEqual(resp.status_code, 200)

        # Recommendation section must still recommend Operating Systems Kernel Lab (Pending)
        self.assertIn(b"Recommended Next Task", resp.data)
        # Recommendation heading contains title
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)

        # The table below only displays completed tasks
        self.assertIn(b"Computer Networks Quiz Review", resp.data)
        self.assertIn(b"Physics Lab 3 Report", resp.data)

    def test_28_recommendation_independent_of_search(self):
        """Searching for one subject does NOT restrict recommendation to that subject."""
        self._seed_standard_tasks()
        # Search for MATH 201; recommendation should still be Operating Systems Kernel Lab (CS 401)
        resp = self.client.get("/tasks?q=MATH")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)
        # Table only contains Linear Algebra
        self.assertIn(b"Linear Algebra Homework 4", resp.data)

    def test_29_recommendation_independent_of_sorting(self):
        """Changing task list sort does NOT alter recommended next task."""
        self._seed_standard_tasks()
        # Sort by title A-Z (which puts Computer Networks Quiz Review first in table)
        resp = self.client.get("/tasks?sort=title_asc")
        self.assertEqual(resp.status_code, 200)
        # Recommendation is still Operating Systems Kernel Lab
        self.assertIn(b"Operating Systems Kernel Lab", resp.data)

    def test_30_recommendation_never_recommends_completed_task(self):
        """If all pending tasks are completed, recommendation shows all-caught-up banner."""
        database.create_task(
            title="Done Project",
            subject="CS 101",
            task_type="Project",
            due_date="2026-10-10",
            importance=5,
            estimated_hours=8.0,
            status="Completed",
            db_path=self.db_path,
        )
        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"You're all caught up!", resp.data)
        self.assertNotIn(b"Priority Score:", resp.data)

    # ----------------------------------------------------------------------
    # G. Regression & Security Tests
    # ----------------------------------------------------------------------

    def test_31_clear_filters_restores_default_list(self):
        """Navigating to /tasks without query params clears filters and restores all tasks."""
        self._seed_standard_tasks()
        # With filter: 1 task
        resp_filtered = self.client.get("/tasks?q=Ethics")
        self.assertIn(b"Showing <strong>1</strong> of <strong>6</strong> tasks", resp_filtered.data)

        # Clear filters by GET /tasks
        resp_clean = self.client.get("/tasks")
        self.assertIn(b"Showing <strong>6</strong> of <strong>6</strong> tasks", resp_clean.data)

    def test_32_user_input_in_search_field_escaped(self):
        """Malicious script tags in search query are escaped by Jinja."""
        self._seed_standard_tasks()
        xss_payload = '<script>alert("xss")</script>'
        resp = self.client.get(f"/tasks?q={xss_payload}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b'<script>alert("xss")</script>', resp.data)
        self.assertIn(b'&lt;script&gt;alert(&#34;xss&#34;)&lt;/script&gt;', resp.data)

    def test_33_static_assets_continue_to_load(self):
        """CSS and JS endpoints load with HTTP 200."""
        resp_css = self.client.get("/static/css/style.css")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn(b"filter-panel-card", resp_css.data)

        resp_js = self.client.get("/static/js/main.js")
        self.assertEqual(resp_js.status_code, 200)
        self.assertIn(b"Smart Search, Filtering & Sorting", resp_js.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
