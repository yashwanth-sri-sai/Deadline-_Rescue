"""
Deadline Rescue — CSRF Protection Test Suite

Comprehensive tests verifying that:
1. All ordinary GET requests succeed without requiring CSRF tokens.
2. Rendered HTML pages contain valid session-anchored CSRF tokens in forms and meta tags.
3. Every state-changing route (create, edit, complete, reopen, delete) accepts requests with valid tokens.
4. Every state-changing route strictly rejects requests with missing CSRF tokens (HTTP 400).
5. Every state-changing route strictly rejects requests with invalid or tampered tokens (HTTP 400).
6. Cross-session token reuse is rejected (HTTP 400).
7. Custom HTTP header tokens (X-CSRFToken) are accepted for API/AJAX compatibility.
8. Uninstrumented raw Flask test clients are protected by default.
"""

import os
import re
import tempfile
import unittest
from flask.testing import FlaskClient

from app import create_app
import database


class CSRFProtectionTestCase(unittest.TestCase):
    """Test suite verifying comprehensive CSRF protection across Deadline Rescue."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except OSError:
            pass

    def _create_sample_task(self, title="Test Assignment", status="Pending") -> int:
        """Helper to insert a sample task directly into the test database."""
        task_id = database.create_task(
            title=title,
            subject="CS 301",
            task_type="Assignment",
            due_date="2026-12-01",
            importance=4,
            estimated_hours=3.5,
            description="Test task description",
            db_path=self.db_path,
        )
        if status == "Completed":
            database.set_task_status(task_id, "Completed", db_path=self.db_path)
        return task_id

    # -------------------------------------------------------------------------
    # 1. Safe Methods (GET) Do Not Require CSRF Tokens
    # -------------------------------------------------------------------------

    def test_get_dashboard_does_not_require_csrf(self):
        """GET / loads with HTTP 200 without submitting any CSRF token."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_get_tasks_does_not_require_csrf(self):
        """GET /tasks loads with HTTP 200 without submitting any CSRF token."""
        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)

    def test_get_analytics_does_not_require_csrf(self):
        """GET /analytics loads with HTTP 200 without submitting any CSRF token."""
        resp = self.client.get("/analytics")
        self.assertEqual(resp.status_code, 200)

    def test_get_new_task_form_does_not_require_csrf(self):
        """GET /tasks/new loads with HTTP 200 without submitting any CSRF token."""
        resp = self.client.get("/tasks/new")
        self.assertEqual(resp.status_code, 200)

    def test_get_edit_task_form_does_not_require_csrf(self):
        """GET /tasks/<id>/edit loads with HTTP 200 without submitting any CSRF token."""
        task_id = self._create_sample_task("Edit Test")
        resp = self.client.get(f"/tasks/{task_id}/edit")
        self.assertEqual(resp.status_code, 200)

    # -------------------------------------------------------------------------
    # 2. Rendered Templates Include CSRF Tokens
    # -------------------------------------------------------------------------

    def test_task_form_renders_csrf_token_hidden_input(self):
        """The task creation form template contains the hidden csrf_token input field."""
        resp = self.client.get("/tasks/new")
        html = resp.get_data(as_text=True)
        self.assertIn('name="csrf_token"', html)
        match = re.search(r'name="csrf_token"\s+value="([a-f0-9]{64})"', html)
        self.assertIsNotNone(match, "Expected 64-character hexadecimal CSRF token in task form.")

    def test_base_template_renders_csrf_meta_tag(self):
        """The base template includes a <meta name="csrf-token"> tag for frontend scripts."""
        resp = self.client.get("/")
        html = resp.get_data(as_text=True)
        self.assertIn('name="csrf-token"', html)
        match = re.search(r'name="csrf-token"\s+content="([a-f0-9]{64})"', html)
        self.assertIsNotNone(match, "Expected 64-character hexadecimal CSRF token in meta tag.")

    def test_tasks_list_renders_csrf_token_in_action_forms(self):
        """The tasks list template includes csrf_token in complete, reopen, and delete forms."""
        self._create_sample_task("Pending Task", status="Pending")
        self._create_sample_task("Completed Task", status="Completed")
        resp = self.client.get("/tasks")
        html = resp.get_data(as_text=True)
        token_matches = re.findall(r'name="csrf_token"\s+value="([a-f0-9]{64})"', html)
        self.assertGreaterEqual(len(token_matches), 3, "Expected multiple action forms with CSRF tokens.")

    # -------------------------------------------------------------------------
    # 3. Create Task Route (POST /tasks/new)
    # -------------------------------------------------------------------------

    def test_create_task_with_valid_token_succeeds(self):
        """POST /tasks/new with a valid token creates the task and redirects."""
        data = {
            "title": "Secure Create",
            "subject": "SEC 101",
            "task_type": "Assignment",
            "due_date": "2026-11-20",
            "importance": 4,
            "estimated_hours": 2.0,
            "description": "Validated form",
        }
        resp = self.client.post("/tasks/new", data=data, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        tasks = database.get_all_tasks(self.db_path)
        self.assertTrue(any(t["title"] == "Secure Create" for t in tasks))

    def test_create_task_missing_token_rejected_400(self):
        """POST /tasks/new with missing CSRF token returns 400 and does not create task."""
        data = {
            "title": "Forged Task",
            "subject": "HACK 101",
            "task_type": "Assignment",
            "due_date": "2026-11-20",
            "importance": 5,
            "estimated_hours": 1.0,
        }
        resp = self.client.post("/tasks/new", data=data, headers={"X-Test-No-CSRF": "1"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("CSRF token missing", resp.get_data(as_text=True))
        tasks = database.get_all_tasks(self.db_path)
        self.assertFalse(any(t["title"] == "Forged Task" for t in tasks))

    def test_create_task_invalid_token_rejected_400(self):
        """POST /tasks/new with invalid CSRF token returns 400 and does not create task."""
        self.client.get("/tasks/new")  # Establish session
        data = {
            "title": "Forged Task Invalid Token",
            "subject": "HACK 101",
            "task_type": "Assignment",
            "due_date": "2026-11-20",
            "importance": 5,
            "estimated_hours": 1.0,
            "csrf_token": "tampered_csrf_token_value_xyz",
        }
        resp = self.client.post("/tasks/new", data=data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("CSRF token invalid", resp.get_data(as_text=True))
        tasks = database.get_all_tasks(self.db_path)
        self.assertFalse(any(t["title"] == "Forged Task Invalid Token" for t in tasks))

    def test_post_without_session_rejected_400(self):
        """POST /tasks/new without an established session returns 400."""
        raw_client = FlaskClient(self.app, response_wrapper=self.app.response_class)
        data = {
            "title": "No Session Task",
            "csrf_token": "arbitrary_token_without_session",
        }
        resp = raw_client.post("/tasks/new", data=data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("CSRF session token missing", resp.get_data(as_text=True))

    def test_create_task_empty_token_rejected_400(self):
        """POST /tasks/new with empty csrf_token value returns 400."""
        data = {
            "title": "Blank Token Task",
            "subject": "HACK 101",
            "task_type": "Assignment",
            "due_date": "2026-11-20",
            "importance": 5,
            "estimated_hours": 1.0,
            "csrf_token": "",
        }
        resp = self.client.post("/tasks/new", data=data)
        self.assertEqual(resp.status_code, 400)

    # -------------------------------------------------------------------------
    # 4. Edit Task Route (POST /tasks/<id>/edit)
    # -------------------------------------------------------------------------

    def test_edit_task_with_valid_token_succeeds(self):
        """POST /tasks/<id>/edit with a valid token updates the task and redirects."""
        task_id = self._create_sample_task("Before Edit")
        data = {
            "title": "After Edit",
            "subject": "CS 301",
            "task_type": "Assignment",
            "due_date": "2026-12-05",
            "importance": 5,
            "estimated_hours": 4.0,
        }
        resp = self.client.post(f"/tasks/{task_id}/edit", data=data, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        updated = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(updated["title"], "After Edit")

    def test_edit_task_missing_token_rejected_400(self):
        """POST /tasks/<id>/edit with missing CSRF token returns 400 and preserves original."""
        task_id = self._create_sample_task("Original Title")
        data = {
            "title": "Malicious Modification",
            "subject": "CS 301",
            "task_type": "Assignment",
            "due_date": "2026-12-05",
            "importance": 5,
            "estimated_hours": 4.0,
        }
        resp = self.client.post(
            f"/tasks/{task_id}/edit", data=data, headers={"X-Test-No-CSRF": "1"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["title"], "Original Title")

    def test_edit_task_invalid_token_rejected_400(self):
        """POST /tasks/<id>/edit with invalid CSRF token returns 400 and preserves original."""
        task_id = self._create_sample_task("Original Title")
        data = {
            "title": "Malicious Modification",
            "subject": "CS 301",
            "task_type": "Assignment",
            "due_date": "2026-12-05",
            "importance": 5,
            "estimated_hours": 4.0,
            "csrf_token": "invalid_edit_token",
        }
        resp = self.client.post(f"/tasks/{task_id}/edit", data=data)
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["title"], "Original Title")

    # -------------------------------------------------------------------------
    # 5. Complete Task Route (POST /tasks/<id>/complete)
    # -------------------------------------------------------------------------

    def test_complete_task_with_valid_token_succeeds(self):
        """POST /tasks/<id>/complete with valid token marks task as Completed."""
        task_id = self._create_sample_task("Pending To Complete", status="Pending")
        resp = self.client.post(f"/tasks/{task_id}/complete", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["status"], "Completed")

    def test_complete_task_missing_token_rejected_400(self):
        """POST /tasks/<id>/complete with missing CSRF token returns 400; status stays Pending."""
        task_id = self._create_sample_task("Keep Pending", status="Pending")
        resp = self.client.post(
            f"/tasks/{task_id}/complete", headers={"X-Test-No-CSRF": "1"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["status"], "Pending")

    def test_complete_task_invalid_token_rejected_400(self):
        """POST /tasks/<id>/complete with invalid CSRF token returns 400; status stays Pending."""
        task_id = self._create_sample_task("Keep Pending", status="Pending")
        resp = self.client.post(
            f"/tasks/{task_id}/complete", data={"csrf_token": "wrong_token"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["status"], "Pending")

    # -------------------------------------------------------------------------
    # 6. Reopen Task Route (POST /tasks/<id>/reopen)
    # -------------------------------------------------------------------------

    def test_reopen_task_with_valid_token_succeeds(self):
        """POST /tasks/<id>/reopen with valid token marks task as Pending."""
        task_id = self._create_sample_task("Completed To Reopen", status="Completed")
        resp = self.client.post(f"/tasks/{task_id}/reopen", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["status"], "Pending")

    def test_reopen_task_missing_token_rejected_400(self):
        """POST /tasks/<id>/reopen with missing CSRF token returns 400; status stays Completed."""
        task_id = self._create_sample_task("Keep Completed", status="Completed")
        resp = self.client.post(
            f"/tasks/{task_id}/reopen", headers={"X-Test-No-CSRF": "1"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["status"], "Completed")

    def test_reopen_task_invalid_token_rejected_400(self):
        """POST /tasks/<id>/reopen with invalid CSRF token returns 400; status stays Completed."""
        task_id = self._create_sample_task("Keep Completed", status="Completed")
        resp = self.client.post(
            f"/tasks/{task_id}/reopen", data={"csrf_token": "bad_token"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertEqual(task["status"], "Completed")

    # -------------------------------------------------------------------------
    # 7. Delete Task Route (POST /tasks/<id>/delete)
    # -------------------------------------------------------------------------

    def test_delete_task_with_valid_token_succeeds(self):
        """POST /tasks/<id>/delete with valid token deletes the task record."""
        task_id = self._create_sample_task("Task To Delete")
        resp = self.client.post(f"/tasks/{task_id}/delete", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertIsNone(task)

    def test_delete_task_missing_token_rejected_400(self):
        """POST /tasks/<id>/delete with missing CSRF token returns 400; task is not deleted."""
        task_id = self._create_sample_task("Protected From Forgery Delete")
        resp = self.client.post(
            f"/tasks/{task_id}/delete", headers={"X-Test-No-CSRF": "1"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertIsNotNone(task, "Task must not be deleted when CSRF token is missing.")

    def test_delete_task_invalid_token_rejected_400(self):
        """POST /tasks/<id>/delete with invalid CSRF token returns 400; task is not deleted."""
        task_id = self._create_sample_task("Protected From Tampered Delete")
        resp = self.client.post(
            f"/tasks/{task_id}/delete", data={"csrf_token": "fake_token_attempt"}
        )
        self.assertEqual(resp.status_code, 400)
        task = database.get_task_by_id(task_id, self.db_path)
        self.assertIsNotNone(task, "Task must not be deleted when CSRF token is invalid.")

    # -------------------------------------------------------------------------
    # 8. Header-Based Token & Cross-Session Isolation
    # -------------------------------------------------------------------------

    def test_header_based_csrf_token_succeeds(self):
        """State-changing requests with X-CSRFToken header succeed."""
        # Initialize session token
        with self.client.session_transaction() as sess:
            sess["_csrf_token"] = "custom_valid_header_token_1234567890123456"
            token = sess["_csrf_token"]

        data = {
            "title": "Header Token Task",
            "subject": "API 101",
            "task_type": "Assignment",
            "due_date": "2026-11-30",
            "importance": 3,
            "estimated_hours": 1.5,
        }
        resp = self.client.post("/tasks/new", data=data, headers={"X-CSRFToken": token})
        self.assertEqual(resp.status_code, 302)
        tasks = database.get_all_tasks(self.db_path)
        self.assertTrue(any(t["title"] == "Header Token Task" for t in tasks))

    def test_cross_session_token_reuse_rejected_400(self):
        """A valid CSRF token from Session A submitted in Session B is rejected (HTTP 400)."""
        # Session A gets a token
        client_a = self.app.test_client()
        resp_a = client_a.get("/tasks/new")
        html_a = resp_a.get_data(as_text=True)
        token_a = re.search(r'name="csrf_token"\s+value="([a-f0-9]{64})"', html_a).group(1)

        # Session B attempts to use token A
        client_b = self.app.test_client()
        client_b.get("/tasks/new")  # Initialize Session B with its own token

        data = {
            "title": "Cross Session Attack",
            "subject": "SEC 501",
            "task_type": "Assignment",
            "due_date": "2026-11-30",
            "importance": 3,
            "estimated_hours": 1.5,
            "csrf_token": token_a,  # Maliciously reusing Session A token
        }
        resp_b = client_b.post("/tasks/new", data=data)
        self.assertEqual(resp_b.status_code, 400)
        self.assertIn("CSRF token invalid", resp_b.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # 9. Raw Uninstrumented Client Behavior
    # -------------------------------------------------------------------------

    def test_raw_uninstrumented_client_rejected_without_token(self):
        """A raw uninstrumented FlaskClient (external requester) is blocked without CSRF token."""
        raw_client = FlaskClient(self.app, response_wrapper=self.app.response_class)
        data = {
            "title": "Raw Client Attack",
            "subject": "SEC 501",
            "task_type": "Assignment",
            "due_date": "2026-11-30",
            "importance": 3,
            "estimated_hours": 1.5,
        }
        resp = raw_client.post("/tasks/new", data=data)
        self.assertEqual(resp.status_code, 400)

    def test_raw_uninstrumented_client_succeeds_with_proper_session_and_token(self):
        """A raw client properly obtaining a token and submitting it in form data succeeds."""
        raw_client = FlaskClient(self.app, response_wrapper=self.app.response_class)
        # 1. GET page to establish session and obtain token
        get_resp = raw_client.get("/tasks/new")
        self.assertEqual(get_resp.status_code, 200)
        html = get_resp.get_data(as_text=True)
        token = re.search(r'name="csrf_token"\s+value="([a-f0-9]{64})"', html).group(1)

        # 2. POST form with obtained token
        data = {
            "title": "Raw Client Success",
            "subject": "SEC 501",
            "task_type": "Assignment",
            "due_date": "2026-11-30",
            "importance": 3,
            "estimated_hours": 1.5,
            "csrf_token": token,
        }
        post_resp = raw_client.post("/tasks/new", data=data)
        self.assertEqual(post_resp.status_code, 302)
        tasks = database.get_all_tasks(self.db_path)
        self.assertTrue(any(t["title"] == "Raw Client Success" for t in tasks))


if __name__ == "__main__":
    unittest.main()
