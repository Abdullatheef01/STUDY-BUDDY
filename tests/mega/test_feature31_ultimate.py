"""Feature 31 ultimate: harsh tests for monthly report, benchmarks, nudges."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.health_review import action_nudges, monthly_report, peer_benchmarks
from tests.mega.harsh_corpus import HARSH_STRINGS


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


REVIEW = {"month": "2026-10", "dimensions": {
    "applications": {"score": 75, "evidence": "Applied to 8 roles"},
    "interview_prep": {"score": 45, "evidence": "1 mock"},
    "learning": {"score": 60, "evidence": "2 modules"},
}}

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_report_never_crashes(s):
    assert _ok(monthly_report, {"dimensions": {"a": {"score": 50, "evidence": s}}})
    assert _ok(monthly_report, s)
    assert _ok(monthly_report, None)


def test_report_structure():
    m = monthly_report(REVIEW)
    assert m["overall"] == 60.0
    assert m["headline"]
    assert m["markdown"].startswith("#")
    assert len(m["concerns"]) >= 1  # interview_prep 45 < 60


def test_report_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        monthly_report({"dimensions": {}})
    with pytest.raises((ValueError, TypeError)):
        monthly_report("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_benchmark_never_crashes(s):
    assert _ok(peer_benchmarks, {"a": 50}, [{"a": 60}])
    assert _ok(peer_benchmarks, s, s)
    assert _ok(peer_benchmarks, None, None)


def test_benchmark_percentile():
    b = peer_benchmarks({"x": 90}, [{"x": 10}, {"x": 20}, {"x": 30}])
    assert b["benchmarks"][0]["percentile"] == 100.0
    assert "Top 10%" in b["benchmarks"][0]["standing"]


def test_benchmark_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        peer_benchmarks({}, [{"a": 1}])
    with pytest.raises((ValueError, TypeError)):
        peer_benchmarks({"a": 1}, [])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_nudges_never_crashes(s):
    assert _ok(action_nudges, {"applications": 50}, {"applications": s})
    assert _ok(action_nudges, s)
    assert _ok(action_nudges, None)


def test_nudges_low_score():
    n = action_nudges({"networking": 10, "applications": 80})
    assert any(x["dimension"] == "networking" for x in n["nudges"])


def test_nudges_drop():
    n = action_nudges({"interview_prep": 40}, {"interview_prep": 70})
    assert n["urgent_count"] == 1


def test_nudges_rejects_non_dict():
    with pytest.raises((ValueError, TypeError)):
        action_nudges("nope")
