"""Peer Mocks ultimate: skill-matched pairing, structured rubrics, recurring slots.

Feature 28 x3:
  28.1 match_partners — pair by complementary strengths, not random.
  28.2 mock_rubric — both sides score on the same sheet; compare.
  28.3 recurring_slot — weekly standing mock appointments.
"""
import re
from datetime import datetime, timezone


def _clean(text):
    return re.sub(r"<[^>]*>", "", text or "")


def match_partners(users):
    """Pair users by complementary strengths.

    users: list of {user_id, name, strengths (list), weaknesses (list)}.
    Returns {pairs: [{a, b, why}], unpaired: [...]}. Greedy: each pair maximizes
    (a.weakness ∩ b.strength) + (b.weakness ∩ a.strength).
    """
    if not isinstance(users, (list, tuple)):
        raise ValueError("users must be a list.")
    clean = []
    for u in users:
        if not isinstance(u, dict) or u.get("user_id") is None:
            continue
        s = {str(x).lower() for x in (u.get("strengths") or []) if isinstance(x, str)}
        w = {str(x).lower() for x in (u.get("weaknesses") or []) if isinstance(x, str)}
        clean.append({"user_id": u["user_id"],
                      "name": _clean(u.get("name") or "Anonymous")[:40],
                      "strengths": s, "weaknesses": w})
    pairs = []
    remaining = list(clean)
    while len(remaining) >= 2:
        best = None  # (score, i, j, reasons)
        for i in range(len(remaining)):
            for j in range(i + 1, len(remaining)):
                a, b = remaining[i], remaining[j]
                a_helps_b = b["weaknesses"] & a["strengths"]
                b_helps_a = a["weaknesses"] & b["strengths"]
                score = len(a_helps_b) + len(b_helps_a)
                reasons = []
                if a_helps_b:
                    reasons.append(f"{a['name']} strengthens {b['name']} in {', '.join(sorted(a_helps_b)[:2])}")
                if b_helps_a:
                    reasons.append(f"{b['name']} strengthens {a['name']} in {', '.join(sorted(b_helps_a)[:2])}")
                if best is None or score > best[0]:
                    best = (score, i, j, reasons)
        _, i, j, reasons = best
        a = remaining.pop(j)
        b = remaining.pop(i)
        pairs.append({"a": {"user_id": a["user_id"], "name": a["name"]},
                      "b": {"user_id": b["user_id"], "name": b["name"]},
                      "complementarity": best[0],
                      "why": reasons or ["Random pairing — add strengths for better matches."]})
    return {"pairs": pairs,
            "unpaired": [{"user_id": u["user_id"], "name": u["name"]} for u in remaining],
            "guidance": "Meet your partner, swap roles (interviewer/candidate) halfway."}


# Shared rubric: both sides score 1-5 on the same dimensions.
_RUBRIC_DIMS = [
    ("clarity", "Clarity of thought", "Structured answer, easy to follow"),
    ("depth", "Technical depth", "Correct concepts, no hand-waving"),
    ("communication", "Communication", "Pace, confidence, no rambling"),
    ("problem_solving", "Problem solving", "Approach before code, edge cases"),
    ("behavioral", "Behavioral", "STAR structure, quantified results"),
]


def mock_rubric():
    """Return the shared scoring rubric."""
    return {"dimensions": [{"id": d, "label": l, "hint": h} for d, l, h in _RUBRIC_DIMS],
            "scale": "1 (weak) – 5 (hire-ready)",
            "guidance": "Both interviewer and candidate score independently, then compare."}


def score_rubric(scores):
    """Score a completed rubric; compare two sides.

    scores: {dimension_id: 1-5} or {"interviewer": {...}, "candidate": {...}}.
    Returns {averages, total, gaps}.
    """
    if not isinstance(scores, dict):
        raise ValueError("scores must be a dict.")
    valid = {d for d, _, _ in _RUBRIC_DIMS}

    def _avg(side):
        vals = []
        for k, v in (side or {}).items():
            if k in valid:
                try:
                    vals.append(max(1, min(5, int(v))))
                except (TypeError, ValueError):
                    continue
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    if "interviewer" in scores or "candidate" in scores:
        iv = _avg(scores.get("interviewer"))
        ca = _avg(scores.get("candidate"))
        gap = round(abs(iv - ca), 2)
        return {"interviewer_avg": iv, "candidate_avg": ca,
                "perception_gap": gap,
                "verdict": ("Aligned perceptions — great." if gap < 0.75 else
                            "Perception gap — discuss where you saw it differently."),
                "total": round((iv + ca) / 2, 2)}
    avg = _avg(scores)
    weak = [d for d, _, _ in _RUBRIC_DIMS
            if isinstance(scores.get(d), (int, float)) and scores[d] <= 2]
    return {"average": avg, "total": avg,
            "weak_dimensions": weak,
            "verdict": ("Hire-ready." if avg >= 4 else
                        "Getting there — drill weak dimensions." if avg >= 3 else
                        "Keep practicing — focus on fundamentals.")}


_VALID_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
               "saturday", "sunday"]


def recurring_slot(day, time_hhmm, duration_min=60):
    """Create a weekly standing mock appointment.

    Returns {day, time, duration_min, next_occurrence, summary}.
    """
    day = _clean(day or "").strip().lower()
    if day not in _VALID_DAYS:
        raise ValueError(f"day must be one of {', '.join(_VALID_DAYS)}.")
    m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", _clean(time_hhmm or "").strip())
    if not m:
        raise ValueError("time must be HH:MM (24h).")
    try:
        duration_min = int(duration_min)
    except (TypeError, ValueError):
        duration_min = 60
    duration_min = max(30, min(180, duration_min))
    # Next occurrence of that weekday.
    now = datetime.now(timezone.utc)
    target = _VALID_DAYS.index(day)
    days_ahead = (target - now.weekday()) % 7
    nxt = now + __import__("datetime").timedelta(days=days_ahead)
    nxt = nxt.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if nxt <= now:
        nxt += __import__("datetime").timedelta(days=7)
    return {"day": day.capitalize(), "time": f"{m.group(1)}:{m.group(2)}",
            "duration_min": duration_min,
            "next_occurrence": nxt.isoformat(),
            "summary": (f"Every {day.capitalize()} at {m.group(1)}:{m.group(2)} "
                        f"({duration_min} min) — mock interview with your partner.")}
