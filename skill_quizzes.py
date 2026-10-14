"""Skill quiz engine (Wave 3 feature #19).

Backed by the committed bank data/skill_quizzes.json: 320 questions
across 16 skills. Each question: id, skill, topic, difficulty
(easy/medium/hard), question, 4 options, answer index, explanation.

Answers/explanations never leave the server except through the graded
check endpoint. Scoring is fully deterministic.
"""

import json
import os
import random

BANK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "skill_quizzes.json")

DIFFICULTIES = ("easy", "medium", "hard")
MAX_QUESTIONS = 25

_bank = None
_by_id = None


def _load():
    global _bank, _by_id
    if _bank is None:
        try:
            with open(BANK_PATH, encoding="utf-8") as f:
                _bank = json.load(f)
        except OSError:
            _bank = []
        _by_id = {q["id"]: q for q in _bank if "id" in q}
    return _bank


def _by_id_map():
    _load()
    return _by_id


def get_question(qid):
    return _by_id_map().get(qid)


def quiz_skills():
    """Sorted [(skill_id, question_count)]."""
    counts = {}
    for q in _load():
        counts[q.get("skill")] = counts.get(q.get("skill"), 0) + 1
    return sorted(counts.items())


def skill_topics(skill):
    """Sorted [(topic, count)] for one skill."""
    counts = {}
    for q in _load():
        if q.get("skill") == skill:
            t = q.get("topic", "General")
            counts[t] = counts.get(t, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def public_question(q):
    """Client-safe question payload (no answer, no explanation)."""
    return {"id": q["id"], "skill": q.get("skill"), "topic": q.get("topic"),
            "difficulty": q.get("difficulty"), "question": q.get("question"),
            "options": list(q.get("options", []))}


def build_quiz(skill, n=10, difficulties=None, seed=None):
    """Pick n questions for a skill, optionally filtered by difficulty.

    Returns list of FULL question dicts (server-side). Use public_question
    before sending to the client.
    """
    pool = [q for q in _load() if q.get("skill") == skill]
    if difficulties:
        want = {d for d in difficulties if d in DIFFICULTIES}
        if want:
            pool = [q for q in pool if q.get("difficulty") in want]
    if not pool:
        return []
    rng = random.Random(seed) if seed is not None else random
    n = max(1, min(int(n or 10), MAX_QUESTIONS, len(pool)))
    # Stratify by difficulty when no filter: round-robin easy/medium/hard
    # so a mixed quiz covers the range.
    if not difficulties:
        by_diff = {d: [q for q in pool if q.get("difficulty") == d]
                   for d in DIFFICULTIES}
        picked, seen = [], set()
        order = ["easy", "medium", "hard"]
        i = 0
        while len(picked) < n and any(by_diff[d] for d in order):
            d = order[i % 3]
            if by_diff[d]:
                q = by_diff[d].pop(rng.randrange(len(by_diff[d])))
                if q["id"] not in seen:
                    seen.add(q["id"])
                    picked.append(q)
            i += 1
            if i > n * 6:  # safety
                break
        # top up from leftovers if stratification ran short
        rest = [q for q in pool if q["id"] not in seen]
        rng.shuffle(rest)
        picked += rest[: max(0, n - len(picked))]
        return picked[:n]
    return rng.sample(pool, n)


def check_answer(question, chosen_index):
    """Grade one answer. Returns {correct, correct_index, explanation}."""
    try:
        chosen = int(chosen_index)
    except (TypeError, ValueError):
        chosen = -1
    correct = chosen == question.get("answer")
    return {"correct": correct,
            "correct_index": question.get("answer"),
            "explanation": question.get("explanation", "")}


def grade_quiz(questions, answers):
    """Grade a full attempt.

    questions: list of full question dicts (in attempt order).
    answers: {question_id: chosen_index}.
    Returns (results, summary) where results is per-question detail and
    summary has score, percentage, per-difficulty and per-topic accuracy,
    plus weak-topic diagnosis.
    """
    results = []
    for q in questions:
        raw = answers.get(q["id"]) if isinstance(answers, dict) else None
        try:
            chosen = int(raw)
        except (TypeError, ValueError):
            chosen = None
        if chosen is not None and not 0 <= chosen <= 3:
            chosen = None
        chk = check_answer(q, chosen if chosen is not None else -1)
        results.append({
            "question_id": q["id"],
            "skill": q.get("skill"),
            "topic": q.get("topic", "General"),
            "difficulty": q.get("difficulty"),
            "question": q.get("question"),
            "options": list(q.get("options", [])),
            "chosen_index": chosen,
            "correct": chk["correct"],
            "correct_index": chk["correct_index"],
            "explanation": chk["explanation"],
        })
    total = len(results)
    right = sum(1 for r in results if r["correct"])
    by_diff, by_topic = {}, {}
    for r in results:
        d = by_diff.setdefault(r["difficulty"], [0, 0])
        d[r["correct"]] += 1
        t = by_topic.setdefault(r["topic"], [0, 0])
        t[r["correct"]] += 1
    diff_acc = {d: {"correct": v[1], "total": v[0] + v[1],
                    "pct": round(v[1] / (v[0] + v[1]) * 100) if (v[0] + v[1]) else 0}
                for d, v in by_diff.items()}
    topic_acc = {t: {"correct": v[1], "total": v[0] + v[1],
                     "pct": round(v[1] / (v[0] + v[1]) * 100) if (v[0] + v[1]) else 0}
                 for t, v in by_topic.items()}
    # Weak topics: >=2 questions attempted and accuracy < 60%.
    weak = sorted(
        [t for t, a in topic_acc.items() if a["total"] >= 2 and a["pct"] < 60],
        key=lambda t: topic_acc[t]["pct"])
    summary = {
        "score": right, "total": total,
        "pct": round(right / total * 100) if total else 0,
        "by_difficulty": diff_acc,
        "by_topic": topic_acc,
        "weak_topics": weak,
        "verdict": _verdict(right / total if total else 0),
    }
    return results, summary


def _verdict(ratio):
    if ratio >= 0.85:
        return "Excellent — interview-ready on this skill."
    if ratio >= 0.65:
        return "Solid — polish the weak topics below."
    if ratio >= 0.4:
        return "Developing — work through the roadmap stages for this skill."
    return "Foundations needed — start from the beginner stage of the roadmap."


def validate_start_payload(payload):
    """Validate {skill, num_questions, difficulties, timed, time_limit_sec}."""
    if not isinstance(payload, dict):
        return None, "Provide a JSON object."
    skill = (payload.get("skill") or "").strip()
    if skill not in {s for s, _ in quiz_skills()}:
        return None, "Choose a valid quiz skill."
    try:
        n = int(payload.get("num_questions", 10))
    except (TypeError, ValueError):
        return None, "num_questions must be a number."
    n = max(5, min(n, MAX_QUESTIONS))
    diffs = payload.get("difficulties") or []
    if not isinstance(diffs, list):
        return None, "difficulties must be a list."
    diffs = [d for d in diffs if d in DIFFICULTIES]
    timed = bool(payload.get("timed"))
    try:
        limit = int(payload.get("time_limit_sec", 0))
    except (TypeError, ValueError):
        limit = 0
    if timed:
        limit = max(60, min(limit or n * 60, 3600))
    else:
        limit = 0
    return {"skill": skill, "num_questions": n, "difficulties": diffs,
            "timed": timed, "time_limit_sec": limit}, None


def best_scores(attempt_rows):
    """Per-skill best percentage across a user's attempts."""
    best = {}
    for r in attempt_rows:
        try:
            pct = (r.summary_json or {}).get("pct", 0)
        except AttributeError:
            pct = 0
        s = r.skill
        if pct > best.get(s, {}).get("pct", -1):
            best[s] = {"pct": pct, "score": (r.summary_json or {}).get("score", 0),
                       "total": (r.summary_json or {}).get("total", 0),
                       "attempt_id": r.id,
                       "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None}
    return best
