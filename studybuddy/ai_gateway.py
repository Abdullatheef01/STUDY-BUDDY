"""AI Gateway — multi-provider LLM access with automatic fallback.

Provider chain (all free tiers):
    1. Gemini  (GEMINI_API_KEY)      — google-genai SDK
    2. Groq    (GROQ_API_KEY)        — OpenAI-compatible, llama-3.3-70b-versatile
    3. OpenRouter (OPENROUTER_API_KEY) — OpenAI-compatible, free :free models

generate() tries each configured provider in order and returns the first
successful response. Every provider failure is logged; only if ALL fail
does AIError raise. Callers never need to know which provider served them.

Keys are read from the environment on every call (never cached), so key
rotation via Render env vars takes effect without a restart.
"""

import logging
import os

import requests

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 45

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

_KEY_SENTINELS = frozenset({
    "", "your_actual_api_key_here", "<redacted>", "change-me",
    "YOUR_API_KEY", "paste-your-key-here",
})


class AIError(Exception):
    """All providers failed; message is safe to show to users."""


def _key(name):
    key = (os.getenv(name) or "").strip().strip('"').strip("'")
    return key if key and key not in _KEY_SENTINELS else None


def gemini_configured():
    return _key("GEMINI_API_KEY") is not None


def groq_configured():
    return _key("GROQ_API_KEY") is not None


def openrouter_configured():
    return _key("OPENROUTER_API_KEY") is not None


def ai_ready():
    """True when at least one provider key is configured."""
    return gemini_configured() or groq_configured() or openrouter_configured()


def providers_configured():
    """Ordered list of configured provider names (for status pages)."""
    out = []
    if gemini_configured():
        out.append("gemini")
    if groq_configured():
        out.append("groq")
    if openrouter_configured():
        out.append("openrouter")
    return out


def _openai_compatible_generate(url, key, model, prompt, provider):
    """POST a chat-completion request to an OpenAI-compatible endpoint."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://study-buddy.app"
        headers["X-Title"] = "STUDY-BUDDY"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    text = (data["choices"][0]["message"]["content"] or "").strip()
    if not text:
        raise ValueError(f"{provider}: empty response")
    return text


def _groq_generate(prompt):
    key = _key("GROQ_API_KEY")
    if not key:
        raise AIError("Groq key not configured")
    return _openai_compatible_generate(_GROQ_URL, key, _GROQ_MODEL, prompt, "groq")


def _openrouter_generate(prompt):
    key = _key("OPENROUTER_API_KEY")
    if not key:
        raise AIError("OpenRouter key not configured")
    return _openai_compatible_generate(_OPENROUTER_URL, key, _OPENROUTER_MODEL,
                                       prompt, "openrouter")


def _gemini_generate(prompt):
    """Delegate to the existing Gemini implementation in unified_app."""
    # Local import to avoid a hard dependency cycle at module load.
    import unified_app as app_mod
    return app_mod.call_gemini_direct(prompt)


def generate(prompt):
    """Generate text via the first working provider.

    Order: Gemini -> Groq -> OpenRouter. Raises AIError only when every
    configured provider fails (or none is configured).
    """
    chain = []
    if gemini_configured():
        chain.append(("gemini", _gemini_generate))
    if groq_configured():
        chain.append(("groq", _groq_generate))
    if openrouter_configured():
        chain.append(("openrouter", _openrouter_generate))
    if not chain:
        raise AIError(
            "No AI provider is configured. Add GEMINI_API_KEY, GROQ_API_KEY, "
            "or OPENROUTER_API_KEY to your environment.")

    errors = []
    for name, fn in chain:
        try:
            text = fn(prompt)
            if text:
                log.info("AI gateway: served by %s", name)
                return text
            errors.append(f"{name}: empty response")
        except Exception as exc:
            log.warning("AI gateway: %s failed: %r", name, exc)
            errors.append(f"{name}: {exc}")
    raise AIError(
        "All AI providers failed just now. Please try again in a moment. "
        f"({'; '.join(errors)[:200]})")
