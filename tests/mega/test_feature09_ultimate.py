"""Feature 9 ultimate: harsh tests for case study, link checker, recruiter preview."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.portfolio import (
    check_demo_links,
    generate_case_study,
    recruiter_preview,
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
def test_case_never_crashes(s):
    assert _ok(generate_case_study, {"title": s, "description": s, "tech": [s]})
    assert _ok(generate_case_study, s)
    assert _ok(generate_case_study, None)


def test_case_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        generate_case_study("not a dict")
    with pytest.raises((ValueError, TypeError)):
        generate_case_study({"title": "   "})


def test_case_structure():
    c = generate_case_study({
        "title": "ShipIt",
        "description": "Deploys were painful. I built a dashboard. Rollbacks dropped 90% for 200 users.",
        "tech": ["Python"], "role": "Solo"})
    assert c["completeness_pct"] >= 60
    assert c["markdown"]
    assert 0 <= c["completeness_pct"] <= 100


def test_case_flags_gaps():
    c = generate_case_study({"title": "X"})
    assert len(c["prompts"]) >= 3  # no desc, no tech, no demo


def test_case_no_html():
    c = generate_case_study({"title": "<script>alert(1)</script>App",
                             "description": "Does <b>things</b>."})
    assert "<script" not in c["markdown"]


@pytest.mark.parametrize("projects", [
    [],
    [{"title": "x", "demo_link": "not-a-url"}],
    [{"title": "x", "demo_link": "https://bad.invalid.example"}],
    [{"title": "x", "link": "ftp://x.com/y"}],
    "not a list",
    [{"title": "x"}],  # no links at all
])
def test_links_never_crashes(projects):
    assert _ok(check_demo_links, projects, timeout=3)


def test_links_marks_invalid():
    r = check_demo_links([{"title": "x", "demo_link": "notaurl"}], timeout=3)
    assert r["checked"] == 1
    assert r["alive_count"] == 0
    assert r["dead"]


def test_links_example_com():
    r = check_demo_links([{"title": "x", "demo_link": "https://example.com"}], timeout=8)
    assert r["checked"] == 1
    # example.com should be reachable; if the sandbox blocks it, result must still be well-formed
    assert isinstance(r["alive_count"], int)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_preview_never_crashes(s):
    assert _ok(recruiter_preview, {"display_name": s, "headline": s,
                                   "skills": [s], "projects": [{"title": s}]})
    assert _ok(recruiter_preview, s)


def test_preview_rejects_non_dict():
    with pytest.raises((ValueError, TypeError)):
        recruiter_preview("nope")


def test_preview_good_beats_empty():
    good = recruiter_preview({
        "display_name": "Aarav", "headline": "Backend Developer",
        "skills": ["Python", "SQL", "Redis", "Docker", "AWS", "Flask", "Git", "Linux"],
        "projects": [{"title": "ShipIt", "description": "Served 500 users",
                      "demo_link": "https://x.com"}] * 3})
    bad = recruiter_preview({})
    assert good["score"] > bad["score"]
    assert good["grade"].startswith("A")
    assert bad["fixes"]


def test_preview_bounds():
    r = recruiter_preview({"display_name": "x" * 5000, "skills": ["a"] * 100,
                           "projects": [{"title": "t"}] * 50})
    assert 0 <= r["score"] <= 100
