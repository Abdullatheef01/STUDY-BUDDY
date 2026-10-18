"""Feature 16 ultimate: harsh tests for exam mode, drills, leaderboard."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.skill_quizzes import (
    certification_exam_mode,
    get_question,
    grade_exam,
    leaderboard,
    quiz_skills,
    weakness_drill,
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


SKILL = quiz_skills()[0][0]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_exam_never_crashes(s):
    assert _ok(certification_exam_mode, s, s, seed=1)
    assert _ok(certification_exam_mode, None)


def test_exam_structure():
    e = certification_exam_mode(SKILL, "aws-clf-c02", seed=1)
    assert e["minutes"] == 90
    assert e["pass_pct"] == 70
    assert e["total"] > 0
    # No answers leak to client
    assert all("answer" not in q for q in e["questions"])


def test_exam_unknown_format_falls_back():
    e = certification_exam_mode(SKILL, "nope", seed=1)
    assert e["exam"] == "Generic Certification Exam"


def test_exam_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        certification_exam_mode("", "generic")
    with pytest.raises((ValueError, TypeError)):
        certification_exam_mode("no_such_skill_xyz", "generic")


def test_grade_exam_pass_fail():
    e = certification_exam_mode(SKILL, "generic", seed=1)
    good = {q["id"]: get_question(q["id"])["answer"] for q in e["questions"]}
    g = grade_exam(e["questions"], good, "generic")
    assert g["passed"] is True and g["scored_pct"] == 100
    g2 = grade_exam(e["questions"], {}, "generic")
    assert g2["passed"] is False


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_drill_never_crashes(s):
    assert _ok(weakness_drill, s, {"weak_topics": [s]}, 5, seed=1)
    assert _ok(weakness_drill, SKILL, s, 5)


def test_drill_targets_weak():
    d = weakness_drill(SKILL, {"weak_topics": ["Hashing"]}, n=5, seed=1)
    assert d["total"] == 5
    assert "Hashing" in d["target_topics"] or d["target_topics"] == ["general"]


def test_drill_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        weakness_drill("", {}, 5)


@pytest.mark.parametrize("entries", [
    [], None, "junk",
    [{"user_id": 1, "score_pct": "bad"}],
    [{"user_id": 1, "name": "<script>alert(1)</script>", "score_pct": 80}],
    [{"user_id": 1, "score_pct": 150}, {"user_id": 2, "score_pct": -20}],
])
def test_leaderboard_never_crashes(entries):
    assert _ok(leaderboard, entries, 1)


def test_leaderboard_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        leaderboard("nope")


def test_leaderboard_ranks():
    lb = leaderboard([
        {"user_id": 1, "name": "A", "score_pct": 70, "quizzes_taken": 3},
        {"user_id": 2, "name": "B", "score_pct": 90, "quizzes_taken": 5},
    ], current_user_id=1)
    assert lb["leaders"][0]["name"] == "B"
    assert lb["leaders"][0]["rank"] == 1
    assert lb["your_rank"] == 2
    assert lb["leaders"][1]["is_you"] is True
