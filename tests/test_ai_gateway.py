"""Tests for the AI gateway (studybuddy.ai_gateway)."""
import pytest

from studybuddy import ai_gateway
from studybuddy.ai_gateway import AIError


def _ok_response(text):
    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": text}}]}
    return R()


def test_no_providers_raises(monkeypatch):
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
    with pytest.raises(AIError, match="No AI provider"):
        ai_gateway.generate("hi")


def test_groq_serves(monkeypatch):
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "_key", lambda n: "k")
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _ok_response("from groq"))
    assert ai_gateway.generate("hi") == "from groq"


def test_fallback_groq_to_openrouter(monkeypatch):
    """Groq fails -> OpenRouter serves."""
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "_key", lambda n: "k")
    import requests
    calls = []
    def fake_post(url, **kwargs):
        calls.append(url)
        if "groq" in url:
            raise ConnectionError("groq down")
        return _ok_response("from openrouter")
    monkeypatch.setattr(requests, "post", fake_post)
    assert ai_gateway.generate("hi") == "from openrouter"
    assert any("groq" in u for u in calls) and any("openrouter" in u for u in calls)


def test_all_fail_raises_aierror(monkeypatch):
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "_key", lambda n: "k")
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(AIError, match="All AI providers failed"):
        ai_gateway.generate("hi")


def test_ai_ready(monkeypatch):
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: False)
    assert ai_gateway.ai_ready() is True
    assert ai_gateway.providers_configured() == ["groq"]
