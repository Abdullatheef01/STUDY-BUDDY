"""Tests for lit_review.py — the literature-review engine (study feature #22).

Split per the zero-error protocol:
  - HAPPY-PATH tests: sentence splitting, scoring, claim extraction, theme
    clustering, full review generation, Markdown/HTML export.
  - ERROR-PATH tests: every public function is exercised with invalid input
    and must return a clean failure value — no function may raise unhandled.

Golden fixture: three synthetic mini-papers with known themes
(attention / pretraining / quantization). Citation integrity is asserted
end-to-end: every cited page must exist in its document and every cited
excerpt must be a verbatim substring of the referenced chunk.
"""
import pytest

from studybuddy.lit_review import (
    cluster_themes,
    extract_claims,
    generate_review,
    review_to_html,
    review_to_markdown,
    score_sentences,
    split_sentences,
)
from unified_app import User, StudyDoc, db


# ---------------------------------------------------------------------------
# Golden fixture: three synthetic mini-papers, 5 substantive sentences each
# ---------------------------------------------------------------------------

PAPER_A_TITLE = "Sparse Attention for Long Sequences"
PAPER_B_TITLE = "Pretraining Language Models at Scale"
PAPER_C_TITLE = "Quantized Inference for Transformers"

PAPER_A_CHUNKS = [
    {"page": 1, "index": 0, "heading": "",
     "text": "Transformers rely on self-attention to model long-range "
             "dependencies in text. We study sparse attention patterns that "
             "reduce the quadratic cost of dense attention."},
    {"page": 1, "index": 1, "heading": "",
     "text": "We demonstrate that local sliding-window attention matches "
             "dense attention perplexity on long documents."},
    {"page": 2, "index": 2, "heading": "",
     "text": "We report that sparse models outperform dense baselines on "
             "sequences longer than 4096 tokens. We conclude that sparsity "
             "is essential for scaling attention to very long inputs."},
]

PAPER_B_CHUNKS = [
    {"page": 1, "index": 0, "heading": "",
     "text": "Pretraining large language models on web-scale corpora has "
             "transformed natural language processing. We investigate how "
             "pretraining data scale affects downstream task accuracy."},
    {"page": 2, "index": 1, "heading": "",
     "text": "We observe that masked language modeling objectives improve "
             "sample efficiency during pretraining. Our experiments reveal "
             "that larger pretraining corpora consistently improve few-shot "
             "performance."},
    {"page": 2, "index": 2, "heading": "",
     "text": "We conclude that pretraining scale is the dominant factor "
             "behind language model quality."},
]

PAPER_C_CHUNKS = [
    {"page": 1, "index": 0, "heading": "",
     "text": "Deploying transformers in production requires efficient and "
             "low-latency inference. We study quantization and knowledge "
             "distillation to accelerate inference on commodity hardware."},
    {"page": 1, "index": 1, "heading": "",
     "text": "We demonstrate that 8-bit quantization reduces model size "
             "fourfold with negligible accuracy loss."},
    {"page": 2, "index": 2, "heading": "",
     "text": "We find that distilled student models achieve 95 percent of "
             "their teacher accuracy. We conclude that quantization is "
             "practical for production inference workloads."},
]


def _enrich(chunks, doc_id, title):
    out = []
    for c in chunks:
        d = dict(c)
        d["doc_id"] = doc_id
        d["doc_title"] = title
        out.append(d)
    return out


@pytest.fixture()
def golden_chunks():
    return (_enrich(PAPER_A_CHUNKS, 1, PAPER_A_TITLE)
            + _enrich(PAPER_B_CHUNKS, 2, PAPER_B_TITLE)
            + _enrich(PAPER_C_CHUNKS, 3, PAPER_C_TITLE))


@pytest.fixture()
def golden_docs(app):
    """Three StudyDoc rows with the golden chunks, committed to the DB."""
    with app.app_context():
        user = User(name="Test User", email="litreview@example.com",
                    password_hash="x")
        db.session.add(user)
        db.session.flush()
        docs = []
        for title, chunks in ((PAPER_A_TITLE, PAPER_A_CHUNKS),
                              (PAPER_B_TITLE, PAPER_B_CHUNKS),
                              (PAPER_C_TITLE, PAPER_C_CHUNKS)):
            doc = StudyDoc(user_id=user.id, title=title,
                           data={"chunks": chunks})
            db.session.add(doc)
            docs.append(doc)
        db.session.commit()
        ids = [d.id for d in docs]
        docs = [StudyDoc.query.get(i) for i in ids]
        yield docs


def _chunk_text_by_index(chunks):
    return {c["index"]: c["text"] for c in chunks}


# ---------------------------------------------------------------------------
# split_sentences — happy path
# ---------------------------------------------------------------------------

def test_split_sentences_basic():
    sents = split_sentences("First sentence here. Second one follows. "
                            "And a third arrives!")
    assert sents == ["First sentence here.", "Second one follows.",
                     "And a third arrives!"]


def test_split_sentences_abbreviations():
    text = ("We use e.g. sparse attention in this work. See Fig. 3 for "
            "details of the setup. Prior work, i.e. dense transformers, "
            "is compared against our method.")
    sents = split_sentences(text)
    assert len(sents) == 3
    assert sents[0].endswith("in this work.")
    assert "Fig. 3" in sents[1]
    # "et al." must not split either
    sents2 = split_sentences("As shown by Smith et al. the results hold. "
                             "We confirm this finding here.")
    assert len(sents2) == 2


def test_split_sentences_drops_fragments():
    sents = split_sentences("Methods. We demonstrate that sparse attention "
                            "reduces memory usage significantly.")
    assert sents == ["We demonstrate that sparse attention reduces memory "
                     "usage significantly."]
    # Every returned sentence is a verbatim substring of the input.
    text = "Hello world, this is fine. Short. Another proper sentence here."
    for s in split_sentences(text):
        assert s in text


def test_split_sentences_invalid_input():
    assert split_sentences(None) == []
    assert split_sentences(123) == []
    assert split_sentences("") == []
    assert split_sentences("   ") == []


# ---------------------------------------------------------------------------
# score_sentences — happy path + error path
# ---------------------------------------------------------------------------

def test_score_sentences_top_n_and_order(golden_chunks):
    scored = score_sentences(golden_chunks, top_n=5)
    assert len(scored) == 5
    for s in scored:
        assert set(s) == {"sentence", "chunk_index", "page",
                          "score", "doc_id", "doc_title"}
    scores = [s["score"] for s in scored]
    assert scores == sorted(scores, reverse=True)


def test_score_sentences_deterministic(golden_chunks):
    first = score_sentences(golden_chunks, top_n=8)
    second = score_sentences(golden_chunks, top_n=8)
    assert first == second


def test_score_sentences_query_terms_boost(golden_chunks):
    scored = score_sentences(_enrich(PAPER_C_CHUNKS, 3, PAPER_C_TITLE),
                             query_terms=["quantization"], top_n=3)
    assert "quantization" in scored[0]["sentence"]


def test_score_sentences_invalid_input():
    assert score_sentences(None) == []
    assert score_sentences([]) == []
    assert score_sentences("not a list") == []
    # Malformed chunk dicts never raise; nothing scorable -> [].
    assert score_sentences([{"nope": 1}, None, {"text": 123}]) == []
    assert score_sentences([{"text": "x" * 10}], top_n=0) == []


# ---------------------------------------------------------------------------
# extract_claims — happy path + error path
# ---------------------------------------------------------------------------

def test_extract_claims_finds_finding_verbs(golden_chunks):
    claims = extract_claims(golden_chunks)
    assert len(claims) >= 9
    texts = [c["claim"] for c in claims]
    assert any("sliding-window attention" in t for t in texts)
    assert any("quantization reduces model size" in t for t in texts)
    assert any("pretraining scale is the dominant factor" in t for t in texts)
    for c in claims:
        assert set(c) == {"claim", "doc_id", "doc_title",
                          "chunk_index", "page"}
    # Non-claim sentences (no finding verb) are excluded.
    assert not any("self-attention to model long-range" in t for t in texts)


def test_extract_claims_dedupe():
    chunks = [
        {"page": 1, "index": 0, "heading": "",
         "text": "We demonstrate that sparse attention reduces memory usage "
                 "significantly in production settings.",
         "doc_id": 1, "doc_title": "Doc One"},
        {"page": 1, "index": 0, "heading": "",
         "text": "We demonstrate that sparse attention reduces memory usage "
                 "significantly in production settings.",
         "doc_id": 2, "doc_title": "Doc Two"},
        {"page": 2, "index": 1, "heading": "",
         "text": "We demonstrate sparse attention reduces memory usage "
                 "significantly in production settings.",
         "doc_id": 2, "doc_title": "Doc Two"},
    ]
    claims = extract_claims(chunks)
    # Exact duplicate + near-duplicate (dropped "that", Jaccard 0.89)
    # collapse to a single claim.
    assert len(claims) == 1
    assert claims[0]["doc_id"] == 1  # first occurrence wins


def test_extract_claims_invalid_input():
    assert extract_claims(None) == []
    assert extract_claims([]) == []
    assert extract_claims("nope") == []


# ---------------------------------------------------------------------------
# cluster_themes — happy path + error path
# ---------------------------------------------------------------------------

def test_cluster_themes_expected_terms(golden_chunks):
    themes = cluster_themes(golden_chunks)
    assert 1 <= len(themes) <= 6
    names = " | ".join(t["name"] for t in themes)
    assert "attention" in names
    assert "pretraining" in names
    assert "quantization" in names
    for t in themes:
        assert set(t) == {"name", "terms", "members"}
        assert t["name"]
        assert t["terms"]


def test_cluster_themes_members_valid(golden_chunks):
    by_doc = {}
    for c in golden_chunks:
        by_doc.setdefault(c["doc_id"], {})[c["index"]] = c
    for theme in cluster_themes(golden_chunks):
        assert theme["members"], "theme %r has no members" % theme["name"]
        for m in theme["members"]:
            chunk = by_doc[m["doc_id"]][m["chunk_index"]]
            assert m["page"] == chunk["page"]
            assert m["doc_title"] == chunk["doc_title"]


def test_cluster_themes_deterministic_and_capped(golden_chunks):
    first = cluster_themes(golden_chunks, max_themes=3)
    second = cluster_themes(golden_chunks, max_themes=3)
    assert first == second
    assert len(first) <= 3


def test_cluster_themes_invalid_input():
    assert cluster_themes(None) == []
    assert cluster_themes([]) == []
    assert cluster_themes("nope") == []
    assert cluster_themes([{"text": ""}]) == []


# ---------------------------------------------------------------------------
# generate_review — golden happy path
# ---------------------------------------------------------------------------

def test_generate_review_golden_full(golden_docs):
    review = generate_review(golden_docs)
    assert "error" not in review
    assert set(review) == {"per_paper", "themes", "claims_table",
                           "coverage_gaps", "bibtex"}

    assert len(review["per_paper"]) == 3
    for p in review["per_paper"]:
        assert set(p) == {"doc_id", "title", "summary", "citations"}
        assert p["summary"]
        assert len(p["citations"]) == 5  # all five sentences cited

    assert review["themes"], "expected at least one theme"
    names = " | ".join(t["name"] for t in review["themes"])
    assert "attention" in names and "pretraining" in names \
        and "quantization" in names

    claim_texts = [c["claim"] for c in review["claims_table"]]
    assert any("sliding-window attention" in t for t in claim_texts)
    assert any("quantization reduces model size" in t for t in claim_texts)

    assert "Only" in review["coverage_gaps"]  # single-paper themes exist
    assert review["bibtex"].count("@") >= 3


def test_citations_pages_exist_and_excerpts_verbatim(golden_docs):
    review = generate_review(golden_docs)
    assert "error" not in review
    doc_info = {}
    for doc in golden_docs:
        chunks = doc.data["chunks"]
        doc_info[doc.title] = {
            "pages": {c["page"] for c in chunks},
            "texts": _chunk_text_by_index(chunks),
        }
    sections = ([c for p in review["per_paper"] for c in p["citations"]]
                + [c for t in review["themes"] for c in t["citations"]]
                + [c for c in review["claims_table"]
                    for c in c["citations"]])
    assert sections, "review produced no citations at all"
    for cit in sections:
        assert set(cit) == {"doc", "page", "chunk", "excerpt"}
        info = doc_info[cit["doc"]]
        assert cit["page"] in info["pages"], \
            "cited page %r not in %r" % (cit["page"], cit["doc"])
        chunk_text = info["texts"][cit["chunk"]]
        assert cit["excerpt"] and cit["excerpt"] in chunk_text, \
            "excerpt not a verbatim substring of chunk %r" % cit["chunk"]


def test_per_paper_summaries_cite_correct_pages(golden_docs):
    review = generate_review(golden_docs)
    by_title = {p["title"]: p for p in review["per_paper"]}
    for title in (PAPER_A_TITLE, PAPER_B_TITLE, PAPER_C_TITLE):
        summary = by_title[title]["summary"]
        # [Title, p.X] markers present for both pages of each paper.
        assert "[%s, p.1]" % title in summary
        assert "[%s, p.2]" % title in summary
        for cit in by_title[title]["citations"]:
            assert cit["doc"] == title


# ---------------------------------------------------------------------------
# generate_review — error paths
# ---------------------------------------------------------------------------

def test_generate_review_single_doc_error(golden_docs):
    review = generate_review(golden_docs[:1])
    assert review["error"]
    assert review["per_paper"] == [] and review["themes"] == []
    assert review["claims_table"] == []
    assert review["bibtex"] == "" and review["coverage_gaps"] == ""


def test_generate_review_no_chunks_error(app):
    with app.app_context():
        user = User(name="U", email="nochunks@example.com",
                    password_hash="x")
        db.session.add(user)
        db.session.flush()
        docs = [StudyDoc(user_id=user.id, title="Empty %d" % i,
                         data={"chunks": []}) for i in range(3)]
        db.session.add_all(docs)
        db.session.commit()
        docs = [StudyDoc.query.get(d.id) for d in docs]
        review = generate_review(docs)
    assert review["error"]
    assert review["per_paper"] == []


def test_generate_review_none_and_garbage():
    for bad in (None, [], "nope", [None, None], [{"x": 1}]):
        review = generate_review(bad)
        assert isinstance(review, dict) and review.get("error"), bad


# ---------------------------------------------------------------------------
# generate_review — polish hook and BibTeX metadata
# ---------------------------------------------------------------------------

def test_generate_review_gemini_polish(golden_docs):
    review = generate_review(
        golden_docs, gemini_polish=lambda t: "POLISHED: " + t)
    assert "error" not in review
    assert review["themes"]
    for theme in review["themes"]:
        if theme["synthesis"]:
            assert theme["synthesis"].startswith("POLISHED: ")

    def _boom(text):
        raise RuntimeError("LLM exploded")

    fallback = generate_review(golden_docs, gemini_polish=_boom)
    plain = generate_review(golden_docs)
    assert fallback == plain  # raising polish falls back silently


def test_generate_review_bibtex_paper_import_match(golden_docs):
    by_title = {d.title: d for d in golden_docs}
    doc_a = by_title[PAPER_A_TITLE]
    review = generate_review(
        golden_docs,
        paper_imports=[{
            "title": "  sparse ATTENTION for long SEQUENCES ",
            "authors": ["Ada Lovelace"], "year": 2024,
            "venue": "NeurIPS", "pubtype": "inproceedings",
        }])
    assert "Lovelace" in review["bibtex"]
    assert "@inproceedings" in review["bibtex"]

    # paper_metas (keyed by doc id) takes precedence over the import match.
    review2 = generate_review(
        golden_docs,
        paper_metas={doc_a.id: {"title": PAPER_A_TITLE,
                                "authors": ["Grace Hopper"], "year": 2023}},
        paper_imports=[{"title": PAPER_A_TITLE,
                        "authors": ["Ada Lovelace"], "year": 2024}])
    assert "Hopper" in review2["bibtex"]
    assert "Lovelace" not in review2["bibtex"]


# ---------------------------------------------------------------------------
# Export: Markdown and HTML
# ---------------------------------------------------------------------------

def test_review_to_markdown_sections(golden_docs):
    md = review_to_markdown(generate_review(golden_docs))
    assert md.startswith("# Literature Review")
    for section in ("## Per-paper summaries", "## Themes",
                    "## Claims table", "## Coverage gaps", "## BibTeX"):
        assert section in md
    assert "```bibtex" in md
    assert PAPER_A_TITLE in md

    err_md = review_to_markdown(generate_review([]))
    assert "Could not generate a review" in err_md


def test_review_to_html_escapes_script(app):
    evil = "<script>alert('xss')</script>"
    with app.app_context():
        user = User(name="U", email="xss@example.com", password_hash="x")
        db.session.add(user)
        db.session.flush()
        docs = []
        for i, title in enumerate(["Paper %s One" % evil,
                                   "Paper %s Two" % evil]):
            doc = StudyDoc(
                user_id=user.id, title=title,
                data={"chunks": [
                    {"page": 1, "index": 0, "heading": "",
                     "text": "We demonstrate that %s handling keeps "
                             "systems safe in every deployment we study."
                             % evil},
                    {"page": 1, "index": 1, "heading": "",
                     "text": "We conclude that careful %s escaping "
                             "prevents markup injection attacks entirely."
                             % evil},
                ]})
            db.session.add(doc)
            docs.append(doc)
        db.session.commit()
        docs = [StudyDoc.query.get(d.id) for d in docs]
        review = generate_review(docs)
    assert "error" not in review
    html_out = review_to_html(review)
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert "alert" in html_out  # text preserved, markup neutralised


def test_review_to_html_error_dict():
    html_out = review_to_html(generate_review([]))
    assert "Could not generate a review" in html_out
    assert "<h1>Literature Review</h1>" in html_out
    # Never raises on garbage either.
    assert "Literature Review" in review_to_html(None)
    assert "Literature Review" in review_to_markdown(None)
