"""Unit tests for gap_finder.py (Wave 4, #23). Logic module only — no Flask.

Precision is the headline requirement: every evidence excerpt must be a
verbatim substring of the chunk it cites. test_excerpts_verbatim_exhaustive
checks this for every gap produced by every finder over a mixed collection.
"""
from types import SimpleNamespace

import pytest

from gap_finder import (
    find_conflicts,
    find_single_paper_topics,
    find_underexplored,
    generate_gap_report,
    suggest_next_papers,
    term_stats,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def make_entry(doc_id, title, page, idx, text):
    return {"doc_id": doc_id, "doc": title, "page": page,
            "index": idx, "text": text}


def make_doc(doc_id, title, texts, user_id=1):
    chunks = [{"page": 1, "index": i, "heading": "", "text": t}
              for i, t in enumerate(texts)]
    return SimpleNamespace(id=doc_id, user_id=user_id, title=title,
                           data={"chunks": chunks})


def golden_docs():
    """3 synthetic papers: paper 1 pro-dropout, paper 2 anti-dropout
    (with a contrast marker), paper 3 neutral with no shared terms."""
    return [
        make_doc(1, "Paper One", [
            "Dropout improves generalization in deep neural networks. "
            "Our experiments show dropout regularization improves "
            "generalization across benchmarks.",
        ]),
        make_doc(2, "Paper Two", [
            "However, dropout harms convergence. In our training runs, "
            "dropout harms convergence and slows optimization significantly.",
        ]),
        make_doc(3, "Paper Three", [
            "Batch normalization stabilizes training. We study batch "
            "normalization effects on model stability.",
        ]),
    ]


def ranking_docs():
    """One collection exercising all three gap types distinctly."""
    return [
        make_doc(1, "Alpha", [
            "Dropout improves generalization in deep neural networks. "
            "Our experiments show dropout regularization improves "
            "generalization across benchmarks.",
            "We apply pruning to compress the network. Pruning removes "
            "redundant weights and pruning speeds up inference.",
            "Further pruning experiments confirm benefits. Repeated pruning "
            "trials show pruning maintains accuracy.",
            "A third pruning study validates the method. Pruning remains "
            "effective and pruning is widely adopted.",
        ]),
        make_doc(2, "Beta", [
            "However, dropout harms convergence. In our training runs, "
            "dropout harms convergence and slows optimization significantly.",
        ]),
        make_doc(3, "Gamma", [
            "Quantization reduces model size. Our quantization approach uses "
            "quantization aware calibration for deployment.",
        ]),
    ]


def entries_of(docs):
    out = []
    for d in docs:
        for c in d.data["chunks"]:
            out.append(make_entry(d.id, d.title, c["page"], c["index"], c["text"]))
    return out


def chunk_lookup(docs):
    """(title, chunk index) -> chunk text, for verbatim-excerpt checks."""
    look = {}
    for d in docs:
        for c in d.data["chunks"]:
            look[(d.title, c["index"])] = c["text"]
    return look


# ---------------------------------------------------------------------------
# 1. term_stats
# ---------------------------------------------------------------------------

def test_term_stats_counts_and_docs():
    entries = [
        make_entry(1, "A", 1, 0, "Dropout improves generalization in networks."),
        make_entry(1, "A", 1, 1, "We study dropout effects on generalization."),
        make_entry(2, "B", 1, 0, "Dropout harms convergence badly."),
    ]
    stats = term_stats(entries)
    assert stats["dropout"]["count"] == 3
    assert stats["dropout"]["docs"] == {1, 2}
    assert stats["generalization"]["count"] == 2
    assert stats["generalization"]["docs"] == {1}
    assert stats["convergence"]["docs"] == {2}


def test_term_stats_stoplist_and_numbers():
    entries = [make_entry(1, "A", 1, 0,
                          "The study of the model uses data 12345 and the "
                          "results show the method works.")]
    stats = term_stats(entries)
    for banned in ("the", "study", "model", "data", "results", "method",
                   "12345", "uses", "show"):
        assert banned not in stats, banned
    assert "works" in stats  # length>=4, not a stopword


def test_term_stats_bigrams():
    entries = [make_entry(1, "A", 1, i,
                          "We use a neural network for the task. The neural "
                          "network trains well on this neural network data.")
               for i in range(3)]
    stats = term_stats(entries)
    assert "neural network" in stats
    assert stats["neural network"]["count"] >= 3


def test_term_stats_bad_input():
    assert term_stats(None) == {}
    assert term_stats([]) == {}
    assert term_stats("garbage") == {}
    assert term_stats([None, {"text": 123}, {"no_text": True}]) == {}


# ---------------------------------------------------------------------------
# 2. find_underexplored
# ---------------------------------------------------------------------------

def test_underexplored_finds_narrow_topic():
    docs = ranking_docs()
    gaps = find_underexplored(entries_of(docs))
    pruning = [g for g in gaps if g["type"] == "underexplored"
               and "pruning" in g["title"]]
    assert len(pruning) == 1
    gap = pruning[0]
    assert 2 <= len(gap["evidence"]) <= 3
    assert all(e["doc"] == "Alpha" for e in gap["evidence"])
    assert gap["suggested_questions"]  # honest, template-based questions
    assert any("pruning" in q for q in gap["suggested_questions"])


def test_underexplored_skips_widespread_terms():
    entries = [
        make_entry(1, "A", 1, i, "Dropout appears here many times dropout.")
        for i in range(3)
    ] + [
        make_entry(2, "B", 1, i, "Dropout appears here many times dropout.")
        for i in range(3)
    ] + [
        # Control: a genuinely narrow term must still be found.
        make_entry(1, "A", 1, 10 + i,
                   "We study pruning methods. Pruning compresses models.")
        for i in range(3)
    ]
    gaps = find_underexplored(entries)
    assert not any("dropout" in g["title"] for g in gaps)
    assert any("pruning" in g["title"] for g in gaps)


def test_underexplored_concentrated_rule():
    entries = [
        make_entry(1, "A", 1, 0, "Federated learning is federated and federated."),
        make_entry(1, "A", 1, 1, "More federated systems are federated and federated."),
        make_entry(2, "B", 1, 0, "Unrelated text about databases and indexes."),
    ]
    gaps = find_underexplored(entries)
    assert any(g["type"] == "underexplored" and "federated" in g["title"]
               for g in gaps)


# ---------------------------------------------------------------------------
# 3. find_conflicts — golden test + negatives
# ---------------------------------------------------------------------------

def test_conflict_golden_dropout():
    docs = golden_docs()
    gaps = find_conflicts(entries_of(docs))
    conflicts = [g for g in gaps if g["type"] == "conflict"]
    assert conflicts, "expected a conflict gap for the dropout disagreement"
    cited = {e["doc"] for g in conflicts for e in g["evidence"]}
    pair = next(
        g for g in conflicts
        if {e["doc"] for e in g["evidence"]} == {"Paper One", "Paper Two"}
    )
    assert len(pair["evidence"]) == 2  # BOTH sides cited
    look = chunk_lookup(docs)
    for ev in pair["evidence"]:
        assert ev["excerpt"] in look[(ev["doc"], ev["chunk"])]
    assert any("dropout" in ev["excerpt"].lower() for ev in pair["evidence"])


def test_conflict_needs_two_docs():
    entries = [make_entry(1, "A", 1, 0,
                          "However, dropout harms convergence badly here.")]
    assert find_conflicts(entries) == []
    assert find_conflicts([]) == []
    assert find_conflicts(None) == []


def test_conflict_no_markers_no_gaps():
    entries = [
        make_entry(1, "A", 1, 0, "Dropout improves generalization a lot."),
        make_entry(2, "B", 1, 0, "Dropout harms convergence a lot."),
    ]
    assert find_conflicts(entries) == []


# ---------------------------------------------------------------------------
# 4. find_single_paper_topics
# ---------------------------------------------------------------------------

def test_single_paper_topics_found():
    docs = ranking_docs()
    gaps = find_single_paper_topics(entries_of(docs))
    quant = [g for g in gaps if "quantization" in g["title"]]
    assert len(quant) == 1
    gap = quant[0]
    assert gap["type"] == "single-paper"
    assert all(e["doc"] == "Gamma" for e in gap["evidence"])
    assert gap["evidence"]
    # Comparative questions, not invented facts.
    assert any("compar" in q.lower() for q in gap["suggested_questions"])
    # Underexplored 'pruning' must NOT be duplicated here.
    assert not any("pruning" in g["title"] for g in gaps)


def test_single_paper_topics_skips_shared():
    docs = golden_docs()
    gaps = find_single_paper_topics(entries_of(docs))
    titles = " ".join(g["title"] for g in gaps)
    assert "dropout" not in titles  # covered by two papers


# ---------------------------------------------------------------------------
# 5. Exhaustive verbatim-excerpt precision check
# ---------------------------------------------------------------------------

def test_excerpts_verbatim_exhaustive():
    docs = ranking_docs()
    look = chunk_lookup(docs)
    entries = entries_of(docs)
    all_gaps = (find_conflicts(entries) + find_underexplored(entries)
                + find_single_paper_topics(entries))
    assert all_gaps, "fixture should produce gaps"
    for gap in all_gaps:
        assert gap["evidence"], "every gap needs >=1 evidence item"
        for ev in gap["evidence"]:
            text = look.get((ev["doc"], ev["chunk"]))
            assert text is not None, "evidence must reference a real chunk"
            assert ev["excerpt"] in text, (
                "excerpt not verbatim in cited chunk: %r" % ev["excerpt"][:60]
            )


# ---------------------------------------------------------------------------
# 6. suggest_next_papers
# ---------------------------------------------------------------------------

def make_import(title, nodes, edges, user_id=1):
    return SimpleNamespace(title=title, user_id=user_id,
                           data={"graph": {"nodes": nodes, "edges": edges}})


def sample_graph_import():
    nodes = [
        {"id": "W0", "title": "Imported Paper", "year": 2020, "is_center": True},
        {"id": "W1", "title": "Cited Neighbor", "year": 2019},
        {"id": "W2", "title": "Citing Neighbor", "year": 2021},
    ]
    edges = [{"from": "W0", "to": "W1"}, {"from": "W2", "to": "W0"}]
    return make_import("Imported Paper", nodes, edges)


def test_suggest_next_papers_reasons_and_edges():
    out = suggest_next_papers(1, [sample_graph_import()], [])
    by_title = {s["title"]: s for s in out}
    assert by_title["Cited Neighbor"]["reason"] == "Cited by 'Imported Paper'"
    assert by_title["Citing Neighbor"]["reason"] == "References 'Imported Paper'"
    assert by_title["Cited Neighbor"]["year"] == 2019
    assert all(set(s) == {"title", "year", "reason"} for s in out)


def test_suggest_next_papers_excludes_library_dedupes_and_caps():
    imp = sample_graph_import()
    dup = make_import("Second Paper",
                      [{"id": "W9", "title": "Second Paper", "year": 2022,
                        "is_center": True},
                       {"id": "W1", "title": "Cited Neighbor", "year": 2019}],
                      [{"from": "W9", "to": "W1"}])
    as_dict = {"title": "Dict Import", "user_id": 1,
               "data": {"graph": {"nodes": [
                   {"id": "D0", "title": "Dict Import", "is_center": True},
                   {"id": "D1", "title": "Dict Neighbor", "year": 2018}],
                   "edges": [{"from": "D0", "to": "D1"}]}}}
    out = suggest_next_papers(1, [imp, dup, as_dict],
                              ["Cited Neighbor"], max_n=2)
    titles = [s["title"] for s in out]
    assert "Cited Neighbor" not in titles  # already in library
    assert len(titles) == len(set(titles))  # deduped
    assert len(out) == 2  # max_n honored
    assert "Dict Neighbor" in titles  # dict-style imports work too


def test_suggest_next_papers_no_graphs_empty_and_no_network(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise AssertionError("network must never be touched")

    monkeypatch.setattr(requests, "get", _boom)
    imports = [
        SimpleNamespace(title="No Data", user_id=1, data=None),
        SimpleNamespace(title="Empty", user_id=1, data={}),
        SimpleNamespace(title="Err", user_id=1,
                        data={"graph": {"error": "boom"}}),
        SimpleNamespace(title="No Nodes", user_id=1,
                        data={"graph": {"nodes": [], "edges": []}}),
        SimpleNamespace(title="Wrong User", user_id=2,
                        data={"graph": {"nodes": [
                            {"id": "W0", "title": "X", "is_center": True},
                            {"id": "W1", "title": "Y"}],
                            "edges": []}}),
    ]
    assert suggest_next_papers(1, imports, []) == []
    assert suggest_next_papers(1, None, []) == []


# ---------------------------------------------------------------------------
# 7. generate_gap_report
# ---------------------------------------------------------------------------

def test_generate_gap_report_ranking():
    docs = ranking_docs()
    report = generate_gap_report(docs)
    assert "gaps" in report and "next_papers" in report
    assert "note" not in report
    rank = {"conflict": 0, "underexplored": 1, "single-paper": 2}
    types = [g["type"] for g in report["gaps"]]
    assert "conflict" in types and "underexplored" in types \
        and "single-paper" in types
    assert [rank[t] for t in types] == sorted(rank[t] for t in types), \
        "conflicts first, then underexplored, then single-paper"


def test_generate_gap_report_thin_states():
    for docs in ([], None, "garbage",
                 [make_doc(1, "Solo", ["Only one paper here."])],
                 [make_doc(1, "A", []), make_doc(2, "B", [])],
                 [make_doc(1, "A", ["   "]), make_doc(2, "B", [""])],
                 [SimpleNamespace(id=9, title="Weird", data=None)]):
        report = generate_gap_report(docs)
        assert report["gaps"] == []
        assert report["next_papers"] == []
        assert isinstance(report.get("note"), str) and report["note"]


def test_generate_gap_report_contract():
    docs = ranking_docs()
    report = generate_gap_report(docs, [sample_graph_import()])
    assert set(report) >= {"gaps", "next_papers"}
    for gap in report["gaps"]:
        assert set(gap) >= {"title", "type", "evidence", "suggested_questions"}
        assert gap["type"] in ("underexplored", "conflict", "single-paper")
        assert isinstance(gap["title"], str) and gap["title"]
        assert len(gap["evidence"]) >= 1
        for ev in gap["evidence"]:
            assert set(ev) >= {"doc", "page", "chunk", "excerpt"}
            assert isinstance(ev["excerpt"], str) and ev["excerpt"]
        assert all(isinstance(q, str) and q for q in gap["suggested_questions"])
    for s in report["next_papers"]:
        assert set(s) == {"title", "year", "reason"}


# ---------------------------------------------------------------------------
# 8. Never raises on garbage
# ---------------------------------------------------------------------------

def test_never_raises_on_garbage():
    garbage = [None, 123, "x", [None], [{"text": 123}],
               [{"doc_id": {"un": "hashable"}, "text": "some valid text here"}]]
    for g in garbage:
        term_stats(g)
        find_underexplored(g)
        find_conflicts(g)
        find_single_paper_topics(g)
        generate_gap_report(g)
    suggest_next_papers(None, garbage, garbage, max_n="bad")
    suggest_next_papers(1, [{"title": 1, "data": {"graph": None}}], None)
