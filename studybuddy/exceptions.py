"""ARC-09: Custom exceptions and central error handling.

Replaces bare `except Exception` with specific exception types.
"""
import logging

log = logging.getLogger(__name__)


class StudyBuddyError(Exception):
    """Base for all application errors."""
    status_code = 500
    user_message = "Something went wrong. Please try again."


class ValidationError(StudyBuddyError):
    """Invalid user input."""
    status_code = 400
    user_message = "Invalid input. Please check and try again."


class ExternalServiceError(StudyBuddyError):
    """Third-party API/service failed."""
    status_code = 502
    user_message = "An external service is unavailable. Please try again later."


class QuotaExceeded(StudyBuddyError):
    """Rate limit or quota exceeded."""
    status_code = 429
    user_message = "You've hit a limit. Please try again later."


class NotFoundError(StudyBuddyError):
    """Resource not found or not owned by user."""
    status_code = 404
    user_message = "Not found."


class AuthRequiredError(StudyBuddyError):
    """Login required."""
    status_code = 401
    user_message = "Please log in to continue."


def handle_studybuddy_error(error):
    """Central error handler — returns consistent JSON/HTML."""
    from flask import jsonify, request
    log.warning("app_error type=%s msg=%s path=%s",
                type(error).__name__, str(error)[:200],
                request.path if request else "?")
    if request and request.path.startswith("/api/"):
        return jsonify({"error": error.user_message}), error.status_code
    # For HTML, let Flask's error handlers render the page
    from werkzeug.exceptions import HTTPException
    http_exc = HTTPException(description=error.user_message)
    http_exc.code = error.status_code
    raise http_exc
