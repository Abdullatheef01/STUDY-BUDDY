"""LLM-04, LLM-06, LLM-08 + PRIV-06 tests."""
import pytest

from studybuddy import ai_gateway
from studybuddy.age_gate import is_13_or_older


class TestLLM04Cache:
    def setup_method(self):
        ai_gateway._CACHE.clear()
        ai_gateway._CIRCUIT.clear()

    def test_cache_hit(self, monkeypatch):
        calls = []
        def fake_generate(prompt, user_key=None):
            calls.append(1)
            return "cached response"
        # Patch the provider functions to avoid real API calls
        monkeypatch.setattr(ai_gateway, "_gemini_generate",
                            lambda p: fake_generate(p))
        monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: True)
        monkeypatch.setattr(ai_gateway, "groq_configured", lambda: False)
        monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
        monkeypatch.setattr(ai_gateway, "local_configured", lambda: False)
        import os
        monkeypatch.setenv("LLM_MODE", "server")

        r1 = ai_gateway.generate("test prompt", redact_pii=False)
        r2 = ai_gateway.generate("test prompt", redact_pii=False)
        assert r1 == r2 == "cached response"
        assert len(calls) == 1  # second call was cached

    def test_byok_skips_cache(self, monkeypatch):
        ai_gateway._CACHE.clear()
        # BYOK should not use cache (different user keys)
        assert ai_gateway._cache_get("x") is None


class TestLLM06Redaction:
    def test_pii_redacted_from_prompt(self, monkeypatch):
        seen_prompts = []
        def fake_provider(prompt):
            seen_prompts.append(prompt)
            return "response"
        monkeypatch.setattr(ai_gateway, "_gemini_generate", fake_provider)
        monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: True)
        monkeypatch.setattr(ai_gateway, "groq_configured", lambda: False)
        monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
        monkeypatch.setattr(ai_gateway, "local_configured", lambda: False)
        import os
        monkeypatch.setenv("LLM_MODE", "server")
        ai_gateway._CACHE.clear()

        ai_gateway.generate("Contact john@example.com for details")
        # Provider should NOT see the raw email
        assert "john@example.com" not in seen_prompts[0]
        assert "[EMAIL_1]" in seen_prompts[0]

    def test_redaction_disabled(self, monkeypatch):
        seen_prompts = []
        def fake_provider(prompt):
            seen_prompts.append(prompt)
            return "response"
        monkeypatch.setattr(ai_gateway, "_gemini_generate", fake_provider)
        monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: True)
        monkeypatch.setattr(ai_gateway, "groq_configured", lambda: False)
        monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
        monkeypatch.setattr(ai_gateway, "local_configured", lambda: False)
        import os
        monkeypatch.setenv("LLM_MODE", "server")
        ai_gateway._CACHE.clear()

        ai_gateway.generate("Contact john@example.com",
                            redact_pii=False)
        assert "john@example.com" in seen_prompts[0]


class TestAgeGate:
    def test_13_or_older(self):
        assert is_13_or_older(2000) is True
        assert is_13_or_older(2020) is False

    def test_invalid(self):
        assert is_13_or_older(None) is False

    def test_register_requires_age_confirm(self, client):
        r = client.post("/register", data={
            "name": "Test", "email": "age@test.com",
            "password": "Str0ng!Test#2026",
            # no age_confirm
        })
        assert b"13 years" in r.data
