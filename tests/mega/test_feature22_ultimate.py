"""Feature 22 ultimate: harsh tests for trend check, feasibility, proposal export."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.gap_finder import trend_cross_check, feasibility_score, gap_to_proposal


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


GAP = "Nobody has benchmarked small language models for low-resource Indian languages"
TRENDING = [
    {"title": "Benchmarking SLMs for Hindi", "abstract": "We benchmark small language models on Hindi tasks."},
    {"title": "Cat pictures", "abstract": "A study of cats."},
]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_trend_never_crashes(s):
    assert _ok(trend_cross_check, s, TRENDING)
    assert _ok(trend_cross_check, GAP, s)
    assert _ok(trend_cross_check, None, None)


def test_trend_finds_overlap():
    t = trend_cross_check(GAP, TRENDING)
    assert t["overlap_count"] == 1
    assert t["overlap"][0]["title"].startswith("Benchmarking")


def test_trend_clear_field():
    t = trend_cross_check(GAP, [{"title": "Cats", "abstract": "meow"}])
    assert t["overlap_count"] == 0
    assert "Clear field" in t["verdict"]


def test_trend_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        trend_cross_check("short", TRENDING)
    with pytest.raises((ValueError, TypeError)):
        trend_cross_check(GAP, "nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_feas_never_crashes(s):
    assert _ok(feasibility_score, s, ["python"])
    assert _ok(feasibility_score, GAP, s)


def test_feas_bounds():
    for gap in [GAP, "Build a survey of open source tools",
                "Train a massive model on a TPU pod with million dollar budget"]:
        f = feasibility_score(gap)
        assert 0 <= f["score"] <= 100
    easy = feasibility_score("A survey of open-source Python tools on public datasets")
    hard = feasibility_score("Train a massive model on a TPU pod costing million dollars")
    assert easy["score"] > hard["score"]


def test_feas_rejects_short():
    with pytest.raises((ValueError, TypeError)):
        feasibility_score("tiny")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_proposal_never_crashes(s):
    assert _ok(gap_to_proposal, s, s)
    assert _ok(gap_to_proposal, None)


def test_proposal_structure():
    p = gap_to_proposal(GAP)
    assert p["title"]
    assert len(p["sections"]) == 7
    assert all("prompts" in s for s in p["sections"])


def test_proposal_rejects_short():
    with pytest.raises((ValueError, TypeError)):
        gap_to_proposal("tiny")
