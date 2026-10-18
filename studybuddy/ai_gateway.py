"""AI Gateway — multi-provider LLM access with automatic fallback.

Provider chain (all free tiers):
    1. Gemini  (GEMINI_API_KEY)      — google-genai SDK
    2. Groq    (GROQ_API_KEY)        — OpenAI-compatible, llama-3.3-70b-versatile
    3. OpenRouter (OPENROUTER_API_KEY) — OpenAI-compatible, free :free models
    4. Local   (LLM_BASE_URL)        — OpenAI-compatible local endpoint (Ollama)

PRIV-05 modes (via LLM_MODE env):
    - "server" (default): use server-configured provider keys
    - "off": no LLM calls — raise AIError("disabled") so callers use rule-based fallbacks
    - "byok": caller must pass user_key; used for that request only, never logged

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
_OPENROUTER_MODEL = "google/gemma-4-31b-it:free"  # verified in :free list 2026-10-15

# PRIV-05: local OpenAI-compatible endpoint (e.g. Ollama at http://localhost:11434/v1)
_LOCAL_URL = os.getenv("LLM_BASE_URL", "").rstrip("/") + "/chat/completions" \
    if os.getenv("LLM_BASE_URL") else None
_LOCAL_MODEL = os.getenv("LLM_MODEL", "llama3.2")

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
    return gemini_configured() or groq_configured() or openrouter_configured() \
        or local_configured()


def local_configured():
    """PRIV-05: True when LLM_BASE_URL points at a local OpenAI-compatible endpoint."""
    return bool(os.getenv("LLM_BASE_URL", "").strip())


def llm_mode():
    """PRIV-05: current LLM mode — off|byok|server (from env, default server)."""
    mode = os.getenv("LLM_MODE", "server").strip().lower()
    return mode if mode in ("off", "byok", "server") else "server"


def _local_generate(prompt, api_key=None):
    """PRIV-05: generate via local OpenAI-compatible endpoint (Ollama etc.)."""
    base = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise AIError("Local LLM not configured (LLM_BASE_URL)")
    return _openai_compatible_generate(
        base + "/chat/completions", api_key or "ollama",
        os.getenv("LLM_MODEL", "llama3.2"), prompt, "local")


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


def generate(prompt, user_key=None):
    """Generate text via the first working provider.

    PRIV-05 modes:
    - LLM_MODE=off: raises AIError("disabled") — callers use rule-based fallbacks.
    - LLM_MODE=byok: uses user_key (the user's own API key) via OpenRouter;
      raises if no key provided.
    - default: server chain — local (LLM_BASE_URL) -> Gemini -> Groq -> OpenRouter.

    user_key is never logged.
    """
    mode = llm_mode()
    if mode == "off":
        raise AIError(
            "AI features are disabled (LLM_MODE=off). "
            "Rule-based results are shown instead.")
    if mode == "byok":
        if not user_key or user_key in _KEY_SENTINELS:
            raise AIError(
                "BYOK mode: add your own API key in Profile → AI Settings "
                "to use AI features.")
        # Use the user's key against OpenRouter (OpenAI-compatible)
        return _openai_compatible_generate(
            _OPENROUTER_URL, user_key, _OPENROUTER_MODEL, prompt, "byok")

    chain = []
    if local_configured():
        chain.append(("local", _local_generate))
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
