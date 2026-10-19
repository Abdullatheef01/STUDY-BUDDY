"""SEC-09: Authentication hardening helpers.

- Password policy: min 10 chars, block common passwords
- Email verification tokens (itsdangerous, time-limited)
- Password reset tokens (single-use via DB)
"""
import re
import secrets
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Common passwords blocklist (top ~50; full 100k list would be a data file)
COMMON_PASSWORDS = frozenset({
    "password", "1234567890", "123456789", "qwerty123", "password123",
    "admin123", "welcome123", "letmein123", "monkey123", "dragon123",
    "12345678", "123456789", "qwerty", "abc123", "password1",
    "123123", "admin", "welcome", "monkey", "login",
    "princess", "qwertyuiop", "solo", "passw0rd", "starwars",
    "trustno1", "whatever", "freedom", "hello123", "charlie",
    "aa123456", "donald", "password12", "qwerty1234", "1q2w3e4r",
    "baseball", "football", "superman", "iloveyou", "trustno1",
})

MIN_PASSWORD_LEN = 10
MAX_PASSWORD_LEN = 128


def check_password_policy(password):
    """Return (ok, message). Enforces SEC-09 password policy."""
    if not password:
        return False, "Password is required."
    if len(password) < MIN_PASSWORD_LEN:
        return False, f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if len(password) > MAX_PASSWORD_LEN:
        return False, f"Password must be at most {MAX_PASSWORD_LEN} characters."
    if password.lower() in COMMON_PASSWORDS:
        return False, "This password is too common. Please choose a stronger one."
    # Block simple sequences
    if re.fullmatch(r"(.)\1{9,}", password):
        return False, "Password cannot be all the same character."
    return True, ""


def password_strength(password):
    """Simple 0-4 strength score (zxcvbn-style heuristic, no external dep)."""
    score = 0
    if len(password) >= 10:
        score += 1
    if len(password) >= 14:
        score += 1
    if re.search(r"[a-z]", password) and re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"\d", password) and re.search(r"[^a-zA-Z0-9]", password):
        score += 1
    return min(score, 4)


def _serializer(secret_key, salt):
    return URLSafeTimedSerializer(secret_key, salt=salt)


def generate_email_token(user_id, secret_key, expires_sec=86400):
    """Generate email verification token."""
    s = _serializer(secret_key, "email-verify")
    return s.dumps({"uid": user_id})


def verify_email_token(token, secret_key, max_age=86400):
    """Return user_id or None."""
    s = _serializer(secret_key, "email-verify")
    try:
        data = s.loads(token, max_age=max_age)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


def generate_reset_token():
    """Generate a secure random reset token (stored hashed in DB)."""
    return secrets.token_urlsafe(32)
