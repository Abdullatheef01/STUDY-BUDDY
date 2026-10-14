"""LinkedIn profile grader (Wave 1 feature #5).

Deterministic, server-side scoring of PASTED LinkedIn profile text (we never
scrape LinkedIn). Score is 0-100 with a transparent breakdown:

  - headline strength ........... 20
  - about-section quality ........ 25
  - experience quantification .... 25
  - skills relevance ............. 15
  - completeness ................. 15

Gemini (wired in unified_app.py) produces polished fix suggestions when
available; the rule-based suggestions below are the guaranteed fallback.
"""

import re

MAX_FIELD_CHARS = 10000  # per pasted field
MIN_ABOUT_CHARS = 40

ACTION_VERBS = {
    "built", "led", "designed", "developed", "launched", "shipped", "drove",
    "improved", "increased", "reduced", "automated", "created", "owned",
    "delivered", "scaled", "optimized", "mentored", "architected",
    "implemented", "spearheaded", "managed", "coordinated", "streamlined",
    "pioneered", "achieved", "generated", "grew", "transformed",
}

NUMBER_RE = re.compile(r"\d+\s*(?:%|\+|k|K|million|years?|yrs?|months?|\+)?")
METRIC_RE = re.compile(
    r"\d[\d,]*\s*(?:%|percent|\+|x|X|k|K|million|users|customers|clients|"
    r"revenue|orders|requests|latency|uptime|conversion|traffic|followers)"
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _words(text):
    return re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*", text or "")


def _action_verb_hits(text):
    words = {w.lower() for w in _words(text)}
    return sorted(v for v in ACTION_VERBS if v in words)


def _score_headline(headline):
    """0-20: a headline should say what you do, not just a job title."""
    text = (headline or "").strip()
    score, notes = 0.0, []
    if not text:
        return 0.0, ["Add a headline - it is the first thing recruiters read."]
    n = len(text)
    if n >= 40:
        score += 8
    elif n >= 20:
        score += 5
        notes.append("Expand your headline past 40 characters so it says more than a job title.")
    else:
        notes.append("Your headline is very short - add your specialty and value proposition.")
    # Separators (| - •) signal a structured, keyword-rich headline.
    if re.search(r"[|•·\-–—]", text):
        score += 4
    else:
        notes.append("Use separators (| or •) to pack role + specialty + proof into your headline.")
    words = {w.lower() for w in _words(text)}
    verbs = ACTION_VERBS & words
    if verbs or any(k in text.lower() for k in ("engineer", "developer", "designer", "analyst",
                                                "manager", "scientist", "student", "intern")):
        score += 4
    else:
        notes.append("Include your target role or domain keyword in the headline.")
    if re.search(r"\d", text):
        score += 4
    else:
        notes.append("Add a number to your headline (years, projects shipped, users reached).")
    return round(min(20.0, score), 1), notes


def _score_about(about):
    """0-25: the About section should tell a story with proof."""
    text = (about or "").strip()
    score, notes = 0.0, []
    if not text:
        return 0.0, ["Write an About section - profiles with one get far more views."]
    n = len(text)
    if n >= 600:
        score += 10
    elif n >= 260:
        score += 7
    elif n >= MIN_ABOUT_CHARS:
        score += 4
        notes.append("Flesh out your About section (aim for 260+ characters with specifics).")
    else:
        notes.append("Your About section is too short to say anything meaningful - expand it.")
    verbs = _action_verb_hits(text)
    if len(verbs) >= 3:
        score += 6
    elif verbs:
        score += 3
        notes.append("Add more action verbs (built, led, shipped) to your About section.")
    else:
        notes.append("Your About section has no action verbs - rewrite it around what you did, not just who you are.")
    if METRIC_RE.search(text):
        score += 5
    else:
        notes.append("Add at least one quantified achievement to your About section.")
    if re.search(r"\b(i'm|i am|my|i've|i have)\b", text, re.I):
        score += 4
    else:
        notes.append("Write About in first person - it reads as authentic on LinkedIn.")
    return round(min(25.0, score), 1), notes


def _score_experience(experience):
    """0-25: experience bullets should show impact, quantified."""
    text = (experience or "").strip()
    score, notes = 0.0, []
    if not text:
        return 0.0, ["Add experience entries - even internships, projects, and freelance work count."]
    entries = [e for e in re.split(r"\n\s*\n", text) if e.strip()]
    if len(entries) >= 2:
        score += 6
    elif len(entries) == 1:
        score += 3
        notes.append("Add at least 2 experience entries (roles, internships, major projects).")
    metrics = METRIC_RE.findall(text)
    if len(metrics) >= 3:
        score += 9
    elif metrics:
        score += 5
        notes.append("Quantify more achievements - every bullet should ideally carry a number.")
    else:
        notes.append("No quantified results found - add numbers (%, users, revenue, time saved) to each role.")
    verbs = _action_verb_hits(text)
    if len(verbs) >= 4:
        score += 6
    elif verbs:
        score += 3
        notes.append("Start more bullets with strong action verbs instead of 'responsible for'.")
    else:
        notes.append("Avoid 'responsible for' phrasing - lead every bullet with an action verb.")
    if re.search(r"(19|20)\d{2}", text):
        score += 4
    else:
        notes.append("Add dates to each role - recruiters filter on recency.")
    return round(min(25.0, score), 1), notes


def _score_skills(skills):
    """0-15: skills should be specific and plentiful (but not stuffed)."""
    text = (skills or "").strip()
    score, notes = 0.0, []
    if not text:
        return 0.0, ["List your skills - it is the cheapest SEO on LinkedIn."]
    items = [s.strip() for s in re.split(r"[,;\n•·|]", text) if s.strip()]
    # Deduplicate case-insensitively.
    seen, uniq = set(), []
    for s in items:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    n = len(uniq)
    if 8 <= n <= 50:
        score += 9
    elif 4 <= n < 8:
        score += 6
        notes.append("Add more skills (aim for 8+ covering tools, languages, and soft skills).")
    elif n > 50:
        score += 5
        notes.append("Trim your skills list - 50 focused skills beat 100 vague ones.")
    else:
        notes.append("List at least 4 concrete skills, not just job titles.")
    techy = sum(1 for s in uniq if re.search(r"[+#]|js$|sql|api|cloud|data|ml|ai", s, re.I))
    if techy >= 3 or n >= 8:
        score += 6
    else:
        score += 3
        notes.append("Mix in specific tools/technologies alongside domain skills.")
    return round(min(15.0, score), 1), notes


def _score_completeness(headline, about, experience, skills):
    """0-15: every section filled, plus a way to contact you."""
    score, notes = 0.0, []
    filled = sum(bool((f or "").strip()) for f in (headline, about, experience, skills))
    score += filled * 3  # up to 12
    if filled < 4:
        notes.append("Fill every section - incomplete profiles are filtered out of recruiter searches.")
    combined = " ".join(f or "" for f in (headline, about, experience, skills))
    if EMAIL_RE.search(combined) or re.search(r"(portfolio|github\.com|linkedin\.com/in)", combined, re.I):
        score += 3
    else:
        notes.append("Add a contact email or portfolio/GitHub link somewhere on your profile.")
    return round(min(15.0, score), 1), notes


def grade_linkedin_profile(headline, about, experience, skills):
    """Grade pasted LinkedIn profile text. Returns a JSON-serializable report."""
    headline = (headline or "")[:MAX_FIELD_CHARS]
    about = (about or "")[:MAX_FIELD_CHARS]
    experience = (experience or "")[:MAX_FIELD_CHARS]
    skills = (skills or "")[:MAX_FIELD_CHARS]

    parts = {}
    all_notes = []
    parts["headline_strength"], n = _score_headline(headline)
    all_notes += [("Headline", x) for x in n]
    parts["about_quality"], n = _score_about(about)
    all_notes += [("About", x) for x in n]
    parts["experience_quantification"], n = _score_experience(experience)
    all_notes += [("Experience", x) for x in n]
    parts["skills_relevance"], n = _score_skills(skills)
    all_notes += [("Skills", x) for x in n]
    parts["completeness"], n = _score_completeness(headline, about, experience, skills)
    all_notes += [("Profile", x) for x in n]

    score = round(sum(parts.values()), 1)
    # Prioritize: weakest categories first, then completeness fixes.
    order = {"Headline": 0, "About": 1, "Experience": 2, "Skills": 3, "Profile": 4}
    suggestions = [
        {"section": sec, "fix": note}
        for sec, note in sorted(all_notes, key=lambda x: order.get(x[0], 9))
    ]
    return {
        "score": score,
        "breakdown": parts,
        "suggestions": suggestions[:10],
        "ai_powered": False,
    }


def generate_rule_based_summary(report):
    """One-line verdict for the report header."""
    score = report.get("score") or 0
    if score >= 85:
        return "Recruiter-ready. Polish the last few gaps and you are set."
    if score >= 70:
        return "Strong foundation. A few targeted fixes will make it stand out."
    if score >= 50:
        return "Decent start, but recruiters will scroll past the weak spots."
    return "Needs serious work - start with the highest-priority fixes below."


def validate_linkedin_inputs(payload):
    """Validate and normalize grader inputs. Returns (data, error)."""
    fields = {}
    for key in ("headline", "about", "experience", "skills"):
        val = (payload.get(key) or "").strip()
        if len(val) > MAX_FIELD_CHARS:
            return None, "The {} field is too long (max {:,} characters).".format(
                key, MAX_FIELD_CHARS)
        fields[key] = val
    if not any(fields.values()):
        return None, "Paste at least one profile section (headline, about, experience, or skills)."
    total = sum(len(v) for v in fields.values())
    if total < MIN_ABOUT_CHARS:
        return None, "That looks too short to grade - paste more of your profile."
    return fields, None
