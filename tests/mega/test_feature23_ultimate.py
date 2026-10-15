"""Feature 23 ultimate: harsh tests for Anki export, exam sprint, weak loop."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.flashcards import anki_export, exam_sprint, weak_card_loop


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


CARDS = [
    {"id": "c1", "question": "What is RAG?", "answer": "Retrieval-Augmented Generation"},
    {"id": "c2", "question": "What is DP?", "answer": "Dynamic Programming"},
]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_anki_never_crashes(s):
    assert _ok(anki_export, [{"question": s, "answer": s}], s)
    assert _ok(anki_export, s)
    assert _ok(anki_export, None)


def test_anki_tsv_format():
    a = anki_export(CARDS, "Test Deck")
    assert a["count"] == 2
    lines = a["tsv"].split("\n")
    assert len(lines) == 2
    assert all("\t" in ln for ln in lines)
    # No raw tabs/newlines inside fields
    assert all(ln.count("\t") == 1 for ln in lines)


def test_anki_skips_invalid():
    a = anki_export([{"question": "", "answer": "x"}, {"question": "q", "answer": ""}] + CARDS)
    assert a["count"] == 2


def test_anki_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        anki_export("nope")
    with pytest.raises((ValueError, TypeError)):
        anki_export([{"question": "", "answer": ""}])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_sprint_never_crashes(s):
    assert _ok(exam_sprint, CARDS, s, seed=1)
    assert _ok(exam_sprint, s)
    assert _ok(exam_sprint, None)


def test_sprint_structure():
    s = exam_sprint(CARDS, seconds_per_card=15, seed=1)
    assert s["total_cards"] == 2
    assert s["total_seconds"] == 30
    assert all(r["seconds"] == 15 for r in s["rounds"])


def test_sprint_deterministic():
    a = exam_sprint(CARDS, seed=5)
    b = exam_sprint(CARDS, seed=5)
    assert [r["card_id"] for r in a["rounds"]] == [r["card_id"] for r in b["rounds"]]


def test_sprint_clamps():
    s = exam_sprint(CARDS, seconds_per_card=9999)
    assert s["rounds"][0]["seconds"] == 120


def test_sprint_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        exam_sprint([])
    with pytest.raises((ValueError, TypeError)):
        exam_sprint("nope")


@pytest.mark.parametrize("stats", [{}, None, "nope", {"c1": "bad"}, {"c1": {"wrong": "x"}}])
def test_weak_never_crashes(stats):
    assert _ok(weak_card_loop, stats, CARDS)


def test_weak_orders_correctly():
    w = weak_card_loop({"c1": {"wrong": 4, "right": 0}, "c2": {"wrong": 0, "right": 4}}, CARDS)
    assert w["queue"][0]["id"] == "c1"  # weakest first
    assert w["weak_count"] == 1


def test_weak_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        weak_card_loop("nope", CARDS)
    with pytest.raises((ValueError, TypeError)):
        weak_card_loop({}, "nope")
