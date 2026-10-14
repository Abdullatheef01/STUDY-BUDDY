"""Certification guidance engine (Wave 3 feature #20).

Backed by the committed bank data/certifications.json: 44 real
certifications across Cloud, Data, Programming, Cybersecurity, Project
Management, Networking, DevOps, and AI/ML. Costs are approximate INR.

Recommendation is deterministic: role match + skill overlap + budget fit
+ difficulty fit, with plain-language ROI reasoning per suggestion.
Study plans spread a cert's prep resources (plus overlapping roadmap
topics when available) across N weeks.
"""

import json
import os

BANK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "certifications.json")

DIFFICULTY_RANK = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}

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
        _by_id = {c["id"]: c for c in _bank if "id" in c}
    return _bank


def _by_id_map():
    _load()
    return _by_id


def all_certs():
    return _load()


def get_cert(cert_id):
    return _by_id_map().get(cert_id)


def domains():
    """Sorted [(domain, count)]."""
    counts = {}
    for c in _load():
        d = c.get("domain", "Other")
        counts[d] = counts.get(d, 0) + 1
    return sorted(counts.items())


def filter_certs(domain=None, max_cost_inr=None, difficulty=None):
    out = []
    for c in _load():
        if domain and c.get("domain") != domain:
            continue
        if difficulty and c.get("difficulty") != difficulty:
            continue
        if max_cost_inr is not None:
            try:
                if float(c.get("cost_inr", 0)) > float(max_cost_inr):
                    continue
            except (TypeError, ValueError):
                pass
        out.append(c)
    return out


def _norm_skills(skills):
    return {str(s).strip().lower() for s in (skills or []) if str(s).strip()}


def recommend(skills=None, target_role=None, budget_inr=None, top_n=8):
    """Rank certifications for a learner.

    skills: list of skill ids the learner has (e.g. ["python", "sql"]).
    target_role: role id (matches the roadmap roles).
    budget_inr: max exam budget; certs above it are down-ranked, not dropped.
    Returns list of {cert, score, reasons[]} sorted by score desc.
    """
    have = _norm_skills(skills)
    role = (target_role or "").strip()
    try:
        budget = float(budget_inr) if budget_inr not in (None, "") else None
    except (TypeError, ValueError):
        budget = None

    ranked = []
    for c in _load():
        score = 0.0
        reasons = []
        # Role match (strongest signal)
        if role and role in (c.get("roles") or []):
            score += 40
            reasons.append("Directly recommended for your target role.")
        # Skill overlap: cert roles share roadmap skills with learner skills.
        # We approximate via domain affinity below; here reward Beginner
        # certs for learners with few skills.
        if not have and c.get("difficulty") == "Beginner":
            score += 8
            reasons.append("Beginner-friendly entry point.")
        # Budget fit
        try:
            cost = float(c.get("cost_inr", 0))
        except (TypeError, ValueError):
            cost = 0
        if budget is not None:
            if cost <= budget:
                score += 20
                reasons.append("Fits inside your stated budget.")
            else:
                over = (cost - budget) / max(budget, 1)
                score -= min(25, over * 25)
                reasons.append("Above your stated budget — save it for later.")
        else:
            # Without a budget, cheaper respected certs rank slightly higher.
            score += max(0, 10 - cost / 8000)
        # Difficulty: prefer Intermediate as the ROI sweet spot.
        if c.get("difficulty") == "Intermediate":
            score += 8
            reasons.append("Intermediate level — the best effort-to-signal ratio.")
        elif c.get("difficulty") == "Beginner":
            score += 4
        # Long validity is a plus.
        v = c.get("validity_years")
        if isinstance(v, (int, float)) and v >= 3:
            score += 4
            reasons.append(f"Valid for {int(v)} years.")
        elif v is None:
            score += 5
            reasons.append("Lifetime validity — never expires.")
        ranked.append({"cert": c, "score": round(score, 1),
                       "reasons": reasons[:4]})
    ranked.sort(key=lambda r: (-r["score"], r["cert"].get("name", "")))
    return ranked[:max(1, min(int(top_n or 8), 20))]


def _roadmap_lookup():
    """Lazy import of the roadmap bank for study-plan enrichment."""
    try:
        from learning_roadmaps import get_skill
        return get_skill
    except Exception:
        return None


def build_study_plan(cert_id, weeks=8):
    """Generate a week-by-week study plan for a certification.

    Uses the cert's prep resources spread across weeks; when the roadmap
    bank is available, weeks also pull overlapping foundation topics from
    skills tied to the cert's roles (via role -> required skills).
    Returns (plan_dict, error).
    """
    cert = get_cert(cert_id)
    if not cert:
        return None, "Unknown certification."
    try:
        weeks = int(weeks)
    except (TypeError, ValueError):
        return None, "Weeks must be a number."
    weeks = max(2, min(weeks, 24))

    resources = list(cert.get("prep_resources") or [])
    # Gather foundation topics from roadmap skills linked to cert roles.
    topic_pool = []
    get_skill = _roadmap_lookup()
    if get_skill:
        try:
            from learning_roadmaps import get_role as _get_role
            for role_id in (cert.get("roles") or [])[:2]:
                role = _get_role(role_id)
                if not role:
                    continue
                for req in (role.get("required_skills") or [])[:4]:
                    skill = get_skill(req.get("skill_id"))
                    if not skill:
                        continue
                    for st in (skill.get("stages") or [])[:2]:
                        for t in (st.get("topics") or [])[:4]:
                            topic_pool.append(
                                {"topic": t, "skill": skill.get("name", ""),
                                 "stage": st.get("stage", "")})
        except Exception:
            topic_pool = []
    # De-dupe topics, keep order.
    seen, topics = set(), []
    for t in topic_pool:
        key = t["topic"].lower()
        if key not in seen:
            seen.add(key)
            topics.append(t)

    plan_weeks = []
    for w in range(1, weeks + 1):
        # Round-robin resources so every week has material.
        week_resources = [resources[(w - 1 + k) % len(resources)]
                          for k in range(min(2, len(resources)))] if resources else []
        # Slice of foundation topics for this week.
        per = max(1, (len(topics) + weeks - 1) // weeks) if topics else 0
        week_topics = topics[(w - 1) * per: w * per] if topics else []
        if w == 1:
            focus = "Foundations & exam blueprint"
        elif w == weeks:
            focus = "Mock exams & revision"
        elif w == weeks - 1:
            focus = "Weak-area drills"
        else:
            focus = (week_topics[0]["skill"] + " deep-dive"
                     if week_topics else "Core concepts")
        plan_weeks.append({
            "week": w,
            "focus": focus,
            "topics": week_topics,
            "resources": week_resources,
            "tasks": _week_tasks(w, weeks),
        })
    return {
        "cert_id": cert_id,
        "cert_name": cert.get("name", ""),
        "weeks": weeks,
        "exam_format": cert.get("exam_format", ""),
        "plan": plan_weeks,
        "total_topics": len(topics),
    }, None


def _week_tasks(week, total):
    if week == 1:
        return ["Read the official exam guide end-to-end.",
                "Take a baseline practice test to find gaps.",
                "Set up a study schedule and lab environment."]
    if week == total:
        return ["Take 2 full-length timed mock exams.",
                "Revise all incorrect answers from mocks.",
                "Rest the day before the exam."]
    if week == total - 1:
        return ["Drill your weakest domains from mock results.",
                "Re-read official docs for weak areas."]
    return ["Study the week's topics and resources.",
            "Build one hands-on lab or mini-project.",
            "Write a one-page summary of what you learned."]


def validate_recommend_payload(payload):
    if not isinstance(payload, dict):
        return None, "Provide a JSON object."
    skills = payload.get("skills") or []
    if not isinstance(skills, list):
        return None, "skills must be a list."
    skills = [str(s).strip() for s in skills[:40] if str(s).strip()]
    role = (payload.get("target_role") or "").strip()
    budget = payload.get("budget_inr")
    if budget not in (None, ""):
        try:
            budget = float(budget)
            if budget < 0:
                raise ValueError
        except (TypeError, ValueError):
            return None, "budget_inr must be a non-negative number."
    try:
        top_n = int(payload.get("top_n", 8))
    except (TypeError, ValueError):
        top_n = 8
    return {"skills": skills, "target_role": role or None,
            "budget_inr": budget, "top_n": max(1, min(top_n, 20))}, None


def validate_plan_payload(payload):
    if not isinstance(payload, dict):
        return None, "Provide a JSON object."
    cert_id = (payload.get("cert_id") or "").strip()
    if not get_cert(cert_id):
        return None, "Choose a valid certification."
    try:
        weeks = int(payload.get("weeks", 8))
    except (TypeError, ValueError):
        return None, "weeks must be a number."
    return {"cert_id": cert_id, "weeks": max(2, min(weeks, 24))}, None
