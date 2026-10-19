"""PRIV-08: PII redaction layer.

Redacts emails, phones, URLs before LLM calls and logging.
Supports Indian phone formats.
"""
import re

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}|\+\d[\d\s-]{7,}\d")
_URL_RE = re.compile(
    r"https?://[^\s)>\"]+|(?:www\.|linkedin\.com/|github\.com/)[^\s)>\"]*")


def redact(text, keep=None, placeholders=True):
    """Replace PII with placeholders.

    Args:
        text: input text
        keep: set of types to NOT redact (e.g. {"url"})
        placeholders: if True use [EMAIL], [PHONE], [URL]; else use ███

    Returns:
        (redacted_text, mapping) where mapping can reinsert originals.
    """
    keep = keep or set()
    mapping = {}
    counter = {"email": 0, "phone": 0, "url": 0}

    def _sub(pattern, kind, label):
        def repl(m):
            if kind in keep:
                return m.group(0)
            counter[kind] += 1
            key = f"[{label}_{counter[kind]}]" if placeholders else "███"
            mapping[key] = m.group(0)
            return key
        return repl

    result = _EMAIL_RE.sub(_sub(_EMAIL_RE, "email", "EMAIL"), text)
    result = _PHONE_RE.sub(_sub(_PHONE_RE, "phone", "PHONE"), result)
    result = _URL_RE.sub(_sub(_URL_RE, "url", "URL"), result)
    return result, mapping


def unredact(text, mapping):
    """Reinsert original values from mapping."""
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text


def redact_for_llm(text):
    """Redact PII before sending to LLM (keeps URLs if needed for context)."""
    redacted, mapping = redact(text)
    return redacted, mapping


def redact_for_log(text, max_len=200):
    """Redact PII and truncate for safe logging."""
    redacted, _ = redact(text, placeholders=False)
    if len(redacted) > max_len:
        redacted = redacted[:max_len] + "..."
    return redacted
