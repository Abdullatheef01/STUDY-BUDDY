"""AI bullet rewriter engine (Wave 1 feature #2).

Deterministic, server-side bullet improvement for resume lines:

- ``improve_bullet`` — rule-based rewrite producing 3 variants of a bullet:
  1. verb-strengthened (weak verbs swapped for strong action verbs),
  2. quantified (number placeholders the user can fill in),
  3. concise ATS-tightened version.

The numeric rewrites never depend on the LLM; Gemini (wired in
unified_app.py) is used only for an AI-polished alternative with a
rule-based fallback, following the JD-matcher constructor pattern.
"""

import re

# Weak phrasing -> strong action verb. Checked at the start of the bullet
# (case-insensitive) and also for "responsible for X" style fragments.
WEAK_VERB_MAP = [
    (re.compile(r"^worked\s+on\b", re.I), "Engineered"),
    (re.compile(r"^helped\b", re.I), "Collaborated"),
    (re.compile(r"^responsible\s+for\b", re.I), "Owned"),
    (re.compile(r"^did\b", re.I), "Executed"),
    (re.compile(r"^made\b", re.I), "Built"),
    (re.compile(r"^got\b", re.I), "Achieved"),
    (re.compile(r"^used\b", re.I), "Leveraged"),
    (re.compile(r"^was\s+involved\s+in\b", re.I), "Contributed to"),
    (re.compile(r"^participated\s+in\b", re.I), "Drove"),
    (re.compile(r"^handled\b", re.I), "Managed"),
    (re.compile(r"^assisted\s+(with\s+|in\s+)?", re.I), "Supported"),
    (re.compile(r"^tasked\s+with\b", re.I), "Delivered"),
    (re.compile(r"^in\s+charge\s+of\b", re.I), "Led"),
]

# Inline weak fragments anywhere in the bullet.
INLINE_FIXES = [
    (re.compile(r"\bresponsible\s+for\b", re.I), "owning"),
    (re.compile(r"\bworked\s+on\b", re.I), "engineered"),
]

QUANT_HINTS = re.compile(r"\d+\s*%|\d+\s*(x|times)|\$\d+|\d+\s*(users|clients|projects|requests|ms|s\b)|\b\d+\b")

METRIC_PLACEHOLDERS = [
    "[add a metric, e.g. improved performance by 30%]",
    "[quantify the outcome, e.g. served 10k+ requests/day]",
    "[add scale, e.g. across a team of 5]",
]


def _capitalize_first(text):
    if not text:
        return text
    return text[0].upper() + text[1:]


def strengthen_verbs(bullet):
    """Swap weak opening verbs for strong action verbs (deterministic)."""
    text = bullet.strip()
    for pattern, replacement in WEAK_VERB_MAP:
        new_text, n = pattern.subn(replacement, text, count=1)
        if n:
            return _capitalize_first(new_text)
    # Fallback: ensure it starts with a strong verb-ish word
    first = text.split(" ", 1)[0].rstrip(".,:;")
    if first.lower() in {"the", "a", "an", "my", "our", "this"}:
        return "Delivered " + text[0].lower() + text[1:]
    return text


def _has_metric(bullet):
    return bool(QUANT_HINTS.search(bullet))


def quantified_version(bullet):
    """Insert a metric placeholder when the bullet lacks quantification."""
    text = strengthen_verbs(bullet).rstrip(".")
    if _has_metric(text):
        return text + "."
    # Pick a placeholder deterministically from the bullet length.
    placeholder = METRIC_PLACEHOLDERS[len(text) % len(METRIC_PLACEHOLDERS)]
    return f"{text} {placeholder}."


def concise_version(bullet):
    """Tighten the bullet: strip filler, cap length, keep one line."""
    text = strengthen_verbs(bullet)
    for pattern, replacement in INLINE_FIXES:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\b(very|really|quite|basically|actually|just)\b", "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip().rstrip(".")
    words = text.split()
    if len(words) > 28:
        text = " ".join(words[:28])
    return _capitalize_first(text) + "."


def improve_bullet(bullet_text):
    """Return 3 rule-based rewrite variants for a resume bullet.

    Each variant is a dict {"label": ..., "text": ..., "tip": ...}.
    Raises ValueError on invalid input.
    """
    bullet = (bullet_text or "").strip()
    if not bullet:
        raise ValueError("Please enter a bullet to rewrite.")
    if len(bullet) < BULLET_MIN_CHARS:
        raise ValueError(
            f"That bullet looks too short (minimum {BULLET_MIN_CHARS} characters)."
        )
    if len(bullet) > BULLET_MAX_CHARS:
        raise ValueError(
            f"That bullet is too long (maximum {BULLET_MAX_CHARS} characters)."
        )
    variants = [
        {
            "label": "Stronger action verb",
            "text": strengthen_verbs(bullet),
            "tip": "Starts with a punchy verb recruiters scan for.",
        },
        {
            "label": "Quantified impact",
            "text": quantified_version(bullet),
            "tip": "Numbers prove impact — fill in the bracket with your real metric.",
        },
        {
            "label": "Concise & ATS-friendly",
            "text": concise_version(bullet),
            "tip": "One line, no filler — parses cleanly in applicant tracking systems.",
        },
    ]
    # De-duplicate identical variants (short bullets can converge).
    seen, unique = set(), []
    for v in variants:
        if v["text"] not in seen:
            seen.add(v["text"])
            unique.append(v)
    return unique


BULLET_MIN_CHARS = 10
BULLET_MAX_CHARS = 1000
