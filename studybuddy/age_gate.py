"""PRIV-06: Minors and age gating.

Simple age gate: users confirm they are 13+ on registration.
For full COPPA/GDPR-K compliance, consult legal counsel.
"""
from datetime import date


def is_13_or_older(birth_year, birth_month=1, birth_day=1):
    """Check if birth date indicates 13+ years old."""
    try:
        born = date(birth_year, birth_month, birth_day)
        today = date.today()
        age = today.year - born.year - (
            (today.month, today.day) < (born.month, born.day))
        return age >= 13
    except (ValueError, TypeError):
        return False


AGE_GATE_TEXT = (
    "You must be at least 13 years old to create an account. "
    "If you are under 18, please have a parent or guardian review "
    "our Privacy Policy and Terms of Service with you."
)
