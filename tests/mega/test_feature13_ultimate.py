"""Feature 13 ultimate: harsh tests for video checklist, HR sim, clarity score."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.communication_coach import (
    clarity_score,
    hr_round_simulator,
    video_presence_checklist,
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
def test_video_never_crashes(s):
    assert _ok(video_presence_checklist, {"eye_contact": s})
    assert _ok(video_presence_checklist, s)
    assert _ok(video_presence_checklist, None)


def test_video_scoring():
    all_done = {c: True for c in ["eye_contact", "framing", "background", "posture",
                                   "gestures", "audio", "attire"]}
    r = video_presence_checklist(all_done)
    assert r["score"] == 100
    assert r["verdict"] == "Camera-ready."
    r2 = video_presence_checklist({})
    assert r2["score"] == 0
    assert len(r2["priority_fixes"]) == 3


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_hr_never_crashes(s):
    assert _ok(hr_round_simulator, s)


def test_hr_full_set():
    h = hr_round_simulator()
    assert h["count"] == 5
    assert all("framework" in q and "model" in q for q in h["questions"])


def test_hr_single():
    h = hr_round_simulator("why_us")
    assert h["question"]["id"] == "why_us"


def test_hr_rejects_unknown():
    with pytest.raises((ValueError, TypeError)):
        hr_round_simulator("no_such_question")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_clarity_never_crashes(s):
    assert _ok(clarity_score, s)
    assert _ok(clarity_score, None)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_clarity_bounds(s):
    try:
        r = clarity_score(s)
    except (ValueError, TypeError):
        return
    assert 0 <= r["score"] <= 100
    assert r["grade"]


def test_clarity_clear_beats_muddy():
    clear = ("I built the payment API. It processes ten thousand transactions daily. "
             "Latency dropped forty percent after I added caching.")
    muddy = ("So basically um like I was working on this thing and stuff, "
             "and actually it was like really slow and basically we had to "
             "leverage synergy to circle back and do a deep dive into stuff things.")
    c = clarity_score(clear)
    m = clarity_score(muddy)
    assert c["score"] > m["score"]


def test_clarity_empty():
    r = clarity_score("   ")
    assert r["score"] == 0
