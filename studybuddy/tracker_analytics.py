"""Job Tracker ultimate: pipeline analytics, follow-up nudges, offer comparator.

Feature 26 x3:
  26.1 pipeline_analytics — conversion rates per stage transition.
  26.2 followup_nudges — "it's been N days, follow up on X".
  26.3 compare_offers — side-by-side offer comparison.
"""
import re
from datetime import date, datetime

STAGE_ORDER = ["wishlist", "applied", "oa", "interview", "offer", "rejected"]
# Highest stage reached per application (rejected is terminal, not a funnel step).
FUNNEL = ["applied", "oa", "interview", "offer"]


def _clean(text):
    return re.sub(r"<[^>]*>", "", text or "")


def _stage_idx(stage):
    try:
        return STAGE_ORDER.index(str(stage or "").lower())
    except ValueError:
        return -1


def pipeline_analytics(applications):
    """Conversion rates across the job pipeline.

    applications: list of {stage}. Returns {funnel: [{stage, count, conv_from_prev}],
    total, insights}.
    An application counts for every funnel stage up to its highest reached.
    """
    if not isinstance(applications, (list, tuple)):
        raise ValueError("applications must be a list.")
    reached = {s: 0 for s in FUNNEL}
    total = 0
    for a in applications:
        if not isinstance(a, dict):
            continue
        total += 1
        stage = str(a.get("stage") or "").lower()
        idx = _stage_idx(stage)
        if idx < 1:  # wishlist or unknown: not in funnel
            continue
        if stage == "rejected":
            # Rejected is terminal: they at least applied, but we don't know
            # how far they got — count conservatively at 'applied' only.
            reached["applied"] += 1
            continue
        # Count for each funnel stage reached.
        for f in FUNNEL:
            if _stage_idx(f) <= idx:
                reached[f] += 1
    funnel = []
    prev = None
    for f in FUNNEL:
        count = reached[f]
        conv = round(count / prev * 100, 1) if prev else 100.0
        funnel.append({"stage": f, "count": count,
                       "conversion_from_prev_pct": conv})
        prev = count if count else prev
    insights = []
    if total:
        applied_n = reached["applied"]
        if applied_n:
            iv_rate = round(reached["interview"] / applied_n * 100, 1)
            insights.append(f"{iv_rate}% of applications reached interview.")
            if iv_rate < 10 and applied_n >= 5:
                insights.append("Low interview rate — your resume/ATS match needs work.")
            offer_rate = round(reached["offer"] / applied_n * 100, 1)
            insights.append(f"{offer_rate}% of applications became offers.")
    return {"funnel": funnel, "total_applications": total,
            "insights": insights or ["Apply to 5+ roles to get meaningful stats."]}


def followup_nudges(applications, today=None, nudge_after_days=7):
    """Nudge follow-ups on stale applications.

    applications: list of {id, company, role, stage, stage_updated_at (iso)}.
    Returns {nudges: [{application, days_stale, message}]}.
    """
    if not isinstance(applications, (list, tuple)):
        raise ValueError("applications must be a list.")
    today = today or date.today()
    if isinstance(today, datetime):
        today = today.date()
    try:
        nudge_after_days = int(nudge_after_days)
    except (TypeError, ValueError):
        nudge_after_days = 7
    nudges = []
    for a in applications:
        if not isinstance(a, dict):
            continue
        stage = str(a.get("stage") or "").lower()
        if stage in ("rejected", "offer", "wishlist"):
            continue
        raw = a.get("stage_updated_at") or a.get("applied_date")
        try:
            if isinstance(raw, date) and not isinstance(raw, datetime):
                updated = raw
            else:
                updated = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        except (ValueError, TypeError, AttributeError):
            continue
        days_stale = (today - updated).days
        if days_stale >= nudge_after_days:
            nudges.append({
                "application_id": a.get("id"),
                "company": _clean(a.get("company"))[:60],
                "role": _clean(a.get("role"))[:60],
                "stage": stage, "days_stale": days_stale,
                "message": (f"It's been {days_stale} days on {a.get('company')} "
                            f"({stage}) — send a polite follow-up."),
            })
    nudges.sort(key=lambda x: -x["days_stale"])
    return {"nudges": nudges, "count": len(nudges)}


def compare_offers(offers):
    """Side-by-side offer comparison on salary, growth, culture signals.

    offers: list of {company, role, base_lpa, variable_lpa?, joining_bonus?,
    esops?, review_months?, wfh?, notes?}. Returns {table, winner, guidance}.
    """
    if not isinstance(offers, (list, tuple)) or len(offers) < 2:
        raise ValueError("At least two offers are needed to compare.")
    rows = []
    for o in offers:
        if not isinstance(o, dict):
            continue
        try:
            base = float(o.get("base_lpa") or 0)
        except (TypeError, ValueError):
            base = 0
        try:
            var = float(o.get("variable_lpa") or 0)
        except (TypeError, ValueError):
            var = 0
        try:
            bonus = float(o.get("joining_bonus") or 0)
        except (TypeError, ValueError):
            bonus = 0
        # Year-1 total comp estimate.
        y1 = base + var * 0.7 + bonus / 100000
        rows.append({
            "company": _clean(o.get("company") or "Unknown")[:40],
            "role": _clean(o.get("role") or "")[:40],
            "base_lpa": round(base, 1), "variable_lpa": round(var, 1),
            "joining_bonus": round(bonus),
            "year1_estimate_lpa": round(y1, 1),
            "wfh": bool(o.get("wfh")),
            "review_months": o.get("review_months"),
            "notes": _clean(o.get("notes") or "")[:120],
        })
    if len(rows) < 2:
        raise ValueError("At least two valid offers are needed.")
    rows.sort(key=lambda x: -x["year1_estimate_lpa"])
    rows[0]["is_top_comp"] = True
    best = rows[0]
    return {"offers": rows, "count": len(rows),
            "top_by_comp": best["company"],
            "guidance": ("Highest Year-1 comp is marked, but weigh growth + team + "
                         "learning equally — Year-1 money is the smallest part of a career.")}
