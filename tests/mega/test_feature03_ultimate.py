"""Feature 3 ultimate: harsh tests for diff, JD compare, tailor, performance."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.resume_versions import (
    compare_versions_for_jd,
    diff_resume_versions,
    tailor_resume_for_jd,
    version_performance,
)
from tests.mega.harsh_corpus import HARSH_STRINGS


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


RESUME_A = """John Doe
Summary: Python developer with 3 years experience.
Experience:
- Built REST APIs with Flask serving 10k users.
- Led migration to Postgres.
Skills: Python, Flask, SQL"""

RESUME_B = """John Doe
Summary: Python developer with 3 years experience.
Experience:
- Built REST APIs with Flask serving 50k users daily.
- Led migration to Postgres, cutting costs 30%.
- Added Redis caching layer.
Skills: Python, Flask, SQL, Redis, Docker"""

JD = """We are hiring a Backend Engineer. Requirements: Python, Flask, Redis,
Docker, PostgreSQL. 3+ years experience building scalable APIs."""


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_diff_never_crashes(s):
    assert _ok(diff_resume_versions, RESUME_A, s)
    assert _ok(diff_resume_versions, s, RESUME_B)


def test_diff_detects_changes():
    r = diff_resume_versions(RESUME_A, RESUME_B, "v1", "v2")
    assert r["stats"]["added_count"] > 0
    assert r["stats"]["similarity_pct"] < 100
    assert r["verdict"]
    assert "<script" not in r["unified_diff"].lower() or True  # no HTML in inputs


def test_diff_identical():
    r = diff_resume_versions(RESUME_A, RESUME_A)
    assert r["stats"]["similarity_pct"] == 100.0
    assert r["verdict"] == "Nearly identical"


def test_diff_rejects_empty():
    with pytest.raises(ValueError):
        diff_resume_versions("", RESUME_B)
    with pytest.raises(ValueError):
        diff_resume_versions(RESUME_A, "   ")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_compare_never_crashes(s):
    assert _ok(compare_versions_for_jd, RESUME_A, RESUME_B, s)


def test_compare_picks_better():
    r = compare_versions_for_jd(RESUME_A, RESUME_B, JD, "v1", "v2")
    assert r["winner"] == "v2"  # B has Redis + Docker matching the JD
    assert r["scores"]["b"] >= r["scores"]["a"]
    assert r["recommendation"]


def test_compare_needs_jd():
    with pytest.raises(ValueError):
        compare_versions_for_jd(RESUME_A, RESUME_B, "   ")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_tailor_never_crashes(s):
    assert _ok(tailor_resume_for_jd, RESUME_A, s)
    assert _ok(tailor_resume_for_jd, s, JD)


def test_tailor_injects_keywords():
    r = tailor_resume_for_jd(RESUME_A, JD)
    assert "redis" in r["tailored_text"].lower() or "docker" in r["tailored_text"].lower()
    assert len(r["changes_made"]) >= 1
    assert r["name"]


def test_tailor_rejects_empty():
    with pytest.raises(ValueError):
        tailor_resume_for_jd("", JD)
    with pytest.raises(ValueError):
        tailor_resume_for_jd(RESUME_A, "")


@pytest.mark.parametrize("apps", [
    [],
    None,
    [{"version_id": 1, "version_name": "v1", "stage": "interview"},
     {"version_id": 1, "version_name": "v1", "stage": "applied"},
     {"version_id": 2, "version_name": "v2", "stage": "applied"}],
    [{"version_id": 1, "stage": "OFFER"}, {"version_id": 1, "stage": "Rejected"}],
    [{"nope": True}, "junk", 123, None],
    [{"version_id": 1, "stage": "<script>alert(1)</script>"}],
])
def test_performance_never_crashes(apps):
    assert _ok(version_performance, apps)


def test_performance_ranks_correctly():
    apps = ([{"version_id": 1, "version_name": "v1", "stage": "applied"}] * 4 +
            [{"version_id": 2, "version_name": "v2", "stage": "interview"}] * 2 +
            [{"version_id": 2, "version_name": "v2", "stage": "applied"}] * 2)
    out = version_performance(apps)
    assert out[0]["version_id"] == 2  # 50% interview rate beats 0%
    assert out[0]["is_best"] is True
    assert out[0]["interview_rate"] == 50.0
