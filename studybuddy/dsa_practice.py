"""DSA practice engine: filtering, progressive hints, weak-topic diagnosis
(Wave 2 feature #15). Backed by the committed bank data/dsa_problems.json
(120 problems across 43 topics)."""

import json
import os

BANK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "dsa_problems.json")

_bank = None
_by_id = None


def _load():
    global _bank, _by_id
    if _bank is None:
        with open(BANK_PATH, encoding="utf-8") as f:
            _bank = json.load(f)
        _by_id = {p["id"]: p for p in _bank}
    return _bank


def all_problems():
    return _load()


def get_problem(problem_id):
    return _load_by_id().get(problem_id)


def _load_by_id():
    _load()
    return _by_id


def topics():
    """Sorted [(topic, count)] across the bank."""
    counts = {}
    for p in _load():
        for t in p.get("topics", []):
            counts[t] = counts.get(t, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def difficulties():
    counts = {}
    for p in _load():
        d = p.get("difficulty", "Medium")
        counts[d] = counts.get(d, 0) + 1
    order = ["Easy", "Medium", "Hard"]
    return [(d, counts.get(d, 0)) for d in order]


def filter_problems(topic=None, difficulty=None):
    """Return summary dicts for problems matching the filters."""
    out = []
    for p in _load():
        if topic and topic not in p.get("topics", []):
            continue
        if difficulty and p.get("difficulty") != difficulty:
            continue
        out.append({"id": p["id"], "title": p["title"],
                    "difficulty": p.get("difficulty"),
                    "topics": p.get("topics", [])})
    return out


def public_problem(problem_id, hints_revealed=0):
    """Problem payload for the client. Hints beyond `hints_revealed` are
    withheld; the approach outline is withheld until explicitly requested."""
    p = get_problem(problem_id)
    if not p:
        return None
    hints = p.get("hints", []) or []
    return {
        "id": p["id"],
        "title": p["title"],
        "statement": p.get("statement"),
        "difficulty": p.get("difficulty"),
        "topics": p.get("topics", []),
        "complexity": p.get("complexity"),
        "pitfalls": p.get("pitfalls", []),
        "leetcode_url": p.get("leetcode_url"),
        "total_hints": len(hints),
        "hints_revealed": min(hints_revealed, len(hints)),
        "hints": hints[:hints_revealed],
        "approach": None,  # revealed only via explicit request
    }


def reveal_hint(problem_id, hints_revealed):
    """Next progressive hint, or None when exhausted."""
    p = get_problem(problem_id)
    if not p:
        return None, 0
    hints = p.get("hints", []) or []
    if hints_revealed < len(hints):
        return hints[hints_revealed], hints_revealed + 1
    return None, hints_revealed


def reveal_approach(problem_id):
    """Full approach outline — only when the user explicitly asks."""
    p = get_problem(problem_id)
    return p.get("approach") if p else None


VALID_STATUSES = {"attempted", "solved", "stuck"}


def validate_status_payload(payload):
    status = (payload.get("status") or "").strip().lower()
    if status not in VALID_STATUSES:
        return None, "Status must be one of: attempted, solved, stuck."
    code = payload.get("code") or ""
    if len(code) > 20000:
        return None, "Code is too long (max 20000 characters)."
    return {"status": status, "code": code}, None


def weak_topic_diagnosis(progress_rows):
    """Per-topic solve/stuck rates + recommended next topics/problems.

    progress_rows: iterable of dicts {problem_id, status, hints_used}.
    Returns {"topics": [...], "recommendations": [...], "overall": {...}}.
    """
    problems = _load_by_id()
    by_topic = {}
    solved = stuck = attempted = 0
    solved_ids = set()

    for row in progress_rows:
        p = problems.get(row["problem_id"])
        if not p:
            continue
        st = row.get("status")
        if st == "solved":
            solved += 1
            solved_ids.add(row["problem_id"])
        elif st == "stuck":
            stuck += 1
        else:
            attempted += 1
        for t in p.get("topics", []):
            agg = by_topic.setdefault(t, {"attempted": 0, "solved": 0, "stuck": 0})
            agg["attempted"] += 1
            if st == "solved":
                agg["solved"] += 1
            elif st == "stuck":
                agg["stuck"] += 1

    topic_rows = []
    for t, agg in by_topic.items():
        n = agg["attempted"]
        solve_rate = round(agg["solved"] / n * 100, 1) if n else 0.0
        stuck_rate = round(agg["stuck"] / n * 100, 1) if n else 0.0
        topic_rows.append({
            "topic": t, "attempted": n, "solved": agg["solved"],
            "stuck": agg["stuck"], "solve_rate": solve_rate,
            "stuck_rate": stuck_rate,
        })
    # weakest first: lowest solve rate, then highest stuck rate
    topic_rows.sort(key=lambda r: (r["solve_rate"], -r["stuck_rate"]))

    recommendations = []
    # 1) revisit weakest topics with unsolved problems in them
    for tr in topic_rows[:4]:
        if tr["solve_rate"] >= 80 and tr["stuck_rate"] == 0:
            continue
        cands = [p for p in _load()
                 if tr["topic"] in p.get("topics", []) and p["id"] not in solved_ids]
        # prefer easier problems first for weak topics
        order = {"Easy": 0, "Medium": 1, "Hard": 2}
        cands.sort(key=lambda p: order.get(p.get("difficulty"), 1))
        for p in cands[:2]:
            recommendations.append({
                "problem_id": p["id"], "title": p["title"],
                "difficulty": p.get("difficulty"),
                "reason": f"Weak topic: {tr['topic']} "
                          f"(solve rate {tr['solve_rate']}%, stuck {tr['stuck']}x).",
            })
        if len(recommendations) >= 6:
            break
    # 2) if nothing weak, push to harder problems in practiced topics
    if not recommendations and topic_rows:
        strong = [tr for tr in topic_rows if tr["solve_rate"] >= 80][:2]
        for tr in strong:
            cands = [p for p in _load()
                     if tr["topic"] in p.get("topics", [])
                     and p.get("difficulty") == "Hard"
                     and p["id"] not in solved_ids][:2]
            for p in cands:
                recommendations.append({
                    "problem_id": p["id"], "title": p["title"],
                    "difficulty": "Hard",
                    "reason": f"You're strong at {tr['topic']} — level up with a Hard problem.",
                })

    total = solved + stuck + attempted
    return {
        "topics": topic_rows,
        "recommendations": recommendations[:8],
        "overall": {
            "attempted": total, "solved": solved, "stuck": stuck,
            "solve_rate": round(solved / total * 100, 1) if total else 0.0,
        },
    }


# ================= Feature 12 Ultimate Enhancements =================
# 12.1 Pattern mastery map | 12.2 Mock OA simulator | 12.3 Spaced repetition

import re as _re6
from datetime import UTC, datetime, timedelta


def _clean6(text):
    return _re6.sub(r"<[^>]*>", "", text or "")


# The 14 canonical DSA patterns mapped from the bank's topic vocabulary.
_PATTERNS = [
    ("Sliding Window", ["sliding-window", "subarray"]),
    ("Two Pointers", ["two-pointers", "pointers", "cyclic-sort"]),
    ("Binary Search", ["searching", "binary", "quickselect"]),
    ("DFS / BFS", ["dfs", "bfs", "graphs", "trees", "topological-sort", "cycles"]),
    ("Dynamic Programming", ["dynamic programming", "dp", "knapsack", "interval-dp"]),
    ("Greedy", ["greedy", "intervals"]),
    ("Heap", ["heaps", "priority queue"]),
    ("Stack / Queue", ["stacks", "queues", "monotonic-stack", "deque"]),
    ("Hashing", ["hash maps", "hashing", "hash set", "bucket-sort", "prefix-sums"]),
    ("Linked List", ["linked lists", "reversal"]),
    ("Recursion / Backtracking", ["recursion", "backtracking"]),
    ("Sorting", ["sorting"]),
    ("Bit Manipulation", ["bit manipulation", "binary-exponentiation"]),
    ("Graphs Advanced", ["dijkstra", "union-find", "matrix", "bst"]),
]


def pattern_mastery(solved_ids, attempted_ids=None):
    """Mastery % per DSA pattern from solved problem IDs.

    solved_ids: list of problem ids (str or int) the user solved.
    Returns {patterns: [{pattern, solved, total, mastery_pct}], overall}.
    """
    if not isinstance(solved_ids, (list, tuple)):
        raise ValueError("solved_ids must be a list.")
    solved = set()
    for pid in solved_ids:
        if isinstance(pid, str) and pid.strip():
            solved.add(pid.strip())
        elif isinstance(pid, int):
            solved.add(str(pid))
    by_id = {str(p["id"]): p for p in _load()}
    out = []
    total_solved = total_bank = 0
    for pattern, keywords in _PATTERNS:
        pids = [pid for pid, p in by_id.items()
                if any(kw in " ".join(p.get("topics", [])).lower() for kw in keywords)]
        n_total = len(pids)
        n_solved = sum(1 for pid in pids if pid in solved)
        total_solved += n_solved
        total_bank += n_total
        mastery = round(n_solved / n_total * 100, 1) if n_total else 0.0
        out.append({"pattern": pattern, "solved": n_solved, "total": n_total,
                    "mastery_pct": mastery,
                    "status": ("mastered" if mastery >= 80 else
                               "progressing" if mastery >= 40 else "weak")})
    out.sort(key=lambda x: x["mastery_pct"])
    overall = round(total_solved / total_bank * 100, 1) if total_bank else 0.0
    weakest = out[0]["pattern"] if out else None
    return {"patterns": out, "overall_mastery_pct": overall,
            "weakest_pattern": weakest,
            "guidance": (f"Attack '{weakest}' next — it is your bottleneck."
                         if weakest else "No pattern data.")}


def mock_oa(num_questions=2, minutes=60, seed=None):
    """Simulate a real Online Assessment: N questions, time limit, mixed difficulty.

    Returns {questions: [public dicts], minutes, total, instructions}.
    Picks 1 medium + rest mixed for realism.
    """
    try:
        num_questions = int(num_questions)
    except (TypeError, ValueError):
        num_questions = 2
    num_questions = max(1, min(4, num_questions))
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(10, min(180, minutes))

    import random
    rng = random.Random(seed)
    bank = _load()
    mediums = [p for p in bank if p.get("difficulty") == "Medium"]
    rest = [p for p in bank if p.get("difficulty") != "Medium"]
    picks = []
    if mediums:
        picks.append(rng.choice(mediums))
    pool = [p for p in rest if p not in picks]
    rng.shuffle(pool)
    picks += pool[:num_questions - len(picks)]
    rng.shuffle(picks)
    questions = [{"id": p["id"], "title": p["title"],
                  "difficulty": p.get("difficulty"),
                  "topics": p.get("topics", [])} for p in picks]
    return {"questions": questions, "minutes": minutes,
            "total": len(questions),
            "instructions": (
                f"You have {minutes} minutes for {len(questions)} questions. "
                "No hints, no solutions — like the real thing. "
                "Score yourself after: 1 point per solved, 0.5 per partial.")}


def spaced_repetition_queue(mistakes, now=None):
    """Wrong problems resurface after 3/7/14 days.

    mistakes: list of {problem_id, wrong_at (iso str), streak (consecutive
    wrong count)}. Returns {due: [...], upcoming: [...]} sorted by urgency.
    """
    if not isinstance(mistakes, (list, tuple)):
        raise ValueError("mistakes must be a list.")
    now = now or datetime.now(UTC)
    intervals = {1: 3, 2: 7}
    due, upcoming = [], []
    for m in mistakes:
        if not isinstance(m, dict) or m.get("problem_id") is None:
            continue
        pid = m["problem_id"]
        if isinstance(pid, str) and not pid.strip():
            continue
        if not isinstance(pid, (str, int)):
            continue
        try:
            streak = max(1, int(m.get("streak") or 1))
        except (TypeError, ValueError):
            streak = 1
        days = intervals.get(streak, 14)
        try:
            wrong_at = datetime.fromisoformat(str(m.get("wrong_at") or "").replace("Z", "+00:00"))
            if wrong_at.tzinfo is None:
                wrong_at = wrong_at.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            wrong_at = now
        due_at = wrong_at + timedelta(days=days)
        entry = {"problem_id": pid, "streak": streak,
                 "interval_days": days, "due_at": due_at.isoformat(),
                 "overdue_days": max(0, (now - due_at).days)}
        (due if now >= due_at else upcoming).append(entry)
    due.sort(key=lambda x: -x["overdue_days"])
    upcoming.sort(key=lambda x: x["due_at"])
    return {"due": due, "upcoming": upcoming,
            "due_count": len(due),
            "guidance": (f"{len(due)} problem(s) due for review — spaced repetition "
                         "is how patterns stick." if due else
                         "Nothing due. Keep solving — mistakes will queue here.")}
