"""
Deadline Rescue — Priority Engine & Deadline Awareness

This module is completely decoupled from web routes, HTML templates, and SQLite database
connections. All calculations are dynamic and deterministic.
"""

from datetime import date, datetime
import math
from typing import Any, Dict, List, Optional, Tuple


def parse_due_date(due_date_raw: Any) -> Optional[date]:
    """
    Safely parse a due date into a standard Python date object.
    Supports YYYY-MM-DD strings and date/datetime objects.
    Returns None if parsing fails or input is missing.
    """
    if isinstance(due_date_raw, datetime):
        return due_date_raw.date()
    if isinstance(due_date_raw, date):
        return due_date_raw
    if not due_date_raw or not isinstance(due_date_raw, str):
        return None

    try:
        return datetime.strptime(due_date_raw.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def calculate_days_remaining(due_date_input: Any, today: Optional[date] = None) -> Optional[int]:
    """
    Calculate calendar days remaining between today and the due date.
    Positive: due in future.
    0: due today.
    Negative: overdue.
    Returns None if due_date cannot be parsed.
    """
    due_date_obj = parse_due_date(due_date_input)
    if due_date_obj is None:
        return None

    ref_today = today if today is not None else date.today()
    return (due_date_obj - ref_today).days


def calculate_urgency_score(days_remaining: Optional[int]) -> int:
    """
    Calculate the urgency score (0-100) based on calendar days remaining.

    Thresholds:
    - Overdue (days < 0): 100
    - Due today (days == 0): 100
    - Due tomorrow (days == 1): 90
    - Due in 2–3 days: 75
    - Due in 4–7 days: 50
    - Due in 8–14 days: 30
    - Due in > 14 days: 10
    - Fallback (None): 10
    """
    if days_remaining is None:
        return 10

    if days_remaining <= 0:
        return 100
    elif days_remaining == 1:
        return 90
    elif 2 <= days_remaining <= 3:
        return 75
    elif 4 <= days_remaining <= 7:
        return 50
    elif 8 <= days_remaining <= 14:
        return 30
    else:  # days_remaining > 14
        return 10


def calculate_priority_score(urgency_score: float, importance: Any, estimated_hours: Any) -> float:
    """
    Calculate the overall priority score using the exact formula:
    Priority = 0.60 * U + 0.25 * (I / 5 * 100) + 0.15 * min(H / 8, 1) * 100

    Weights:
    - 60% Urgency (U: 0–100)
    - 25% Importance (I: 1–5, normalized to 100)
    - 15% Effort (H: hours, capped at 8 hours -> 100)

    Returns:
        float: Exact unrounded priority score.
    """
    # Safe Urgency
    try:
        u = float(urgency_score)
        u = max(0.0, min(100.0, u))
    except (ValueError, TypeError):
        u = 10.0

    # Safe Importance: integer 1 to 5
    try:
        i = int(importance)
        i = max(1, min(5, i))
    except (ValueError, TypeError):
        i = 3

    # Safe Estimated Hours: non-negative, finite
    try:
        h = float(estimated_hours)
        if math.isnan(h) or math.isinf(h) or h < 0.0:
            h = 0.0
    except (ValueError, TypeError):
        h = 0.0

    # Components
    urgency_contrib = 0.60 * u
    importance_contrib = 0.25 * (i / 5.0 * 100.0)
    effort_contrib = 0.15 * (min(h / 8.0, 1.0) * 100.0)

    total_score = urgency_contrib + importance_contrib + effort_contrib
    return total_score


def get_priority_label(priority_score: float) -> str:
    """
    Determine priority categorical label based on unrounded priority score:
    - 75 to 100: Critical
    - 50 to less than 75: High
    - 25 to less than 50: Medium
    - 0 to less than 25: Low
    """
    if priority_score >= 75.0:
        return "Critical"
    elif priority_score >= 50.0:
        return "High"
    elif priority_score >= 25.0:
        return "Medium"
    else:
        return "Low"


def get_deadline_status(days_remaining: Optional[int], is_completed: bool) -> Tuple[str, str]:
    """
    Determine the deadline status badge label and human-readable deadline message.

    Returns:
        Tuple[str, str]: (deadline_status, deadline_message)
    """
    if is_completed:
        return "Completed", "Completed"

    if days_remaining is None:
        return "Upcoming", "No deadline set"

    if days_remaining < 0:
        days_overdue = abs(days_remaining)
        plural = "s" if days_overdue != 1 else ""
        return "Overdue", f"Overdue by {days_overdue} day{plural}"
    elif days_remaining == 0:
        return "Due Today", "Due today"
    elif days_remaining == 1:
        return "Due Tomorrow", "Due tomorrow"
    else:
        return "Upcoming", f"Due in {days_remaining} days"


def prepare_task_priority(task: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    """
    Enrich a task dictionary with dynamic priority calculations and deadline awareness.
    Does not modify the original dictionary; returns an enriched copy.
    """
    enriched = dict(task)
    is_completed = (task.get("status") == "Completed")

    days_remaining = calculate_days_remaining(task.get("due_date"), today=today)
    urgency = calculate_urgency_score(days_remaining)

    raw_priority = calculate_priority_score(
        urgency_score=urgency,
        importance=task.get("importance", 3),
        estimated_hours=task.get("estimated_hours", 0.0),
    )

    priority_label = get_priority_label(raw_priority)
    deadline_status, deadline_message = get_deadline_status(days_remaining, is_completed=is_completed)

    enriched["days_remaining"] = days_remaining
    enriched["urgency_score"] = urgency
    enriched["priority_score"] = raw_priority
    enriched["priority_score_display"] = round(raw_priority, 2)
    enriched["priority_label"] = priority_label
    enriched["deadline_status"] = deadline_status
    enriched["deadline_message"] = deadline_message
    enriched["is_completed"] = is_completed

    return enriched


def get_recommended_next_task(
    tasks: List[Dict[str, Any]], today: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """
    Select the single highest-priority pending task.

    Ranking Rules:
    1. Only consider tasks where status == 'Pending' (never recommend completed tasks).
    2. Primary: highest priority score descending.
    3. Tie-breaker 1: earlier due date ascending (YYYY-MM-DD).
    4. Tie-breaker 2: smaller task ID ascending.

    Returns:
        Optional[Dict[str, Any]]: The enriched top-recommended task, or None if no pending tasks exist.
    """
    pending_tasks: List[Dict[str, Any]] = []

    for task in tasks:
        # Check completion status
        if task.get("status") == "Completed":
            continue

        # Ensure task is enriched with priority attributes
        if "priority_score" not in task:
            enriched = prepare_task_priority(task, today=today)
        else:
            enriched = task

        pending_tasks.append(enriched)

    if not pending_tasks:
        return None

    def sort_key(t: Dict[str, Any]):
        # Descending priority score
        score = t.get("priority_score", 0.0)
        # Ascending due date (empty or invalid string sorts last)
        due_date_str = str(t.get("due_date") or "9999-99-99")
        # Ascending task ID
        task_id = int(t.get("id") or 999999)
        return (-score, due_date_str, task_id)

    pending_tasks.sort(key=sort_key)
    return pending_tasks[0]


def get_distinct_subjects(tasks: List[Dict[str, Any]]) -> List[str]:
    """
    Extract unique course subjects from tasks, sorted alphabetically (case-insensitive).
    Deduplicates subjects in a case-insensitive manner while preserving clean display.
    Handles empty tasks list or missing subjects safely.
    """
    seen_lower = set()
    unique_subjects = []

    for task in tasks:
        subj = str(task.get("subject") or "").strip()
        if subj and subj.lower() not in seen_lower:
            seen_lower.add(subj.lower())
            unique_subjects.append(subj)

    return sorted(unique_subjects, key=lambda s: s.lower())


def filter_and_sort_tasks(
    tasks: List[Dict[str, Any]],
    q: Optional[str] = None,
    status: Optional[str] = None,
    subject: Optional[str] = None,
    priority_label: Optional[str] = None,
    sort_by: Optional[str] = "recommended",
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Filter and sort an enriched list of coursework tasks.

    Filtering:
    - q: Case-insensitive substring match against task title or subject.
         Whitespace-only queries are ignored.
    - status: 'Pending' or 'Completed' (case-sensitive or exact). Other values ignored.
    - subject: Exact case-insensitive match against task subject. Empty string ignored.
    - priority_label: 'Critical', 'High', 'Medium', 'Low'. Other values ignored.

    Sorting:
    - 'recommended': Priority score descending, earlier deadline, smaller task ID.
    - 'deadline_asc': Earliest deadline first, higher priority, smaller task ID.
    - 'deadline_desc': Latest deadline first, higher priority, smaller task ID.
    - 'priority_desc': Higher priority score first, earlier deadline, smaller task ID.
    - 'priority_asc': Lower priority score first, earlier deadline, smaller task ID.
    - 'title_asc': Title A-Z (case-insensitive), smaller task ID.
    - 'title_desc': Title Z-A (reverse case-insensitive), smaller task ID.
    - 'created_desc': Newest creation timestamp first, larger task ID.

    Returns:
        List[Dict[str, Any]]: New filtered and sorted list of task dictionaries.
    """
    # Ensure all tasks have priority engine attributes
    enriched_tasks: List[Dict[str, Any]] = []
    for t in tasks:
        if "priority_score" not in t:
            enriched_tasks.append(prepare_task_priority(t, today=today))
        else:
            enriched_tasks.append(dict(t))

    # Clean filter inputs
    clean_q = q.strip().lower() if q and str(q).strip() else None
    clean_status = status.strip() if status and str(status).strip() in ("Pending", "Completed") else None
    clean_subject = subject.strip().lower() if subject and str(subject).strip() else None

    clean_priority = None
    if priority_label and str(priority_label).strip():
        cap = str(priority_label).strip().capitalize()
        if cap in ("Critical", "High", "Medium", "Low"):
            clean_priority = cap

    # Apply filters (AND logic across all active criteria)
    filtered: List[Dict[str, Any]] = []
    for t in enriched_tasks:
        # Search filter (matches title OR subject substring)
        if clean_q is not None:
            title_text = str(t.get("title") or "").lower()
            subject_text = str(t.get("subject") or "").lower()
            if (clean_q not in title_text) and (clean_q not in subject_text):
                continue

        # Status filter
        if clean_status is not None:
            if t.get("status") != clean_status:
                continue

        # Subject filter
        if clean_subject is not None:
            t_subj = str(t.get("subject") or "").strip().lower()
            if t_subj != clean_subject:
                continue

        # Priority filter
        if clean_priority is not None:
            if t.get("priority_label") != clean_priority:
                continue

        filtered.append(t)

    # Validate and normalize sort_by option
    valid_sorts = (
        "recommended",
        "deadline_asc",
        "deadline_desc",
        "priority_desc",
        "priority_asc",
        "title_asc",
        "title_desc",
        "created_desc",
    )
    sort_mode = sort_by.strip().lower() if sort_by and str(sort_by).strip().lower() in valid_sorts else "recommended"

    # Sorting helpers
    def parse_iso_created(val: Any) -> Optional[datetime]:
        if not val or not isinstance(val, str):
            return None
        try:
            return datetime.fromisoformat(val.strip())
        except (ValueError, TypeError):
            return None

    if sort_mode == "recommended":
        filtered.sort(
            key=lambda t: (
                -float(t.get("priority_score", 0.0)),
                str(t.get("due_date") or "9999-99-99"),
                int(t.get("id") or 999999),
            )
        )
    elif sort_mode == "deadline_asc":
        def deadline_asc_key(t: Dict[str, Any]):
            d = parse_due_date(t.get("due_date"))
            return (
                d is None,  # Valid dates come first (False < True)
                d.toordinal() if d else 9999999,
                -float(t.get("priority_score", 0.0)),
                int(t.get("id") or 999999),
            )
        filtered.sort(key=deadline_asc_key)
    elif sort_mode == "deadline_desc":
        def deadline_desc_key(t: Dict[str, Any]):
            d = parse_due_date(t.get("due_date"))
            return (
                d is None,  # Valid dates come first (False < True)
                -d.toordinal() if d else 0,
                -float(t.get("priority_score", 0.0)),
                int(t.get("id") or 999999),
            )
        filtered.sort(key=deadline_desc_key)
    elif sort_mode == "priority_desc":
        def priority_desc_key(t: Dict[str, Any]):
            d = parse_due_date(t.get("due_date"))
            return (
                -float(t.get("priority_score", 0.0)),
                d is None,
                d.toordinal() if d else 9999999,
                int(t.get("id") or 999999),
            )
        filtered.sort(key=priority_desc_key)
    elif sort_mode == "priority_asc":
        def priority_asc_key(t: Dict[str, Any]):
            d = parse_due_date(t.get("due_date"))
            return (
                float(t.get("priority_score", 0.0)),
                d is None,
                d.toordinal() if d else 9999999,
                int(t.get("id") or 999999),
            )
        filtered.sort(key=priority_asc_key)
    elif sort_mode == "title_asc":
        filtered.sort(
            key=lambda t: (
                str(t.get("title") or "").strip().lower(),
                int(t.get("id") or 999999),
            )
        )
    elif sort_mode == "title_desc":
        # Two-pass stable sort:
        # 1. Tie-breaker: smaller task ID ascending
        filtered.sort(key=lambda t: int(t.get("id") or 999999))
        # 2. Primary: title descending (Python's Timsort preserves pass 1 order for ties)
        filtered.sort(key=lambda t: str(t.get("title") or "").strip().lower(), reverse=True)
    elif sort_mode == "created_desc":
        def created_desc_key(t: Dict[str, Any]):
            dt = parse_iso_created(t.get("created_at"))
            return (
                dt is None,  # Valid timestamps come first
                -dt.timestamp() if dt else 0,
                -int(t.get("id") or 0),  # Newer task ID first if timestamps equal
            )
        filtered.sort(key=created_desc_key)

    return filtered
