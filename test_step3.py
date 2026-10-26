"""
Comprehensive Test Suite for Deadline Rescue — Step 3
Covers all 27 verification requirements from Section 11 using an isolated temporary SQLite database.
"""

import os
import tempfile
import time
import unittest
from app import create_app
import database


class Step3TestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for each test run
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)

        # Initialize the test app with the isolated database
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        # Safely remove the temporary database
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    # ----------------------------------------------------------------------
    # A. Regression Tests (1 - 6)
    # ----------------------------------------------------------------------

    def test_01_home_route_works(self):
        """1. The home route still works."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Take control of your deadlines", resp.data)

    def test_02_tasks_route_works(self):
        """2. /tasks still works."""
        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Assignments &amp; Deadlines", resp.data)

    def test_03_tasks_new_displays_form(self):
        """3. /tasks/new still displays the creation form."""
        resp = self.client.get("/tasks/new")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Create New Task", resp.data)
        self.assertIn(b'name="title"', resp.data)

    def test_04_valid_task_can_be_created(self):
        """4. A valid task can still be created."""
        data = {
            "title": "Quantum Computing Assignment 1",
            "subject": "PHYS 350",
            "task_type": "Assignment",
            "due_date": "2026-11-20",
            "importance": "4",
            "estimated_hours": "5.5",
            "description": "Solve Hadamard gate circuit equations",
        }
        resp = self.client.post("/tasks/new", data=data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Quantum Computing Assignment 1", resp.data)
        self.assertIn(b"created successfully", resp.data)

    def test_05_invalid_creation_data_rejected(self):
        """5. Invalid creation data is still rejected."""
        resp = self.client.post("/tasks/new", data={
            "title": "",
            "subject": "CS 101",
            "task_type": "Assignment",
            "due_date": "2026-11-20",
            "importance": "3",
            "estimated_hours": "2.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Task title is required", resp.data)

    def test_06_tasks_available_after_fresh_connections(self):
        """6. Existing tasks remain available after fresh database connections."""
        tid = database.create_task(
            title="Compiler Design Lexer",
            subject="CS 410",
            task_type="Project",
            due_date="2026-12-01",
            importance=5,
            estimated_hours=10.0,
            db_path=self.db_path,
        )
        # Create fresh client/app to simulate app restart
        fresh_app = create_app({"TESTING": True, "DATABASE": self.db_path})
        fresh_client = fresh_app.test_client()
        resp = fresh_client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Compiler Design Lexer", resp.data)

    # ----------------------------------------------------------------------
    # B. Edit & Update Tests (7 - 13)
    # ----------------------------------------------------------------------

    def test_07_existing_task_can_be_edited(self):
        """7. An existing task can be edited (GET form displays prepopulated data)."""
        tid = database.create_task(
            title="Software Engineering Milestone 1",
            subject="SE 301",
            task_type="Project",
            due_date="2026-11-12",
            importance=4,
            estimated_hours=8.0,
            description="Initial architectural design document",
            db_path=self.db_path,
        )
        resp = self.client.get(f"/tasks/{tid}/edit")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Edit Task:", resp.data)
        self.assertIn(b"Software Engineering Milestone 1", resp.data)
        self.assertIn(b"SE 301", resp.data)
        self.assertIn(b"2026-11-12", resp.data)
        self.assertIn(b"Save Changes", resp.data)

    def test_08_all_editable_fields_updated_correctly(self):
        """8. All editable fields are updated correctly."""
        tid = database.create_task(
            title="Original Title",
            subject="ORIG 100",
            task_type="Assignment",
            due_date="2026-11-01",
            importance=2,
            estimated_hours=2.0,
            description="Original description",
            db_path=self.db_path,
        )
        updated_data = {
            "title": "Updated Title",
            "subject": "NEW 200",
            "task_type": "Lab",
            "due_date": "2026-11-15",
            "importance": "5",
            "estimated_hours": "6.5",
            "description": "Updated notes and rubric criteria",
        }
        resp = self.client.post(f"/tasks/{tid}/edit", data=updated_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Updated Title", resp.data)
        self.assertIn(b"updated successfully", resp.data)

        # Verify in SQLite
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["title"], "Updated Title")
        self.assertEqual(task["subject"], "NEW 200")
        self.assertEqual(task["task_type"], "Lab")
        self.assertEqual(task["due_date"], "2026-11-15")
        self.assertEqual(task["importance"], 5)
        self.assertEqual(task["estimated_hours"], 6.5)
        self.assertEqual(task["description"], "Updated notes and rubric criteria")

    def test_09_task_id_remains_unchanged_after_edit(self):
        """9. The task ID remains unchanged after editing."""
        tid = database.create_task(
            title="Immutable ID Task",
            subject="ID 101",
            task_type="Quiz",
            due_date="2026-11-05",
            importance=3,
            estimated_hours=1.0,
            db_path=self.db_path,
        )
        self.client.post(f"/tasks/{tid}/edit", data={
            "title": "Renamed Task",
            "subject": "ID 101",
            "task_type": "Quiz",
            "due_date": "2026-11-06",
            "importance": "3",
            "estimated_hours": "1.0",
        })
        task = database.get_task_by_id(tid, self.db_path)
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], tid)
        # Verify no duplicate was created
        all_tasks = database.get_all_tasks(self.db_path)
        self.assertEqual(len(all_tasks), 1)

    def test_10_original_creation_timestamp_remains_unchanged(self):
        """10. The original creation timestamp remains unchanged."""
        tid = database.create_task(
            title="Timestamp Check Task",
            subject="TIME 101",
            task_type="Other",
            due_date="2026-11-08",
            importance=2,
            estimated_hours=1.5,
            db_path=self.db_path,
        )
        original_task = database.get_task_by_id(tid, self.db_path)
        original_created_at = original_task["created_at"]

        # Sleep briefly to ensure time difference if timestamp were updated
        time.sleep(0.01)

        self.client.post(f"/tasks/{tid}/edit", data={
            "title": "Timestamp Check Updated",
            "subject": "TIME 101",
            "task_type": "Other",
            "due_date": "2026-11-09",
            "importance": "3",
            "estimated_hours": "2.0",
        })
        updated_task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(updated_task["created_at"], original_created_at)

    def test_11_existing_status_preserved_during_editing(self):
        """11. The existing status (e.g. Completed) is preserved during editing."""
        tid = database.create_task(
            title="Pre-completed Task",
            subject="STAT 200",
            task_type="Assignment",
            due_date="2026-11-02",
            importance=3,
            estimated_hours=2.0,
            status="Completed",
            db_path=self.db_path,
        )
        self.client.post(f"/tasks/{tid}/edit", data={
            "title": "Pre-completed Task Revised",
            "subject": "STAT 200",
            "task_type": "Assignment",
            "due_date": "2026-11-03",
            "importance": "4",
            "estimated_hours": "2.5",
        })
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["status"], "Completed")

    def test_12_invalid_edit_data_does_not_modify_saved_record(self):
        """12. Invalid edit data does not modify the saved record."""
        tid = database.create_task(
            title="Protected Task",
            subject="SAFE 101",
            task_type="Quiz",
            due_date="2026-11-04",
            importance=3,
            estimated_hours=1.0,
            db_path=self.db_path,
        )
        # Attempt edit with invalid data (blank title, negative hours)
        resp = self.client.post(f"/tasks/{tid}/edit", data={
            "title": "   ",
            "subject": "SAFE 101",
            "task_type": "Quiz",
            "due_date": "2026-11-04",
            "importance": "3",
            "estimated_hours": "-5.0",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Task title is required", resp.data)
        self.assertIn(b"Estimated hours cannot be negative", resp.data)

        # Database record must be unchanged
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["title"], "Protected Task")
        self.assertEqual(task["estimated_hours"], 1.0)

    def test_13_nonexistent_edit_id_returns_not_found(self):
        """13. A nonexistent edit ID returns an appropriate not-found response (404)."""
        resp_get = self.client.get("/tasks/99999/edit")
        self.assertEqual(resp_get.status_code, 404)

        resp_post = self.client.post("/tasks/99999/edit", data={
            "title": "Ghost Task",
            "subject": "GHO 000",
            "task_type": "Other",
            "due_date": "2026-11-01",
            "importance": "1",
            "estimated_hours": "1.0",
        })
        self.assertEqual(resp_post.status_code, 404)

    # ----------------------------------------------------------------------
    # C. Completion & Reopen Tests (14 - 18)
    # ----------------------------------------------------------------------

    def test_14_pending_task_can_be_completed(self):
        """14. A pending task can be completed."""
        tid = database.create_task(
            title="Complete Me Task",
            subject="CS 201",
            task_type="Assignment",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )
        resp = self.client.post(f"/tasks/{tid}/complete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"marked as Completed", resp.data)
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["status"], "Completed")

    def test_15_completed_task_can_be_reopened(self):
        """15. A completed task can be reopened."""
        tid = database.create_task(
            title="Reopen Me Task",
            subject="CS 201",
            task_type="Assignment",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=2.0,
            status="Completed",
            db_path=self.db_path,
        )
        resp = self.client.post(f"/tasks/{tid}/reopen", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"reopened", resp.data)
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["status"], "Pending")

    def test_16_status_change_persists_in_sqlite(self):
        """16. The status change persists in SQLite."""
        tid = database.create_task(
            title="Persistence Task",
            subject="CS 201",
            task_type="Assignment",
            due_date="2026-11-10",
            importance=3,
            estimated_hours=2.0,
            db_path=self.db_path,
        )
        self.client.post(f"/tasks/{tid}/complete")

        # Verify directly in fresh connection
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["status"], "Completed")

    def test_17_repeated_or_invalid_status_transitions_handled_safely(self):
        """17. Repeated or invalid status transitions are handled safely."""
        tid = database.create_task(
            title="Idempotent Task",
            subject="MATH 300",
            task_type="Quiz",
            due_date="2026-11-05",
            importance=2,
            estimated_hours=1.0,
            status="Completed",
            db_path=self.db_path,
        )
        # Calling complete on an already completed task
        resp = self.client.post(f"/tasks/{tid}/complete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        task = database.get_task_by_id(tid, self.db_path)
        self.assertEqual(task["status"], "Completed")

        # Database layer rejects invalid statuses with ValueError
        with self.assertRaises(ValueError):
            database.set_task_status(tid, "Archived", self.db_path)

    def test_18_nonexistent_task_id_handled_gracefully(self):
        """18. A nonexistent task ID for complete/reopen returns 404."""
        resp_comp = self.client.post("/tasks/99999/complete")
        self.assertEqual(resp_comp.status_code, 404)

        resp_reop = self.client.post("/tasks/99999/reopen")
        self.assertEqual(resp_reop.status_code, 404)

    # ----------------------------------------------------------------------
    # D. Delete Tests (19 - 23)
    # ----------------------------------------------------------------------

    def test_19_valid_task_can_be_deleted(self):
        """19. A valid task can be deleted."""
        tid = database.create_task(
            title="Task To Delete",
            subject="DEL 101",
            task_type="Assignment",
            due_date="2026-11-01",
            importance=1,
            estimated_hours=1.0,
            db_path=self.db_path,
        )
        resp = self.client.post(f"/tasks/{tid}/delete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"was deleted successfully", resp.data)
        self.assertIsNone(database.get_task_by_id(tid, self.db_path))

    def test_20_deleting_task_does_not_delete_unrelated_tasks(self):
        """20. Deleting a task does not delete unrelated tasks."""
        tid1 = database.create_task("Keep Me 1", "CS 101", "Lab", "2026-11-01", 3, 2.0, db_path=self.db_path)
        tid2 = database.create_task("Delete Me", "CS 102", "Quiz", "2026-11-02", 2, 1.0, db_path=self.db_path)
        tid3 = database.create_task("Keep Me 2", "CS 103", "Project", "2026-11-03", 4, 3.0, db_path=self.db_path)

        self.client.post(f"/tasks/{tid2}/delete")

        all_tasks = database.get_all_tasks(self.db_path)
        remaining_ids = [t["id"] for t in all_tasks]
        self.assertIn(tid1, remaining_ids)
        self.assertIn(tid3, remaining_ids)
        self.assertNotIn(tid2, remaining_ids)
        self.assertEqual(len(all_tasks), 2)

    def test_21_delete_route_rejects_get_requests(self):
        """21. The delete route rejects GET requests (Method Not Allowed 405)."""
        tid = database.create_task("No GET Delete", "SEC 101", "Lab", "2026-11-01", 3, 1.0, db_path=self.db_path)
        resp = self.client.get(f"/tasks/{tid}/delete")
        self.assertEqual(resp.status_code, 405)
        # Task must still exist
        self.assertIsNotNone(database.get_task_by_id(tid, self.db_path))

    def test_22_canceling_confirmation_does_not_delete_task(self):
        """
        22. Canceling the browser confirmation does not delete a task.
        Client-side verification: The form contains onsubmit='return confirm(...);'
        which cancels the POST request when false is returned.
        """
        tid = database.create_task("Confirm Check", "UI 101", "Quiz", "2026-11-01", 2, 1.0, db_path=self.db_path)
        resp = self.client.get("/tasks")
        self.assertIn(b"onsubmit=\"return confirm(", resp.data)
        # Verify task is not deleted when no POST request is issued
        self.assertIsNotNone(database.get_task_by_id(tid, self.db_path))

    def test_23_nonexistent_deletion_target_handled_gracefully(self):
        """23. A nonexistent deletion target is handled gracefully (404)."""
        resp = self.client.post("/tasks/99999/delete")
        self.assertEqual(resp.status_code, 404)

    # ----------------------------------------------------------------------
    # E. Security & Integration Tests (24 - 27)
    # ----------------------------------------------------------------------

    def test_24_user_input_stored_safely_with_parameterized_sql(self):
        """24. User input remains safely stored using parameterized SQL."""
        injection_str = "'; DROP TABLE tasks; --"
        tid = database.create_task("Initial", "CS 100", "Lab", "2026-11-01", 2, 1.0, db_path=self.db_path)
        self.client.post(f"/tasks/{tid}/edit", data={
            "title": injection_str,
            "subject": "SEC 300",
            "task_type": "Other",
            "due_date": "2026-11-05",
            "importance": "3",
            "estimated_hours": "2.0",
        })
        task = database.get_task_by_id(tid, self.db_path)
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], injection_str)

    def test_25_user_generated_html_escaped_in_rendered_templates(self):
        """25. User-generated HTML remains escaped in rendered templates."""
        xss_title = "<script>alert('pwned')</script>"
        tid = database.create_task(xss_title, "XSS 101", "Lab", "2026-11-01", 2, 1.0, db_path=self.db_path)
        resp = self.client.get("/tasks")
        self.assertNotIn(b"<script>alert", resp.data)
        self.assertIn(b"&lt;script&gt;alert", resp.data)

    def test_26_static_assets_still_load(self):
        """26. Existing CSS and JavaScript endpoints still work."""
        resp_css = self.client.get("/static/css/style.css")
        self.assertEqual(resp_css.status_code, 200)
        resp_js = self.client.get("/static/js/main.js")
        self.assertEqual(resp_js.status_code, 200)

    def test_27_handles_missing_task_ids_without_500_error(self):
        """27. The application handles missing task IDs without an internal server error (500)."""
        for endpoint in ["/tasks/9999/edit", "/tasks/9999/complete", "/tasks/9999/reopen", "/tasks/9999/delete"]:
            resp = self.client.post(endpoint)
            self.assertNotEqual(resp.status_code, 500, f"Endpoint {endpoint} threw 500!")
            self.assertEqual(resp.status_code, 404, f"Endpoint {endpoint} did not return 404!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
