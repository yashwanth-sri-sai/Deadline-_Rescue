"""
Comprehensive Test Suite for Deadline Rescue — Step 2
Tests all 12 required verification criteria using isolated temporary SQLite database.
"""

import os
import tempfile
import unittest
from app import create_app
import database


class Step2TestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for isolated test database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)

        # Initialize the app with the test database
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up temporary database
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_01_home_route_works(self):
        """1. The home route still works."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Take control of your deadlines", response.data)
        self.assertIn(b"Deadline Rescue", response.data)

    def test_02_get_tasks_empty_database(self):
        """2. GET /tasks works with an empty database."""
        response = self.client.get("/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No tasks found", response.data)
        self.assertIn(b"Add Your First Task", response.data)

    def test_03_get_tasks_new_displays_form(self):
        """3. GET /tasks/new displays the form."""
        response = self.client.get("/tasks/new")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create New Task", response.data)
        self.assertIn(b'name="title"', response.data)
        self.assertIn(b'name="subject"', response.data)
        self.assertIn(b'name="task_type"', response.data)
        self.assertIn(b'name="due_date"', response.data)
        self.assertIn(b'name="importance"', response.data)
        self.assertIn(b'name="estimated_hours"', response.data)

    def test_04_valid_task_saved_and_displayed(self):
        """4. A valid task is saved and displayed."""
        task_data = {
            "title": "Machine Learning Term Project",
            "subject": "CS 450",
            "task_type": "Project",
            "due_date": "2026-11-15",
            "importance": "5",
            "estimated_hours": "14.5",
            "description": "Implement convolutional neural network from scratch.",
        }
        # POST submission (expect redirect 302 to /tasks)
        response = self.client.post("/tasks/new", data=task_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Machine Learning Term Project", response.data)
        self.assertIn(b"CS 450", response.data)
        self.assertIn(b"Project", response.data)
        self.assertIn(b"2026-11-15", response.data)
        self.assertIn(b"Level 5/5", response.data)
        self.assertIn(b"14.5 hrs", response.data)
        self.assertIn(b"created successfully", response.data)

    def test_05_saved_task_persists_across_reconnect(self):
        """5. A saved task remains after reconnecting to the database or restarting the app."""
        # Insert task
        database.create_task(
            title="Database Systems Lab 2",
            subject="CS 320",
            task_type="Lab",
            due_date="2026-10-30",
            importance=4,
            estimated_hours=3.0,
            description="B-Tree indexing queries",
            db_path=self.db_path,
        )

        # Simulate a completely fresh app instance pointing to the same SQLite file
        new_app = create_app({"TESTING": True, "DATABASE": self.db_path})
        new_client = new_app.test_client()

        response = new_client.get("/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Database Systems Lab 2", response.data)
        self.assertIn(b"CS 320", response.data)

    def test_06_blank_title_and_subject_rejected(self):
        """6. Blank title and subject are rejected (including whitespace-only)."""
        # Blank / whitespace title
        resp = self.client.post("/tasks/new", data={
            "title": "   ",
            "subject": "MATH 201",
            "task_type": "Assignment",
            "due_date": "2026-11-01",
            "importance": "3",
            "estimated_hours": "2.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Task title is required and cannot be blank", resp.data)

        # Blank / whitespace subject
        resp = self.client.post("/tasks/new", data={
            "title": "Linear Algebra Homework",
            "subject": "   ",
            "task_type": "Assignment",
            "due_date": "2026-11-01",
            "importance": "3",
            "estimated_hours": "2.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Subject / course code is required and cannot be blank", resp.data)

    def test_07_invalid_dates_and_unsupported_task_types_rejected(self):
        """7. Invalid dates and unsupported task types are rejected."""
        # Non-existent calendar date (February 30)
        resp = self.client.post("/tasks/new", data={
            "title": "Quiz Review",
            "subject": "PHY 101",
            "task_type": "Quiz",
            "due_date": "2026-02-30",
            "importance": "2",
            "estimated_hours": "1.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"valid calendar date", resp.data)

        # Invalid format
        resp = self.client.post("/tasks/new", data={
            "title": "Quiz Review",
            "subject": "PHY 101",
            "task_type": "Quiz",
            "due_date": "tomorrow",
            "importance": "2",
            "estimated_hours": "1.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"valid calendar date", resp.data)

        # Unsupported task type
        resp = self.client.post("/tasks/new", data={
            "title": "Hackathon Attendance",
            "subject": "CS 100",
            "task_type": "Hackathon",
            "due_date": "2026-11-10",
            "importance": "3",
            "estimated_hours": "5.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Unsupported task type", resp.data)

    def test_08_importance_outside_1_to_5_rejected(self):
        """8. Importance values outside 1-5 are rejected."""
        for bad_val in ["0", "6", "-2", "critical", ""]:
            resp = self.client.post("/tasks/new", data={
                "title": "Task with Bad Importance",
                "subject": "ENG 101",
                "task_type": "Assignment",
                "due_date": "2026-11-05",
                "importance": bad_val,
                "estimated_hours": "2.0",
            })
            self.assertEqual(resp.status_code, 400, f"Failed to reject importance: {bad_val}")
            self.assertIn(b"Importance", resp.data)

    def test_09_negative_and_non_numeric_hours_rejected(self):
        """9. Negative, non-numeric, or non-finite estimated hours are rejected."""
        for bad_hours in ["-1", "-0.5", "three", "nan", "inf", ""]:
            resp = self.client.post("/tasks/new", data={
                "title": "Task with Bad Hours",
                "subject": "BIO 110",
                "task_type": "Lab",
                "due_date": "2026-11-05",
                "importance": "3",
                "estimated_hours": bad_hours,
            })
            self.assertEqual(resp.status_code, 400, f"Failed to reject estimated hours: {bad_hours}")
            self.assertIn(b"Estimated hours", resp.data)

    def test_10_failed_validation_does_not_insert_task(self):
        """10. Failed validation does not insert a task."""
        # Attempt failed submission
        self.client.post("/tasks/new", data={
            "title": "Invalid Phantom Task",
            "subject": "",  # invalid
            "task_type": "Assignment",
            "due_date": "2026-11-01",
            "importance": "3",
            "estimated_hours": "2.0",
        })

        # Check database directly
        tasks = database.get_all_tasks(self.db_path)
        self.assertEqual(len(tasks), 0)

    def test_11_user_input_stored_safely_with_parameterized_sql(self):
        """11. User input is stored safely using parameterized SQL."""
        injection_payload = "'; DROP TABLE tasks; --"
        task_data = {
            "title": injection_payload,
            "subject": "SEC 501",
            "task_type": "Other",
            "due_date": "2026-11-20",
            "importance": "4",
            "estimated_hours": "1.5",
            "description": "<script>alert('xss');</script> & ' or '1'='1",
        }
        resp = self.client.post("/tasks/new", data=task_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Confirm tasks table still exists and record is preserved as literal string
        tasks = database.get_all_tasks(self.db_path)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], injection_payload)

        # Confirm Jinja properly escaped script tag in HTML response
        self.assertNotIn(b"<script>alert", resp.data)
        self.assertIn(b"&lt;script&gt;alert", resp.data)

    def test_12_static_assets_continue_to_load(self):
        """12. CSS and JavaScript assets continue to load."""
        resp_css = self.client.get("/static/css/style.css")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn(b"--dr-primary", resp_css.data)

        resp_js = self.client.get("/static/js/main.js")
        self.assertEqual(resp_js.status_code, 200)
        self.assertIn(b"Deadline Rescue", resp_js.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
