"""Feature 12 ultimate: harsh tests for pattern mastery, mock OA, spaced repetition."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from datetime import datetime, timezone, timedelta

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.dsa_practice import (
    pattern_mastery, mock_oa, spaced_repetition_queue, all_problems,
)


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_mastery_never_crashes(s):
    assert _ok(pattern_mastery, [s, 1, None])
    assert _ok(pattern_mastery, s)


def test_mastery_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        pattern_mastery("nope")


def test_mastery_structure():
    m = pattern_mastery([])
    assert len(m["patterns"]) == 14
    assert all(0 <= p["mastery_pct"] <= 100 for p in m["patterns"])
    assert m["weakest_pattern"]


def test_mastery_counts_solved():
    ids = [p["id"] for p in all_problems()[:10]]
    m = pattern_mastery(ids)
    assert m["overall_mastery_pct"] > 0


@pytest.mark.parametrize("n", [0, 1, 2, 5, -1, "bad", None, 2.5])
def test_oa_never_crashes(n):
    assert _ok(mock_oa, n, 60, seed=1)


def test_oa_structure():
    oa = mock_oa(2, 60, seed=42)
    assert oa["total"] == 2
    assert oa["minutes"] == 60
    assert len(oa["questions"]) == 2
    assert oa["instructions"]


def test_oa_deterministic_seed():
    a = mock_oa(2, 60, seed=7)
    b = mock_oa(2, 60, seed=7)
    assert [q["id"] for q in a["questions"]] == [q["id"] for q in b["questions"]]


def test_oa_clamps():
    assert mock_oa(99)["total"] == 4
    assert mock_oa(2, 999)["minutes"] == 180


@pytest.mark.parametrize("mistakes", [
    [], None, "junk",
    [{"problem_id": "bad", "wrong_at": "not-a-date"}],
    [{"problem_id": 1}],
    [{"no_id": True}],
])
def test_queue_never_crashes(mistakes):
    assert _ok(spaced_repetition_queue, mistakes)


def test_queue_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        spaced_repetition_queue("nope")


def test_queue_intervals():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    q = spaced_repetition_queue([
        {"problem_id": 1, "wrong_at": old, "streak": 1},
        {"problem_id": 2, "wrong_at": old, "streak": 2},
        {"problem_id": 3, "wrong_at": old, "streak": 5},
    ])
    by_id = {e["problem_id"]: e["interval_days"] for e in q["due"]}
    assert by_id[1] == 3 and by_id[2] == 7 and by_id[3] == 14
    assert q["due_count"] == 3


def test_queue_future_not_due():
    recent = datetime.now(timezone.utc).isoformat()
    q = spaced_repetition_queue([{"problem_id": 1, "wrong_at": recent, "streak": 1}])
    assert q["due_count"] == 0
    assert len(q["upcoming"]) == 1
