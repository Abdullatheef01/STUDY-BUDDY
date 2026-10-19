"""PRIV-08: PII redaction tests."""
import pytest

from studybuddy.pii_redaction import (
    redact,
    redact_for_llm,
    redact_for_log,
    unredact,
)


class TestRedact:
    def test_email(self):
        text = "Contact me at john@example.com for details."
        redacted, mapping = redact(text)
        assert "john@example.com" not in redacted
        assert "[EMAIL_1]" in redacted
        assert mapping["[EMAIL_1]"] == "john@example.com"

    def test_indian_phone_spaced(self):
        text = "Call +91 98765 43210"
        redacted, mapping = redact(text)
        assert "98765 43210" not in redacted
        assert "[PHONE_1]" in redacted

    def test_indian_phone_dashed(self):
        text = "Call 98765-43210"
        redacted, _ = redact(text)
        assert "98765-43210" not in redacted

    def test_indian_phone_plain(self):
        text = "Call 9876543210"
        redacted, _ = redact(text)
        assert "9876543210" not in redacted

    def test_url(self):
        text = "See https://example.com/page for more."
        redacted, mapping = redact(text)
        assert "https://example.com/page" not in redacted
        assert "[URL_1]" in redacted

    def test_keep_url(self):
        text = "See https://example.com for more."
        redacted, _ = redact(text, keep={"url"})
        assert "https://example.com" in redacted

    def test_unredact(self):
        text = "Email john@example.com now."
        redacted, mapping = redact(text)
        assert unredact(redacted, mapping) == text

    def test_no_pii(self):
        text = "Built a web app with Python."
        redacted, mapping = redact(text)
        assert redacted == text
        assert mapping == {}

    def test_multilingual_name_preserved(self):
        # Names are NOT redacted by default (only emails/phones/URLs)
        text = "Rahul Sharma built this."
        redacted, _ = redact(text)
        assert "Rahul Sharma" in redacted


class TestRedactForLLM:
    def test_llm_redaction(self):
        text = "John at john@example.com, phone 9876543210"
        redacted, mapping = redact_for_llm(text)
        assert "john@example.com" not in redacted
        assert "9876543210" not in redacted
        assert len(mapping) == 2


class TestRedactForLog:
    def test_truncation(self):
        text = "x" * 500
        assert len(redact_for_log(text)) <= 203

    def test_pii_removed(self):
        text = "User john@example.com did something"
        logged = redact_for_log(text)
        assert "john@example.com" not in logged
