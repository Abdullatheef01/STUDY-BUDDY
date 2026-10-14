"""Portfolio one-page builder (Wave 1 feature #12).

Helpers for validating portfolio payloads and generating unique public slugs.
All user content is length-bounded; URLs are restricted to http(s).
"""

import re
import unicodedata

MAX_NAME = 80
MAX_HEADLINE = 140
MAX_BIO = 600
MAX_SKILLS = 30
MAX_SKILL_LEN = 40
MAX_PROJECTS = 12
MAX_PROJECT_TITLE = 80
MAX_PROJECT_DESC = 400
MAX_LINKS = 8
MAX_LINK_LABEL = 40


def slugify(text):
    """Turn a display name into a URL-safe slug base."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:40] or "portfolio"


def _clean_url(url):
    """Return a safe http(s) URL or None."""
    url = (url or "").strip()
    if not url:
        return None
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return None
    if len(url) > 500 or any(c.isspace() for c in url):
        return None
    return url


def validate_portfolio_payload(payload):
    """Validate a portfolio save payload.

    Returns (data, error). data is the cleaned dict ready for storage;
    error is a human-readable message or None.
    """
    if not isinstance(payload, dict):
        return None, "Invalid portfolio data."
    display_name = (payload.get("display_name") or "").strip()
    if not display_name:
        return None, "Display name is required."
    if len(display_name) > MAX_NAME:
        return None, f"Display name must be {MAX_NAME} characters or fewer."
    headline = (payload.get("headline") or "").strip()
    if len(headline) > MAX_HEADLINE:
        return None, f"Headline must be {MAX_HEADLINE} characters or fewer."
    bio = (payload.get("bio") or "").strip()
    if len(bio) > MAX_BIO:
        return None, f"Bio must be {MAX_BIO} characters or fewer."

    raw_skills = payload.get("skills") or []
    if not isinstance(raw_skills, list):
        return None, "Skills must be a list."
    skills = []
    for s in raw_skills:
        s = (s or "").strip()
        if not s:
            continue
        if len(s) > MAX_SKILL_LEN:
            return None, f"Each skill must be {MAX_SKILL_LEN} characters or fewer."
        if s not in skills:
            skills.append(s)
    if len(skills) > MAX_SKILLS:
        return None, f"At most {MAX_SKILLS} skills allowed."

    raw_projects = payload.get("projects") or []
    if not isinstance(raw_projects, list):
        return None, "Projects must be a list."
    if len(raw_projects) > MAX_PROJECTS:
        return None, f"At most {MAX_PROJECTS} projects allowed."
    projects = []
    for p in raw_projects:
        if not isinstance(p, dict):
            return None, "Each project must be an object."
        title = (p.get("title") or "").strip()
        desc = (p.get("description") or "").strip()
        link = _clean_url(p.get("link"))
        if not title and not desc and not link:
            continue  # skip empty rows
        if not title:
            return None, "Each project needs a title."
        if len(title) > MAX_PROJECT_TITLE:
            return None, f"Project titles must be {MAX_PROJECT_TITLE} characters or fewer."
        if len(desc) > MAX_PROJECT_DESC:
            return None, f"Project descriptions must be {MAX_PROJECT_DESC} characters or fewer."
        projects.append({"title": title, "description": desc, "link": link})

    raw_links = payload.get("links") or []
    if not isinstance(raw_links, list):
        return None, "Links must be a list."
    if len(raw_links) > MAX_LINKS:
        return None, f"At most {MAX_LINKS} links allowed."
    links = []
    for ln in raw_links:
        if not isinstance(ln, dict):
            return None, "Each link must be an object."
        label = (ln.get("label") or "").strip()
        url = _clean_url(ln.get("url"))
        if not label and not url:
            continue
        if not label or not url:
            return None, "Each link needs both a label and a valid https:// URL."
        if len(label) > MAX_LINK_LABEL:
            return None, f"Link labels must be {MAX_LINK_LABEL} characters or fewer."
        links.append({"label": label, "url": url})

    return {
        "display_name": display_name,
        "headline": headline,
        "bio": bio,
        "skills": skills,
        "projects": projects,
        "links": links,
        "show_github": bool(payload.get("show_github")),
        "show_leetcode": bool(payload.get("show_leetcode")),
        "is_published": bool(payload.get("is_published")),
    }, None


def unique_slug(base, taken):
    """Return a unique slug given a base and a set of taken slugs."""
    base = slugify(base)
    if base not in taken:
        return base
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"
