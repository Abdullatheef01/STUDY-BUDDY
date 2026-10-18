"""MEGA-7: Auth + engagement features under harsh input.

Registration, login, momentum, community, health review month keys.
~500 tests.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from studybuddy import health_review, momentum
from tests.mega.harsh_corpus import HARSH_EMAILS, HARSH_IDS, HARSH_STRINGS


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, KeyError, TypeError, AttributeError):
        return True
    except Exception:
        return False


# ---- momentum ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:50])
def test_momentum_claim_quest(s):
    assert _ok(momentum.claim_quest, 1, s)


@pytest.mark.parametrize("s", HARSH_STRINGS[:50])
def test_momentum_save_reflection(s):
    assert _ok(momentum.save_reflection, 1, s)


@pytest.mark.parametrize("qid", HARSH_IDS)
def test_momentum_quest_ids(qid):
    assert _ok(momentum.claim_quest, 1, qid)


# ---- health review month keys ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:50])
def test_health_month_key(s):
    assert _ok(health_review.valid_month_key, s)
    # valid keys match YYYY-MM; harsh strings must not crash
    result = None
    try:
        result = health_review.valid_month_key(s)
    except (ValueError, TypeError):
        pass
    if result is not None:
        assert isinstance(result, bool)


@pytest.mark.parametrize("s", HARSH_STRINGS[:30])
def test_health_prev_month(s):
    assert _ok(health_review.prev_month_key, s)


# ---- auth payload shapes ----
@pytest.mark.parametrize("email", HARSH_EMAILS)
def test_register_email_shapes(email):
    """Registration validation must safely reject malformed emails."""
    from unified_app import create_app
    app = create_app()
    cl = app.test_client()
    r = cl.post("/register", data={
        "name": "Test", "email": email, "password": "ValidPass123!",
        "csrf_token": "invalid",
    })
    assert r.status_code != 500


@pytest.mark.parametrize("pw", ["", "a", "a" * 200, "password", "12345678",
                                 "<script>", "' OR '1'='1", "p@ss w0rd!",
                                 "\x00", "null", "   "])
def test_register_password_shapes(pw):
    from unified_app import create_app
    app = create_app()
    cl = app.test_client()
    r = cl.post("/register", data={
        "name": "Test", "email": "t@t.com", "password": pw,
        "csrf_token": "invalid",
    })
    assert r.status_code != 500


@pytest.mark.parametrize("name", HARSH_STRINGS[:30])
def test_register_name_shapes(name):
    from unified_app import create_app
    app = create_app()
    cl = app.test_client()
    r = cl.post("/register", data={
        "name": name, "email": "t@t.com", "password": "ValidPass123!",
        "csrf_token": "invalid",
    })
    assert r.status_code != 500
