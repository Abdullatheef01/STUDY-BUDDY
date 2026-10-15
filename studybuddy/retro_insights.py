"""Retrospectives ultimate: pattern alerts, experiment tracker, win library.

Feature 29 x3:
  29.1 pattern_alerts — "3 rejections mention DSA — that's your bottleneck."
  29.2 track_experiment — A/B test resume versions, measure callbacks.
  29.3 win_library — save what worked; replay the playbook.
"""
import re
from datetime import datetime, timezone


def _clean(text):
    return re.sub(r"<[^>]*>", "", text or "")


# Bottleneck keyword fingerprints.
_BOTTLENECKS = [
    ("dsa", ["dsa", "coding", "algorithm", "leetcode", "data structure"]),
    ("behavioral", ["behavioral", "hr round", "culture fit", "tell me about"]),
    ("system_design", ["system design", "architecture", "scalability", "hld", "lld"]),
    ("resume", ["resume", "ats", "shortlist", "screening"]),
    ("communication", ["communication", "english", "presentation", "nervous"]),
    ("projects", ["project", "portfolio", "experience", "internship"]),
    ("aptitude", ["aptitude", "quant", "logical", "oa "]),
]


def pattern_alerts(retrospectives, min_mentions=2):
    """Detect recurring rejection themes across retrospectives.

    retrospectives: list of {notes/feedback text}. Returns {alerts:
    [{theme, mentions, message}]} sorted by frequency.
    """
    if not isinstance(retrospectives, (list, tuple)):
        raise ValueError("retrospectives must be a list.")
    try:
        min_mentions = int(min_mentions)
    except (TypeError, ValueError):
        min_mentions = 2
    counts = {}
    for r in retrospectives:
        if not isinstance(r, dict):
            continue
        text = (_clean(r.get("notes") or "") + " " +
                _clean(r.get("feedback") or "") + " " +
                _clean(r.get("reason") or "")).lower()
        if not text.strip():
            continue
        for theme, keywords in _BOTTLENECKS:
            if any(kw in text for kw in keywords):
                counts[theme] = counts.get(theme, 0) + 1
    alerts = []
    for theme, n in sorted(counts.items(), key=lambda x: -x[1]):
        if n >= min_mentions:
            label = theme.replace("_", " ")
            alerts.append({
                "theme": theme, "mentions": n,
                "message": (f"{n} retrospectives mention {label} — "
                            f"that's your bottleneck. Fix this first."),
                "action": f"Drill {label} for 2 weeks, then re-measure.",
            })
    return {"alerts": alerts, "total_retros": len(retrospectives),
            "verdict": (alerts[0]["message"] if alerts else
                        "No repeating pattern yet — keep logging retrospectives.")}


def track_experiment(name, variants):
    """A/B test anything (resume versions, outreach templates...).

    variants: list of {name, sent (int), callbacks (int)}. Returns per-variant
    {callback_rate, winner} + statistical caution for small samples.
    """
    name = _clean(name or "").strip()[:80] or "Experiment"
    if not isinstance(variants, (list, tuple)) or len(variants) < 2:
        raise ValueError("At least two variants are needed.")
    rows = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        try:
            sent = max(0, int(v.get("sent") or 0))
            cb = max(0, int(v.get("callbacks") or 0))
        except (TypeError, ValueError):
            continue
        rate = round(cb / sent * 100, 1) if sent else 0.0
        rows.append({"name": _clean(v.get("name") or "Variant")[:40],
                     "sent": sent, "callbacks": cb, "callback_rate": rate})
    if len(rows) < 2:
        raise ValueError("At least two valid variants are needed.")
    rows.sort(key=lambda x: -x["callback_rate"])
    rows[0]["is_winner"] = True
    total_sent = sum(r["sent"] for r in rows)
    caution = (total_sent < 30 and
               "Small sample — treat the winner as a hypothesis, not proof. "
               "Get to 30+ sends per variant.")
    return {"experiment": name, "variants": rows,
            "winner": rows[0]["name"],
            "lift": round(rows[0]["callback_rate"] - rows[1]["callback_rate"], 1),
            "caution": caution or "Decent sample — the winner is likely real.",
            "guidance": "Double down on the winner; test a new challenger next."}


def win_library(wins):
    """Save what worked — replay the playbook.

    wins: list of {title, what_worked, context?}. Returns {wins, playbook}.
    """
    if not isinstance(wins, (list, tuple)):
        raise ValueError("wins must be a list.")
    clean = []
    for w in wins:
        if not isinstance(w, dict):
            continue
        title = _clean(w.get("title") or "").strip()
        what = _clean(w.get("what_worked") or "").strip()
        if not title and not what:
            continue
        clean.append({
            "title": title[:80] or "Win",
            "what_worked": what[:500],
            "context": _clean(w.get("context") or "")[:200],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        })
    # Extract repeatable patterns: most common action verbs.
    verbs = []
    for w in clean:
        verbs.extend(re.findall(r"\b(sent|followed up|practiced|referred|tailored|posted|built|asked)\b",
                                w["what_worked"].lower()))
    from collections import Counter
    top_verbs = [v for v, _ in Counter(verbs).most_common(3)]
    return {"wins": clean, "count": len(clean),
            "playbook": ([f"Keep doing: {v}" for v in top_verbs] if top_verbs
                         else ["Log 3+ wins to detect your winning patterns."]),
            "guidance": "Before every application, re-read your playbook."}
