"""Feature 17 ultimate: harsh tests for exam-day sim, ROI, renewal tracker."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from datetime import date, timedelta

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.cert_guide import (
    exam_day_simulator, cert_roi, renewal_status, all_certs,
)


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


CERT = all_certs()[0]["id"]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_sim_never_crashes(s):
    assert _ok(exam_day_simulator, s, seed=1)
    assert _ok(exam_day_simulator, None)


def test_sim_structure():
    e = exam_day_simulator(CERT, seed=1)
    assert e["minutes"] > 0
    assert e["cert"]["id"] == CERT
    assert e["instructions"]
    assert all("answer" not in q for q in e["questions"])


def test_sim_rejects_unknown():
    with pytest.raises((ValueError, TypeError)):
        exam_day_simulator("no_such_cert_xyz")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_roi_never_crashes(s):
    assert _ok(cert_roi, s, 6.0)
    assert _ok(cert_roi, CERT, s)


def test_roi_math():
    r = cert_roi(CERT, 6.0)
    assert r["cost_inr"] >= 0
    assert r["expected_bump_lpa"] > 0
    assert r["payback_months"] is None or r["payback_months"] >= 0
    assert r["verdict"]


def test_roi_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        cert_roi(CERT, "not a number")
    with pytest.raises((ValueError, TypeError)):
        cert_roi(CERT, -5)
    with pytest.raises((ValueError, TypeError)):
        cert_roi("nope", 6.0)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_renewal_never_crashes(s):
    assert _ok(renewal_status, s, "2024-01-15")
    assert _ok(renewal_status, CERT, s)


def test_renewal_urgency_ladder():
    today = date.today()
    cases = [
        (today - timedelta(days=365 * 3 - 5), "critical"),
        (today - timedelta(days=365 * 3 - 20), "warning"),
        (today - timedelta(days=365 * 3 - 60), "upcoming"),
        (today - timedelta(days=100), "healthy"),
        (today - timedelta(days=365 * 4), "expired"),
    ]
    for earned, expected in cases:
        r = renewal_status(CERT, earned.isoformat())
        assert r["urgency"] == expected, f"{earned}: got {r['urgency']}"


def test_renewal_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        renewal_status(CERT, "not-a-date")
    with pytest.raises((ValueError, TypeError)):
        renewal_status("nope", "2024-01-01")
