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


def rule_based_cover_letter(resume_text, jd_text, tone="professional"):
    """Build a tailored cover letter from templates (fallback path)."""
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
