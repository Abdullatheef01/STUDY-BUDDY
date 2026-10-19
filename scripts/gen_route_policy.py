"""Generate tests/route_policy.yaml from current url_map.

Classification rules (secure-by-default):
- /api/* → auth (unless explicitly public)
- /account/*, /profile/*, /dashboard → auth
- /consent/* → auth
- Static pages (/, /privacy, /terms, /accessibility) → public
- /healthz, /readyz, /version → public (ops)
- /login, /register, /auth/* → public (entry points)
- Everything else → auth (secure by default)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["STUDYBUDDY_NO_PARSE_SANDBOX"] = "1"

from unified_app import create_app

PUBLIC_EXACT = {
    "/", "/privacy", "/terms", "/accessibility",
    "/healthz", "/readyz", "/version", "/health",
    "/login", "/register", "/logout",
    "/auth/google", "/auth/google/callback",
    "/csp-report",  # violation reports (rate-limited, no auth needed)
    "/analyze",  # SEC-12: intentionally public (TF-IDF only, no LLM)
    "/try",  # PROD-03: zero-friction demo
    # Read-only public APIs (static data, no user data, no LLM)
    "/api/coding-practice",
    "/api/coding-practice/<company>",
    "/api/companies",
    "/api/dsa/problems",
    "/api/interview-questions/<company>",
    "/api/star/examples",
    "/api/topics",
    "/cards/leetcode/<username>.svg",  # embeddable badge
    # Public feature landing pages (work for anonymous + authed)
    "/aptitude",
    "/coach",
    "/dsa",
    "/interview",
    "/learn",
    "/learn/certs",
    "/learn/certs/browse",
    "/learn/quizzes",
    "/learn/roadmaps",
    "/opportunities",
    "/forgot-password",  # SEC-09: public (for users who can't log in)
    "/reset-password/<token>",
}

PUBLIC_PREFIXES = (
    "/auth/",
    "/static/",
)

def classify(rule):
    if rule in PUBLIC_EXACT:
        return "public"
    for prefix in PUBLIC_PREFIXES:
        if rule.startswith(prefix):
            return "public"
    return "auth"


def main():
    app = create_app({"TESTING": True})
    rules = sorted(set(
        str(r.rule) for r in app.url_map.iter_rules()
        if "static" not in str(r.rule)))
    out = ["# TEST-05: Route policy — every endpoint classified.",
           "# public: no login needed | auth: login required",
           "# Generated; review manually. CI fails if a route is unlisted.",
           ""]
    for rule in rules:
        out.append(f'"{rule}": {classify(rule)}')
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tests", "route_policy.yaml")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"Wrote {path} ({len(rules)} routes)")


if __name__ == "__main__":
    main()
