"""STAR answer builder engine (Wave 2 feature #17).

Guided builder for Situation/Task/Action/Result interview answers:
competency picker, annotated example bank, rule-based per-section scoring
with specific rewrite suggestions. Gemini only polishes suggestion wording
(constructor pattern); numeric scores never depend on the LLM.
"""
import json
import os
import re

BANK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "star_examples.json")

COMPETENCIES = [
    ("leadership", "Leadership", "Taking charge and guiding others to a goal"),
    ("teamwork", "Teamwork", "Collaborating effectively with others"),
    ("conflict_resolution", "Conflict Resolution", "Resolving disagreements constructively"),
    ("failure_setback", "Failure & Setbacks", "Learning from mistakes and bouncing back"),
    ("ownership", "Ownership", "Taking responsibility beyond your assigned role"),
    ("adaptability", "Adaptability", "Thriving through change and uncertainty"),
    ("communication", "Communication", "Explaining clearly to any audience"),
    ("time_management", "Time Management", "Delivering under competing priorities"),
    ("problem_solving", "Problem Solving", "Diagnosing and fixing hard problems"),
    ("mentorship", "Mentorship", "Helping others grow"),
    ("customer_focus", "Customer Focus", "Putting the user's real needs first"),
]

COMPETENCY_IDS = [c[0] for c in COMPETENCIES]

SECTIONS = ("situation", "task", "action", "result")

SECTION_GUIDE = {
    "situation": {
        "tip": "Set the scene in 2-3 sentences: where, when, and what was at "
               "stake. Give just enough context for the rest to make sense.",
        "good": "Our college tech fest was three weeks away and the event app "
                "had no working build — the coordinator was considering "
                "cancelling the launch for 2,000 attendees.",
        "bad": "There was a difficult situation at my college once.",
        "why_bad": "No specifics: no place, time, scale, or stakes.",
    },
    "task": {
        "tip": "State YOUR specific responsibility in 1-2 sentences. Make it "
               "clear what you — not the team — were accountable for.",
        "good": "As the elected tech lead, I had to get a working app shipped "
                "in time for 2,000 expected attendees.",
        "bad": "We had to do something about it.",
        "why_bad": "Vague and team-focused; your personal task is invisible.",
    },
    "action": {
        "tip": "This is the heart of your answer (40-50% of it). Walk through "
               "the specific steps YOU took, in order. Use 'I', not 'we'.",
        "good": "I split the work into one-day deliverables, ran a 15-minute "
                "standup every evening, unblocked the payment integration myself "
                "over a weekend, and paired juniors with seniors.",
        "bad": "We worked hard and eventually finished it.",
        "why_bad": "No concrete steps, hides behind 'we', no initiative shown.",
    },
    "result": {
        "tip": "Close with the outcome in 1-2 sentences — quantified if at "
               "all possible — plus what you learned.",
        "good": "We shipped two days early; the app handled 1,800 "
                "registrations with zero downtime.",
        "bad": "It went well and everyone was happy.",
        "why_bad": "Unverifiable and unquantified; interviewers can't assess impact.",
    },
}

ACTION_VERBS = {
    "led", "built", "designed", "launched", "shipped", "created", "developed",
    "implemented", "drove", "owned", "initiated", "spearheaded", "delivered",
    "improved", "reduced", "increased", "automated", "fixed", "resolved",
    "mentored", "coached", "persuaded", "negotiated", "analyzed", "diagnosed",
    "proposed", "organized", "coordinated", "streamlined", "revamped",
    "pioneered", "championed", "orchestrated", "accelerated", "transformed",
}

_bank = None
_by_comp = None


def _load():
    global _bank, _by_comp
    if _bank is None:
        with open(BANK_PATH, encoding="utf-8") as f:
            _bank = json.load(f)
        _by_comp = {}
        for e in _bank:
            _by_comp.setdefault(e["competency"], []).append(e)
    return _bank


def all_examples():
    return _load()


def examples_for(competency):
    _load()
    return _by_comp.get(competency, [])


def get_example(example_id):
    for e in _load():
        if e["id"] == example_id:
            return e
    return None


def validate_draft(payload):
    """Return (cleaned, error). cleaned: {competency, sections{4}}."""
    if not isinstance(payload, dict):
        return None, "Invalid request."
    comp = str(payload.get("competency") or "").strip().lower()
    if comp not in COMPETENCY_IDS:
        return None, "Unknown competency."
    sections = {}
    for s in SECTIONS:
        text = payload.get(s) or ""
        text = str(text).strip()
        if len(text) > 4000:
            return None, f"The {s} section is too long (max 4000 characters)."
        sections[s] = text
    if not any(sections.values()):
        return None, "Write at least one STAR section first."
    return {"competency": comp, "sections": sections}, None


def _has_metrics(text):
    return bool(re.search(r"\d+\s*(%|percent|x\b|rs\.?|inr|lakh|crore|days?|weeks?|months?|hours?|users?|customers?)", text, re.I))


def _action_verb_count(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    return len(words & ACTION_VERBS)


def score_section(section, text):
    """Deterministic 0-25 score + specific suggestions for one section."""
    suggestions = []
    if not text.strip():
        return 0, ["This section is empty — even two sentences will help."]
    n = len(text)
    words = len(text.split())
    score = 12  # base for non-empty

    # length appropriateness (per-section sweet spots)
    if section == "action":
        ideal = (80, 600)
    else:
        ideal = (40, 350)
    if ideal[0] <= n <= ideal[1]:
        score += 5
    elif n < ideal[0]:
        suggestions.append(
            f"Quite short ({words} words). Add one concrete detail — a "
            f"number, a name, or a specific step you took.")
    else:
        score -= 3
        suggestions.append(
            "A bit long — trim to the essentials so the interviewer stays "
            "with you.")

    # first-person ownership (action/task especially)
    if section in ("action", "task"):
        i_count = len(re.findall(r"\bi\b", text.lower()))
        we_count = len(re.findall(r"\bwe\b", text.lower()))
        if i_count >= 2:
            score += 3
        elif we_count > i_count:
            suggestions.append(
                "This section leans on 'we' — interviewers score YOU. "
                "Recast key steps with 'I'.")
            score -= 2

    # action verbs
    verbs = _action_verb_count(text)
    if verbs >= 3:
        score += 3
    elif verbs == 0 and section == "action":
        suggestions.append(
            "No strong action verbs detected. Start sentences with verbs "
            "like built, led, shipped, or resolved.")
        score -= 2

    # quantification (result especially)
    if section == "result":
        if _has_metrics(text):
            score += 4
        else:
            suggestions.append(
                "No numbers in your result. Add one: time saved, % improved, "
                "people reached, money saved.")
            score -= 2
    elif _has_metrics(text):
        score += 2

    # vague filler check
    vague = re.findall(
        r"\b(very|really|things|stuff|a lot|hard working|did my best)\b",
        text.lower())
    if vague:
        suggestions.append(
            f"Replace vague phrasing ({', '.join(sorted(set(vague))[:3])}) "
            f"with specifics.")
        score -= 2

    # learning reflection bonus for result
    if section == "result" and re.search(
            r"\b(learned|lesson|next time|takeaway)\b", text.lower()):
        score += 2

    score = max(0, min(25, score))
    if score >= 20 and not suggestions:
        suggestions.append("Strong section — keep this level of specificity.")
    return score, suggestions


def score_draft(sections):
    """Score all four sections. Returns {sections: {s: {score, suggestions}},
    overall: 0-100}."""
    out = {}
    total = 0
    for s in SECTIONS:
        sc, sug = score_section(s, sections.get(s) or "")
        out[s] = {"score": sc, "max": 25, "suggestions": sug}
        total += sc
    return {"sections": out, "overall": total}


def generate_rule_based_rewrite_tip(section, text):
    """One concrete rewrite direction per section (fallback)."""
    tips = {
        "situation": "Open with when/where/scale: 'In [month/year], as [role], "
                     "we faced [concrete problem affecting N people].'",
        "task": "Name your personal accountability: 'I was responsible for "
                "[specific deliverable] by [deadline].'",
        "action": "List 3-4 steps in order, each starting with a strong verb "
                 "and naming a concrete move you made.",
        "result": "End with a number and a lesson: '[metric] improved by X; "
                 "I learned [lesson].'",
    }
    return tips[section]
