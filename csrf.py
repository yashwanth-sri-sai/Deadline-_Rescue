"""
Deadline Rescue — CSRF Protection Module

Implements industry-standard Synchronizer Token Pattern (STP) CSRF protection
for Flask applications without requiring external dependencies (such as Flask-WTF).

Features:
- Cryptographically secure 256-bit random tokens via standard library `secrets`.
- Constant-time token verification using `hmac.compare_digest` to prevent timing attacks.
- Session-anchored token storage protected by Flask's signed session cookie.
- Automatic verification on all state-changing HTTP methods: POST, PUT, PATCH, DELETE.
- Support for token submission via form data (`csrf_token`) or HTTP headers (`X-CSRFToken` / `X-CSRF-Token`).
- Route exemption decorator (`@csrf.exempt`) for specific endpoints.
- Template global function `{{ csrf_token() }}` for seamless Jinja2 template integration.
- Custom Test Client integration to facilitate automated testing without weakening production security.
"""

from functools import wraps
import hmac
import secrets
from typing import Any, Callable
from flask import Flask, abort, current_app, request, session
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_KEY = "csrf_token"
CSRF_HEADER_KEYS = ("X-CSRFToken", "X-CSRF-Token")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def generate_csrf_token() -> str:
    """
    Generate or retrieve the active session-anchored CSRF token.
    Stores the token in the current Flask session if not already present.

    Returns:
        str: A 64-character hexadecimal CSRF token with 256 bits of entropy.
    """
    token = session.get(CSRF_SESSION_KEY)
    if not token or not isinstance(token, str):
        token = secrets.token_hex(32)
        session[CSRF_SESSION_KEY] = token
    return token


def get_submitted_csrf_token() -> str | None:
    """
    Extract the submitted CSRF token from request form data or HTTP headers.

    Returns:
        str | None: The submitted token string, or None if not found.
    """
    # 1. Check form data
    try:
        if request.form:
            val = request.form.get(CSRF_FORM_KEY)
            if val and isinstance(val, str):
                return val.strip()
    except Exception:
        pass

    # 2. Check HTTP headers (X-CSRFToken, X-CSRF-Token)
    for header in CSRF_HEADER_KEYS:
        val = request.headers.get(header)
        if val and isinstance(val, str):
            return val.strip()

    return None


def validate_csrf_token(token: str | None = None) -> bool:
    """
    Validate a submitted CSRF token against the current session token using constant-time comparison.

    Args:
        token: Optional explicit token to validate. If None, extracts from request.

    Returns:
        bool: True if the token matches the session token, False otherwise.
    """
    expected = session.get(CSRF_SESSION_KEY)
    if not expected or not isinstance(expected, str):
        return False

    if token is None:
        token = get_submitted_csrf_token()

    if not token or not isinstance(token, str):
        return False

    return hmac.compare_digest(token, expected)


class CSRFTestClient(FlaskClient):
    """
    Custom test client that automatically provides a valid session CSRF token for
    state-changing requests during testing, simulating a browser interaction.

    This preserves 100% active CSRF validation on the server without disabling
    protection during tests.

    To explicitly test missing or invalid CSRF tokens in tests:
    - Pass headers={"X-Test-No-CSRF": "1"} to omit the token.
    - Pass data={"csrf_token": "invalid"} to test invalid tokens.
    """

    def open(self, *args: Any, **kwargs: Any) -> TestResponse:
        method = kwargs.get("method")
        if not method and len(args) > 2:
            method = args[2]
        if not method:
            method = "GET"
        method = str(method).upper()

        headers = kwargs.get("headers")
        if headers is None:
            headers_dict: dict[str, str] = {}
            kwargs["headers"] = headers_dict
        elif isinstance(headers, dict):
            headers_dict = headers
        else:
            headers_dict = dict(headers)
            kwargs["headers"] = headers_dict

        omit_csrf = headers_dict.pop("X-Test-No-CSRF", None)
        data = kwargs.get("data")

        # Check if caller already supplied an explicit csrf_token in form data or headers
        has_form_csrf = isinstance(data, dict) and (CSRF_FORM_KEY in data)
        has_header_csrf = any(h in headers_dict for h in CSRF_HEADER_KEYS)

        if (
            method not in SAFE_METHODS
            and not omit_csrf
            and not has_form_csrf
            and not has_header_csrf
        ):
            with self.session_transaction() as sess:
                if CSRF_SESSION_KEY not in sess:
                    sess[CSRF_SESSION_KEY] = secrets.token_hex(32)
                token = sess[CSRF_SESSION_KEY]
            headers_dict[CSRF_HEADER_KEYS[0]] = token

        return super().open(*args, **kwargs)


class CSRFProtect:
    """
    Flask CSRF protection extension adhering to the standard Flask extension pattern.
    """

    def __init__(self, app: Flask | None = None):
        self._exempt_views: set[str] = set()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        """
        Initialize CSRF protection on the Flask application.
        """
        app.extensions["csrf"] = self

        # Register template global function: {{ csrf_token() }}
        app.jinja_env.globals["csrf_token"] = generate_csrf_token

        # Register pre-request protection hook
        app.before_request(self._csrf_protect_hook)

        # Register CSRFTestClient as the app's test client class
        app.test_client_class = CSRFTestClient

    def exempt(self, view_func: Callable) -> Callable:
        """
        Decorator to exempt a specific view function from CSRF protection.
        """
        setattr(view_func, "_csrf_exempt", True)
        return view_func

    def _csrf_protect_hook(self):
        """
        Request pre-processing hook to validate CSRF tokens on all state-changing requests.
        """
        if request.method in SAFE_METHODS:
            return None

        # Check if view function is exempt
        endpoint = request.endpoint
        if endpoint and endpoint in current_app.view_functions:
            view_func = current_app.view_functions[endpoint]
            if getattr(view_func, "_csrf_exempt", False):
                return None

        submitted = get_submitted_csrf_token()
        if not submitted:
            abort(400, description="CSRF token missing. Form submission rejected.")

        expected = session.get(CSRF_SESSION_KEY)
        if not expected:
            abort(400, description="CSRF session token missing. Please refresh and try again.")

        if not hmac.compare_digest(submitted, expected):
            abort(400, description="CSRF token invalid. Form submission rejected.")

        return None


# Module-level instance for convenient imports
csrf = CSRFProtect()
init_app = csrf.init_app
exempt = csrf.exempt
