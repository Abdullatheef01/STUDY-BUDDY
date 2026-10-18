"""Feature 14 ultimate: harsh tests for story bank, search, followups, pitch."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.star_builder import (
    predict_followups,
    search_stories,
    story_bank_manager,
    thirty_second_pitch,
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


STORIES = [
    {"id": 1, "title": "Led migration",
     "text": "I led a team of 4 to migrate the API. We disagreed on approach but aligned. Shipped in 6 weeks."},
    {"id": 2, "title": "Failed deploy",
     "text": "I shipped a bug that broke checkout. I learned canary deploys and owned the postmortem."},
]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_bank_never_crashes(s):
    assert _ok(story_bank_manager, [{"id": 1, "title": s, "text": s}])
    assert _ok(story_bank_manager, s)
    assert _ok(story_bank_manager, None)


def test_bank_coverage():
    b = story_bank_manager(STORIES)
    assert len(b["coverage"]) == 8
    assert b["total_stories"] == 2
    assert b["covered_count"] >= 2
    assert b["gaps"]


def test_bank_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        story_bank_manager("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_search_never_crashes(s):
    assert _ok(search_stories, STORIES, s)
    assert _ok(search_stories, None, s)


def test_search_finds():
    r = search_stories(STORIES, "migration")
    assert r["count"] >= 1
    assert r["results"][0]["id"] == 1


def test_search_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        search_stories(STORIES, "   ")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_followups_never_crashes(s):
    assert _ok(predict_followups, s)


def test_followups_themed():
    f = predict_followups("I led the team through a tough migration.")
    assert len(f["followups"]) == 3
    assert f["theme"] == "led"


def test_followups_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        predict_followups("   ")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_pitch_never_crashes(s):
    assert _ok(thirty_second_pitch, s)


def test_pitch_compresses():
    long_story = ("When I joined the team the deploy pipeline was broken. "
                 "I spent two weeks learning it. Then I rebuilt it with caching. "
                 "We shipped the new pipeline. Latency dropped 50% for 200 users. "
                 "The team was happy with the result and we celebrated.")
    p = thirty_second_pitch(long_story)
    assert p["word_count"] <= 70
    assert p["pitch"]


def test_pitch_rejects_short():
    with pytest.raises((ValueError, TypeError)):
        thirty_second_pitch("too short")
