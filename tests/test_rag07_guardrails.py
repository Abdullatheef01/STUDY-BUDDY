"""RAG-07: Paper constructor integrity guardrails tests."""
import pytest

from studybuddy.constructor_guardrails import (
    AI_DISCLOSURE_TEMPLATE,
    TODO_PLACEHOLDER,
    WATERMARK,
    build_grounded_prompt,
    contains_banned_phrase,
    extract_citations,
    find_invented_numbers,
    post_process_paper,
    strip_banned_phrases,
    verify_citations,
)


class TestBannedPhrases:
    def test_detect_ieee_ready(self):
        assert contains_banned_phrase("This is IEEE-ready for submission.")

    def test_detect_publication_ready(self):
        assert "publication-ready" in contains_banned_phrase(
            "A publication-ready manuscript.")

    def test_clean_text_no_banned(self):
        assert contains_banned_phrase(
            "This is a draft requiring review.") == []

    def test_strip_removes_phrases(self):
        text = "This IEEE-ready paper is publication-ready."
        stripped = strip_banned_phrases(text)
        assert "ieee-ready" not in stripped.lower()
        assert "publication-ready" not in stripped.lower()


class TestWatermark:
    def test_watermark_content(self):
        assert "AI-assisted draft" in WATERMARK
        assert "verify every claim" in WATERMARK

    def test_disclosure_mentions_author(self):
        d = AI_DISCLOSURE_TEMPLATE.format(author="Jane Doe")
        assert "Jane Doe" in d
        assert "AI" in d


class TestInventedNumbers:
    def test_no_invented(self):
        inp = "stars 100 forks 20 files 50"
        out = "The repo has 100 stars and 20 forks across 50 files."
        assert find_invented_numbers(inp, out) == []

    def test_invented_percentage_flagged(self):
        inp = "stars 100 forks 20"
        out = "Achieved 99.9% accuracy with 10x speedup."
        invented = find_invented_numbers(inp, out)
        assert len(invented) > 0

    def test_invented_count_flagged(self):
        inp = "A small Python project."
        out = "Serving 10,000 users daily."
        invented = find_invented_numbers(inp, out)
        assert "10,000" in invented


class TestPostProcess:
    def _sample(self):
        return {
            "title": "A Study of Foo",
            "abstract": "This IEEE-ready paper presents results.",
            "results": "Achieved 95% accuracy, 10x faster.",
        }

    def test_watermark_added(self):
        processed, _ = post_process_paper(self._sample(), "stars 10")
        assert processed["_watermark"] == WATERMARK

    def test_disclosure_added(self):
        processed, _ = post_process_paper(
            self._sample(), "stars 10", author="Test Author")
        assert "Test Author" in processed["_ai_disclosure"]

    def test_banned_phrase_removed(self):
        processed, report = post_process_paper(self._sample(), "stars 10")
        assert "ieee-ready" not in processed["abstract"].lower()
        assert len(report["banned_phrases_removed"]) > 0

    def test_invented_numbers_flagged_with_todo(self):
        processed, report = post_process_paper(self._sample(), "stars 10")
        assert TODO_PLACEHOLDER in processed["results"]
        assert len(report["invented_numbers"]) > 0

    def test_grounded_numbers_kept(self):
        analysis = {"results": "The repo has 10 stars."}
        processed, report = post_process_paper(analysis, "stars 10")
        assert TODO_PLACEHOLDER not in processed["results"]
        assert report["invented_numbers"] == []


class TestGroundedPrompt:
    def test_integrity_rules_injected(self):
        prompt = build_grounded_prompt("Base prompt.")
        assert "NEVER invent" in prompt
        assert TODO_PLACEHOLDER in prompt
        assert "Base prompt." in prompt


class TestCitations:
    def test_extract_doi(self):
        text = "See Smith et al. (doi: 10.1234/example.2024) for details."
        cites = extract_citations(text)
        assert len(cites["dois"]) > 0

    def test_extract_arxiv(self):
        text = "See arXiv: 2101.12345 for details."
        cites = extract_citations(text)
        assert "2101.12345" in cites["arxiv"]

    def test_bad_doi_removed(self):
        # Fake DOI that won't resolve
        text = "As shown in 10.9999/fake.doi.that.does.not.exist.xyz"
        verified, removed = verify_citations(
            text,
            verify_fn_doi=lambda d: False,  # mock: always fail
            verify_fn_arxiv=lambda a: True,
        )
        assert "unverified" in verified
        assert len(removed) > 0

    def test_good_doi_kept(self):
        text = "See 10.1234/real.doi here."
        verified, removed = verify_citations(
            text,
            verify_fn_doi=lambda d: True,  # mock: always pass
            verify_fn_arxiv=lambda a: True,
        )
        assert "10.1234/real.doi" in verified
        assert removed == []

    def test_network_failure_keeps_citation(self):
        text = "See 10.1234/maybe.doi here."
        verified, removed = verify_citations(
            text,
            verify_fn_doi=lambda d: None,  # mock: unknown
            verify_fn_arxiv=lambda a: None,
        )
        # Unknown -> keep (don't punish for network issues)
        assert "10.1234/maybe.doi" in verified
