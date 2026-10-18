"""Feature 20 ultimate: harsh tests for in-text cite, style match, duplicates."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.citation_fmt import (
    find_duplicates,
    in_text_citation,
    match_journal_style,
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


META = {"authors": ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki"],
        "year": "2017", "title": "Attention Is All You Need"}

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_intext_never_crashes(s):
    assert _ok(in_text_citation, {"authors": [s], "year": s, "title": s}, s)
    assert _ok(in_text_citation, s)
    assert _ok(in_text_citation, None)


def test_intext_structure():
    c = in_text_citation(META, "apa")
    assert c["bibtex_key"] == "vaswani2017attention"
    assert c["default_for_style"] == "(Vaswani et al., 2017)"
    assert c["snippets"]["latex"] == "\\cite{vaswani2017attention}"
    assert "narrative" in c["snippets"]


def test_intext_single_author():
    c = in_text_citation({"authors": ["Turing, Alan"], "year": "1950", "title": "X"})
    assert c["snippets"]["apa"] == "(Turing, 1950)"


def test_intext_rejects_non_dict():
    with pytest.raises((ValueError, TypeError)):
        in_text_citation("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_match_never_crashes(s):
    assert _ok(match_journal_style, s)


def test_match_apa():
    m = match_journal_style(
        "Vaswani, A., & Shazeer, N. (2017). Attention is all you need. "
        "Advances in neural information processing systems. https://doi.org/10.1/x")
    assert m["best"] == "apa"


def test_match_ieee():
    m = match_journal_style(
        "[1] A. Vaswani et al., \"Attention is all you need,\" "
        "in Proc. NeurIPS, 2017, pp. 5998-6008.")
    assert m["best"] == "ieee"


def test_match_rejects_short():
    with pytest.raises((ValueError, TypeError)):
        match_journal_style("too short")


@pytest.mark.parametrize("refs", [
    [], None, "nope",
    ["a", "b", "c"],
    [{"title": "X"}, {"title": "X"}],
    ["x" * 5000, "x" * 5000],
])
def test_dupes_never_crashes(refs):
    assert _ok(find_duplicates, refs)


def test_dupes_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        find_duplicates("nope")


def test_dupes_finds_near_dupes():
    d = find_duplicates([
        "Vaswani et al. Attention Is All You Need. NeurIPS 2017.",
        "Vaswani et al. Attention Is All You Need. NeurIPS, 2017.",
        "A completely different paper about databases. 2020.",
    ])
    assert d["count"] == 1
    assert d["duplicates"][0]["similarity"] >= 0.85


def test_dupes_doi_match():
    d = find_duplicates([
        {"title": "Paper A", "doi": "10.1234/abc"},
        {"title": "Totally different title", "doi": "10.1234/abc"},
    ])
    assert d["count"] == 1
