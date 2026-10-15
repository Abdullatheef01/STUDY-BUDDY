"""Feature 7 ultimate: harsh tests for AI-role fit, roadmap export, delta."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.career_assessment import ai_role_fit, roadmap_export, assessment_delta


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_fit_never_crashes(s):
    assert _ok(ai_role_fit, [s, s])
    assert _ok(ai_role_fit, s)


def test_fit_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        ai_role_fit("python")


def test_fit_ranks_sensibly():
    r = ai_role_fit(["python", "llm", "rag", "langchain", "vector db",
                     "evaluation", "api", "prompt engineering"])
    assert r["roles"][0]["id"] == "genai_engineer"
    assert r["best_bet"] == "GenAI Engineer"
    assert all(0 <= x["fit"] <= 100 for x in r["roles"])


def test_fit_empty_skills():
    r = ai_role_fit([])
    assert len(r["roles"]) == 5
    assert all(x["fit"] == 0 for x in r["roles"])


def test_fit_no_html():
    r = ai_role_fit(["<script>alert(1)</script>python"])
    assert "<script" not in str(r)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_roadmap_never_crashes(s):
    assert _ok(roadmap_export, {"name": s, "skills": [s, s]}, 8)


def test_roadmap_structure():
    p = roadmap_export({"name": "Backend Dev", "skills": ["Python", "SQL"]}, weeks=8)
    assert p["total_weeks"] == 8
    assert len(p["weeks"]) == 8
    phases = [w["phase"] for w in p["weeks"]]
    assert phases[0] == "Foundations" and phases[-1] == "Polish"
    assert len(p["milestones"]) == 4


def test_roadmap_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        roadmap_export("not a dict")
    with pytest.raises((ValueError, TypeError)):
        roadmap_export({"name": "x", "skills": []})


def test_roadmap_weeks_clamped():
    assert roadmap_export({"name": "x", "skills": ["a"]}, weeks=999)["total_weeks"] == 52
    assert roadmap_export({"name": "x", "skills": ["a"]}, weeks=1)["total_weeks"] == 4


@pytest.mark.parametrize("pair", [
    ([], []),
    (None, None),
    ([{"id": "a", "match": "bad"}], [{"id": "a", "match": 50}]),
    ([{"no_id": 1}], [{"id": "a", "match": 50}]),
])
def test_delta_never_crashes(pair):
    assert _ok(assessment_delta, pair[0], pair[1])


def test_delta_detects_growth():
    old = [{"id": "be", "name": "Backend", "match": 60}]
    new = [{"id": "be", "name": "Backend", "match": 80}]
    d = assessment_delta(old, new)
    assert d["grew"][0]["delta"] == 20.0
    assert d["top_mover"]["id"] == "be"


def test_delta_detects_shrink():
    old = [{"id": "ds", "name": "Data", "match": 70}]
    new = [{"id": "ds", "name": "Data", "match": 50}]
    d = assessment_delta(old, new)
    assert d["shrank"][0]["delta"] == -20.0


def test_delta_needs_both():
    with pytest.raises((ValueError, TypeError)):
        assessment_delta([], [{"id": "a", "match": 50}])
