"""Company-specific AI mock interviews with rubric scoring (Wave 2 feature #13).

Question bank: data/interview_questions.json (339 questions, tagged by
company/role/category/difficulty, each with ideal-answer key points).

Rubric (per answer, 0-100, deterministic and server-side):
  - correctness / approach ........ 40
  - communication ................. 25
  - depth ......................... 20
  - edge cases / completeness ..... 15

Gemini (wired in unified_app.py) polishes strengths/improvements when
available; the rule-based feedback below is the guaranteed fallback.
The numeric score never depends on the LLM.
"""

import json
import os
import random
import re

BANK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "interview_questions.json")

_bank = None


def _load_bank():
    global _bank
    if _bank is None:
        with open(BANK_PATH, encoding="utf-8") as f:
            _bank = json.load(f)
    return _bank


def _filler_entries():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "filler_words.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return []


_FILLERS = None


def _fillers():
    global _FILLERS
    if _FILLERS is None:
        _FILLERS = _filler_entries()
    return _FILLERS


def interview_options():
    """Distinct companies, roles, categories for the setup form."""
    bank = _load_bank()
    companies = sorted({c for q in bank for c in q["companies"]})
    roles = sorted({r for q in bank for r in q["roles"]})
    categories = sorted({q["category"] for q in bank})
    return {"companies": companies, "roles": roles, "categories": categories}


def _content_words(text):
    words = re.findall(r"[a-z][a-z0-9+\-#]*", (text or "").lower())
    stop = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
            "with", "is", "are", "was", "were", "be", "it", "its", "that",
            "this", "as", "by", "at", "from", "you", "your", "we", "our",
            "they", "their", "i", "my", "me", "so", "if",
            "not", "no", "do", "does", "did", "have", "has", "had", "will",
            "would", "can", "could", "should", "what", "when", "where",
            "which", "who", "how", "why"}
    # instructional verbs that appear in key-point guidance, not in answers
    instructional = {"describe", "list", "explain", "discuss", "tell", "give",
                     "show", "mention", "include", "provide", "outline",
                     "quantify", "name", "state", "share", "walk", "cover"}
    out = []
    for w in words:
        if w in stop or w in instructional or len(w) <= 2:
            continue
        out.append(_stem(w))
    return out


def _stem(w):
    """Very light stemmer so 'recovered' matches 'recovery', etc."""
    if len(w) > 5:
        for suf in ("ational", "tion", "ing", "edly", "ed", "ies", "es", "s", "ly"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                if suf == "ies":
                    return w[:-3] + "y"
                return w[:-len(suf)]
    return w


def _key_point_coverage(key_points, answer):
    """Mean partial credit per key point (50% overlap = full credit)."""
    ans_words = set(_content_words(answer))
    if not ans_words:
        return 0.0, []
    ratios = []
    hits = []
    for kp in key_points or []:
        kp_words = set(_content_words(kp))
        if not kp_words:
            continue
        overlap = len(kp_words & ans_words) / len(kp_words)
        ratios.append(min(1.0, overlap / 0.5))
        if overlap >= 0.35:
            hits.append(kp)
    mean_ratio = sum(ratios) / len(ratios) if ratios else 1.0
    return mean_ratio, hits


def _filler_penalty(answer):
    """Severity-weighted filler hits per 100 words, capped."""
    words = _content_words(answer)
    n = max(1, len(words))
    lowered = " " + (answer or "").lower() + " "
    penalty = 0
    hits = []
    for entry in _fillers():
        w = entry["word"].lower()
        # match whole words/phrases
        count = len(re.findall(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", lowered))
        if count:
            penalty += count * entry["severity"]
            hits.append(entry["word"])
    per_100 = penalty / n * 100
    return min(1.0, per_100 / 12.0), sorted(set(hits))


DEPTH_SIGNALS = ("trade-off", "tradeoff", "however", "alternatively", "because",
                 "measured", "metric", "improved", "reduced", "increased",
                 "specifically", "for example", "e.g.", "resulted", "led to")
EDGE_SIGNALS = ("edge case", "complexity", "o(n", "o(log", "scale", "failure",
                 "fallback", "alternative", "trade-off", "tradeoff", "test",
                 "validate", "assumption")


def _signal_ratio(answer, signals):
    lowered = (answer or "").lower()
    found = [s for s in signals if s in lowered]
    return min(1.0, len(found) / 3.0), found


def score_answer(question, answer):
    """Score one answer against the rubric. Returns a detailed dict."""
    answer = (answer or "").strip()
    words = _content_words(answer)
    if not words:
        return {
            "question_id": question.get("id"),
            "scores": {"correctness": 0.0, "communication": 0.0,
                       "depth": 0.0, "edge_cases": 0.0},
            "total": 0.0,
            "key_points_hit": [],
            "key_points_total": len(question.get("key_points") or []),
            "filler_hits": [],
            "word_count": 0,
            "depth_signals": [],
            "edge_signals": [],
        }
    key_points = question.get("key_points") or []

    # --- correctness / approach (40) ---
    coverage, hits = _key_point_coverage(key_points, answer)
    correctness = 40.0 * coverage
    if len(words) < 20:
        correctness *= 0.4  # too thin to judge
    correctness = round(min(40.0, correctness), 1)

    # --- communication (25) ---
    filler_ratio, filler_hits = _filler_penalty(answer)
    sentences = [s for s in re.split(r"[.!?]+", answer) if s.strip()]
    comm = 25.0 * (1.0 - 0.7 * filler_ratio)
    if sentences:
        avg_len = len(words) / len(sentences)
        if avg_len > 45:
            comm -= 5  # run-on sentences
        if len(sentences) == 1 and len(words) > 30:
            comm -= 4  # wall of text
    if len(words) < 20:
        comm *= 0.5
    comm = round(max(0.0, min(25.0, comm)), 1)

    # --- depth (20) ---
    depth_ratio, depth_found = _signal_ratio(answer, DEPTH_SIGNALS)
    has_number = bool(re.search(r"\d", answer))
    depth = 20.0 * depth_ratio + (3 if has_number else 0)
    if len(words) < 20:
        depth *= 0.5
    depth = round(min(20.0, depth), 1)

    # --- edge cases / completeness (15) ---
    edge_ratio, edge_found = _signal_ratio(answer, EDGE_SIGNALS)
    edge = round(15.0 * edge_ratio, 1)

    total = round(min(100.0, correctness + comm + depth + edge), 1)
    return {
        "question_id": question.get("id"),
        "scores": {
            "correctness": correctness,
            "communication": comm,
            "depth": depth,
            "edge_cases": edge,
        },
        "total": total,
        "key_points_hit": hits,
        "key_points_total": len(key_points),
        "filler_hits": filler_hits,
        "word_count": len(words),
        "depth_signals": depth_found,
        "edge_signals": edge_found,
    }


def generate_rule_based_feedback(scored, question):
    """Strengths + improvements from the rubric, no LLM needed."""
    s = scored["scores"]
    strengths, improvements = [], []
    if s["correctness"] >= 28:
        strengths.append("Strong coverage of the ideal answer's key points.")
    elif s["correctness"] >= 16:
        improvements.append(
            "Hit more of the key points: " +
            "; ".join((question.get("key_points") or [])[:3]))
    else:
        improvements.append(
            "Restructure around the key points: " +
            "; ".join((question.get("key_points") or [])[:3]))
    if s["communication"] >= 18:
        strengths.append("Clear, filler-light delivery.")
    else:
        improvements.append(
            "Tighten delivery: cut fillers (%s) and break run-on sentences."
            % (", ".join(scored["filler_hits"][:4]) or "none detected"))
    if s["depth"] >= 14:
        strengths.append("Good depth with specifics and reasoning.")
    else:
        improvements.append(
            "Add depth: quantify outcomes, name trade-offs, explain 'why'.")
    if s["edge_cases"] >= 10:
        strengths.append("Nice attention to edge cases and completeness.")
    else:
        improvements.append(
            "Discuss edge cases, complexity, and alternatives explicitly.")
    if scored["word_count"] < 20:
        improvements.append("Answer is too thin - aim for a structured 60-120 word response.")
    return {"strengths": strengths, "improvements": improvements}


def pick_questions(company, role, category, n=5, seed=None):
    """Select n questions matching the filters (randomized, seedable)."""
    bank = _load_bank()
    pool = [q for q in bank
            if company in q["companies"] and role in q["roles"]
            and q["category"] == category]
    if len(pool) < n:
        # fall back: relax company, keep role+category
        pool = [q for q in bank if role in q["roles"] and q["category"] == category]
    if len(pool) < n:
        # fall back: category only
        pool = [q for q in bank if q["category"] == category]
    rng = random.Random(seed)
    return rng.sample(pool, min(n, len(pool)))


def validate_interview_setup(payload):
    """Validate the setup form. Returns (cleaned, error)."""
    company = (payload.get("company") or "").strip()
    role = (payload.get("role") or "").strip()
    category = (payload.get("category") or "").strip()
    try:
        n = int(payload.get("num_questions") or 5)
    except (TypeError, ValueError):
        return None, "Number of questions must be an integer."
    if not (1 <= n <= 10):
        return None, "Number of questions must be between 1 and 10."
    opts = interview_options()
    if company not in opts["companies"]:
        return None, "Unknown company selected."
    if role not in opts["roles"]:
        return None, "Unknown role selected."
    if category not in opts["categories"]:
        return None, "Unknown category selected."
    return {"company": company, "role": role, "category": category, "n": n}, None


# ================= Feature 11 Ultimate Enhancements =================
# 11.1 Voice interview prep | 11.2 Company intel cards | 11.3 Redo loop

import re as _re5


def _clean5(text):
    return _re5.sub(r"<[^>]*>", "", text or "")


def voice_interview_prep(question, answer_text, seconds_taken):
    """Spoken-answer simulator: score content + delivery pacing.

    question: dict with question text. answer_text: what they said (transcribed).
    seconds_taken: how long they spoke. Returns {wpm, pacing verdict,
    content score (via score_answer), delivery tips}.
    Ideal speaking pace: 130-160 wpm.
    """
    if not isinstance(question, dict):
        raise ValueError("question must be a dict.")
    answer = _clean5(answer_text or "")
    words = len(answer.split())
    try:
        secs = float(seconds_taken)
    except (TypeError, ValueError):
        raise ValueError("seconds_taken must be a number.")
    if secs <= 0:
        raise ValueError("seconds_taken must be positive.")
    wpm = round(words / secs * 60, 1)

    if wpm < 100:
        pacing = "Too slow — you sound unsure. Aim for 130-160 wpm."
    elif wpm <= 170:
        pacing = "Good pace — clear and confident."
    else:
        pacing = "Too fast — slow down, interviewers can't follow."
    tips = []
    if words < 40:
        tips.append("Answer is thin — add an example or a number.")
    if _re5.search(r"\b(um+|uh+|like,)\b", answer, _re5.I):
        tips.append("Filler words detected — pause silently instead.")
    if secs > 180:
        tips.append("Over 3 minutes — tighten to 90 seconds for behavioral questions.")

    try:
        content = score_answer(question, answer)
        content_score = content.get("score", 0)
    except Exception:
        content_score = 0
    return {"wpm": wpm, "word_count": words, "seconds": round(secs, 1),
            "pacing": pacing, "content_score": content_score,
            "delivery_tips": tips,
            "verdict": ("Ready for voice screens." if wpm >= 100 and wpm <= 170
                        and content_score >= 60 and not tips
                        else "Keep practicing — see tips above.")}


def company_intel(company):
    """Interview intel card per company from the question bank.

    Returns {company, total_questions, categories: {cat: count},
    top_roles, sample_questions, focus_tip}.
    """
    company = _clean5(company or "").strip()
    if not company:
        raise ValueError("Company name is required.")
    bank = _load_bank()
    matched = [q for q in bank
               if any(company.lower() in c.lower() for c in q.get("companies", []))]
    if not matched:
        # Fallback: all-questions overview so the card is never empty.
        matched = bank
        note = f"No company-specific data for '{company}' — showing overall trends."
    else:
        note = f"Based on {len(matched)} banked questions for {company}."
    cats = {}
    roles = {}
    for q in matched:
        cats[q.get("category", "General")] = cats.get(q.get("category", "General"), 0) + 1
        for r in q.get("roles", []):
            roles[r] = roles.get(r, 0) + 1
    top_roles = sorted(roles, key=roles.get, reverse=True)[:5]
    samples = [{"question": q.get("question", "")[:120],
                "category": q.get("category", "")} for q in matched[:5]]
    top_cat = max(cats, key=cats.get) if cats else "General"
    return {"company": company, "total_questions": len(matched),
            "categories": cats, "top_roles": top_roles,
            "sample_questions": samples, "note": note,
            "focus_tip": f"{top_cat} questions dominate — master those first."}


def redo_tracker(attempts):
    """Track re-answers of the same question; measure improvement.

    attempts: list of {question_id, score, timestamp?} in chronological order.
    Returns per-question {attempts, first, latest, improvement, trend}.
    """
    if not isinstance(attempts, (list, tuple)):
        raise ValueError("attempts must be a list.")
    by_q = {}
    for a in attempts:
        if not isinstance(a, dict) or not a.get("question_id"):
            continue
        try:
            score = float(a.get("score") or 0)
        except (TypeError, ValueError):
            continue
        by_q.setdefault(str(a["question_id"]), []).append(max(0, min(100, score)))
    out = []
    for qid, scores in by_q.items():
        first, latest = scores[0], scores[-1]
        imp = round(latest - first, 1)
        trend = ("improving" if imp >= 5 else "declining" if imp <= -5 else "flat")
        out.append({"question_id": qid, "attempts": len(scores),
                    "first": first, "latest": latest,
                    "improvement": imp, "trend": trend})
    out.sort(key=lambda x: x["improvement"])
    return {"questions": out, "total_redos": sum(o["attempts"] - 1 for o in out),
            "guidance": "Redo any question until improvement plateaus — that is mastery."}
