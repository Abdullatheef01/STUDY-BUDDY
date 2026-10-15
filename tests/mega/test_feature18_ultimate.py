"""Feature 18 ultimate: harsh tests for multi-doc QA, citation verify, notes export."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.pdf_qa import (
    answer_across_docs, verify_citations, qa_to_notes, chunk_pages,
)


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


def _docs():
    pages_a = ["Transformers use self-attention to process sequences in parallel. "
               "The attention mechanism was introduced in 2017 by Vaswani et al. " * 4]
    pages_b = ["BERT builds on the transformer architecture with bidirectional training. "
               "It achieved state of the art results on GLUE benchmarks in 2018. " * 4]
    return [
        {"title": "Paper A", "chunks": chunk_pages(pages_a, "Paper A")},
        {"title": "Paper B", "chunks": chunk_pages(pages_b, "Paper B")},
    ]

DOCS = _docs()

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_multi_never_crashes(s):
    assert _ok(answer_across_docs, s, DOCS)
    assert _ok(answer_across_docs, "query", s)
    assert _ok(answer_across_docs, None, None)


def test_multi_structure():
    r = answer_across_docs("What are transformers?", DOCS)
    assert r["docs_consulted"] >= 1
    assert r["per_doc"]
    assert r["citations"]


def test_multi_no_result():
    r = answer_across_docs("quantum banana photosynthesis", DOCS)
    assert r["answer"] == "I couldn't find this in your documents."
    assert r["citations"] == []


def test_multi_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        answer_across_docs("", DOCS)
    with pytest.raises((ValueError, TypeError)):
        answer_across_docs("q", [])
    with pytest.raises((ValueError, TypeError)):
        answer_across_docs("q", "nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_verify_never_crashes(s):
    assert _ok(verify_citations, {"answer": s})
    assert _ok(verify_citations, s)
    assert _ok(verify_citations, None)


def test_verify_cited():
    v = verify_citations({"answer": 'The paper says "attention is all you need" [Paper A, p.1].'})
    assert v["ok"] is True
    assert v["claims"] == 1


def test_verify_uncited():
    v = verify_citations({"answer": 'The paper says "attention is all you need" with no marker.'})
    assert v["ok"] is False
    assert v["uncited"] == 1


def test_verify_rejects_non_dict():
    with pytest.raises((ValueError, TypeError)):
        verify_citations("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_notes_never_crashes(s):
    assert _ok(qa_to_notes, [{"question": s, "answer": s}], s)
    assert _ok(qa_to_notes, s)
    assert _ok(qa_to_notes, None)


def test_notes_structure():
    n = qa_to_notes([
        {"question": "What is X?", "answer": "X is Y. It does Z. It was made in 2020.",
         "citations": [{"doc": "Paper A", "page": 1}]}])
    assert n["sections"] == 1
    assert n["markdown"].startswith("#")
    assert "Sources:" in n["markdown"]


def test_notes_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        qa_to_notes([])
    with pytest.raises((ValueError, TypeError)):
        qa_to_notes([{"question": "", "answer": ""}])
