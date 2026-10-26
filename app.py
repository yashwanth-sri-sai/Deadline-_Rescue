"""
Deadline Rescue — Smart Assignment & Deadline Management System
Step 3: Complete Task Management: Edit, Update, Complete, Reopen & Delete

This module serves as the core application entry point.
It initializes Flask, registers configuration settings, connects the SQLite
database, and provides complete lifecycle routes for coursework tasks.
"""

from datetime import datetime
import math
import os
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

import analytics
import database
import priority


def validate_task_data(form_data: dict) -> tuple[dict, dict]:
    """
    Perform thorough server-side validation on submitted task form data.

    Returns:
        tuple[dict, dict]: (cleaned_data, errors_dict)
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}

    # Title validation: required, non-empty, reject whitespace-only
    title_raw = form_data.get("title") or ""
    title = title_raw.strip()
    if not title:
        errors["title"] = "Task title is required and cannot be blank."
    else:
        cleaned["title"] = title

    # Subject validation: required, non-empty, reject whitespace-only
    subject_raw = form_data.get("subject") or ""
    subject = subject_raw.strip()
    if not subject:
        errors["subject"] = "Subject / course code is required and cannot be blank."
    else:
        cleaned["subject"] = subject

    # Task type validation: required, must be in supported list
    task_type_raw = form_data.get("task_type") or ""
    task_type = task_type_raw.strip()
    if not task_type:
        errors["task_type"] = "Please select a task type."
    elif task_type not in database.VALID_TASK_TYPES:
        allowed = ", ".join(database.VALID_TASK_TYPES)
        errors["task_type"] = f"Unsupported task type. Permitted types: {allowed}."
    else:
        cleaned["task_type"] = task_type

    # Due date validation: required, valid calendar date in YYYY-MM-DD
    due_date_raw = (form_data.get("due_date") or "").strip()
    if not due_date_raw:
        errors["due_date"] = "Due date is required."
    else:
        try:
            parsed_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
            cleaned["due_date"] = parsed_date.isoformat()
        except (ValueError, TypeError):
            errors["due_date"] = "Due date must be a valid calendar date in YYYY-MM-DD format."

    # Importance validation: required integer in range 1 to 5
    importance_raw = form_data.get("importance")
    if importance_raw is None or str(importance_raw).strip() == "":
        errors["importance"] = "Importance level is required (1 to 5)."
    else:
        try:
            importance_val = int(str(importance_raw).strip())
            if not (1 <= importance_val <= 5):
                errors["importance"] = "Importance must be an integer between 1 and 5."
            else:
                cleaned["importance"] = importance_val
        except (ValueError, TypeError):
            errors["importance"] = "Importance must be an integer between 1 and 5."

    # Estimated hours validation: required, non-negative, finite number
    hours_raw = form_data.get("estimated_hours")
    if hours_raw is None or str(hours_raw).strip() == "":
        errors["estimated_hours"] = "Estimated hours is required."
    else:
        try:
            hours_val = float(str(hours_raw).strip())
            if math.isnan(hours_val) or math.isinf(hours_val):
                errors["estimated_hours"] = "Estimated hours must be a finite number."
            elif hours_val < 0:
                errors["estimated_hours"] = "Estimated hours cannot be negative."
            else:
                cleaned["estimated_hours"] = hours_val
        except (ValueError, TypeError):
            errors["estimated_hours"] = "Estimated hours must be a valid non-negative number."

    # Description: optional, clean whitespace
    desc_raw = form_data.get("description")
    if desc_raw and desc_raw.strip():
        cleaned["description"] = desc_raw.strip()
    else:
        cleaned["description"] = None

    return cleaned, errors


def create_app(test_config: dict | None = None) -> Flask:
    """
    Application factory pattern to configure and return the Flask application instance.
    
    Args:
        test_config: Optional dictionary of configuration overrides (useful for testing).

    Returns:
        Flask: The initialized and configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=True)

    # Core application configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-deadline-rescue-secret-key-step-3"),
        DATABASE=os.path.join(app.instance_path, "deadline_rescue.db"),
        DEBUG=os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1"),
    )

    if test_config:
        app.config.update(test_config)

    # Initialize SQLite database schema
    database.init_app(app)

    @app.route("/")
    def index():
        """
        Dashboard route handler.
        Retrieves all registered tasks from SQLite, computes live progress analytics,
        summary cards, subject workloads, and upcoming deadlines, and renders the dashboard template.
        """
        raw_tasks = database.get_all_tasks(app.config.get("DATABASE"))
        dashboard_data = analytics.get_dashboard_data(raw_tasks)

        return render_template(
            "dashboard.html",
            dashboard=dashboard_data,
            page_title="Academic Command Center — Deadline Rescue",
            active_page="home",
        )

    @app.route("/tasks")
    def list_tasks():
        """
        Task list route handler with smart search, filtering, and sorting.
        Retrieves all registered tasks from SQLite, enriches each with dynamic
        priority and deadline awareness, computes the global recommended next task
        across all pending tasks, applies active search/filters/sort for the display list,
        and renders the tasks template.
        """
        raw_tasks = database.get_all_tasks(app.config.get("DATABASE"))
        all_tasks = [priority.prepare_task_priority(t) for t in raw_tasks]

        # 1. Global recommended next task: always evaluated over all pending tasks in the database
        recommended_task = priority.get_recommended_next_task(all_tasks)

        # 2. Distinct available subjects for the filter dropdown
        available_subjects = priority.get_distinct_subjects(all_tasks)

        # 3. Extract and normalize query parameters
        q = request.args.get("q", "").strip()
        status = request.args.get("status", "").strip()
        subject = request.args.get("subject", "").strip()
        priority_filter = request.args.get("priority", "").strip()
        sort_by = request.args.get("sort", "recommended").strip()

        # Normalization
        if status not in ("Pending", "Completed"):
            status = ""
        if priority_filter.capitalize() not in ("Critical", "High", "Medium", "Low"):
            priority_filter = ""
        else:
            priority_filter = priority_filter.capitalize()
        valid_sorts = (
            "recommended", "deadline_asc", "deadline_desc",
            "priority_desc", "priority_asc",
            "title_asc", "title_desc", "created_desc"
        )
        if sort_by not in valid_sorts:
            sort_by = "recommended"

        has_active_filters = bool(q or status or subject or priority_filter or (sort_by != "recommended"))

        # 4. Filter and sort displayed tasks
        displayed_tasks = priority.filter_and_sort_tasks(
            all_tasks,
            q=q,
            status=status,
            subject=subject,
            priority_label=priority_filter,
            sort_by=sort_by,
        )

        return render_template(
            "tasks.html",
            tasks=displayed_tasks,
            total_tasks_count=len(all_tasks),
            recommended_task=recommended_task,
            available_subjects=available_subjects,
            has_active_filters=has_active_filters,
            q=q,
            selected_status=status,
            selected_subject=subject,
            selected_priority=priority_filter,
            selected_sort=sort_by,
            page_title="Assignments & Coursework — Deadline Rescue",
            active_page="tasks",
        )

    @app.route("/tasks/new", methods=["GET", "POST"])
    def create_task_route():
        """
        New task creation route handler.
        GET: Displays task creation form.
        POST: Performs server-side validation, writes to SQLite, and uses POST/Redirect/GET.
        """
        if request.method == "POST":
            cleaned_data, errors = validate_task_data(request.form)

            if errors:
                return (
                    render_template(
                        "task_form.html",
                        form=request.form,
                        errors=errors,
                        valid_task_types=database.VALID_TASK_TYPES,
                        is_edit=False,
                        page_title="Create New Task — Deadline Rescue",
                        active_page="tasks",
                    ),
                    400,
                )

            try:
                database.create_task(
                    title=cleaned_data["title"],
                    subject=cleaned_data["subject"],
                    task_type=cleaned_data["task_type"],
                    due_date=cleaned_data["due_date"],
                    importance=cleaned_data["importance"],
                    estimated_hours=cleaned_data["estimated_hours"],
                    description=cleaned_data["description"],
                    db_path=app.config.get("DATABASE"),
                )
                flash(f"Task '{cleaned_data['title']}' created successfully!", "success")
                return redirect(url_for("list_tasks"))
            except Exception:
                errors["general"] = "An error occurred while saving the task to the database. Please try again."
                return (
                    render_template(
                        "task_form.html",
                        form=request.form,
                        errors=errors,
                        valid_task_types=database.VALID_TASK_TYPES,
                        is_edit=False,
                        page_title="Create New Task — Deadline Rescue",
                        active_page="tasks",
                    ),
                    500,
                )

        # GET request
        return render_template(
            "task_form.html",
            form={},
            errors={},
            valid_task_types=database.VALID_TASK_TYPES,
            is_edit=False,
            page_title="Create New Task — Deadline Rescue",
            active_page="tasks",
        )

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    def edit_task_route(task_id: int):
        """
        Task edit route handler.
        GET: Displays edit form prepopulated with saved values.
        POST: Performs server-side validation and updates existing task record.
        """
        task = database.get_task_by_id(task_id, app.config.get("DATABASE"))
        if not task:
            abort(404)

        if request.method == "POST":
            cleaned_data, errors = validate_task_data(request.form)

            if errors:
                return (
                    render_template(
                        "task_form.html",
                        task=task,
                        form=request.form,
                        errors=errors,
                        valid_task_types=database.VALID_TASK_TYPES,
                        is_edit=True,
                        page_title=f"Edit Task: {task['title']} — Deadline Rescue",
                        active_page="tasks",
                    ),
                    400,
                )

            try:
                database.update_task(
                    task_id=task_id,
                    title=cleaned_data["title"],
                    subject=cleaned_data["subject"],
                    task_type=cleaned_data["task_type"],
                    due_date=cleaned_data["due_date"],
                    importance=cleaned_data["importance"],
                    estimated_hours=cleaned_data["estimated_hours"],
                    description=cleaned_data["description"],
                    db_path=app.config.get("DATABASE"),
                )
                flash(f"Task '{cleaned_data['title']}' updated successfully!", "success")
                return redirect(url_for("list_tasks"))
            except Exception:
                errors["general"] = "An error occurred while updating the task. Please try again."
                return (
                    render_template(
                        "task_form.html",
                        task=task,
                        form=request.form,
                        errors=errors,
                        valid_task_types=database.VALID_TASK_TYPES,
                        is_edit=True,
                        page_title=f"Edit Task: {task['title']} — Deadline Rescue",
                        active_page="tasks",
                    ),
                    500,
                )

        # GET request
        return render_template(
            "task_form.html",
            task=task,
            form={},
            errors={},
            valid_task_types=database.VALID_TASK_TYPES,
            is_edit=True,
            page_title=f"Edit Task: {task['title']} — Deadline Rescue",
            active_page="tasks",
        )

    @app.route("/tasks/<int:task_id>/complete", methods=["POST"])
    def complete_task_route(task_id: int):
        """
        Mark a pending task as Completed.
        Accepts POST only.
        """
        task = database.get_task_by_id(task_id, app.config.get("DATABASE"))
        if not task:
            abort(404)

        database.set_task_status(task_id, "Completed", db_path=app.config.get("DATABASE"))
        flash(f"Task '{task['title']}' marked as Completed!", "success")
        return redirect(url_for("list_tasks"))

    @app.route("/tasks/<int:task_id>/reopen", methods=["POST"])
    def reopen_task_route(task_id: int):
        """
        Reopen a completed task, setting status back to Pending.
        Accepts POST only.
        """
        task = database.get_task_by_id(task_id, app.config.get("DATABASE"))
        if not task:
            abort(404)

        database.set_task_status(task_id, "Pending", db_path=app.config.get("DATABASE"))
        flash(f"Task '{task['title']}' reopened!", "success")
        return redirect(url_for("list_tasks"))

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    def delete_task_route(task_id: int):
        """
        Delete an existing task record.
        Accepts POST only.
        """
        task = database.get_task_by_id(task_id, app.config.get("DATABASE"))
        if not task:
            abort(404)

        database.delete_task(task_id, db_path=app.config.get("DATABASE"))
        flash(f"Task '{task['title']}' was deleted successfully.", "success")
        return redirect(url_for("list_tasks"))

    @app.errorhandler(404)
    def page_not_found(error):
        """Custom 404 handler returning friendly not-found page."""
        return render_template("404.html", page_title="Not Found — Deadline Rescue"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        """Custom 500 handler returning friendly error page without leaking sensitive tracebacks."""
        return render_template("500.html", page_title="Internal Error — Deadline Rescue"), 500

    return app


# Create the application instance for WSGI runners and local development
app = create_app()

if __name__ == "__main__":
    # Local development server entry point
    port = int(os.environ.get("PORT", 5000))
    debug_mode = app.config.get("DEBUG", True)
    app.run(host="127.0.0.1", port=port, debug=debug_mode)
