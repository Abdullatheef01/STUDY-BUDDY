"""Feature 4 ultimate: harsh tests for recipient finder, follow-ups, outreach score."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.cover_generator import (
    followup_sequence,
    outreach_score,
    suggest_recipients,
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
def test_recipients_never_crashes(s):
    assert _ok(suggest_recipients, s, s)
    assert _ok(suggest_recipients, s)
    assert _ok(suggest_recipients, None, None)


def test_recipients_role_routing():
    r = suggest_recipients("Backend Engineer", "Acme")
    assert "Engineering Manager" in r["recipients"]
    r2 = suggest_recipients("UX Designer")
    assert "Design Manager" in r2["recipients"]
    r3 = suggest_recipients("Sales Executive")
    assert "VP Sales" in r3["recipients"]


def test_recipients_no_html():
    r = suggest_recipients("<script>alert(1)</script>Engineer", "<b>Acme</b>")
    assert "<script" not in str(r)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_followup_never_crashes(s):
    assert _ok(followup_sequence, s, s, s)


def test_followup_structure():
    f = followup_sequence("Priya", "Backend Engineer", "Acme")
    assert len(f["followups"]) == 2
    assert f["followups"][0]["day"] == 3
    assert f["followups"][1]["day"] == 7
    assert "Priya" in f["followups"][0]["body"]
    assert f["guidance"]


def test_followup_bad_tone_falls_back():
    f = followup_sequence("X", "Y", tone="weird")
    assert len(f["followups"]) == 2


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_score_never_crashes(s):
    assert _ok(outreach_score, s, s, s)
    assert _ok(outreach_score, s)
    assert _ok(outreach_score, None)


@pytest.mark.parametrize("msg", ["", "   ", None])
def test_score_empty_bounds(msg):
    try:
        r = outreach_score(msg)
    except (ValueError, TypeError):
        return
    assert 0 <= r["score"] <= 100


def test_score_good_beats_bad():
    good = ("Hi Priya, I saw the Backend Engineer role at Acme. "
            "I built APIs serving 50k users and cut latency 40%. "
            "Would you be open to a 15-minute chat next week?")
    bad = ("Dear Sir/Madam, I am a passionate synergy ninja rockstar. "
           "Please consider my application for your esteemed organization. " * 6)
    g = outreach_score(good, "Priya", "Acme")
    b = outreach_score(bad)
    assert g["score"] > b["score"]
    assert g["grade"].startswith("A")
    assert b["score"] < 60


def test_score_long_penalty():
    long_msg = "word " * 300
    r = outreach_score(long_msg)
    assert any(s["label"].startswith("Penalty") and s["points"] < 0
               for s in r["signals"] if s["hit"])
