"""LeetCode profile integration via the public GraphQL endpoint.

Username-based — no credentials needed. Includes an SVG stat-card generator
(github-readme-stats style) served at /cards/leetcode/<username>.svg.
"""
import re
import time
from html import escape as _xml_escape

import requests

_GQL = "https://leetcode.com/graphql"
_TIMEOUT = 10

# LeetCode usernames: letters, digits, underscore, hyphen (max 39 chars).
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,38}$")

_PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking }
    submitStatsGlobal {
      acSubmissionNum { difficulty count }
    }
    badges { displayName }
  }
  userContestRanking(username: $username) {
    rating
    globalRanking
    attendedContestsCount
    topPercentage
  }
}
"""

# Tiny in-memory cache for the public SVG card (username -> (stats, epoch)).
_CARD_CACHE = {}
_CARD_CACHE_TTL = 600
_CARD_CACHE_MAX = 200


class LeetCodeAPIError(Exception):
    """A LeetCode API failure with a user-safe message (safe to show clients)."""


def validate_leetcode_username(username):
    """Return the normalized username or raise LeetCodeAPIError."""
    u = (username or "").strip()
    if not _USERNAME_RE.match(u):
        raise LeetCodeAPIError(
            "That doesn't look like a valid LeetCode username. "
            "Use letters, numbers, underscores and hyphens (max 39 characters).")
    return u


def fetch_leetcode_stats(username):
    """Fetch public stats for a LeetCode user. Returns a stats dict.

    Raises LeetCodeAPIError on bad usernames or fetch problems.
    """
    username = validate_leetcode_username(username)
    try:
        resp = requests.post(
            _GQL,
            json={"query": _PROFILE_QUERY, "variables": {"username": username}},
            headers={"Content-Type": "application/json",
                     "User-Agent": "acra-student-platform",
                     "Referer": "https://leetcode.com"},
            timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise LeetCodeAPIError(
            "Could not reach LeetCode right now. Check your connection and try again."
        ) from e
    if not resp.ok:
        raise LeetCodeAPIError("LeetCode returned an unexpected response. Please try again later.")
    try:
        payload = resp.json()
    except ValueError as e:
        raise LeetCodeAPIError("LeetCode returned an unreadable response. Please try again.") from e
    data = (payload or {}).get("data") or {}
    matched = data.get("matchedUser")
    if not matched:
        raise LeetCodeAPIError(
            f"LeetCode user '{username}' was not found. Check the spelling and try again.")

    solved = {"easy": 0, "medium": 0, "hard": 0, "total": 0}
    stats_global = matched.get("submitStatsGlobal") or {}
    for row in stats_global.get("acSubmissionNum") or []:
        diff = str(row.get("difficulty") or "").lower()
        count = int(row.get("count") or 0)
        if diff in solved:
            solved[diff] = count
            if diff != "total":
                solved["total"] += count

    profile = matched.get("profile") or {}
    contest = data.get("userContestRanking") or {}
    badges = [b.get("displayName") for b in (matched.get("badges") or []) if b.get("displayName")]

    return {
        "username": username,
        "ranking": profile.get("ranking"),
        "solved": solved,
        "rating": round(contest.get("rating"), 1) if contest.get("rating") else None,
        "global_rank": contest.get("globalRanking"),
        "contests": contest.get("attendedContestsCount") or 0,
        "badges": badges[:12],
    }


def get_card_stats(username):
    """Stats for the SVG card with a short in-memory cache (kind to LeetCode)."""
    now = time.monotonic()
    hit = _CARD_CACHE.get(username.lower())
    if hit and now - hit[1] < _CARD_CACHE_TTL:
        return hit[0]
    stats = fetch_leetcode_stats(username)
    if len(_CARD_CACHE) >= _CARD_CACHE_MAX:
        _CARD_CACHE.clear()
    _CARD_CACHE[username.lower()] = (stats, now)
    return stats


def _esc(text):
    return _xml_escape(str(text if text is not None else ""))


def render_leetcode_card_svg(stats):
    """Render a dark stat card (github-readme-stats style). Returns SVG text."""
    username = _esc(stats.get("username", ""))
    solved = stats.get("solved") or {}
    easy, med, hard = solved.get("easy", 0), solved.get("medium", 0), solved.get("hard", 0)
    total = solved.get("total", 0) or (easy + med + hard)
    rating = stats.get("rating")
    crank = stats.get("global_rank")
    contests = stats.get("contests", 0)

    def bar(value, maximum, color, y):
        pct = min(100.0, (100.0 * value / maximum)) if maximum else 0
        return (
            f'<rect x="20" y="{y}" width="220" height="8" rx="4" fill="#1e2235"/>'
            f'<rect x="20" y="{y}" width="{2.2 * pct:.1f}" height="8" rx="4" fill="{color}"/>'
        )

    def row(label, value, color, y):
        return (
            f'<text x="20" y="{y}" fill="#94a3b8" font-size="12" font-family="Inter,sans-serif">{_esc(label)}</text>'
            f'<text x="380" y="{y}" fill="{color}" font-size="13" font-weight="700" text-anchor="end" font-family="Inter,sans-serif">{_esc(value)}</text>'
            f'{bar(value, max(total, 1), color, y + 8)}'
        )

    rating_line = "Rating " + (str(rating) if rating else "—")
    if crank:
        rating_line += "  ·  Rank #" + str(crank)

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="218" viewBox="0 0 400 218" role="img" aria-label="LeetCode stats for {u}">'
        '<rect width="400" height="218" rx="14" fill="#0a0b1e"/>'
        '<rect width="400" height="218" rx="14" fill="none" stroke="rgba(255,255,255,0.12)"/>'
        '<text x="20" y="34" fill="#f8fafc" font-size="17" font-weight="800" font-family="Outfit,Inter,sans-serif">{u}</text>'
        '<text x="20" y="54" fill="#22d3ee" font-size="12" font-family="Inter,sans-serif">LeetCode Stats</text>'
        '<text x="380" y="34" fill="#f8fafc" font-size="22" font-weight="800" text-anchor="end" font-family="Outfit,Inter,sans-serif">{total}</text>'
        '<text x="380" y="54" fill="#94a3b8" font-size="11" text-anchor="end" font-family="Inter,sans-serif">solved</text>'
        '{r1}{r2}{r3}'
        '<text x="20" y="196" fill="#94a3b8" font-size="12" font-family="Inter,sans-serif">{rating}</text>'
        '<text x="380" y="196" fill="#94a3b8" font-size="12" text-anchor="end" font-family="Inter,sans-serif">{contests} contests</text>'
        '</svg>'
    ).format(
        u=username, total=_esc(total),
        r1=row("Easy", easy, "#10b981", 84),
        r2=row("Medium", med, "#f59e0b", 122),
        r3=row("Hard", hard, "#ec4899", 160),
        rating=_esc(rating_line), contests=_esc(contests),
    )


def render_error_svg(message):
    """Small graceful-degradation card when stats can't be fetched."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="90" viewBox="0 0 400 90" role="img">'
        '<rect width="400" height="90" rx="14" fill="#0a0b1e"/>'
        '<rect width="400" height="90" rx="14" fill="none" stroke="rgba(255,255,255,0.12)"/>'
        '<text x="20" y="38" fill="#f8fafc" font-size="14" font-weight="700" font-family="Inter,sans-serif">LeetCode Stats</text>'
        f'<text x="20" y="62" fill="#94a3b8" font-size="12" font-family="Inter,sans-serif">{_esc(message[:90])}</text>'
        '</svg>'
    )
