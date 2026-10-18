"""Feature 30 ultimate: harsh tests for async QA, prep packets, alumni outcomes."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.mentor_extras import (
    alumni_outcomes,
    async_qa_digest,
    prep_packet,
    validate_async_question,
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
def test_validate_never_crashes(s):
    d, e = validate_async_question({"question": s, "topic": s})
    assert (d is None) != (e is None)  # exactly one is None
    d2, e2 = validate_async_question(s)
    assert d2 is None and e2


def test_validate_rules():
    d, e = validate_async_question({"question": "How do I prepare for interviews at product companies?"})
    assert e is None and d["topic"] == "General"
    d2, e2 = validate_async_question({"question": "short"})
    assert d2 is None and e2


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_digest_never_crashes(s):
    assert _ok(async_qa_digest, [{"question": s, "topic": s}], s)
    assert _ok(async_qa_digest, s)
    assert _ok(async_qa_digest, None)


def test_digest_structure():
    d = async_qa_digest([
        {"question": "How do I negotiate my first salary offer?", "topic": "Career", "asker": "A"},
        {"question": "x"},  # too short, skipped
    ], "Priya")
    assert d["count"] == 1
    assert "Priya" in d["markdown"]


def test_digest_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        async_qa_digest([])
    with pytest.raises((ValueError, TypeError)):
        async_qa_digest("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_packet_never_crashes(s):
    assert _ok(prep_packet, {"name": s}, {"name": s}, s)
    assert _ok(prep_packet, s, {}, s)


def test_packet_structure():
    p = prep_packet({"name": "A", "goals": "Get hired"}, {"name": "B", "headline": "SDE"}, "DSA")
    assert len(p["agenda"]) == 4
    assert len(p["for_mentee"]["points"]) == 5
    assert len(p["for_mentor"]["points"]) == 4


def test_packet_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        prep_packet("nope", {}, "x")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_outcomes_never_crashes(s):
    assert _ok(alumni_outcomes, 1, [{"mentor_id": 1, "company": s}])
    assert _ok(alumni_outcomes, s, s)


def test_outcomes_counts():
    a = alumni_outcomes(1, [
        {"mentor_id": 1, "company": "Google", "role": "SDE"},
        {"mentor_id": 1, "company": "Google", "role": "SDE-2"},
        {"mentor_id": 2, "company": "X", "role": "Y"},
    ])
    assert a["count"] == 2
    assert a["top_companies"][0] == {"company": "Google", "count": 2}


def test_outcomes_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        alumni_outcomes(1, "nope")
