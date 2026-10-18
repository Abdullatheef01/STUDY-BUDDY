"""Feature 11 ultimate: harsh tests for voice prep, company intel, redo loop."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.mock_interview import (
    company_intel,
    redo_tracker,
    voice_interview_prep,
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


Q = {"question": "Tell me about yourself", "key_points": ["background", "skills"]}

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_voice_never_crashes(s):
    assert _ok(voice_interview_prep, Q, s, 60)
    assert _ok(voice_interview_prep, s, s, s)
    assert _ok(voice_interview_prep, None, None, None)


def test_voice_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        voice_interview_prep("not a dict", "answer", 60)
    with pytest.raises((ValueError, TypeError)):
        voice_interview_prep(Q, "answer", 0)
    with pytest.raises((ValueError, TypeError)):
        voice_interview_prep(Q, "answer", -5)


def test_voice_wpm_math():
    # 130 words in 60s = 130 wpm
    r = voice_interview_prep(Q, "word " * 130, 60)
    assert r["wpm"] == 130.0
    assert "Good pace" in r["pacing"]


def test_voice_flags_fillers():
    r = voice_interview_prep(Q, "um I like uh worked on like stuff " * 5, 60)
    assert any("Filler" in t for t in r["delivery_tips"])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_intel_never_crashes(s):
    assert _ok(company_intel, s)
    assert _ok(company_intel, None)


def test_intel_structure():
    c = company_intel("Google")
    assert c["total_questions"] > 0
    assert c["categories"]
    assert c["focus_tip"]


def test_intel_unknown_company_fallback():
    c = company_intel("NoSuchCorpXYZ123")
    assert c["total_questions"] > 0  # falls back to overall trends
    assert "No company-specific" in c["note"]


def test_intel_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        company_intel("   ")


@pytest.mark.parametrize("attempts", [
    [], None, "junk",
    [{"question_id": "q1", "score": "bad"}],
    [{"no_id": 1}],
    [{"question_id": "q1", "score": 150}, {"question_id": "q1", "score": -20}],
])
def test_redo_never_crashes(attempts):
    assert _ok(redo_tracker, attempts)


def test_redo_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        redo_tracker("nope")


def test_redo_tracks_improvement():
    r = redo_tracker([{"question_id": "q1", "score": 40},
                      {"question_id": "q1", "score": 70}])
    assert r["questions"][0]["trend"] == "improving"
    assert r["questions"][0]["improvement"] == 30.0
    assert r["total_redos"] == 1
