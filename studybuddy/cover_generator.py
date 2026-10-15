"""Cover-letter and cold-outreach generator (Wave 1 feature #4).

Deterministic, server-side template generation with tone variants.
Gemini (wired in unified_app.py) produces the tailored version when
available; these rule-based templates are the guaranteed fallback.
"""

import re

TONES = ("professional", "enthusiastic", "concise")

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")


def extract_contact(resume_text):
    """Best-effort name/email/phone extraction from resume text."""
    text = resume_text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = ""
    for line in lines[:3]:
        # A name line is short, has 2-4 words, no digits or @.
        words = line.split()
        if 1 < len(words) <= 4 and not re.search(r"[\d@|]", line):
            name = line
            break
    email = (EMAIL_RE.search(text).group(0) if EMAIL_RE.search(text) else "")
    phone_m = PHONE_RE.search(text)
    phone = phone_m.group(1).strip() if phone_m else ""
    return {"name": name, "email": email, "phone": phone}


def _jd_keywords(jd_text, top_n=8):
    from studybuddy.jd_matcher import extract_jd_keywords
    try:
        kws = extract_jd_keywords(jd_text or "", top_n=top_n)
        return [k["keyword"] for k in kws]
    except Exception:
        return []


def _skills_line(resume_text):
    from models.skill_extractor import extract_skills, get_skill_names
    try:
        return ", ".join(get_skill_names(extract_skills(resume_text or ""))[:8])
    except Exception:
        return ""


def _tone_openers(tone):
    return {
        "professional": (
            "I am writing to express my interest in this position.",
            "I would welcome the opportunity to discuss how I can contribute to your team.",
        ),
        "enthusiastic": (
            "I was thrilled to see this opening — it matches exactly what I love doing.",
            "I would be excited to bring my energy and skills to your team.",
        ),
        "concise": (
            "I am applying for this role with directly relevant experience.",
            "I would appreciate the chance to discuss fit in a brief call.",
        ),
    }[tone]


def _strip_html(text):
    """Remove HTML tags — plain-text output, tags are never legitimate."""
    return re.sub(r"<[^>]*>", "", text or "")


def rule_based_cover_letter(resume_text, jd_text, tone="professional"):
    """Build a tailored cover letter from templates (fallback path)."""
    resume_text = _strip_html(resume_text)
    jd_text = _strip_html(jd_text)
    if tone not in TONES:
        tone = "professional"
    contact = extract_contact(resume_text)
    keywords = _jd_keywords(jd_text)
    skills = _skills_line(resume_text)
    opener, closer = _tone_openers(tone)
    name = contact["name"] or "Applicant"

    # First JD line as the role/company hint.
    jd_first = (jd_text or "").strip().splitlines()[0][:100] if (jd_text or "").strip() else "the open position"

    kw_phrase = ", ".join(keywords[:5]) if keywords else "the required skills"
    body = (
        f"{opener} With my background spanning {skills or 'software development'}, "
        f"I bring hands-on experience directly relevant to {jd_first}.\n\n"
        f"In my recent work I have delivered results across {kw_phrase}. "
        f"My experience includes building and shipping real systems end to end, "
        f"and I am comfortable owning problems from design through deployment.\n\n"
        f"{closer}"
    )
    if tone == "concise":
        # Trim to two short paragraphs.
        body = (
            f"{opener} My recent work covers {kw_phrase}, "
            f"with hands-on delivery across {skills or 'the stack you use'}.\n\n"
            f"{closer}"
        )
    header = name
    if contact["email"]:
        header += f" | {contact['email']}"
    if contact["phone"]:
        header += f" | {contact['phone']}"
    return f"{header}\n\nDear Hiring Manager,\n\n{body}\n\nSincerely,\n{name}"


def rule_based_outreach(resume_text, jd_text, tone="professional"):
    """Build a short cold-outreach message (LinkedIn/email style)."""
    if tone not in TONES:
        tone = "professional"
    contact = extract_contact(resume_text)
    keywords = _jd_keywords(jd_text)
    skills = _skills_line(resume_text)
    name = contact["name"] or "there"
    jd_first = (jd_text or "").strip().splitlines()[0][:80] if (jd_text or "").strip() else "the open role"
    kw = ", ".join(keywords[:3]) if keywords else "the stack"

    intros = {
        "professional": f"Hi, I hope you are well. I came across {jd_first} and wanted to reach out briefly.",
        "enthusiastic": f"Hi! I just saw {jd_first} and had to reach out — this looks like a great fit.",
        "concise": f"Hi — quick note on {jd_first}.",
    }
    return (
        f"{intros[tone]} I am {name}, working with {skills or kw}. "
        f"My recent work touches {kw}, closely aligned with what you are hiring for. "
        f"Would you be open to a 15-minute chat next week? Happy to share my resume."
    )


def validate_cover_inputs(payload):
    """Validate and normalize generator inputs. Returns (data, error)."""
    tone = (payload.get("tone") or "professional").strip().lower()
    if tone not in TONES:
        tone = "professional"
    jd_text = (payload.get("jd_text") or "").strip()
    resume_text = (payload.get("resume_text") or "").strip()
    version_id = payload.get("version_id")
    if not jd_text:
        return None, "Please paste the job description or describe the company/role."
    if len(jd_text) > 20000:
        return None, "The job description is too long (max 20,000 characters)."
    if resume_text and len(resume_text) > 50000:
        return None, "Resume text is too long (max 50,000 characters)."
    return ({
        "tone": tone,
        "jd_text": jd_text,
        "resume_text": resume_text,
        "version_id": version_id,
    }, None)


# ================= Feature 4 Ultimate Enhancements =================
# 4.1 Hiring-manager finder | 4.2 Follow-up sequencer | 4.3 Reply-rate optimizer

# Who to contact for a given role family.
_RECIPIENT_PLAYBOOK = [
    (re.compile(r"\b(engineer|developer|sde|backend|frontend|devops|data|ml|ai)\b", re.I),
     ["Engineering Manager", "Tech Lead", "VP Engineering", "Technical Recruiter"],
     "Engineering managers hire for skill; tech leads refer. Recruiters are the fallback."),
    (re.compile(r"\b(design|ux|ui|product designer)\b", re.I),
     ["Design Manager", "Head of Design", "Product Manager", "Design Recruiter"],
     "Design hiring is portfolio-driven — the hiring manager matters most."),
    (re.compile(r"\b(product|pm|program)\b", re.I),
     ["VP Product", "Group PM", "Founder (at startups)", "Product Recruiter"],
     "PM hiring is relationship-driven; warm intros beat cold mail."),
    (re.compile(r"\b(marketing|growth|content|seo)\b", re.I),
     ["Head of Marketing", "Growth Lead", "Founder", "Marketing Recruiter"],
     "Show one concrete growth idea in the first message."),
    (re.compile(r"\b(sales|account|bd|business)\b", re.I),
     ["VP Sales", "Sales Manager", "Founder", "Sales Recruiter"],
     "Numbers first: quota, pipeline, win rate."),
]
_GENERIC_RECIPIENTS = (["Hiring Manager", "Team Lead", "HR / Talent Team", "Recruiter"],
                       "No role pattern matched — start broad, then narrow.")


def suggest_recipients(role_title, company_name=""):
    """Who to send the outreach to. Returns {recipients, rationale, search_tips}."""
    role = _strip_html(role_title or "")
    company = _strip_html(company_name or "").strip()
    recipients, rationale = _GENERIC_RECIPIENTS
    for pattern, recs, why in _RECIPIENT_PLAYBOOK:
        if pattern.search(role):
            recipients, rationale = recs, why
            break
    tips = [
        f"LinkedIn search: {' '.join(recipients[0].split()[:2])} at {company}" if company
        else f"LinkedIn search: '{recipients[0]}' + your target company",
        "Prefer the hiring manager over HR — response rates are 3-5x higher.",
        "Check 'People' tab on the company's LinkedIn page, filter by title.",
    ]
    return {"role": role[:120], "company": company[:120],
            "recipients": recipients, "rationale": rationale,
            "search_tips": tips}


def followup_sequence(name, role_title, company_name="", tone="professional"):
    """Day-3 and day-7 follow-up drafts. Returns {followups: [{day, subject, body}]}."""
    if tone not in TONES:
        tone = "professional"
    name = _strip_html(name or "there").strip()[:60] or "there"
    role = _strip_html(role_title or "the role").strip()[:120] or "the role"
    company = _strip_html(company_name or "").strip()[:120]
    at_co = f" at {company}" if company else ""

    day3 = {
        "day": 3,
        "subject": f"Following up — {role}{at_co}",
        "body": (f"Hi {name}, just floating this back to the top of your inbox. "
                 f"I am excited about {role}{at_co} and would love 15 minutes to discuss "
                 f"how I can contribute. Happy to share my resume or work samples."),
    }
    day7 = {
        "day": 7,
        "subject": f"Last note — {role}{at_co}",
        "body": (f"Hi {name}, I will keep this brief — this is my last follow-up. "
                 f"If the timing is not right for {role}{at_co}, no worries at all. "
                 f"If things change, I would love to reconnect. Wishing you and the team well."),
    }
    if tone == "enthusiastic":
        day3["body"] = day3["body"].replace("just floating", "quickly bumping")
        day7["body"] = day7["body"].replace("I will keep this brief", "One last quick note")
    return {"followups": [day3, day7],
            "guidance": ("Send day-3 only if no reply. Day-7 is the breakup email — "
                         "never send a third follow-up; it hurts your brand.")}


# Personalization signals scored by the reply-rate optimizer.
_OUTREACH_SIGNALS = [
    ("uses_recipient_name", re.compile(r"\b(hi|hello|dear)\s+[A-Z][a-z]+", re.I),
     15, "Addresses the recipient by name"),
    ("company_specific", None, 15, "Mentions the company (pass company to check)"),
    ("specific_ask", re.compile(r"\b(15[-\s]?minute|call|chat|coffee|intro)\b", re.I),
     15, "Contains a specific, low-friction ask"),
    ("proof_point", re.compile(r"\d+\s*%|\d+\s*(users|projects|years)|shipped|built|led", re.I),
     15, "Includes a concrete proof point"),
    ("short_enough", None, 15, "Under 120 words (busy people skim)"),
    ("has_cta", re.compile(r"\b(would you|open to|let me know|happy to share)\b", re.I),
     10, "Ends with a clear call to action"),
    ("no_generic_flattery", re.compile(r"\b(passionate|synergy|guru|ninja|rockstar)\b", re.I),
     -10, "Avoids cringe buzzwords"),
    ("not_too_long", None, -15, "Penalty: over 200 words"),
]


def outreach_score(message, recipient_name="", company=""):
    """Score a cold-outreach message on reply-rate signals (0-100).

    Returns {score, grade, signals: [{label, points, hit}], fixes}.
    Never raises on hostile input.
    """
    msg = _strip_html(message or "")
    words = len(msg.split())
    signals = []
    total = 0
    fixes = []

    for key, pattern, pts, label in _OUTREACH_SIGNALS:
        if key == "company_specific":
            hit = bool(company and company.strip().lower() in msg.lower())
        elif key == "short_enough":
            hit = 0 < words <= 120
        elif key == "not_too_long":
            hit = words > 200
        else:
            hit = bool(pattern.search(msg))
        # Negative-point signals: hit means penalty applies.
        earned = pts if (hit == (pts > 0)) else 0
        if pts < 0:
            earned = pts if hit else 0
        total += earned
        signals.append({"label": label, "points": earned, "hit": bool(hit)})
        if not hit and pts > 0:
            fixes.append(label)

    total = max(0, min(100, total + 25))  # base 25 for sending anything sane
    grade = ("A — send it" if total >= 80 else
             "B — solid, small tweaks" if total >= 60 else
             "C — needs work" if total >= 40 else
             "D — rewrite before sending")
    return {"score": total, "grade": grade, "signals": signals,
            "fixes": fixes[:4], "word_count": words}
