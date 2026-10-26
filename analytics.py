"""
Deadline Rescue — Dashboard Analytics Service
Step 6: Progress analytics, summary metrics, workload by subject, and upcoming deadlines.

This module provides testable, decoupled analytics functions using Python's standard library
and existing task fields. All calculations are dynamic and deterministic.
"""

from datetime import date
import math
from typing import Any, Dict, List, Optional

import priority


def get_summary_stats(
    tasks: List[Dict[str, Any]], today: Optional[date] = None
) -> Dict[str, Any]:
    """
    Calculate summary metrics across all tasks in the database.

    Metrics:
    - total_tasks: Count of all tasks (Pending + Completed).
    - pending_tasks: Count of tasks with status 'Pending'.
    - completed_tasks: Count of tasks with status 'Completed'.
    - overdue_tasks: Pending tasks with valid due_date < today. (Completed tasks NEVER overdue).
    - due_today_tasks: Pending tasks with valid due_date == today.
    - due_soon_tasks: Pending tasks with valid due_date where 1 <= days_remaining <= 7.
    - completion_percentage: completed_tasks / total_tasks * 100 (0.0 if total_tasks == 0).

    Args:
        tasks: Full list of task dictionaries from database.
        today: Optional reference date for deterministic testing. Defaults to date.today().

    Returns:
        Dict[str, Any]: Calculated summary metrics.
    """
    ref_today = today if today is not None else date.today()

    total_tasks = len(tasks)
    pending_tasks = 0
    completed_tasks = 0
    overdue_tasks = 0
    due_today_tasks = 0
    due_soon_tasks = 0

    for task in tasks:
        status = task.get("status")
        is_completed = (status == "Completed")

        if is_completed:
            completed_tasks += 1
            # Completed tasks are strictly excluded from active deadline categories
            continue

        # Task is Pending
        pending_tasks += 1

        days_remaining = priority.calculate_days_remaining(task.get("due_date"), today=ref_today)

        # Invalid or missing dates must NOT be counted as overdue, due today, or due soon
        if days_remaining is None:
            continue

        if days_remaining < 0:
            overdue_tasks += 1
        elif days_remaining == 0:
            due_today_tasks += 1
        elif 1 <= days_remaining <= 7:
            due_soon_tasks += 1

    if total_tasks > 0:
        completion_percentage = (completed_tasks / total_tasks) * 100.0
    else:
        completion_percentage = 0.0

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,
        "due_today_tasks": due_today_tasks,
        "due_soon_tasks": due_soon_tasks,
        "completion_percentage": completion_percentage,
        "completion_percentage_display": round(completion_percentage, 1),
    }


def get_workload_by_subject(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate estimated coursework workload by subject for active (Pending) tasks.

    Rules:
    - Only Pending tasks contribute to remaining hours.
    - Groups subjects case-insensitively, preserving a clean display name.
    - Blank or missing subjects fallback to 'Unspecified Subject'.
    - Handles malformed or negative estimated_hours safely (fallback 0.0).
    - Sorts subjects alphabetically by name.
    - Calculates total remaining hours across all pending tasks.

    Returns:
        Dict[str, Any]: {
            "subjects": List[Dict[str, Any]],
            "total_remaining_hours": float,
            "has_workload": bool,
        }
    """
    # Group accumulator: key is normalized lowercase subject
    # value: {"display_name": str, "pending_count": int, "completed_count": int, "remaining_hours": float}
    groups: Dict[str, Dict[str, Any]] = {}

    for task in tasks:
        # Subject extraction and normalization
        raw_subj = task.get("subject")
        if raw_subj and str(raw_subj).strip():
            clean_subj = str(raw_subj).strip()
            group_key = clean_subj.lower()
        else:
            clean_subj = "Unspecified Subject"
            group_key = "unspecified subject"

        if group_key not in groups:
            groups[group_key] = {
                "subject": clean_subj,
                "pending_tasks": 0,
                "completed_tasks": 0,
                "remaining_hours": 0.0,
            }

        status = task.get("status")
        if status == "Completed":
            groups[group_key]["completed_tasks"] += 1
            # Completed tasks do not add to remaining hours
        else:
            groups[group_key]["pending_tasks"] += 1

            # Safe extraction of estimated hours
            raw_hours = task.get("estimated_hours")
            try:
                h = float(raw_hours) if raw_hours is not None else 0.0
                if math.isnan(h) or math.isinf(h) or h < 0.0:
                    h = 0.0
            except (ValueError, TypeError):
                h = 0.0

            groups[group_key]["remaining_hours"] += h

    # Calculate total remaining hours across all pending tasks
    total_remaining_hours = sum(g["remaining_hours"] for g in groups.values())

    # Build sorted list of subject summaries
    subject_list: List[Dict[str, Any]] = []
    for g in groups.values():
        rem_hrs = round(g["remaining_hours"], 2)
        if total_remaining_hours > 0:
            pct_of_total = round((g["remaining_hours"] / total_remaining_hours) * 100.0, 1)
        else:
            pct_of_total = 0.0

        subject_list.append({
            "subject": g["subject"],
            "pending_tasks": g["pending_tasks"],
            "completed_tasks": g["completed_tasks"],
            "total_tasks": g["pending_tasks"] + g["completed_tasks"],
            "remaining_hours": rem_hrs,
            "percentage_of_total_hours": pct_of_total,
        })

    # Sort alphabetically by subject name
    subject_list.sort(key=lambda s: s["subject"].lower())

    return {
        "subjects": subject_list,
        "total_remaining_hours": round(total_remaining_hours, 2),
        "has_workload": bool(total_remaining_hours > 0),
    }


def get_upcoming_deadlines(
    tasks: List[Dict[str, Any]], limit: int = 5, today: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Select up to `limit` upcoming active deliverables for dashboard display.

    Rules:
    1. Include ONLY Pending tasks with valid due_date >= today (due today or future).
    2. Exclude overdue tasks (days_remaining < 0).
    3. Exclude completed tasks (status == 'Completed').
    4. Exclude tasks with missing or unparseable deadlines.
    5. Sort order:
       - Earliest deadline first (due_date ascending)
       - Priority score descending (tie-breaker 1)
       - Task ID ascending (tie-breaker 2)
    6. Enrich each task with priority scoring, priority label, and deadline status.

    Returns:
        List[Dict[str, Any]]: Up to `limit` sorted upcoming tasks.
    """
    ref_today = today if today is not None else date.today()
    candidates: List[Dict[str, Any]] = []

    for task in tasks:
        # 1. Must be Pending
        if task.get("status") == "Completed":
            continue

        # 2. Must have valid due date
        d_obj = priority.parse_due_date(task.get("due_date"))
        if d_obj is None:
            continue

        days_remaining = (d_obj - ref_today).days
        # 3. Must be due today or in future (exclude overdue)
        if days_remaining < 0:
            continue

        # Enrich with priority attributes
        if "priority_score" not in task:
            enriched = priority.prepare_task_priority(task, today=ref_today)
        else:
            enriched = dict(task)

        enriched["_due_date_obj"] = d_obj
        candidates.append(enriched)

    # Sort: earliest deadline first, priority score descending, task ID ascending
    def sort_key(t: Dict[str, Any]):
        return (
            t["_due_date_obj"].toordinal(),
            -float(t.get("priority_score", 0.0)),
            int(t.get("id") or 999999),
        )

    candidates.sort(key=sort_key)

    # Clean internal temporary object
    result: List[Dict[str, Any]] = []
    for item in candidates[:limit]:
        cleaned = dict(item)
        cleaned.pop("_due_date_obj", None)
        result.append(cleaned)

    return result


def get_dashboard_data(
    tasks: List[Dict[str, Any]], today: Optional[date] = None
) -> Dict[str, Any]:
    """
    Assemble the complete dashboard analytics payload for template rendering.

    Args:
        tasks: Full collection of task dictionaries from SQLite.
        today: Optional reference date.

    Returns:
        Dict[str, Any]: Complete dashboard data structure.
    """
    summary = get_summary_stats(tasks, today=today)
    workload = get_workload_by_subject(tasks)
    upcoming = get_upcoming_deadlines(tasks, limit=5, today=today)

    return {
        "summary": summary,
        "workload": workload,
        "upcoming_deadlines": upcoming,
        "total_tasks_count": summary["total_tasks"],
        "has_tasks": bool(summary["total_tasks"] > 0),
        "has_pending_tasks": bool(summary["pending_tasks"] > 0),
    }
