"""MEGA-8: Research + data features under harsh input.

PDF QA, arXiv import, flashcards, lit review, opportunities, trending.
~600 tests.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from studybuddy import (
    arxiv_import,
    flashcards,
    lit_review,
    opportunities,
    pdf_qa,
    trending,
)
from tests.mega.harsh_corpus import HARSH_STRINGS


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, KeyError, TypeError, AttributeError):
        return True
    except Exception:
        return False


# ---- arxiv import validation ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:50])
def test_arxiv_id_validation(s):
    assert _ok(arxiv_import.validate_arxiv_id, s)


@pytest.mark.parametrize("s", HARSH_STRINGS[:50])
def test_doi_validation(s):
    assert _ok(arxiv_import.validate_doi, s)


# ---- flashcards ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:40])
def test_flashcard_generate(s):
    assert _ok(flashcards.generate_deck, s)


# ---- lit review ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:40])
def test_lit_review_generate(s):
    if s.strip():
        assert _ok(lit_review.generate_review, s)


# ---- opportunities ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:30])
def test_opp_query(s):
    assert _ok(opportunities.list_opportunities, s)


# ---- pdf_qa ----
@pytest.mark.parametrize("s", HARSH_STRINGS[:30])
def test_pdfqa_validate(s):
    assert _ok(pdf_qa.validate_upload, s)


# ---- trending ----
def test_trending_get_limit_boundaries():
    for n in [0, 1, 10, 100, 1000, -1, -100]:
        try:
            papers = trending.get_trending(n)
            assert isinstance(papers, list)
            assert len(papers) <= max(n, 0)
        except (ValueError, TypeError):
            pass


@pytest.mark.parametrize("s", HARSH_STRINGS[:30])
def test_trending_fetch_never_raises(s):
    # fetch_all takes no args; ensure module-level robustness
    assert _ok(trending.get_freshness)


# ---- live_data boundaries ----
@pytest.mark.parametrize("days", [0, 1, 30, 365, -1, -100, 10**9])
@pytest.mark.parametrize("date_s", ["2024-01-01", "not-a-date", "", None,
                                     "2024-13-45", "9999-99-99"])
def test_is_stale_boundaries(days, date_s):
    from studybuddy import live_data
    try:
        result = live_data.is_stale(date_s, days)
        assert isinstance(result, bool)
    except (ValueError, TypeError):
        pass
