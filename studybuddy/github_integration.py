"""GitHub profile integration: fetch public profile + repos, analyze, score.

Username-based — no credentials needed. An optional GITHUB_TOKEN env var
raises the API rate limit (60 -> 5000 requests/hour).
"""
import base64
import os
import re
from datetime import UTC, datetime

import requests

_API = "https://api.github.com"
_TIMEOUT = 10

# GitHub usernames: alphanumeric + hyphens, max 39 chars, no leading/trailing hyphen.
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")

_README_KEYWORDS = ("install", "usage", "getting started", "quickstart",
                    "example", "contributing", "how to", "setup")


class GithubAPIError(Exception):
    """A GitHub API failure with a user-safe message (safe to show clients)."""


def validate_github_username(username):
    """Return the normalized username or raise GithubAPIError."""
    u = (username or "").strip()
    if not _USERNAME_RE.match(u):
        raise GithubAPIError(
            "That doesn't look like a valid GitHub username. "
            "Use letters, numbers and single hyphens (max 39 characters).")
    return u


def _headers():
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "acra-student-platform"}
    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _get(path, params=None, what="GitHub"):
    """GET a GitHub API path; raises GithubAPIError with friendly messages."""
    try:
        resp = requests.get(_API + path, headers=_headers(),
                            params=params, timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise GithubAPIError(
            "Could not reach GitHub right now. Check your connection and try again."
        ) from e
    if resp.status_code == 404:
        raise GithubAPIError(
            f"{what} was not found on GitHub. Check the spelling and try again.")
    if resp.status_code == 403:
        body = (resp.text or "").lower()
        if "rate limit" in body or resp.headers.get("X-RateLimit-Remaining") == "0":
            raise GithubAPIError(
                "GitHub's API rate limit was hit. Please try again in a few minutes.")
        raise GithubAPIError("GitHub refused the request. Please try again later.")
    if resp.status_code == 401:
        raise GithubAPIError("GitHub rejected the API credentials. Please try again later.")
    if not resp.ok:
        raise GithubAPIError(
            "GitHub returned an unexpected response. Please try again later.")
    try:
        return resp.json()
    except ValueError as e:
        raise GithubAPIError("GitHub returned an unreadable response. Please try again.") from e


def fetch_github_profile(username):
    """Fetch public user profile + owned (non-fork) repos. Returns dict."""
    username = validate_github_username(username)
    user = _get("/users/" + username, what=f"GitHub user '@{username}'")
    repos = []
    page = 1
    while page <= 3:  # up to 300 repos is plenty for a profile snapshot
        batch = _get(f"/users/{username}/repos",
                     params={"per_page": 100, "page": page,
                             "type": "owner", "sort": "pushed"},
                     what="repositories")
        if not batch:
            break
        repos.extend(r for r in batch if not r.get("fork"))
        if len(batch) < 100:
            break
        page += 1
    return {"username": username, "user": user, "repos": repos}


def _readme_quality(owner, repo_name):
    """Heuristic README check for one repo: exists? length? useful sections?"""
    try:
        data = _get(f"/repos/{owner}/{repo_name}/readme", what="README")
    except GithubAPIError:
        return {"exists": False, "length": 0, "has_sections": False}
    try:
        text = base64.b64decode(data.get("content", "") or "").decode("utf-8", "ignore")
    except Exception:
        text = ""
    lowered = text.lower()
    return {
        "exists": True,
        "length": len(text),
        "has_sections": any(k in lowered for k in _README_KEYWORDS),
    }


def _parse_github_time(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def analyze_github_profile(username):
    """Fetch and score a GitHub profile 0-100.

    Returns a dict with score, per-category breakdown, concrete suggestions,
    and a compact snapshot payload (suitable for DB caching).
    Raises GithubAPIError on any fetch problem.
    """
    fetched = fetch_github_profile(username)
    username = fetched["username"]
    user = fetched["user"]
    repos = fetched["repos"]

    breakdown = {}
    suggestions = []

    # --- 1. Profile completeness (25) ---
    completeness = 0
    if (user.get("bio") or "").strip():
        completeness += 10
    else:
        suggestions.append("Add a bio to your GitHub profile — one line about what you build.")
    if (user.get("location") or "").strip():
        completeness += 5
    else:
        suggestions.append("Add your location — recruiters filter by it.")
    if (user.get("blog") or "").strip():
        completeness += 5
    else:
        suggestions.append("Link a portfolio, blog or LinkedIn in the website field.")
    if (user.get("company") or "").strip():
        completeness += 5
    else:
        suggestions.append("Add your college or company — it adds credibility at a glance.")
    breakdown["Profile completeness"] = completeness

    # --- 2. Repository count (20) ---
    n_repos = len(repos)
    repo_pts = 20 if n_repos >= 15 else 14 if n_repos >= 8 else 8 if n_repos >= 3 else 4 if n_repos >= 1 else 0
    breakdown["Repositories"] = repo_pts
    if n_repos < 3:
        suggestions.append(
            "You have {} public repo{}. Aim for at least 3 showcase projects.".format(
                n_repos, "" if n_repos == 1 else "s"))

    # --- 3. Total stars (20) ---
    total_stars = sum(int(r.get("stargazers_count") or 0) for r in repos)
    star_pts = (20 if total_stars >= 100 else 15 if total_stars >= 50
                else 10 if total_stars >= 20 else 6 if total_stars >= 5
                else 3 if total_stars >= 1 else 0)
    breakdown["Community stars"] = star_pts

    # --- 4. Language diversity (15) ---
    languages = {r.get("language") for r in repos if r.get("language")}
    lang_pts = (15 if len(languages) >= 5 else 12 if len(languages) >= 4
                else 9 if len(languages) >= 3 else 6 if len(languages) >= 2
                else 3 if len(languages) == 1 else 0)
    breakdown["Language diversity"] = lang_pts
    if len(languages) < 2 and repos:
        suggestions.append("Show range: projects in a second language signal versatility.")

    # --- 5. README quality (10) — top 5 repos by stars ---
    top_repos = sorted(repos, key=lambda r: int(r.get("stargazers_count") or 0),
                       reverse=True)[:5]
    readme_pts = 0
    for repo in top_repos:
        q = _readme_quality(username, repo.get("name", ""))
        if q["exists"]:
            readme_pts += 1
            if q["length"] > 1000 or q["has_sections"]:
                readme_pts += 1
            elif q["length"] < 300:
                suggestions.append(
                    "Repo '{}' has a thin README — add install steps and a usage example.".format(
                        repo.get("name")))
        else:
            suggestions.append(
                "Repo '{}' has no README — add one with what it does and how to run it.".format(
                    repo.get("name")))
    readme_pts = min(readme_pts, 10)
    breakdown["README quality"] = readme_pts

    # --- 6. Recent activity (10) ---
    pushed = [t for t in (_parse_github_time(r.get("pushed_at")) for r in repos) if t]
    activity_pts = 0
    if pushed:
        latest = max(pushed)
        age_days = (datetime.now(UTC) - latest).days
        activity_pts = 10 if age_days <= 30 else 6 if age_days <= 90 else 3 if age_days <= 365 else 0
        if age_days > 90:
            suggestions.append(
                f"No pushes in {age_days} days — push something small to show you're active.")
    else:
        suggestions.append("Push your work regularly — an active contribution graph builds trust.")
    breakdown["Recent activity"] = activity_pts

    score = sum(breakdown.values())
    if not suggestions:
        suggestions.append("Strong profile — keep shipping and pin your best 6 repos.")

    snapshot = {
        "username": username,
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
        "bio": user.get("bio"),
        "public_repos": user.get("public_repos", n_repos),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "total_stars": total_stars,
        "languages": sorted(languages),
        "top_repos": [
            {"name": r.get("name"), "stars": int(r.get("stargazers_count") or 0),
             "language": r.get("language"), "url": r.get("html_url"),
             "description": (r.get("description") or "")[:140]}
            for r in top_repos
        ],
    }
    return {
        "username": username,
        "score": score,
        "breakdown": breakdown,
        "suggestions": suggestions[:8],
        "snapshot": snapshot,
    }


# ================= Feature 6 Ultimate Enhancements =================
# 6.1 README grader | 6.2 Contribution story builder | 6.3 Pin optimizer

# What recruiters look for in a README (in order of impact).
_README_SECTIONS = [
    ("one_line_pitch", re.compile(r"^#\s+.+", re.M), 15,
     "Title + one-line pitch at the top"),
    ("what_it_does", re.compile(r"\b(what|overview|about|description)\b.{0,30}:", re.I), 10,
     "A 'what this does' section"),
    ("demo_link", re.compile(r"\b(demo|live|try it|playground)\b.{0,40}https?://", re.I), 20,
     "A live demo link (recruiters click, don't clone)"),
    ("screenshots", re.compile(r"!\[.*?\]\(.*?\)|<img", re.I), 10,
     "Screenshots or GIFs"),
    ("tech_stack", re.compile(r"\b(tech stack|built with|technologies)\b", re.I), 10,
     "Tech stack listed"),
    ("how_to_run", re.compile(r"\b(install|getting started|quickstart|usage|run)\b", re.I), 15,
     "Install / how-to-run instructions"),
    ("features", re.compile(r"\b(features)\b", re.I), 10,
     "Feature list"),
    ("metrics", re.compile(r"\d+\s*(users|stars|downloads|requests|ms|%)", re.I), 10,
     "Numbers that prove impact"),
]


def grade_readme(readme_text):
    """Grade a README the way a recruiter scans it (0-100).

    Returns {score, grade, checks: [{label, points, hit}], fixes, verdict}.
    Never raises on hostile input.
    """
    text = re.sub(r"<script[^>]*>.*?</script>", "", readme_text or "",
                  flags=re.I | re.S)
    checks = []
    total = 0
    fixes = []
    for _key, pattern, pts, label in _README_SECTIONS:
        try:
            hit = bool(pattern.search(text))
        except Exception:
            hit = False
        earned = pts if hit else 0
        total += earned
        checks.append({"label": label, "points": earned, "max": pts,
                       "hit": hit})
        if not hit:
            fixes.append(label)
    # Length sanity: too short = no substance.
    words = len(text.split())
    if words < 50:
        total -= 10
        fixes.insert(0, "README is too short — add substance (aim 150+ words)")
    total = max(0, min(100, total))
    grade = ("A — recruiter-ready" if total >= 80 else
             "B — good, polish needed" if total >= 60 else
             "C — thin" if total >= 40 else
             "D — rewrite it")
    return {"score": total, "grade": grade, "checks": checks,
            "fixes": fixes[:5], "word_count": words,
            "verdict": ("Add a demo link — it's the single highest-impact fix."
                        if not checks[2]["hit"] else
                        "Solid README." if total >= 70 else
                        "Work through the fixes above.")}


# Commit message -> resume bullet patterns.
_COMMIT_PATTERNS = [
    (re.compile(r"\b(add|implement|create|build)\b(.{5,80})", re.I),
     "Built{}"),
    (re.compile(r"\b(fix|resolve|patch)\b(.{5,80})", re.I),
     "Fixed{}"),
    (re.compile(r"\b(refactor|optimize|improve|speed up)\b(.{5,80})", re.I),
     "Improved{}"),
    (re.compile(r"\b(migrate|upgrade)\b(.{5,80})", re.I),
     "Migrated{}"),
    (re.compile(r"\b(test|add tests|coverage)\b(.{5,80})", re.I),
     "Added tests for{}"),
]


def commit_messages_to_bullets(commit_messages, repo_name=""):
    """Turn commit history into resume bullets.

    commit_messages: list of strings. Returns {bullets, skipped}.
    Picks the most substantial commits, dedupes themes.
    """
    if not isinstance(commit_messages, (list, tuple)):
        raise ValueError("commit_messages must be a list of strings.")
    repo = re.sub(r"<[^>]*>", "", repo_name or "").strip()[:60]
    seen_themes = set()
    bullets = []
    skipped = 0
    for msg in commit_messages:
        if not isinstance(msg, str):
            skipped += 1
            continue
        clean = re.sub(r"<[^>]*>", "", msg).strip()
        if len(clean) < 12 or len(clean) > 300:
            skipped += 1
            continue
        low = clean.lower()
        # Skip noise commits.
        if re.match(r"^(merge|wip|tmp|fix typo|update readme\.?$)", low):
            skipped += 1
            continue
        bullet = None
        for pattern, template in _COMMIT_PATTERNS:
            m = pattern.search(clean)
            if m:
                rest = m.group(2).strip().rstrip(".")
                theme = rest.split()[0] if rest.split() else ""
                if theme in seen_themes:
                    break
                seen_themes.add(theme)
                bullet = template.format(" " + rest)
                break
        if not bullet:
            # Generic but honest fallback.
            words = clean.split()
            theme = words[0] if words else ""
            if theme.lower() in seen_themes:
                skipped += 1
                continue
            seen_themes.add(theme.lower())
            bullet = "Shipped: " + clean[0].upper() + clean[1:]
        if repo:
            bullet += f" [{repo}]"
        bullets.append(bullet[:200])
        if len(bullets) >= 8:
            break
    return {"bullets": bullets, "skipped": skipped,
            "tip": "Add numbers to 2-3 of these (users, %, time saved) before putting them on your resume."}


def pin_optimizer(repos, target_role=""):
    """Which 6 repos to pin for a target role.

    repos: list of {name, description, language, stars, updated_at, topics}.
    Scores: role-keyword match (40) + recency (20) + stars (15) +
            has description (15) + has demo/readme signal (10).
    Returns ranked list with {name, score, reasons}.
    """
    if not isinstance(repos, (list, tuple)):
        raise ValueError("repos must be a list of repo dicts.")
    role_kw = set(re.findall(r"[a-z]{3,}", _clean_role(target_role).lower()))

    ranked = []
    for r in repos:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or "")[:100]
        if not name:
            continue
        desc = str(r.get("description") or "").lower()
        lang = str(r.get("language") or "").lower()
        topics = " ".join(str(t) for t in (r.get("topics") or [])).lower()
        blob = f"{name} {desc} {lang} {topics}".lower()
        score = 0
        reasons = []
        hits = [kw for kw in role_kw if kw in blob]
        if hits and role_kw:
            pts = min(40, len(hits) * 10)
            score += pts
            reasons.append(f"Matches role keywords: {', '.join(hits[:4])} (+{pts})")
        try:
            stars = int(r.get("stars") or 0)
        except (TypeError, ValueError):
            stars = 0
        if stars >= 10:
            score += 15
            reasons.append(f"{stars} stars (+15)")
        elif stars >= 1:
            score += 8
            reasons.append(f"{stars} stars (+8)")
        if desc.strip():
            score += 15
            reasons.append("Has description (+15)")
        else:
            reasons.append("No description — add one (-15 missed)")
        # Recency: updated within 6 months.
        upd = str(r.get("updated_at") or "")
        if re.match(r"20(2[4-9]|[3-9]\d)", upd):
            score += 20
            reasons.append("Recently updated (+20)")
        if "demo" in desc or "live" in desc:
            score += 10
            reasons.append("Mentions demo (+10)")
        ranked.append({"name": name, "score": min(100, score),
                       "reasons": reasons, "language": lang or "unknown"})
    ranked.sort(key=lambda x: -x["score"])
    picks = ranked[:6]
    return {"picks": picks,
            "pinned_names": [p["name"] for p in picks],
            "guidance": ("Pin these 6 in this order. Your top-2 pins get 80% of "
                         "recruiter clicks — make sure they have READMEs with demo links.")}


def _clean_role(role):
    return re.sub(r"<[^>]*>", "", role or "")
