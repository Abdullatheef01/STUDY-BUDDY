"""Feature 5 ultimate: harsh tests for search check, content plan, JD gap."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.linkedin_grader import (
    content_plan,
    profile_jd_gap,
    recruiter_search_check,
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


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_search_never_crashes(s):
    assert _ok(recruiter_search_check, s, s, s, [s, s])
    assert _ok(recruiter_search_check, s, s, s, s)  # non-list queries


def test_search_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        recruiter_search_check("h", "a", "s", "not a list")


def test_search_headline_weighted():
    # Same keyword in headline vs only in about: headline wins.
    q = ["python developer"]
    in_headline = recruiter_search_check("Python Developer", "nothing here", "", q)
    in_about = recruiter_search_check("Student", "python developer here", "", q)
    assert (in_headline["queries"][0]["visibility"]
            > in_about["queries"][0]["visibility"])


def test_search_no_html_leak():
    r = recruiter_search_check("<script>alert(1)</script>Python Dev", "x", "y",
                               ["python"])
    assert "<script" not in str(r)


def test_search_empty_queries():
    r = recruiter_search_check("h", "a", "s", [])
    assert r["discoverability_score"] == 0.0


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_plan_never_crashes(s):
    assert _ok(content_plan, [s, s])
    assert _ok(content_plan, s)  # non-list


def test_plan_structure():
    c = content_plan(["Python", "React"], weeks=4)
    assert c["total_posts"] == 12
    assert len(c["weeks"]) == 4
    for w in c["weeks"]:
        assert len(w["posts"]) == 3
        for p in w["posts"]:
            assert p["prompt"] and "{skill}" not in p["prompt"]


def test_plan_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        content_plan([])
    with pytest.raises((ValueError, TypeError)):
        content_plan("Python")


def test_plan_weeks_clamped():
    c = content_plan(["Python"], weeks=999)
    assert len(c["weeks"]) == 12
    c2 = content_plan(["Python"], weeks=-5)
    assert len(c2["weeks"]) == 1


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_gap_never_crashes(s):
    assert _ok(profile_jd_gap, s, s, s, s, s)


def test_gap_finds_missing():
    g = profile_jd_gap("Student", "Learning", "Projects", "Python",
                       "Hiring Python Flask Redis Docker engineer")
    assert g["sections_needing_work"] >= 1
    assert all("rewrite_tip" in x for x in g["gaps"])


def test_gap_aligned_profile():
    g = profile_jd_gap("Python Flask Redis Developer", "Python Flask Redis expert",
                       "Built Python Flask Redis systems", "Python, Flask, Redis",
                       "Hiring Python Flask Redis engineer")
    # Core skill keywords must not be flagged as missing anywhere.
    all_missing = [kw for x in g["gaps"] for kw in x["missing_keywords"]]
    for skill in ("python", "flask", "redis"):
        assert skill not in [m.lower() for m in all_missing]


def test_gap_needs_jd():
    with pytest.raises(ValueError):
        profile_jd_gap("h", "a", "e", "s", "   ")
