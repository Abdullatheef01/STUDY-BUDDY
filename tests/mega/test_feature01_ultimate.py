"""Feature 1 ultimate: harsh tests for AI pre-screen sim, action plan, probability."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.jd_matcher import (
    simulate_ai_screen, keyword_action_plan, offer_probability,
)


def _ok(fn, *args):
    try:
        fn(*args)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_screen_never_crashes(s):
    assert _ok(simulate_ai_screen, {}, s)
    assert _ok(simulate_ai_screen, None, s)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_screen_score_bounds(s):
    try:
        r = simulate_ai_screen({"matched_skills": ["python"]}, s)
    except (ValueError, TypeError):
        return
    assert 0 <= r["score"] <= 100
    assert r["verdict"]
    assert isinstance(r["signals"], list)


def test_screen_quantified_beats_vague():
    good = ("Led team of 5 engineers and shipped a feature used by 10k users, "
            "increasing revenue by 25% in 2023-2024. " * 8)
    bad = "Responsible for duties included helping with stuff. " * 8
    g = simulate_ai_screen({"matched_skills": ["python"] * 5}, good)
    b = simulate_ai_screen({"matched_skills": []}, bad)
    assert g["score"] > b["score"], f"{g['score']} vs {b['score']}"


def test_screen_keyword_stuffing_penalized():
    stuffed = "python " * 300
    r = simulate_ai_screen({"matched_skills": ["python"] * 60}, stuffed)
    assert any(s["signal"] == "keyword stuffing suspected" for s in r["signals"])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_plan_never_crashes(s):
    assert _ok(keyword_action_plan, {"missing_keywords": [s], "missing_skills": []}, s)
    assert _ok(keyword_action_plan, None, s)
    assert _ok(keyword_action_plan, {}, s)


def test_plan_prioritizes_and_caps():
    report = {"missing_keywords": [f"kw{i}" for i in range(20)],
              "missing_skills": ["kw0", "kw1"]}
    plan = keyword_action_plan(report, "some resume text")
    assert len(plan) <= 5
    assert plan[0]["where"] == "Skills"  # skills first
    for item in plan:
        assert all(k in item for k in ("keyword", "where", "why", "example"))


def test_plan_skips_present_keywords():
    report = {"missing_keywords": ["python"], "missing_skills": []}
    plan = keyword_action_plan(report, "I know python very well")
    assert all(p["keyword"].lower() != "python" for p in plan)


@pytest.mark.parametrize("score", [0, 1, 50, 78.5, 100, -10, 150, None, "bad", float("inf")])
@pytest.mark.parametrize("apps", [None, 0, 1, 50, 200, 10000, -5, "bad"])
def test_probability_bounds(score, apps):
    try:
        r = offer_probability({"score": score}, apps)
    except (ValueError, TypeError, OverflowError):
        return
    assert 1 <= r["probability_pct"] <= 97
    assert r["band"] in ("Strong chance", "Decent chance", "Long shot", "Very unlikely")


def test_probability_more_applicants_lower():
    high_comp = offer_probability({"score": 80}, 5000)["probability_pct"]
    low_comp = offer_probability({"score": 80}, 20)["probability_pct"]
    assert low_comp >= high_comp


def test_probability_higher_score_higher():
    a = offer_probability({"score": 90}, 100)["probability_pct"]
    b = offer_probability({"score": 40}, 100)["probability_pct"]
    assert a > b
