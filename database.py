"""
Deadline Rescue — SQLite Database Layer
Step 2: Database foundation, schema definition, and task persistence.

This module provides simple, reliable, and parameterized database operations
using Python's built-in sqlite3 library.
"""

from contextlib import contextmanager
from datetime import datetime
import os
import sqlite3
from typing import Generator, List, Optional
from flask import Flask, current_app, g

# Supported task categories allowed by the system
VALID_TASK_TYPES = ("Assignment", "Quiz", "Lab", "Project", "Other")

# Supported task statuses
VALID_STATUSES = ("Pending", "Completed")

# Schema definition for Step 2
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    subject TEXT NOT NULL,
    task_type TEXT NOT NULL,
    due_date TEXT NOT NULL,
    importance INTEGER NOT NULL CHECK (importance >= 1 AND importance <= 5),
    estimated_hours REAL NOT NULL CHECK (estimated_hours >= 0),
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL
);
"""


def get_db_path(custom_path: Optional[str] = None) -> str:
    """
    Determine the absolute file path for the SQLite database.
    Guarantees a stable path inside the instance directory, independent of CWD.
    """
    if custom_path:
        return os.path.abspath(custom_path)

    try:
        if current_app and current_app.config.get("DATABASE"):
            return os.path.abspath(current_app.config["DATABASE"])
    except RuntimeError:
        # Outside of application context
        pass

    # Fallback to instance directory relative to this module
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "instance", "deadline_rescue.db")


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager providing a safe, parameterized SQLite connection.
    Automatically closes the connection upon completion.
    """
    path = get_db_path(db_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def get_db() -> sqlite3.Connection:
    """
    Retrieve or create a database connection for the current Flask request context.
    Caches connection on Flask's `g` object.
    """
    if "db" not in g:
        path = get_db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(error: Optional[BaseException] = None) -> None:
    """
    Flask teardown hook to close the request-scoped database connection.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize the database and create tables if they do not exist.
    """
    with get_db_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def create_task(
    title: str,
    subject: str,
    task_type: str,
    due_date: str,
    importance: int,
    estimated_hours: float,
    description: Optional[str] = None,
    status: str = "Pending",
    db_path: Optional[str] = None,
) -> int:
    """
    Insert a new task record into the database using parameterized SQL.

    Returns:
        int: The primary key ID of the newly inserted task.
    """
    created_at = datetime.utcnow().isoformat()
    clean_description = description.strip() if description and description.strip() else None

    query = """
    INSERT INTO tasks (
        title, description, subject, task_type,
        due_date, importance, estimated_hours, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            (
                title.strip(),
                clean_description,
                subject.strip(),
                task_type.strip(),
                due_date.strip(),
                int(importance),
                float(estimated_hours),
                status.strip(),
                created_at,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_tasks(db_path: Optional[str] = None) -> List[dict]:
    """
    Retrieve all tasks in a predictable order (earliest deadline first, highest importance second).

    Returns:
        List[dict]: List of task dictionaries.
    """
    query = """
    SELECT id, title, description, subject, task_type,
           due_date, importance, estimated_hours, status, created_at
    FROM tasks
    ORDER BY due_date ASC, importance DESC, id ASC;
    """

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_task_by_id(task_id: int, db_path: Optional[str] = None) -> Optional[dict]:
    """
    Retrieve a single task by its primary key ID.
    
    Returns:
        Optional[dict]: The task dictionary if found, None otherwise.
    """
    query = """
    SELECT id, title, description, subject, task_type,
           due_date, importance, estimated_hours, status, created_at
    FROM tasks
    WHERE id = ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (int(task_id),))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_task(
    task_id: int,
    title: str,
    subject: str,
    task_type: str,
    due_date: str,
    importance: int,
    estimated_hours: float,
    description: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """
    Update editable fields of an existing task while preserving id, created_at, and status.
    Uses parameterized SQL.
    
    Returns:
        bool: True if a task record was updated, False if task_id does not exist.
    """
    clean_description = description.strip() if description and description.strip() else None

    query = """
    UPDATE tasks
    SET title = ?,
        description = ?,
        subject = ?,
        task_type = ?,
        due_date = ?,
        importance = ?,
        estimated_hours = ?
    WHERE id = ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            query,
            (
                title.strip(),
                clean_description,
                subject.strip(),
                task_type.strip(),
                due_date.strip(),
                int(importance),
                float(estimated_hours),
                int(task_id),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0


def set_task_status(task_id: int, status: str, db_path: Optional[str] = None) -> bool:
    """
    Update the status of an existing task (Pending or Completed).
    Rejects unsupported statuses.
    
    Returns:
        bool: True if status updated, False if task_id does not exist.
    Raises:
        ValueError: If status is not in VALID_STATUSES.
    """
    clean_status = status.strip()
    if clean_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{clean_status}'. Permitted statuses: {', '.join(VALID_STATUSES)}."
        )

    query = """
    UPDATE tasks
    SET status = ?
    WHERE id = ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (clean_status, int(task_id)))
        conn.commit()
        return cursor.rowcount > 0


def delete_task(task_id: int, db_path: Optional[str] = None) -> bool:
    """
    Delete a single task record by primary key ID.
    Uses parameterized SQL.
    
    Returns:
        bool: True if the task was found and deleted, False otherwise.
    """
    query = "DELETE FROM tasks WHERE id = ?;"
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (int(task_id),))
        conn.commit()
        return cursor.rowcount > 0


def init_app(app: Flask) -> None:
    """
    Integrate database management with the Flask application factory.
    Sets default database path in instance folder and initializes tables.
    """
    # Ensure instance directory exists
    os.makedirs(app.instance_path, exist_ok=True)

    default_db = os.path.join(app.instance_path, "deadline_rescue.db")
    app.config.setdefault("DATABASE", default_db)

    # Register teardown function for web requests
    app.teardown_appcontext(close_db)

    # Ensure tables exist on startup
    with app.app_context():
        init_db(app.config["DATABASE"])
