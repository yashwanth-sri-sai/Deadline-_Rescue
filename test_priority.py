"""
Comprehensive Test Suite for Deadline Rescue — Step 4: Priority Engine & Deadline Awareness
Covers all requirements from Section 9 of the specification.
"""

from datetime import date, timedelta
import os
import tempfile
import unittest
from app import create_app
import database
import priority


class PriorityEngineTestCase(unittest.TestCase):
    def setUp(self):
        # Fixed reference date for deterministic testing
        self.ref_date = date(2026, 10, 24)

    # ----------------------------------------------------------------------
    # A. Days Remaining & Urgency Scoring Tests
    # ----------------------------------------------------------------------

    def test_01_urgency_overdue_one_day(self):
        """Overdue by one day (-1) receives urgency score 100."""
        due = self.ref_date - timedelta(days=1)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, -1)
        self.assertEqual(priority.calculate_urgency_score(days), 100)

    def test_02_urgency_overdue_several_days(self):
        """Overdue by several days (-5) receives urgency score 100."""
        due = self.ref_date - timedelta(days=5)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, -5)
        self.assertEqual(priority.calculate_urgency_score(days), 100)

    def test_03_urgency_due_today(self):
        """Due today (0) receives urgency score 100."""
        days = priority.calculate_days_remaining(self.ref_date.isoformat(), today=self.ref_date)
        self.assertEqual(days, 0)
        self.assertEqual(priority.calculate_urgency_score(days), 100)

    def test_04_urgency_due_tomorrow(self):
        """Due tomorrow (1) receives urgency score 90."""
        due = self.ref_date + timedelta(days=1)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 1)
        self.assertEqual(priority.calculate_urgency_score(days), 90)

    def test_05_urgency_due_in_2_days(self):
        """Due in 2 days receives urgency score 75."""
        due = self.ref_date + timedelta(days=2)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 2)
        self.assertEqual(priority.calculate_urgency_score(days), 75)

    def test_06_urgency_due_in_3_days(self):
        """Due in 3 days receives urgency score 75."""
        due = self.ref_date + timedelta(days=3)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 3)
        self.assertEqual(priority.calculate_urgency_score(days), 75)

    def test_07_urgency_due_in_4_days(self):
        """Due in 4 days receives urgency score 50."""
        due = self.ref_date + timedelta(days=4)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 4)
        self.assertEqual(priority.calculate_urgency_score(days), 50)

    def test_08_urgency_due_in_7_days(self):
        """Due in 7 days receives urgency score 50."""
        due = self.ref_date + timedelta(days=7)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 7)
        self.assertEqual(priority.calculate_urgency_score(days), 50)

    def test_09_urgency_due_in_8_days(self):
        """Due in 8 days receives urgency score 30."""
        due = self.ref_date + timedelta(days=8)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 8)
        self.assertEqual(priority.calculate_urgency_score(days), 30)

    def test_10_urgency_due_in_14_days(self):
        """Due in 14 days receives urgency score 30."""
        due = self.ref_date + timedelta(days=14)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 14)
        self.assertEqual(priority.calculate_urgency_score(days), 30)

    def test_11_urgency_due_in_15_days(self):
        """Due in 15 days (more than 14 days) receives urgency score 10."""
        due = self.ref_date + timedelta(days=15)
        days = priority.calculate_days_remaining(due.isoformat(), today=self.ref_date)
        self.assertEqual(days, 15)
        self.assertEqual(priority.calculate_urgency_score(days), 10)

    # ----------------------------------------------------------------------
    # B. Exact Priority Formula Tests
    # ----------------------------------------------------------------------

    def test_12_priority_formula_importance_boundaries(self):
        """Test importance at min (1) and max (5) independently."""
        # U=100, I=1, H=0 -> 0.60*100 + 0.25*(1/5*100) + 0.15*0 = 60 + 5 + 0 = 65.0
        expected_min = 60.0 + 5.0 + 0.0
        score_min = priority.calculate_priority_score(urgency_score=100, importance=1, estimated_hours=0)
        self.assertAlmostEqual(score_min, expected_min, places=4)

        # U=100, I=5, H=0 -> 0.60*100 + 0.25*(5/5*100) + 0.15*0 = 60 + 25 + 0 = 85.0
        expected_max = 60.0 + 25.0 + 0.0
        score_max = priority.calculate_priority_score(urgency_score=100, importance=5, estimated_hours=0)
        self.assertAlmostEqual(score_max, expected_max, places=4)

    def test_13_priority_formula_effort_scaling_and_capping(self):
        """Test estimated hours at 0, 4, 8, and greater than 8."""
        # H=0: effort contrib = 0.15 * 0 = 0.0
        score_h0 = priority.calculate_priority_score(urgency_score=50, importance=3, estimated_hours=0)
        expected_h0 = (0.60 * 50) + (0.25 * 60) + (0.15 * 0)  # 30 + 15 + 0 = 45.0
        self.assertAlmostEqual(score_h0, expected_h0, places=4)

        # H=4: effort contrib = 0.15 * (4/8*100) = 0.15 * 50 = 7.5
        score_h4 = priority.calculate_priority_score(urgency_score=50, importance=3, estimated_hours=4)
        expected_h4 = 30.0 + 15.0 + 7.5  # 52.5
        self.assertAlmostEqual(score_h4, expected_h4, places=4)

        # H=8: effort contrib = 0.15 * (8/8*100) = 0.15 * 100 = 15.0
        score_h8 = priority.calculate_priority_score(urgency_score=50, importance=3, estimated_hours=8)
        expected_h8 = 30.0 + 15.0 + 15.0  # 60.0
        self.assertAlmostEqual(score_h8, expected_h8, places=4)

        # H=16: effort capped at 100, so contrib remains 15.0
        score_h16 = priority.calculate_priority_score(urgency_score=50, importance=3, estimated_hours=16)
        self.assertAlmostEqual(score_h16, expected_h8, places=4)

    def test_14_priority_overdue_task(self):
        """Overdue task with importance 5 and effort 8 receives 100.0."""
        # 0.60*100 + 0.25*100 + 0.15*100 = 100.0
        score = priority.calculate_priority_score(urgency_score=100, importance=5, estimated_hours=8)
        self.assertEqual(score, 100.0)

    def test_15_priority_task_due_today(self):
        """Due today task (urgency=100), importance=4, effort=6."""
        # 0.60*100 + 0.25*(4/5*100) + 0.15*(6/8*100)
        # = 60 + 20 + 0.15*75 = 60 + 20 + 11.25 = 91.25
        score = priority.calculate_priority_score(urgency_score=100, importance=4, estimated_hours=6)
        self.assertAlmostEqual(score, 91.25, places=4)

    def test_16_priority_low_urgency_task(self):
        """Low urgency task (>14 days, U=10), importance=1, effort=0."""
        # 0.60*10 + 0.25*(1/5*100) + 0 = 6 + 5 + 0 = 11.0
        score = priority.calculate_priority_score(urgency_score=10, importance=1, estimated_hours=0)
        self.assertAlmostEqual(score, 11.0, places=4)

    def test_17_priority_rounding_behavior(self):
        """Verify unrounded score precision and rounded display score (2 decimals)."""
        # H=2.33 -> 0.15 * (2.33/8*100) = 0.15 * 29.125 = 4.36875
        # U=75 -> 45.0
        # I=3 -> 15.0
        # Total = 64.36875 -> rounded display = 64.37
        score = priority.calculate_priority_score(urgency_score=75, importance=3, estimated_hours=2.33)
        self.assertAlmostEqual(score, 64.36875, places=5)
        display_score = round(score, 2)
        self.assertEqual(display_score, 64.37)

    # ----------------------------------------------------------------------
    # C. Label Boundary Tests
    # ----------------------------------------------------------------------

    def test_18_priority_label_boundaries(self):
        """Test categorical labels exactly at and around boundary thresholds."""
        # 0 -> Low
        self.assertEqual(priority.get_priority_label(0.0), "Low")
        # 24.99 -> Low
        self.assertEqual(priority.get_priority_label(24.99), "Low")
        # 25.0 -> Medium
        self.assertEqual(priority.get_priority_label(25.0), "Medium")
        # 49.99 -> Medium
        self.assertEqual(priority.get_priority_label(49.99), "Medium")
        # 50.0 -> High
        self.assertEqual(priority.get_priority_label(50.0), "High")
        # 74.99 -> High
        self.assertEqual(priority.get_priority_label(74.99), "High")
        # 75.0 -> Critical
        self.assertEqual(priority.get_priority_label(75.0), "Critical")
        # 100.0 -> Critical
        self.assertEqual(priority.get_priority_label(100.0), "Critical")

    # ----------------------------------------------------------------------
    # D. Deadline Status Tests
    # ----------------------------------------------------------------------

    def test_19_deadline_statuses_pending(self):
        """Test all pending deadline status strings and friendly messages."""
        # Overdue by 3 days
        status, msg = priority.get_deadline_status(-3, is_completed=False)
        self.assertEqual(status, "Overdue")
        self.assertEqual(msg, "Overdue by 3 days")

        # Overdue by 1 day
        status, msg = priority.get_deadline_status(-1, is_completed=False)
        self.assertEqual(status, "Overdue")
        self.assertEqual(msg, "Overdue by 1 day")

        # Due today
        status, msg = priority.get_deadline_status(0, is_completed=False)
        self.assertEqual(status, "Due Today")
        self.assertEqual(msg, "Due today")

        # Due tomorrow
        status, msg = priority.get_deadline_status(1, is_completed=False)
        self.assertEqual(status, "Due Tomorrow")
        self.assertEqual(msg, "Due tomorrow")

        # Due in 5 days
        status, msg = priority.get_deadline_status(5, is_completed=False)
        self.assertEqual(status, "Upcoming")
        self.assertEqual(msg, "Due in 5 days")

    def test_20_deadline_statuses_completed(self):
        """Completed tasks must always report Completed, regardless of deadline."""
        # Past deadline but completed
        status, msg = priority.get_deadline_status(-5, is_completed=True)
        self.assertEqual(status, "Completed")
        self.assertEqual(msg, "Completed")

        # Future deadline and completed
        status, msg = priority.get_deadline_status(5, is_completed=True)
        self.assertEqual(status, "Completed")
        self.assertEqual(msg, "Completed")

    # ----------------------------------------------------------------------
    # E. Next-Task Recommendation Tests
    # ----------------------------------------------------------------------

    def test_21_recommendation_highest_priority_pending(self):
        """Highest priority pending task is selected."""
        t1 = {"id": 1, "title": "Low Task", "due_date": "2026-11-20", "importance": 1, "estimated_hours": 1, "status": "Pending"}
        t2 = {"id": 2, "title": "Urgent Task", "due_date": "2026-10-24", "importance": 5, "estimated_hours": 8, "status": "Pending"}
        rec = priority.get_recommended_next_task([t1, t2], today=self.ref_date)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["id"], 2)

    def test_22_recommendation_never_recommends_completed(self):
        """Completed tasks are never recommended even if priority score is 100."""
        t1 = {"id": 1, "title": "Completed Critical", "due_date": "2026-10-23", "importance": 5, "estimated_hours": 8, "status": "Completed"}
        t2 = {"id": 2, "title": "Pending Low", "due_date": "2026-11-20", "importance": 1, "estimated_hours": 1, "status": "Pending"}
        rec = priority.get_recommended_next_task([t1, t2], today=self.ref_date)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["id"], 2)

    def test_23_recommendation_tie_breaker_earlier_deadline(self):
        """Equal priority score is broken by earlier deadline."""
        # Both tasks have identical urgency (100), importance (5), effort (8) -> score 100
        t1 = {"id": 1, "title": "Due Tomorrow Task", "due_date": "2026-10-24", "importance": 5, "estimated_hours": 8, "status": "Pending"}
        t2 = {"id": 2, "title": "Overdue Yesterday Task", "due_date": "2026-10-23", "importance": 5, "estimated_hours": 8, "status": "Pending"}
        rec = priority.get_recommended_next_task([t1, t2], today=self.ref_date)
        # t2 has earlier due_date ('2026-10-23' < '2026-10-24')
        self.assertEqual(rec["id"], 2)

    def test_24_recommendation_tie_breaker_smaller_id(self):
        """Equal priority and equal deadline is broken by smaller task ID."""
        t1 = {"id": 4, "title": "Task ID 4", "due_date": "2026-10-24", "importance": 5, "estimated_hours": 8, "status": "Pending"}
        t2 = {"id": 2, "title": "Task ID 2", "due_date": "2026-10-24", "importance": 5, "estimated_hours": 8, "status": "Pending"}
        rec = priority.get_recommended_next_task([t1, t2], today=self.ref_date)
        self.assertEqual(rec["id"], 2)

    def test_25_recommendation_empty_or_all_completed(self):
        """Returns None when task list is empty or all tasks are completed."""
        self.assertIsNone(priority.get_recommended_next_task([], today=self.ref_date))

        completed_tasks = [
            {"id": 1, "title": "Done 1", "due_date": "2026-10-20", "importance": 4, "estimated_hours": 2, "status": "Completed"},
            {"id": 2, "title": "Done 2", "due_date": "2026-10-22", "importance": 3, "estimated_hours": 1, "status": "Completed"},
        ]
        self.assertIsNone(priority.get_recommended_next_task(completed_tasks, today=self.ref_date))


class PriorityIntegrationTestCase(unittest.TestCase):
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

    # ----------------------------------------------------------------------
    # F. Integration and Regression Tests
    # ----------------------------------------------------------------------

    def test_26_tasks_page_displays_priority_and_recommendation(self):
        """Tasks page displays priority scores, badges, and recommendation section."""
        database.create_task(
            title="Algorithms Final Exam Review",
            subject="CS 401",
            task_type="Assignment",
            due_date=date.today().isoformat(),  # Due today -> Urgency 100
            importance=5,
            estimated_hours=8.0,
            db_path=self.db_path,
        )

        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        # Check recommendation section exists
        self.assertIn(b"Recommended Next Task", resp.data)
        self.assertIn(b"Priority Score:", resp.data)
        self.assertIn(b"Algorithms Final Exam Review", resp.data)
        # Check priority badge in table
        self.assertIn(b"Critical (100.00)", resp.data)
        self.assertIn(b"Due today", resp.data)

    def test_27_tasks_page_all_completed_empty_recommendation(self):
        """Tasks page shows all-caught-up banner when all tasks are completed."""
        database.create_task(
            title="Finished Thesis",
            subject="CS 499",
            task_type="Project",
            due_date=date.today().isoformat(),
            importance=5,
            estimated_hours=8.0,
            status="Completed",
            db_path=self.db_path,
        )
        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"You're all caught up!", resp.data)
        self.assertIn(b"No pending tasks to recommend", resp.data)

    def test_28_malformed_legacy_date_does_not_crash_page(self):
        """Malformed legacy due date does not crash /tasks route; falls back safely."""
        with database.get_db_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO tasks (title, subject, task_type, due_date, importance, estimated_hours, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                ("Legacy Malformed Task", "OLD 001", "Other", "corrupted-date", 3, 2.0, "Pending", "2026-01-01T00:00:00"),
            )
            conn.commit()

        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Legacy Malformed Task", resp.data)
        self.assertIn(b"No deadline set", resp.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
