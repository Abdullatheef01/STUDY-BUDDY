"""Feature 28 ultimate: harsh tests for pairing, rubrics, recurring slots."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.peer_mocks import (
    match_partners,
    mock_rubric,
    recurring_slot,
    score_rubric,
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
def test_pair_never_crashes(s):
    users = [{"user_id": 1, "name": s, "strengths": [s], "weaknesses": [s]},
             {"user_id": 2, "name": "B", "strengths": ["x"], "weaknesses": ["y"]}]
    assert _ok(match_partners, users)
    assert _ok(match_partners, s)
    assert _ok(match_partners, None)


def test_pair_complementary():
    users = [
        {"user_id": 1, "name": "A", "strengths": ["dsa"], "weaknesses": ["behavioral"]},
        {"user_id": 2, "name": "B", "strengths": ["behavioral"], "weaknesses": ["dsa"]},
    ]
    m = match_partners(users)
    assert len(m["pairs"]) == 1
    assert m["pairs"][0]["complementarity"] == 2
    assert m["unpaired"] == []


def test_pair_odd_one_out():
    users = [{"user_id": i, "name": f"U{i}", "strengths": ["x"], "weaknesses": ["y"]}
             for i in range(3)]
    m = match_partners(users)
    assert len(m["pairs"]) == 1 and len(m["unpaired"]) == 1


def test_pair_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        match_partners("nope")


def test_rubric_structure():
    r = mock_rubric()
    assert len(r["dimensions"]) == 5
    assert r["scale"]


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_score_never_crashes(s):
    assert _ok(score_rubric, {"clarity": s})
    assert _ok(score_rubric, s)
    assert _ok(score_rubric, None)


def test_score_single():
    s = score_rubric({"clarity": 5, "depth": 4, "communication": 5,
                      "problem_solving": 4, "behavioral": 5})
    assert s["average"] == 4.6
    assert "Hire-ready" in s["verdict"]


def test_score_two_sided():
    s = score_rubric({"interviewer": {"clarity": 4, "depth": 4},
                      "candidate": {"clarity": 2, "depth": 2}})
    assert s["perception_gap"] == 2.0
    assert "gap" in s["verdict"].lower()


def test_score_rejects_non_dict():
    with pytest.raises((ValueError, TypeError)):
        score_rubric("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_slot_never_crashes(s):
    assert _ok(recurring_slot, s, s)
    assert _ok(recurring_slot, "saturday", s)


def test_slot_valid():
    t = recurring_slot("saturday", "10:00", 60)
    assert t["day"] == "Saturday"
    assert t["next_occurrence"]


def test_slot_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        recurring_slot("funday", "10:00")
    with pytest.raises((ValueError, TypeError)):
        recurring_slot("monday", "25:00")
    with pytest.raises((ValueError, TypeError)):
        recurring_slot("monday", "nope")
