"""
Deadline Rescue — Vercel WSGI Entry Point

This module is the serverless function entry point for Vercel's Python runtime.
It imports the Flask application factory from the parent directory and exposes
the `app` WSGI callable that Vercel's runtime expects.

Vercel discovers this file via vercel.json builds → api/index.py.
All routes are forwarded here via the catch-all route in vercel.json.

IMPORTANT NOTES for Vercel's serverless model:
- The filesystem is read-only except for /tmp (which is ephemeral).
- SQLite writes are redirected to /tmp at runtime so the DB schema can be
  created on cold start. Data does NOT persist across invocations; this is
  an inherent limitation of serverless SQLite and is documented in the README.
- Local development (python app.py) continues to use the instance/ directory
  and IS fully persistent.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Path fix: make the project root importable so that `import database`,
# `import priority`, and `import analytics` resolve correctly when Vercel
# runs this file from inside the api/ subdirectory.
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ---------------------------------------------------------------------------
# On Vercel, the filesystem root is read-only. We must redirect SQLite to
# /tmp so that init_db() can write the schema file on cold start.
# /tmp is writable but ephemeral — data resets between cold starts.
# ---------------------------------------------------------------------------
_IS_VERCEL = os.environ.get("VERCEL") == "1"
if _IS_VERCEL:
    os.environ.setdefault("DB_PATH", "/tmp/deadline_rescue.db")

# ---------------------------------------------------------------------------
# Import and create the Flask application.
# The module-level `app = create_app()` in app.py is what Vercel's runtime
# binds as the WSGI handler. We re-export it here under the same name.
# ---------------------------------------------------------------------------
from app import create_app  # noqa: E402

_db_path = os.environ.get("DB_PATH") if _IS_VERCEL else None

app = create_app(
    test_config={"DATABASE": _db_path} if _db_path else None
)
