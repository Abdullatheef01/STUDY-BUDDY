"""Feature 19 ultimate: harsh tests for bulk import, related papers, reading queue."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.arxiv_import import bulk_import, reading_queue, related_papers
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
def test_bulk_never_crashes(s):
    assert _ok(bulk_import, s, max_ids=3)


def test_bulk_rejects_non_string():
    with pytest.raises((ValueError, TypeError)):
        bulk_import(None)
    with pytest.raises((ValueError, TypeError)):
        bulk_import(["1706.03762"])


def test_bulk_invalid_ids():
    r = bulk_import("not-an-id, also-bad, ###", max_ids=5)
    assert r["total"] == 0
    assert len(r["failed"]) == 3
    assert r["attempted"] == 3


def test_bulk_dedupes_and_caps():
    r = bulk_import("bad1, bad1, BAD1, bad2", max_ids=2)
    assert r["attempted"] == 2  # deduped + capped


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_related_never_crashes(s):
    # Network may fail; function must return a dict, not raise (except bad input).
    try:
        r = related_papers(s, max_results=3)
        assert isinstance(r, dict)
    except (ValueError, TypeError):
        pass


def test_related_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        related_papers("   ")
    with pytest.raises((ValueError, TypeError)):
        related_papers(None)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_queue_never_crashes(s):
    papers = [{"id": "a", "title": s, "year": 2020, "abstract": s}]
    assert _ok(reading_queue, papers, [s])
    assert _ok(reading_queue, s)
    assert _ok(reading_queue, None)


def test_queue_prioritizes():
    papers = [
        {"id": "old", "title": "Old survey", "year": 2010, "abstract": "x"},
        {"id": "new", "title": "Transformers paper", "year": 2024,
         "abstract": "transformers attention " * 20},
    ]
    q = reading_queue(papers, interests=["transformers"])
    assert q["queue"][0]["id"] == "new"
    assert q["total_minutes"] > 0
    assert q["total_hours"] > 0


def test_queue_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        reading_queue([])
    with pytest.raises((ValueError, TypeError)):
        reading_queue("nope")


def test_queue_clamps_time():
    q = reading_queue([{"id": "a", "title": "T"}], minutes_per_paper=9999)
    assert q["queue"][0]["est_minutes"] == 180
