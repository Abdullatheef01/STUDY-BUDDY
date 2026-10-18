"""JD-matched ATS scoring engine (Wave 1, feature #1).

Deterministic, server-side resume-vs-job-description comparison. All scores
are computed here - never in the browser. The LLM layer (Gemini) is only
used for qualitative, section-by-section fix suggestions; the numeric score
and keyword analysis below stand on their own so the endpoint degrades
gracefully when the AI service is unavailable.
"""

import re

# ---------------------------------------------------------------------------
# Scoring weights (must sum to 100)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "keyword_coverage": 40,      # % of JD keywords present in the resume
    "skills_hit_rate": 35,       # % of JD-required skills present in the resume
    "experience_alignment": 15,  # resume years vs JD-requested years
    "ats_friendliness": 10,      # sections + contact info parseable by an ATS
}

JD_MIN_CHARS = 50
JD_MAX_CHARS = 20000
MAX_KEYWORDS = 60

# Compact English stopword set for keyword extraction.
_STOPWORDS = frozenset("""
a an the and or but if then else when while of at by for with about into
through during before after above below to from up down in out on off over
under again further once here there all any both each few more most other
some such no nor not only own same so than too very can will just don should
now we you your our ours their theirs his her its my me him us them i he she
it this that these those as is are was were be been being have has had having
do does did doing would could ought shall may might must need needs needed
within without across per via etc including include includes included
required requirements require requires looking seek seeking join join us
team role position opportunity ideal candidate responsibilities
qualifications preferred plus strong ability able work working experience
experienced knowledge skills skill year years degree bachelor's master's
business help helps ensure drive deliver building build proven track record
passion passionate environment fast paced excellent great good best new
""".split())


def _tokenize(text):
    """Lowercase alphanumeric tokens of length >= 3."""
    return re.findall(r"[a-z0-9][a-z0-9+\-#\.]{2,}", (text or "").lower())


def extract_jd_keywords(jd_text, top_n=MAX_KEYWORDS):
    """Extract the most frequent meaningful keywords from a job description.

    Returns a list of {"keyword": str, "count": int} ordered by frequency
    (then alphabetically for stability).
    """
    counts = {}
    for tok in _tokenize(jd_text):
        tok = tok.strip(".-+#")
        if len(tok) < 3 or tok in _STOPWORDS:
            continue
        if tok.isdigit():
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"keyword": k, "count": c} for k, c in ranked[:top_n]]


def parse_jd_requirements(jd_text):
    """Pull structured requirements out of a job description.

    Returns {"experience_years_required": int|None, "job_title": str}.
    The experience figure is the maximum "N years" mention found, which is
    the usual reading of the requirement bar in a JD.
    """
    text = jd_text or ""
    years = None
    for m in re.finditer(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", text, re.IGNORECASE):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if 0 < n <= 30 and (years is None or n > years):
            years = n
    title = ""
    for line in text.splitlines():
        line = line.strip()
        if line:
            title = line[:100]
            break
    return {"experience_years_required": years, "job_title": title}


def _score_ats_friendliness(sections, contact):
    """Lightweight ATS-parseability check (sections + contact info)."""
    sections = sections or {}
    essential = ["summary", "education", "experience", "skills"]
    found = sum(1 for s in essential if s in sections)
    section_pts = round(found / len(essential) * 6, 1)
    contact = contact or {}
    contact_pts = 0.0
    if contact.get("email"):
        contact_pts += 2.0
    if contact.get("phone"):
        contact_pts += 2.0
    return round(min(section_pts + contact_pts, 10), 1), {
        "sections_found": [s for s in essential if s in sections],
        "has_email": bool(contact.get("email")),
        "has_phone": bool(contact.get("phone")),
    }


def score_jd_match(resume_text, resume_skill_names, experience_years,
                   sections, contact, jd_text):
    """Score a resume against a job description.

    All inputs are plain data; returns a JSON-serializable report dict with
    a transparent per-category breakdown. Scores are 0-100.
    """
    from models.skill_extractor import extract_skills, get_skill_names

    jd_keywords = extract_jd_keywords(jd_text)
    jd_skills = get_skill_names(extract_skills(jd_text or ""))
    resume_lower = (resume_text or "").lower()
    resume_skill_set = {s.lower() for s in (resume_skill_names or [])}

    # --- 1. Keyword coverage (40) ---
    matched_kw = [k for k in jd_keywords
                  if k["keyword"] in resume_lower]
    kw_total = len(jd_keywords)
    kw_ratio = (len(matched_kw) / kw_total) if kw_total else 1.0
    kw_score = round(kw_ratio * WEIGHTS["keyword_coverage"], 1)

    # --- 2. Required-skills hit rate (35) ---
    matched_skills = [s for s in jd_skills if s.lower() in resume_skill_set]
    missing_skills = [s for s in jd_skills if s.lower() not in resume_skill_set]
    sk_total = len(jd_skills)
    sk_ratio = (len(matched_skills) / sk_total) if sk_total else 1.0
    sk_score = round(sk_ratio * WEIGHTS["skills_hit_rate"], 1)

    # --- 3. Experience alignment (15) ---
    req = parse_jd_requirements(jd_text)
    req_years = req["experience_years_required"]
    resume_years = experience_years or 0
    if req_years:
        exp_ratio = min(resume_years / req_years, 1.0) if req_years > 0 else 1.0
        exp_note = ("Resume shows ~{} yr vs {} yr required."
                    .format(resume_years, req_years))
    else:
        # No explicit bar in the JD: neutral, not punitive, and labelled.
        exp_ratio = 0.6
        exp_note = ("No explicit experience requirement found in the JD; "
                    "neutral score applied.")
    exp_score = round(exp_ratio * WEIGHTS["experience_alignment"], 1)

    # --- 4. ATS friendliness (10) ---
    ats_score, ats_detail = _score_ats_friendliness(sections, contact)

    total = round(min(kw_score + sk_score + exp_score + ats_score, 100), 1)

    # Missing keywords, prioritized: required skills first, then by JD
    # frequency so the most-mentioned gaps surface at the top.
    matched_kw_set = {k["keyword"] for k in matched_kw}
    missing_kw = [k for k in jd_keywords if k["keyword"] not in matched_kw_set]
    prioritized_missing = list(missing_skills)
    seen = {s.lower() for s in prioritized_missing}
    for k in missing_kw:
        if k["keyword"] not in seen:
            prioritized_missing.append(k["keyword"])
            seen.add(k["keyword"])

    return {
        "job_title": req["job_title"],
        "score": total,
        "breakdown": {
            "keyword_coverage": {
                "score": kw_score, "max": WEIGHTS["keyword_coverage"],
                "label": "Keyword Coverage",
                "matched": len(matched_kw), "total": kw_total,
                "details": "{}/{} JD keywords appear in your resume.".format(
                    len(matched_kw), kw_total),
            },
            "skills_hit_rate": {
                "score": sk_score, "max": WEIGHTS["skills_hit_rate"],
                "label": "Required-Skills Hit Rate",
                "matched": len(matched_skills), "total": sk_total,
                "details": "{}/{} skills the JD asks for are on your resume.".format(
                    len(matched_skills), sk_total),
            },
            "experience_alignment": {
                "score": exp_score, "max": WEIGHTS["experience_alignment"],
                "label": "Experience Alignment",
                "matched": None, "total": None,
                "details": exp_note,
            },
            "ats_friendliness": {
                "score": ats_score, "max": WEIGHTS["ats_friendliness"],
                "label": "ATS Friendliness",
                "matched": None, "total": None,
                "details": "Sections found: {}; contact: {}.".format(
                    ", ".join(ats_detail["sections_found"]) or "none",
                    "/".join([p for p, ok in
                              (("email", ats_detail["has_email"]),
                               ("phone", ats_detail["has_phone"])) if ok])
                    or "missing"),
            },
        },
        "matched_keywords": [k["keyword"] for k in matched_kw],
        "missing_keywords": prioritized_missing,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "requirements": req,
        "resume_experience_years": resume_years,
    }


def generate_rule_based_suggestions(report):
    """Deterministic fix suggestions used when the AI service is unavailable.

    Returns a list of {"section", "issue", "fix"} dicts, most impactful first.
    """
    suggestions = []
    missing_skills = report.get("missing_skills") or []
    if missing_skills:
        suggestions.append({
            "section": "Skills",
            "issue": "Missing {} skill(s) the JD explicitly asks for.".format(
                len(missing_skills)),
            "fix": ("Add a Skills section entry for: {}. Only list skills "
                    "you genuinely have; mirror the JD's exact wording so "
                    "ATS parsers catch them.".format(", ".join(missing_skills[:8]))),
        })
    bd = (report.get("breakdown") or {}).get("keyword_coverage", {})
    if bd.get("total") and bd.get("matched", 0) < bd["total"] * 0.5:
        missing_kw = (report.get("missing_keywords") or [])[:6]
        suggestions.append({
            "section": "Overall",
            "issue": "Low keyword overlap with the job description.",
            "fix": ("Weave these JD terms naturally into your experience "
                    "bullets: {}. Use the employer's exact phrasing."
                    .format(", ".join(missing_kw) or "n/a")),
        })
    req_years = (report.get("requirements") or {}).get("experience_years_required")
    resume_years = report.get("resume_experience_years") or 0
    if req_years and resume_years < req_years:
        suggestions.append({
            "section": "Experience",
            "issue": "JD asks for ~{} yr; your resume shows ~{} yr.".format(
                req_years, resume_years),
            "fix": ("Quantify every bullet (%, counts, scale) and surface "
                    "internships, freelance, and project work as experience "
                    "to close the perceived gap."),
        })
    job_title = report.get("job_title") or ""
    if job_title:
        suggestions.append({
            "section": "Summary",
            "issue": "Resume headline does not mirror the target role.",
            "fix": ("Open with the exact role title from the JD ('{}') "
                    "followed by your strongest matching qualification."
                    .format(job_title)),
        })
    ats = (report.get("breakdown") or {}).get("ats_friendliness", {})
    if ats.get("score", 10) < 7:
        suggestions.append({
            "section": "Formatting",
            "issue": "Resume may parse poorly in applicant tracking systems.",
            "fix": ("Use standard section headings (Summary, Experience, "
                    "Education, Skills), keep contact details in the body "
                    "text (not headers/images), and avoid tables and "
                    "graphics for critical information."),
        })
    return suggestions[:6]


# ================= Feature 1 Ultimate Enhancements =================
# 1.1 AI pre-screen simulator | 1.2 Keyword action plan | 1.3 Offer probability

# Signals AI screening bots (2026: 66% of recruiters) actually check.
_BOT_POSITIVE = [
    (r"\b\d+\s*%", "quantified impact (%)"),
    (r"\b\d+\s*(x|times)\b", "quantified multiplier"),
    (r"\$\s?\d|₹\s?\d|\d+\s*(lpa|lakh|k\b)", "monetary/scale numbers"),
    (r"\b(led|built|shipped|launched|owned|drove|architected|scaled)\b", "strong action verbs"),
    (r"\b(20\d{2})\s*[-–—]\s*(20\d{2}|present|now)\b", "dated experience ranges"),
]
_BOT_NEGATIVE = [
    (r"\b(responsible for|duties included|helped with)\b", "passive phrasing"),
    (r"\b(lorem|asdf|xxx+)\b", "placeholder text"),
    (r"(.)\1{5,}", "repeated-character filler"),
]

# Where each keyword type belongs on a resume.
_SECTION_FOR_KEYWORD = {
    "skill": "Skills",
    "tool": "Skills",
    "keyword": "Experience",
}


def _strip_html(text):
    return re.sub(r"<[^>]*>", "", text or "")


def simulate_ai_screen(report, resume_text):
    """Score the resume the way AI pre-screening bots see it (0-100).

    Bots check: quantified achievements, action verbs, dated ranges,
    skill density — and penalize passive phrasing, placeholders, gaps.
    Returns a bot's-eye breakdown dict; never raises on hostile input.
    """
    text = _strip_html(resume_text or "")
    lower = text.lower()
    signals = []
    score = 50.0  # neutral start; signals move it

    for pattern, label in _BOT_POSITIVE:
        hits = len(re.findall(pattern, lower))
        if hits:
            gain = min(8.0, 2.0 * hits)
            score += gain
            signals.append({"signal": label, "effect": f"+{gain:.0f}",
                            "hits": hits, "tone": "positive"})
    for pattern, label in _BOT_NEGATIVE:
        hits = len(re.findall(pattern, lower))
        if hits:
            loss = min(15.0, 5.0 * hits)
            score -= loss
            signals.append({"signal": label, "effect": f"-{loss:.0f}",
                            "hits": hits, "tone": "negative"})

    # Skill density: bots love skills-per-100-words in a sane band.
    words = len(lower.split())
    skills = (report or {}).get("matched_skills", []) or []
    if words > 20:
        density = len(skills) / words * 100
        if density < 1.0:
            score -= 5
            signals.append({"signal": "low skill density", "effect": "-5",
                            "hits": 0, "tone": "negative"})
        elif density > 12.0:
            score -= 8  # keyword stuffing looks bot-generated
            signals.append({"signal": "keyword stuffing suspected", "effect": "-8",
                            "hits": 0, "tone": "negative"})
        else:
            score += 4
            signals.append({"signal": "healthy skill density", "effect": "+4",
                            "hits": 0, "tone": "positive"})

    # Length sanity: bots downrank 1-line and 5-page resumes alike.
    if words and words < 80:
        score -= 10
        signals.append({"signal": "resume too short", "effect": "-10",
                        "hits": 0, "tone": "negative"})
    elif words > 1200:
        score -= 6
        signals.append({"signal": "resume too long", "effect": "-6",
                        "hits": 0, "tone": "negative"})

    score = max(0.0, min(100.0, round(score, 1)))
    verdict = ("Likely to pass AI screening" if score >= 70
               else "Borderline — bots may filter you out" if score >= 45
               else "Likely to be filtered out by AI screening")
    return {"score": score, "verdict": verdict, "signals": signals,
            "word_count": words}


def keyword_action_plan(report, resume_text, sections=None):
    """Top-5 missing keywords with exactly WHERE to add each one.

    Returns a prioritized checklist: [{keyword, where, why, example}].
    Skills/tools -> Skills section; the rest -> Experience bullets.
    """
    report = report or {}
    missing = list(report.get("missing_keywords", []) or [])[:12]
    skills_missing = {s.lower() for s in (report.get("missing_skills", []) or [])}
    resume_lower = (_strip_html(resume_text or "")).lower()

    plan = []
    for kw in missing:
        if not kw or not isinstance(kw, str):
            continue
        kl = kw.lower().strip()
        if not kl or kl in resume_lower:
            continue  # already present (belated match)
        is_skill = kl in skills_missing
        where = _SECTION_FOR_KEYWORD["skill"] if is_skill else _SECTION_FOR_KEYWORD["keyword"]
        if is_skill:
            example = f"Add '{kw}' to your Skills section as a comma-separated item."
            why = "The JD lists it as a required skill; bots match the Skills section first."
        else:
            example = (f"Weave '{kw}' into an Experience bullet: "
                       f"e.g. '... using {kw} to ... [quantified outcome]'.")
            why = "Bots weight keywords inside achievement bullets higher than bare lists."
        plan.append({"keyword": kw, "where": where, "why": why, "example": example})
        if len(plan) >= 5:
            break
    return plan


def competitiveness_checklist(report, applicants_estimate=None):
    """Qualitative competitiveness checklist — explicitly NOT a prediction.

    ENG-08 (Phase 0): the old ``offer_probability()`` turned an ATS score
    into a made-up "offer chance %" via an arbitrary logistic curve. No data
    links those numbers to real hiring outcomes, so the percentages were
    removed. This returns a qualitative, explicitly illustrative checklist
    with no percentages and no chance labels. Never raises.
    """
    report = report or {}
    score = report.get("score", 0) or 0
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(100.0, score))

    try:
        n = int(applicants_estimate) if applicants_estimate is not None else 0
    except (TypeError, ValueError):
        n = 0

    if score >= 75:
        match = ("above", "Your match score is above the range where most "
                          "applications get a first look. Keep the strongest "
                          "evidence in the top third of the resume.")
    elif score >= 55:
        match = ("around", "Your match score is around the typical first-look "
                           "range. Tighten the top skills section to the exact "
                           "terms in the job description.")
    else:
        match = ("below", "Your match score is below the typical first-look "
                          "range. Rework the summary and skills to mirror the "
                          "job description before applying.")

    checklist = [
        {"item": "Resume-to-JD match",
         "status": match[0],
         "note": match[1]},
        {"item": "Competition awareness",
         "status": "known" if n > 0 else "unknown",
         "note": (f"Roughly {n} applicants estimated — larger pools reward "
                  "sharper differentiation in the top third of the resume."
                  if n > 0 else
                  "Applicant count unknown — assume a competitive pool and "
                  "lead with your strongest, most relevant evidence.")},
        {"item": "Proof over claims",
         "status": "check",
         "note": "Every skill listed should have at least one bullet with a "
                 "concrete outcome. Unproven skills read as filler."},
        {"item": "One tailored version per role",
         "status": "check",
         "note": "Re-run the JD match for each application; a generic resume "
                 "underperforms a tailored one even with the same experience."},
    ]
    return {"ats_score": round(score, 1),
            "applicants_estimate": n if n > 0 else None,
            "checklist": checklist,
            "illustrative": True,
            "disclaimer": ("Illustrative checklist only — not a prediction of "
                           "offer chances. No data links these factors to "
                           "actual hiring outcomes.")}
