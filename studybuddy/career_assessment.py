"""Career-discovery assessment (Wave 1 feature #7).

A guided 16-question quiz (interests / strengths / work-style / subjects).
Deterministic, server-side scoring: every answer option carries transparent
weights per career cluster; cluster match % = earned / max-possible.

Gemini (wired in unified_app.py) writes personalized "why you fit" blurbs
when available; the rule-based explanations below are the guaranteed
fallback.
"""

CLUSTERS = {
    "swe": {
        "name": "Software Development",
        "tagline": "Build the apps and systems the world runs on.",
        "skills": ["Python or Java", "Data structures & algorithms", "Git & collaboration", "System design basics"],
        "tools": ["JD-matched ATS scoring", "AI bullet rewriter", "GitHub analyzer", "LeetCode stats"],
        "tool_links": ["/resume#jd-match", "/resume#bullet-rewriter", "/profile", "/profile"],
    },
    "data_ai": {
        "name": "Data Science & AI/ML",
        "tagline": "Turn data into predictions and intelligent products.",
        "skills": ["Python", "Statistics & probability", "Machine learning (scikit-learn)", "SQL"],
        "tools": ["JD-matched ATS scoring", "LeetCode stats", "Application tracker"],
        "tool_links": ["/resume#jd-match", "/profile", "/tracker"],
    },
    "design": {
        "name": "UI/UX Design",
        "tagline": "Design experiences people love to use.",
        "skills": ["Figma", "UX research", "Visual hierarchy", "Prototyping"],
        "tools": ["LinkedIn grader", "Cover-letter generator"],
        "tool_links": ["/resume#linkedin-grader", "/resume#cover-generator"],
    },
    "security": {
        "name": "Cybersecurity",
        "tagline": "Defend systems and hunt vulnerabilities.",
        "skills": ["Networking basics", "Linux", "OWASP Top 10", "Python scripting"],
        "tools": ["GitHub analyzer", "LeetCode stats"],
        "tool_links": ["/profile", "/profile"],
    },
    "cloud": {
        "name": "Cloud & DevOps",
        "tagline": "Ship reliably and scale infrastructure.",
        "skills": ["Linux", "Docker", "CI/CD pipelines", "AWS basics"],
        "tools": ["GitHub analyzer", "JD-matched ATS scoring"],
        "tool_links": ["/profile", "/resume#jd-match"],
    },
    "pm": {
        "name": "Product Management",
        "tagline": "Decide what gets built and why.",
        "skills": ["Analytics", "Communication", "Roadmapping", "SQL basics"],
        "tools": ["Cover-letter generator", "LinkedIn grader", "Application tracker"],
        "tool_links": ["/resume#cover-generator", "/resume#linkedin-grader", "/tracker"],
    },
    "marketing": {
        "name": "Digital Marketing & Content",
        "tagline": "Tell stories that move people to act.",
        "skills": ["Copywriting", "SEO basics", "Analytics", "Content strategy"],
        "tools": ["Cover-letter generator", "LinkedIn grader"],
        "tool_links": ["/resume#cover-generator", "/resume#linkedin-grader"],
    },
    "analytics": {
        "name": "Business & Data Analytics",
        "tagline": "Answer business questions with data.",
        "skills": ["SQL", "Spreadsheets", "Data visualization", "Statistics"],
        "tools": ["JD-matched ATS scoring", "LinkedIn grader"],
        "tool_links": ["/resume#jd-match", "/resume#linkedin-grader"],
    },
}

# Each option maps to {cluster_id: points (0-2)}.
QUESTIONS = [
    # ---- Interests ----
    {"id": "q1", "dimension": "interests", "text": "Which weekend project sounds most fun?",
     "options": [
         {"text": "Building an app or website", "weights": {"swe": 2, "cloud": 1}},
         {"text": "Analyzing a dataset for hidden patterns", "weights": {"data_ai": 2, "analytics": 1}},
         {"text": "Redesigning an app's interface", "weights": {"design": 2, "pm": 1}},
         {"text": "Finding vulnerabilities in a system", "weights": {"security": 2, "swe": 1}},
     ]},
    {"id": "q2", "dimension": "interests", "text": "What kind of problems do you enjoy solving?",
     "options": [
         {"text": "Logic puzzles and algorithms", "weights": {"swe": 2, "data_ai": 1}},
         {"text": "Understanding why people behave a certain way", "weights": {"pm": 2, "marketing": 1, "design": 1}},
         {"text": "Making systems faster and more reliable", "weights": {"cloud": 2, "swe": 1}},
         {"text": "Spotting risks everyone else missed", "weights": {"security": 2, "analytics": 1}},
     ]},
    {"id": "q3", "dimension": "interests", "text": "Pick a headline you'd love about your work:",
     "options": [
         {"text": "\u201cApp used by a million people\u201d", "weights": {"swe": 2, "pm": 1}},
         {"text": "\u201cModel predicts with 99% accuracy\u201d", "weights": {"data_ai": 2, "analytics": 1}},
         {"text": "\u201cDesign wins a global award\u201d", "weights": {"design": 2, "marketing": 1}},
         {"text": "\u201cZero breaches, third year running\u201d", "weights": {"security": 2, "cloud": 1}},
     ]},
    {"id": "q4", "dimension": "interests", "text": "Which content do you binge?",
     "options": [
         {"text": "Coding tutorials and build videos", "weights": {"swe": 2}},
         {"text": "Data stories and visualizations", "weights": {"analytics": 2, "data_ai": 1}},
         {"text": "Design breakdowns", "weights": {"design": 2}},
         {"text": "Startup and product teardowns", "weights": {"pm": 2, "marketing": 1}},
     ]},
    # ---- Strengths ----
    {"id": "q5", "dimension": "strengths", "text": "What are you naturally good at?",
     "options": [
         {"text": "Breaking big problems into steps", "weights": {"swe": 2, "pm": 1}},
         {"text": "Math and statistics", "weights": {"data_ai": 2, "analytics": 2}},
         {"text": "Visual taste and aesthetics", "weights": {"design": 2, "marketing": 1}},
         {"text": "Being thorough and detail-oriented", "weights": {"security": 2, "cloud": 1}},
     ]},
    {"id": "q6", "dimension": "strengths", "text": "Friends ask you for help with\u2026",
     "options": [
         {"text": "Fixing their tech issues", "weights": {"cloud": 2, "swe": 1}},
         {"text": "Making sense of numbers", "weights": {"analytics": 2, "data_ai": 1}},
         {"text": "Making things look good", "weights": {"design": 2, "marketing": 1}},
         {"text": "Planning and organizing", "weights": {"pm": 2, "security": 1}},
     ]},
    {"id": "q7", "dimension": "strengths", "text": "Your superpower in group projects:",
     "options": [
         {"text": "Writing the core logic", "weights": {"swe": 2}},
         {"text": "Doing the research and analysis", "weights": {"analytics": 2, "data_ai": 1}},
         {"text": "Designing the product or pitch", "weights": {"design": 2, "marketing": 1}},
         {"text": "Keeping everyone on track", "weights": {"pm": 2, "cloud": 1}},
     ]},
    {"id": "q8", "dimension": "strengths", "text": "Which statement fits you best?",
     "options": [
         {"text": "\u201cI think in systems and flows\u201d", "weights": {"cloud": 2, "swe": 1}},
         {"text": "\u201cI question assumptions with data\u201d", "weights": {"data_ai": 2, "analytics": 1}},
         {"text": "\u201cI notice what others overlook visually\u201d", "weights": {"design": 2}},
         {"text": "\u201cI think about what could go wrong\u201d", "weights": {"security": 2, "pm": 1}},
     ]},
    # ---- Work style ----
    {"id": "q9", "dimension": "workstyle", "text": "Your ideal workday:",
     "options": [
         {"text": "Deep focus, headphones on, building", "weights": {"swe": 2, "security": 1}},
         {"text": "A mix of analysis and discussions", "weights": {"analytics": 2, "data_ai": 1, "pm": 1}},
         {"text": "Collaborative whiteboard sessions", "weights": {"design": 2, "pm": 2}},
         {"text": "On-call, solving live incidents", "weights": {"cloud": 2, "security": 1}},
     ]},
    {"id": "q10", "dimension": "workstyle", "text": "You prefer feedback that is\u2026",
     "options": [
         {"text": "Binary: it works or it doesn't", "weights": {"swe": 2, "cloud": 1}},
         {"text": "Driven by numbers", "weights": {"data_ai": 2, "analytics": 2}},
         {"text": "Qualitative and human", "weights": {"design": 2, "marketing": 1}},
         {"text": "Strategic and big-picture", "weights": {"pm": 2, "security": 1}},
     ]},
    {"id": "q11", "dimension": "workstyle", "text": "Pick a work setting:",
     "options": [
         {"text": "Solo builder with clear specs", "weights": {"swe": 2}},
         {"text": "Small team running fast experiments", "weights": {"pm": 2, "data_ai": 1}},
         {"text": "Studio-like creative team", "weights": {"design": 2, "marketing": 2}},
         {"text": "Mission-critical ops team", "weights": {"security": 2, "cloud": 2}},
     ]},
    {"id": "q12", "dimension": "workstyle", "text": "How do you feel about ambiguity?",
     "options": [
         {"text": "Love it \u2014 I'll define the problem", "weights": {"pm": 2, "design": 1}},
         {"text": "Fine, if I have data to explore", "weights": {"data_ai": 2, "analytics": 1}},
         {"text": "Prefer clear requirements", "weights": {"swe": 2, "security": 1}},
         {"text": "Thrive in controlled chaos", "weights": {"cloud": 2, "marketing": 1}},
     ]},
    # ---- Subjects ----
    {"id": "q13", "dimension": "subjects", "text": "Favorite subject in school or college:",
     "options": [
         {"text": "Computer science / programming", "weights": {"swe": 2, "cloud": 1}},
         {"text": "Mathematics / statistics", "weights": {"data_ai": 2, "analytics": 2}},
         {"text": "Art / design", "weights": {"design": 2, "marketing": 1}},
         {"text": "Business / economics", "weights": {"pm": 2, "analytics": 1, "marketing": 1}},
     ]},
    {"id": "q14", "dimension": "subjects", "text": "Which elective would you pick?",
     "options": [
         {"text": "Advanced algorithms", "weights": {"swe": 2, "security": 1}},
         {"text": "Machine learning", "weights": {"data_ai": 2, "analytics": 1}},
         {"text": "Human-computer interaction", "weights": {"design": 2, "pm": 1}},
         {"text": "Network security", "weights": {"security": 2, "cloud": 1}},
     ]},
    {"id": "q15", "dimension": "subjects", "text": "A hackathon theme that excites you:",
     "options": [
         {"text": "Build anything in 24 hours", "weights": {"swe": 2, "cloud": 1}},
         {"text": "Predict-a-thon", "weights": {"data_ai": 2, "analytics": 1}},
         {"text": "Design jam", "weights": {"design": 2, "marketing": 1}},
         {"text": "Capture the flag", "weights": {"security": 2}},
     ]},
    {"id": "q16", "dimension": "subjects", "text": "Which book title would you pick up?",
     "options": [
         {"text": "\u201cClean Code\u201d", "weights": {"swe": 2}},
         {"text": "\u201cStorytelling with Data\u201d", "weights": {"analytics": 2, "data_ai": 1, "marketing": 1}},
         {"text": "\u201cDon't Make Me Think\u201d", "weights": {"design": 2, "pm": 1}},
         {"text": "\u201cThe Phoenix Project\u201d", "weights": {"cloud": 2, "pm": 1}},
     ]},
]

QUESTION_IDS = [q["id"] for q in QUESTIONS]
TOP_N_CLUSTERS = 5


def _max_scores():
    """Max possible points per cluster across all questions."""
    maxima = {cid: 0 for cid in CLUSTERS}
    for q in QUESTIONS:
        best = {}
        for opt in q["options"]:
            for cid, pts in opt["weights"].items():
                best[cid] = max(best.get(cid, 0), pts)
        for cid, pts in best.items():
            maxima[cid] = maxima.get(cid, 0) + pts
    return maxima


MAX_SCORES = _max_scores()


def score_assessment(answers):
    """Score {question_id: option_index} answers. Returns ranked cluster results.

    Each result: {id, name, tagline, match (0-100), earned, possible,
    top_signals: [question texts where this cluster won points]}.
    """
    earned = {cid: 0 for cid in CLUSTERS}
    signals = {cid: [] for cid in CLUSTERS}
    for q in QUESTIONS:
        idx = answers.get(q["id"])
        if not isinstance(idx, int) or not 0 <= idx < len(q["options"]):
            continue
        opt = q["options"][idx]
        for cid, pts in opt["weights"].items():
            if pts > 0:
                earned[cid] = earned.get(cid, 0) + pts
                signals[cid].append(q["text"])
    results = []
    for cid, meta in CLUSTERS.items():
        possible = MAX_SCORES.get(cid, 1) or 1
        match = round(100.0 * earned.get(cid, 0) / possible, 1)
        results.append({
            "id": cid,
            "name": meta["name"],
            "tagline": meta["tagline"],
            "match": match,
            "earned": earned.get(cid, 0),
            "possible": possible,
            "skills": meta["skills"],
            "tools": meta["tools"],
            "tool_links": meta["tool_links"],
            "top_signals": signals[cid][:3],
            "why": "",  # filled by rule-based fallback or Gemini
        })
    results.sort(key=lambda r: (-r["match"], r["name"]))
    return results[:TOP_N_CLUSTERS]


def rule_based_why(cluster):
    """Deterministic 'why you fit' blurb from the user's own answers."""
    name = cluster["name"]
    signals = cluster.get("top_signals") or []
    if signals:
        quoted = "; ".join("you leaned toward building/creating in \u201c{}\u201d".format(s) for s in signals[:2])
        return ("Your answers point to {}: {} — a pattern that matches how {}s "
                "think and work.".format(name, quoted, name))
    return ("Your overall answer pattern aligns best with {} — explore its "
            "starter skills below to confirm the fit.".format(name))


def validate_assessment_inputs(payload):
    """Validate submitted answers. Returns (answers, error)."""
    raw = payload.get("answers")
    if not isinstance(raw, dict):
        return None, "Please answer all questions before submitting."
    answers = {}
    for q in QUESTIONS:
        if q["id"] not in raw:
            return None, "Please answer every question (missing: {}).".format(q["id"])
        try:
            idx = int(raw[q["id"]])
        except (TypeError, ValueError):
            return None, "Invalid answer for question {}.".format(q["id"])
        if not 0 <= idx < len(q["options"]):
            return None, "Invalid answer for question {}.".format(q["id"])
        answers[q["id"]] = idx
    return answers, None


def public_questions():
    """Questions safe to embed in the page (no scoring internals beyond weights)."""
    return [
        {"id": q["id"], "dimension": q["dimension"], "text": q["text"],
         "options": [o["text"] for o in q["options"]]}
        for q in QUESTIONS
    ]
