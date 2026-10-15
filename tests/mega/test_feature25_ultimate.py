"""Feature 25 ultimate: harsh tests for deadline alerts, fit score, tracker add."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.opportunities import deadline_alerts, fit_score, to_tracker_payload


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


OPPS = [
    {"id": "a", "title": "Hackathon", "organization": "Org", "days_left": 1, "link": "http://x"},
    {"id": "b", "title": "Internship", "organization": "Co", "days_left": 3, "link": "http://y"},
    {"id": "c", "title": "Old", "organization": "Co", "days_left": -5, "link": "http://z"},
    {"id": "d", "title": "Rolling", "organization": "Co", "days_left": None},
]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_alerts_never_crashes(s):
    assert _ok(deadline_alerts, [{"id": s, "title": s, "days_left": 2}])
    assert _ok(deadline_alerts, s)
    assert _ok(deadline_alerts, None)


def test_alerts_buckets():
    a = deadline_alerts(OPPS)
    assert len(a["critical"]) == 1 and a["critical"][0]["id"] == "a"
    assert len(a["soon"]) == 1 and a["soon"][0]["id"] == "b"
    assert len(a["expired"]) == 1
    assert a["alert_count"] == 2


def test_alerts_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        deadline_alerts("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_fit_never_crashes(s):
    assert _ok(fit_score, {"title": s, "eligibility": s}, [s])
    assert _ok(fit_score, s, ["python"])
    assert _ok(fit_score, None, None)


def test_fit_scoring():
    f = fit_score({"title": "Python ML Internship", "eligibility": "Python required"},
                  ["python", "java"])
    assert f["score"] >= 50
    assert "python" in f["matched"]


def test_fit_bounds():
    f = fit_score({"title": "x"}, ["a", "b", "c"])
    assert 0 <= f["score"] <= 100


def test_fit_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        fit_score("nope", ["x"])
    with pytest.raises((ValueError, TypeError)):
        fit_score({"title": "x"}, [])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_tracker_never_crashes(s):
    assert _ok(to_tracker_payload, {"title": s, "organization": s, "link": s})
    assert _ok(to_tracker_payload, s)
    assert _ok(to_tracker_payload, None)


def test_tracker_payload():
    t = to_tracker_payload({"id": "h1", "title": "SDE Intern", "organization": "Acme",
                            "type": "internship", "deadline": "2026-11-01",
                            "link": "https://acme.com/apply"})
    assert t["company"] == "Acme"
    assert t["role"] == "SDE Intern"
    assert t["stage"] == "wishlist"
    assert "2026-11-01" in t["notes"]


def test_tracker_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        to_tracker_payload({"title": "", "organization": ""})
    with pytest.raises((ValueError, TypeError)):
        to_tracker_payload("nope")
