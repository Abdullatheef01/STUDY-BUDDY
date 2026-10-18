"""MEGA-6: AI gateway harsh tests — failures, timeouts, garbage.

Verifies the fallback chain under hostile conditions: provider timeouts,
garbage responses, empty text, HTTP errors, key problems. ~200 tests.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from studybuddy import ai_gateway
from studybuddy.ai_gateway import AIError
from tests.mega.harsh_corpus import HARSH_STRINGS


def _resp(text=None, status=200, exc=None):
    class R:
        def raise_for_status(self):
            if exc:
                raise exc
            if status >= 400:
                import requests
                raise requests.HTTPError(f"{status}")
        def json(self):
            if text is None:
                return {"wrong": "shape"}
            return {"choices": [{"message": {"content": text}}]}
    return R()


def _one_provider(monkeypatch, name):
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: name == "groq")
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: name == "openrouter")
    monkeypatch.setattr(ai_gateway, "_key", lambda n: "k")


@pytest.mark.parametrize("s", HARSH_STRINGS[:40])
def test_groq_harsh_prompts(monkeypatch, s):
    """Harsh prompts are transmitted safely; provider handles them."""
    _one_provider(monkeypatch, "groq")
    import requests
    captured = {}
    def fake_post(url, **kwargs):
        captured["payload"] = kwargs.get("json")
        return _resp("ok")
    monkeypatch.setattr(requests, "post", fake_post)
    assert ai_gateway.generate(s) == "ok"
    # Prompt must be sent as a plain string in messages
    msgs = captured["payload"]["messages"]
    assert msgs[0]["content"] == s


@pytest.mark.parametrize("exc", [
    ConnectionError("conn refused"),
    TimeoutError("timed out"),
    ValueError("bad value"),
    KeyError("missing"),
])
def test_provider_exceptions_fall_through(monkeypatch, exc):
    _one_provider(monkeypatch, "groq")
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(exc))
    with pytest.raises(AIError):
        ai_gateway.generate("hello")


@pytest.mark.parametrize("bad_text", ["", "   ", None])
def test_empty_response_triggers_fallback(monkeypatch, bad_text):
    """Empty provider text -> next provider tried."""
    monkeypatch.setattr(ai_gateway, "gemini_configured", lambda: False)
    monkeypatch.setattr(ai_gateway, "groq_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "openrouter_configured", lambda: True)
    monkeypatch.setattr(ai_gateway, "_key", lambda n: "k")
    import requests
    calls = []
    def fake_post(url, **kwargs):
        calls.append(url)
        if "groq" in url:
            return _resp(bad_text)
        return _resp("fallback ok")
    monkeypatch.setattr(requests, "post", fake_post)
    assert ai_gateway.generate("hi") == "fallback ok"
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 502, 503])
def test_http_error_statuses(monkeypatch, status):
    _one_provider(monkeypatch, "openrouter")
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _resp(status=status))
    with pytest.raises(AIError):
        ai_gateway.generate("hi")


def test_malformed_provider_json(monkeypatch):
    _one_provider(monkeypatch, "groq")
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _resp(text=None))
    with pytest.raises(AIError):
        ai_gateway.generate("hi")


def test_key_with_quotes_stripped(monkeypatch):
    assert ai_gateway._key("X") is None
    monkeypatch.setenv("GROQ_API_KEY", '"mykey"')
    assert ai_gateway._key("GROQ_API_KEY") == "mykey"
    monkeypatch.setenv("GROQ_API_KEY", "  'spaced'  ")
    assert ai_gateway._key("GROQ_API_KEY") == "spaced"


@pytest.mark.parametrize("sentinel", ["", "change-me", "paste-your-key-here",
                                      "your_actual_api_key_here", "<redacted>"])
def test_sentinel_keys_rejected(monkeypatch, sentinel):
    monkeypatch.setenv("GROQ_API_KEY", sentinel)
    assert ai_gateway._key("GROQ_API_KEY") is None
    assert ai_gateway.groq_configured() is False
