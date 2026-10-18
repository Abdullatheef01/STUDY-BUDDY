"""Mentors ultimate: async Q&A, session prep packets, alumni outcomes.

Feature 30 x3:
  30.1 async_qa — ask a mentor without booking; digest for mentors.
  30.2 prep_packet — auto-brief for both sides before a call.
  30.3 alumni_outcomes — "mentees of X got placed at Y" social proof.
"""
import re
from datetime import UTC, datetime


def _clean(text):
    return re.sub(r"<[^>]*>", "", text or "")


def validate_async_question(payload):
    """Validate an async mentor question. Returns (data, error)."""
    if not isinstance(payload, dict):
        return None, "Invalid question data."
    question = _clean(payload.get("question") or "").strip()
    if len(question) < 20:
        return None, "Question needs at least 20 characters — give context."
    if len(question) > 2000:
        return None, "Question is too long (max 2000 characters)."
    topic = _clean(payload.get("topic") or "").strip()[:80]
    return ({"question": question, "topic": topic or "General",
             "asked_at": datetime.now(UTC).isoformat()}, None)


def async_qa_digest(questions, mentor_name=""):
    """Bundle pending async questions into a mentor-friendly digest.

    questions: list of {question, topic, asker?, asked_at?}.
    Returns {digest markdown, count} for the mentor to answer in one sitting.
    """
    if not isinstance(questions, (list, tuple)):
        raise ValueError("questions must be a list.")
    clean = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        text = _clean(q.get("question") or "").strip()
        if len(text) < 10:
            continue
        clean.append({"question": text[:1000],
                      "topic": _clean(q.get("topic") or "General")[:40],
                      "asker": _clean(q.get("asker") or "Anonymous")[:40]})
    if not clean:
        raise ValueError("No valid questions for the digest.")
    lines = [f"# Async Q&A — {len(clean)} questions for {_clean(mentor_name)[:40] or 'you'}", ""]
    for i, q in enumerate(clean, 1):
        lines.append(f"## Q{i} [{q['topic']}] — {q['asker']}")
        lines.append(q["question"])
        lines.append("")
        lines.append("_Your answer:_")
        lines.append("")
    return {"markdown": "\n".join(lines), "count": len(clean),
            "guidance": "Answer in one sitting (30 min). Short, specific answers beat essays."}


def prep_packet(mentee, mentor, topic):
    """Auto-brief packet for both sides before a mentoring call.

    mentee/mentor: dicts with {name, headline?, goals?/bio?}.
    Returns {for_mentee, for_mentor, agenda}.
    """
    if not isinstance(mentee, dict) or not isinstance(mentor, dict):
        raise ValueError("mentee and mentor must be dicts.")
    topic = _clean(topic or "").strip()[:120] or "General guidance"
    mentee_name = _clean(mentee.get("name") or "Mentee")[:40]
    mentor_name = _clean(mentor.get("name") or "Mentor")[:40]
    for_mentee = {
        "heading": f"Your call with {mentor_name}",
        "points": [
            f"Mentor: {_clean(mentor.get('headline') or '')[:100]}",
            f"Topic: {topic}",
            "Prepare: 3 specific questions (not 'how do I get a job?')",
            "Bring: resume link + one project to discuss",
            "After: send a thank-you + what you will do next",
        ],
    }
    for_mentor = {
        "heading": f"Call with {mentee_name}",
        "points": [
            f"Mentee: {_clean(mentee.get('headline') or '')[:100]}",
            f"Their goal: {_clean(mentee.get('goals') or 'Not specified')[:150]}",
            f"Topic: {topic}",
            "Tip: end with ONE actionable next step, not ten",
        ],
    }
    agenda = [
        "0-5 min: intros + goal for the call",
        "5-20 min: deep dive on the topic",
        "20-25 min: action items",
        "25-30 min: wrap + follow-up plan",
    ]
    return {"for_mentee": for_mentee, "for_mentor": for_mentor,
            "agenda": agenda, "topic": topic}


def alumni_outcomes(mentor_id, placements):
    """Social proof: where did this mentor's mentees land?

    placements: list of {mentor_id, mentee?, company, role}.
    Returns {placements, top_companies, count}.
    """
    if not isinstance(placements, (list, tuple)):
        raise ValueError("placements must be a list.")
    mine = []
    for p in placements:
        if not isinstance(p, dict):
            continue
        try:
            mid = p.get("mentor_id")
            match = str(mid) == str(mentor_id)
        except (TypeError, ValueError):
            continue
        if match:
            mine.append({"company": _clean(p.get("company") or "Unknown")[:60],
                         "role": _clean(p.get("role") or "")[:60]})
    from collections import Counter
    top = Counter(p["company"] for p in mine).most_common(5)
    return {"placements": mine, "count": len(mine),
            "top_companies": [{"company": c, "count": n} for c, n in top],
            "headline": (f"Mentees placed at {len(set(p['company'] for p in mine))} companies."
                         if mine else "No tracked placements yet.")}
