"""GitHub profile integration: fetch public profile + repos, analyze, score.

Username-based — no credentials needed. An optional GITHUB_TOKEN env var
raises the API rate limit (60 -> 5000 requests/hour).
"""
import base64
import os
import re
from datetime import datetime, timezone

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
            "{} was not found on GitHub. Check the spelling and try again.".format(what))
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
    user = _get("/users/" + username, what="GitHub user '@{}'".format(username))
    repos = []
    page = 1
    while page <= 3:  # up to 300 repos is plenty for a profile snapshot
        batch = _get("/users/{}/repos".format(username),
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
        data = _get("/repos/{}/{}/readme".format(owner, repo_name), what="README")
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
        age_days = (datetime.now(timezone.utc) - latest).days
        activity_pts = 10 if age_days <= 30 else 6 if age_days <= 90 else 3 if age_days <= 365 else 0
        if age_days > 90:
            suggestions.append(
                "No pushes in {} days — push something small to show you're active.".format(age_days))
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
