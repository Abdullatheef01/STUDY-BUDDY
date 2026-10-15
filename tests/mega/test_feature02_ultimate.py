"""Feature 2 ultimate: harsh tests for STAR converter, verb ranking, metric finder."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.bullet_rewriter import star_convert, verb_power_report, metric_finder


def _ok(fn, *args):
    try:
        fn(*args)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_star_never_crashes(s):
    assert _ok(star_convert, s)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_star_structure(s):
    try:
        r = star_convert(s)
    except (ValueError, TypeError):
        return
    assert set(r) >= {"situation", "task", "action", "result", "gaps",
                      "star_bullet", "completeness"}
    assert r["completeness"].endswith("parts present")
    # No raw HTML in output
    assert "<script" not in r["star_bullet"].lower()


def test_star_full_bullet_all_parts():
    r = star_convert("When the API was slow I needed to cut latency. "
                     "I migrated caching to Redis. P99 dropped 40%.")
    assert r["completeness"] == "4/4 parts present"
    assert r["gaps"] == []


def test_star_thin_bullet_flags_gaps():
    r = star_convert("Did some work on the project with the team members.")
    assert len(r["gaps"]) >= 1
    assert all("prompt" in g for g in r["gaps"])


@pytest.mark.parametrize("bullets", [
    [], [""], [" "], ["a" * 5],
    ["<script>alert(1)</script> built a thing for users here"],
    ["Led team", "Built api", "Shipped feature", "Led team", "Built api"],
    ["x" * 1000] * 50,
    [123, None, ["nested"], {"d": 1}],
])
def test_verb_report_never_crashes(bullets):
    assert _ok(verb_power_report, bullets)


def test_verb_report_diversity():
    r = verb_power_report(["Led team of five engineers",
                           "Architected payment service",
                           "Shipped mobile app to store"])
    assert r["diversity_score"] == 100.0
    assert r["total_bullets"] == 3


def test_verb_report_detects_weak():
    r = verb_power_report(["Responsible for testing the application thoroughly"])
    assert len(r["weak_hits"]) >= 1
    assert r["weak_hits"][0]["suggestion"]


def test_verb_report_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        verb_power_report("not a list")
    with pytest.raises((ValueError, TypeError)):
        verb_power_report(None)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_metric_never_crashes(s):
    assert _ok(metric_finder, s)


def test_metric_detects_existing():
    r = metric_finder("Improved latency by 40% for 10k users")
    assert r["has_metric"] is True


def test_metric_topic_routing():
    r = metric_finder("Led a team of engineers building the platform")
    assert "team" in r["topic"].lower() or r["topic"] == "general"
    assert len(r["questions"]) == 3
