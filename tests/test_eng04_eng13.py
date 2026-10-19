"""ENG-04 + ENG-13 tests."""
import pytest

from studybuddy.anti_gaming import (
    cap_keyword_counts,
    detect_hidden_text_chars,
    detect_keyword_stuffing,
    gaming_risk_report,
)
from studybuddy.grounded_gen import (
    find_unverified_claims,
    flag_unverified_claims,
    grounded_rewrite_prompt,
)


class TestKeywordStuffing:
    def _long_text(self, prefix=""):
        base = ("Led a team of engineers building microservices. "
                "Designed REST APIs and improved latency by optimizing queries. "
                "Mentored junior developers and conducted code reviews. "
                "Deployed to cloud infrastructure with CI/CD pipelines. "
                "Collaborated with product managers on roadmap planning. ")
        return prefix + base * 4  # ~120 tokens

    def test_normal_text_no_flag(self):
        assert detect_keyword_stuffing(self._long_text()) == []

    def test_stuffed_keyword_flagged(self):
        text = self._long_text("python " * 20)
        stuffed = detect_keyword_stuffing(text)
        assert any(t == "python" for t, _ in stuffed)

    def test_threshold_respected(self):
        text = self._long_text("python " * 3)
        assert detect_keyword_stuffing(text) == []

    def test_short_text_skipped(self):
        assert detect_keyword_stuffing("python python") == []


class TestCountCaps:
    def test_cap_applied(self):
        capped, was = cap_keyword_counts({"python": 20, "java": 3})
        assert capped["python"] == 5
        assert capped["java"] == 3
        assert was is True

    def test_no_cap_needed(self):
        capped, was = cap_keyword_counts({"python": 3})
        assert was is False


class TestHiddenText:
    def test_white_text_detected(self):
        chars = [{"text": "a", "size": 12, "color": (1, 1, 1),
                  "x0": 10, "y0": 10, "page_width": 612, "page_height": 792}
                 for _ in range(20)]
        result = detect_hidden_text_chars(chars)
        assert result["has_hidden_text"] is True
        assert "White" in result["reasons"][0]

    def test_tiny_font_detected(self):
        chars = [{"text": "a", "size": 2, "color": (0, 0, 0),
                  "x0": 10, "y0": 10, "page_width": 612, "page_height": 792}
                 for _ in range(20)]
        result = detect_hidden_text_chars(chars)
        assert result["has_hidden_text"] is True

    def test_normal_text_not_flagged(self):
        chars = [{"text": "a", "size": 12, "color": (0, 0, 0),
                  "x0": 10, "y0": 10, "page_width": 612, "page_height": 792}
                 for _ in range(20)]
        result = detect_hidden_text_chars(chars)
        assert result["has_hidden_text"] is False

    def test_few_hidden_chars_ignored(self):
        # Below threshold (10) to avoid false positives
        chars = [{"text": "a", "size": 2, "color": (0, 0, 0),
                  "x0": 10, "y0": 10, "page_width": 612, "page_height": 792}
                 for _ in range(5)]
        result = detect_hidden_text_chars(chars)
        assert result["has_hidden_text"] is False


class TestGamingRiskReport:
    def test_low_risk(self):
        text = (
            "Led a team building microservices for payment processing. "
            "Designed REST APIs with authentication and rate limiting. "
            "Mentored junior developers through code reviews and pairing. "
            "Improved database query performance using indexing strategies. "
            "Deployed containerized services to cloud infrastructure. "
            "Collaborated with designers on user interface improvements. "
            "Wrote comprehensive tests achieving high coverage metrics. "
            "Optimized caching layer reducing response times significantly. "
            "Participated in architecture discussions for new features. "
            "Documented system design for onboarding new engineers. "
            "Integrated third-party services for notifications and analytics. "
            "Refactored legacy modules improving maintainability scores. ")
        r = gaming_risk_report(text)
        assert r["risk_level"] == "low"

    def test_high_risk(self):
        base = "Built web applications with modern frameworks. " * 20
        text = base + "python " * 30 + "java " * 30
        r = gaming_risk_report(text, skill_counts={"python": 25})
        assert r["risk_level"] in ("medium", "high")
        assert len(r["warnings"]) > 0


class TestGroundedGen:
    def test_no_new_numbers(self):
        inp = "Built a web app serving users."
        out = "Engineered a scalable web application serving thousands of users."
        assert find_unverified_claims(inp, out) == []

    def test_invented_number_flagged(self):
        inp = "Built a web app."
        out = "Built a web app serving 10,000 users with 99.9% uptime."
        unverified = find_unverified_claims(inp, out)
        assert len(unverified) > 0

    def test_existing_number_ok(self):
        inp = "Improved latency by 30%."
        out = "Reduced latency by 30% through optimization."
        assert find_unverified_claims(inp, out) == []

    def test_flag_wraps_text(self):
        inp = "Built a thing."
        out = "Built a thing used by 500 people."
        flagged, unverified = flag_unverified_claims(inp, out)
        assert "[UNVERIFIED" in flagged
        assert len(unverified) > 0

    def test_prompt_has_grounding_rules(self):
        p = grounded_rewrite_prompt("Did stuff.")
        assert "NEVER invent" in p
        assert "[add metric" in p
