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
    text = strengthen_verbs(_strip_html(bullet))
    for pattern, replacement in INLINE_FIXES:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\b(very|really|quite|basically|actually|just)\b", "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip().rstrip(".")
    words = text.split()
    if len(words) > 28:
        text = " ".join(words[:28])
    return _capitalize_first(text) + "."


def _strip_html(text):
    """Remove HTML tags — these are plain-text outputs, tags are never legitimate."""
    return re.sub(r"<[^>]*>", "", text or "")


def improve_bullet(bullet_text):
    """Return 3 rule-based rewrite variants for a resume bullet.

    Each variant is a dict {"label": ..., "text": ..., "tip": ...}.
    Raises ValueError on invalid input.
    """
    bullet = _strip_html((bullet_text or "")).strip()
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


# ================= Feature 2 Ultimate Enhancements =================
# 2.1 STAR auto-converter | 2.2 Verb power ranking | 2.3 Metric finder

# Context clues that hint at each STAR part.
_STAR_CLUES = {
    "situation": [r"\b(when|while|during|amid|facing)\b", r"\b(team|project|company|client)\b"],
    "task": [r"\b(needed to|tasked|goal was|responsible)\b", r"\b(improve|fix|build|launch|reduce)\b"],
    "action": [r"\b(i |we )?(built|designed|implemented|led|created|developed|migrated)\b"],
    "result": [r"\b\d+\s*%", r"\b(result|outcome|impact|achieved|increased|decreased)\b"],
}

# Metric prompts by bullet topic.
_METRIC_PROMPTS = [
    (re.compile(r"\b(api|backend|server|database|query)\b", re.I),
     ["What was the latency before/after?", "How many requests per second/day?",
      "How much data volume did it handle?"]),
    (re.compile(r"\b(team|led|managed|mentored)\b", re.I),
     ["How many people on the team?", "Over what time period?",
      "What did the team deliver?"]),
    (re.compile(r"\b(frontend|ui|ux|app|website)\b", re.I),
     ["How many users?", "Did engagement/conversion change? By how much?",
      "Page load time improvement?"]),
    (re.compile(r"\b(test|qa|bug|ci|deploy)\b", re.I),
     ["Test coverage before/after?", "How many bugs caught?",
      "Deploy frequency change?"]),
    (re.compile(r"\b(cost|budget|infra|cloud)\b", re.I),
     ["How much money saved?", "Percentage cost reduction?",
      "Resource usage before/after?"]),
]


def star_convert(bullet_text):
    """Convert a flat bullet into Situation/Task/Action/Result parts.

    Heuristically splits the bullet into STAR components and flags which
    parts are thin or missing, with prompts to fill them. Never raises
    on hostile input (ValueError only for empty/too-short, like improve_bullet).
    Returns {situation, task, action, result, gaps, star_bullet}.
    """
    bullet = _strip_html((bullet_text or "")).strip()
    if not bullet:
        raise ValueError("Please enter a bullet to rewrite.")
    if len(bullet) < BULLET_MIN_CHARS:
        raise ValueError(
            f"That bullet looks too short (minimum {BULLET_MIN_CHARS} characters).")

    # Split on sentence/clause boundaries for analysis.
    clauses = [c.strip() for c in re.split(r"[.;]|(?:\s+-\s+)", bullet) if c.strip()]
    if not clauses:
        clauses = [bullet]

    parts = {"situation": "", "task": "", "action": "", "result": ""}
    used = set()
    order = ["situation", "task", "action", "result"]
    for part in order:
        best, best_score = "", 0
        for i, clause in enumerate(clauses):
            if i in used:
                continue
            score = sum(len(re.findall(p, clause, re.I))
                        for p in _STAR_CLUES[part])
            # Positional prior: situation early, result late.
            pos_bonus = 0
            if part == "situation" and i == 0:
                pos_bonus = 1
            elif part == "result" and i == len(clauses) - 1:
                pos_bonus = 1
            elif part == "action" and 0 < i < len(clauses) - 1:
                pos_bonus = 0.5
            if score + pos_bonus > best_score:
                best, best_score = clause, score + pos_bonus
        if best:
            parts[part] = best
            used.add(clauses.index(best))

    # Anything unassigned goes to action (the core of a bullet).
    for i, clause in enumerate(clauses):
        if i not in used:
            parts["action"] = (parts["action"] + " " + clause).strip()
            used.add(i)

    # Rescue: if task is empty but another part's text contains a task
    # clause ("needed to X", "goal was Y"), carve it out.
    if not parts["task"]:
        m = re.search(r"\bi needed to ([^.]+)", bullet, re.I)
        if not m:
            m = re.search(r"\b(goal was|tasked with|aim was)\s+([^.]+)", bullet, re.I)
        if m:
            task_text = (m.group(1) if m.lastindex == 1 else m.group(2)).strip()
            if task_text:
                parts["task"] = _capitalize_first(task_text.rstrip(". ")) + "."

    gaps = []
    prompts = {
        "situation": "Add context: what was the situation? (team size, project, challenge)",
        "task": "Add your goal: what were you trying to achieve?",
        "action": "Add what YOU specifically did (verbs, tools, decisions).",
        "result": "Add the outcome with a number: %, users, time saved, revenue.",
    }
    for part in order:
        if not parts[part]:
            gaps.append({"part": part, "prompt": prompts[part]})

    star_bullet = " ".join(
        f"[{p[0].upper()}: {parts[p]}]" for p in order if parts[p])
    return {"situation": parts["situation"], "task": parts["task"],
            "action": parts["action"], "result": parts["result"],
            "gaps": gaps, "star_bullet": star_bullet,
            "completeness": f"{4 - len(gaps)}/4 parts present"}


def verb_power_report(bullets):
    """Rank verbs across a whole resume's bullets.

    Returns {weak_hits: [{bullet_index, weak_verb, suggestion}], diversity_score,
    verdict}. diversity_score = unique strong verbs / total bullets (0-100).
    Accepts a list of bullet strings; never raises on hostile input.
    """
    if not isinstance(bullets, (list, tuple)):
        raise ValueError("bullets must be a list of strings.")
    weak_hits = []
    strong_verbs = set()
    total = 0
    for idx, b in enumerate(bullets):
        if not isinstance(b, str):
            continue
        total += 1
        clean = _strip_html(b).strip()
        if not clean:
            continue
        first_word = clean.split()[0].lower() if clean.split() else ""
        # Check weak patterns.
        for pattern, suggestion in WEAK_VERB_MAP:
            if pattern.search(clean):
                weak_hits.append({"bullet_index": idx, "weak_verb": pattern.pattern,
                                  "suggestion": suggestion,
                                  "bullet": clean[:80]})
                break
        else:
            # Strong if it starts with a punchy verb (capitalized action word).
            m = re.match(r"^([A-Z][a-z]+)\b", clean)
            if m:
                strong_verbs.add(m.group(1).lower())
    diversity = round(len(strong_verbs) / max(total, 1) * 100, 1)
    verdict = ("Excellent verb diversity" if diversity >= 70 else
               "Good — a few repeats" if diversity >= 45 else
               "Weak — many bullets start the same way" if total else
               "No bullets to analyze")
    return {"weak_hits": weak_hits, "diversity_score": diversity,
            "unique_strong_verbs": sorted(strong_verbs),
            "total_bullets": total, "verdict": verdict}


def metric_finder(bullet_text):
    """Suggest plausible metrics to quantify a bullet.

    Detects the bullet's topic and returns targeted questions the user can
    answer to add numbers. Returns {topic, questions, has_metric}.
    """
    bullet = _strip_html((bullet_text or "")).strip()
    if not bullet:
        raise ValueError("Please enter a bullet to analyze.")
    has_metric = bool(QUANT_HINTS.search(bullet))
    questions = []
    topic = "general"
    for pattern, qs in _METRIC_PROMPTS:
        if pattern.search(bullet):
            topic = pattern.pattern.strip("\\b()")
            questions.extend(qs)
            break
    if not questions:
        questions = ["Can you add a number — users, %, time, or money?",
                     "What changed because of this work?",
                     "How big was the scale (team, data, traffic)?"]
    return {"topic": topic, "questions": questions[:3],
            "has_metric": has_metric,
            "verdict": ("Already quantified — nice." if has_metric
                        else "No metrics found — answer one question above to strengthen it.")}
