"""Timed aptitude & reasoning test engine (Wave 2 feature #16).

Backed by the committed bank data/aptitude_questions.json (338 questions
across quantitative / logical / verbal). Scoring is fully server-side;
the client timer is display-only — the server validates the time window
from its own start timestamp.
"""
import json
import os
import random

BANK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "aptitude_questions.json")

CATEGORIES = ("quantitative", "logical", "verbal")
DIFFICULTIES = ("Easy", "Medium", "Hard")

# Grace period (seconds) after the nominal limit before a submission is
# treated as expired — absorbs network latency, not extra thinking time.
SUBMIT_GRACE_SEC = 60

_bank = None
_by_id = None


def _load():
    global _bank, _by_id
    if _bank is None:
        with open(BANK_PATH, encoding="utf-8") as f:
            _bank = json.load(f)
        _by_id = {q["id"]: q for q in _bank}
    return _bank


def all_questions():
    return _load()


def get_question(qid):
    _load()
    return _by_id.get(qid)


def categories():
    """[(category, count)] for the setup page."""
    counts = {}
    for q in _load():
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    return [(c, counts.get(c, 0)) for c in CATEGORIES]


def subcategories(category):
    counts = {}
    for q in _load():
        if q["category"] == category:
            s = q["subcategory"]
            counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items())


def public_question(q):
    """Client-safe view: statement + options, no answer/explanation."""
    return {
        "id": q["id"],
        "category": q["category"],
        "subcategory": q["subcategory"],
        "difficulty": q["difficulty"],
        "statement": q["statement"],
        "options": q["options"],
    }


def pick_questions(category=None, n=10, seed=None):
    """Pick n questions (shuffled). category=None/'mixed' draws evenly."""
    pool = _load()
    if category and category != "mixed":
        pool = [q for q in pool if q["category"] == category]
    rnd = random.Random(seed)
    picked = rnd.sample(pool, min(n, len(pool)))
    rnd.shuffle(picked)
    return [public_question(q) for q in picked]


def validate_test_setup(payload):
    """Return (cleaned, error). cleaned: {category, n, time_limit}."""
    if not isinstance(payload, dict):
        return None, "Invalid request."
    category = str(payload.get("category") or "mixed").strip().lower()
    if category not in CATEGORIES and category != "mixed":
        return None, "Unknown category."
    try:
        n = int(payload.get("num_questions") or 0)
    except (TypeError, ValueError):
        return None, "Question count must be a number."
    if not 5 <= n <= 50:
        return None, "Question count must be between 5 and 50."
    try:
        limit = int(payload.get("time_limit") or 0)
    except (TypeError, ValueError):
        return None, "Time limit must be a number."
    if not 60 <= limit <= 3600:
        return None, "Time limit must be between 1 and 60 minutes."
    return {"category": category, "n": n, "time_limit": limit}, None


def score_attempt(question_ids, answers):
    """Server-side scoring. answers: {qid: option_index}.

    Returns (results, summary). results: per-question dicts with
    correctness + correct answer + explanation (safe to show after submit).
    """
    results = []
    correct = 0
    by_cat = {}
    by_diff = {}
    for qid in question_ids:
        q = get_question(qid)
        if q is None:
            continue
        chosen = answers.get(qid)
        try:
            chosen = int(chosen)
        except (TypeError, ValueError):
            chosen = None
        ok = chosen == q["answer"]
        if ok:
            correct += 1
        results.append({
            "id": qid,
            "category": q["category"],
            "subcategory": q["subcategory"],
            "difficulty": q["difficulty"],
            "statement": q["statement"],
            "options": q["options"],
            "chosen": chosen,
            "correct_index": q["answer"],
            "correct": ok,
            "explanation": q["explanation"],
        })
        for key, bucket in (("category", by_cat), ("difficulty", by_diff)):
            k = q[key]
            b = bucket.setdefault(k, {"total": 0, "correct": 0})
            b["total"] += 1
            if ok:
                b["correct"] += 1
    total = len(results)
    summary = {
        "total": total,
        "correct": correct,
        "score_pct": round(correct / total * 100, 1) if total else 0.0,
        "by_category": {k: {"total": v["total"], "correct": v["correct"],
                            "pct": round(v["correct"] / v["total"] * 100, 1)}
                        for k, v in by_cat.items()},
        "by_difficulty": {k: {"total": v["total"], "correct": v["correct"],
                              "pct": round(v["correct"] / v["total"] * 100, 1)}
                          for k, v in by_diff.items()},
    }
    weak = [k for k, v in summary["by_category"].items() if v["pct"] < 60]
    summary["weak_areas"] = weak
    return results, summary
