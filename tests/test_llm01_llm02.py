"""LLM-01 + LLM-02 tests."""
import pytest
from pydantic import BaseModel

from studybuddy import ai_gateway
from studybuddy.ai_gateway import (
    BadOutput,
    ProviderDown,
    RateLimited,
    _circuit_open,
    _circuit_record,
    _CIRCUIT,
)


class TestCircuitBreaker:
    def setup_method(self):
        _CIRCUIT.clear()

    def test_closed_initially(self):
        assert _circuit_open("test-provider") is False

    def test_opens_after_threshold(self):
        for _ in range(5):
            _circuit_record("test-provider", False)
        assert _circuit_open("test-provider") is True

    def test_resets_on_success(self):
        for _ in range(3):
            _circuit_record("test-provider", False)
        _circuit_record("test-provider", True)
        assert _circuit_open("test-provider") is False
        assert _CIRCUIT["test-provider"]["failures"] == 0


class TestStructuredErrors:
    def test_rate_limited_is_aierror(self):
        assert issubclass(RateLimited, ai_gateway.AIError)

    def test_provider_down_is_aierror(self):
        assert issubclass(ProviderDown, ai_gateway.AIError)

    def test_bad_output_is_aierror(self):
        assert issubclass(BadOutput, ai_gateway.AIError)


class SampleSchema(BaseModel):
    name: str
    score: int


class TestGenerateStructured:
    def test_valid_json(self, monkeypatch):
        def fake_generate(prompt, user_key=None):
            return '{"name": "test", "score": 95}'
        monkeypatch.setattr(ai_gateway, "generate", fake_generate)
        result = ai_gateway.generate_structured("prompt", SampleSchema)
        assert result.name == "test"
        assert result.score == 95

    def test_markdown_fence_stripped(self, monkeypatch):
        def fake_generate(prompt, user_key=None):
            return '```json\n{"name": "x", "score": 1}\n```'
        monkeypatch.setattr(ai_gateway, "generate", fake_generate)
        result = ai_gateway.generate_structured("prompt", SampleSchema)
        assert result.name == "x"

    def test_invalid_raises_bad_output(self, monkeypatch):
        def fake_generate(prompt, user_key=None):
            return "not json at all"
        monkeypatch.setattr(ai_gateway, "generate", fake_generate)
        with pytest.raises(BadOutput):
            ai_gateway.generate_structured(
                "prompt", SampleSchema, max_repair=0)

    def test_repair_retry(self, monkeypatch):
        calls = []
        def fake_generate(prompt, user_key=None):
            calls.append(prompt)
            if len(calls) == 1:
                return "bad json"
            return '{"name": "fixed", "score": 50}'
        monkeypatch.setattr(ai_gateway, "generate", fake_generate)
        result = ai_gateway.generate_structured(
            "prompt", SampleSchema, max_repair=1)
        assert result.name == "fixed"
        assert len(calls) == 2
