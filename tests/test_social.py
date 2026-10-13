"""Tests for social login (Google OAuth) + GitHub/LeetCode profile integrations."""
import base64
from unittest.mock import MagicMock

import pytest

import github_integration
import leetcode_integration
import unified_app
from unified_app import create_app, db, User, ProfileSnapshot


def make_app(**overrides):
    cfg = {"TESTING": True,
           "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
           "SECRET_KEY": "test-secret-key",
           "WTF_CSRF_ENABLED": False}
    cfg.update(overrides)
    return create_app(cfg)


def set_google_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")


def clear_google_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)


def mock_google_client(monkeypatch, userinfo):
    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {"access_token": "tok"}
    mock_google.userinfo.return_value = userinfo
    monkeypatch.setattr(unified_app.oauth, "google", mock_google, raising=False)
    return mock_google


GOOD_USERINFO = {"sub": "google-123", "email": "guser@example.com",
                 "email_verified": True, "name": "G User",
                 "picture": "https://example.com/pic.png"}


def register_login(client, name="Aarav Sharma", email="aarav@example.com",
                   password="password123"):
    client.post("/register", data={"name": name, "email": email,
                                   "password": password})
    return client.post("/login", data={"email": email, "password": password})


# ---------- Google OAuth: hidden when unconfigured ----------

def test_google_routes_hidden_when_unconfigured(client, monkeypatch):
    clear_google_env(monkeypatch)
    app2 = make_app()
    c2 = app2.test_client()
    assert c2.get("/auth/google/login").status_code == 404
    assert c2.get("/auth/google/callback").status_code == 404
    assert b"Continue with Google" not in c2.get("/login").data


def test_google_button_shown_when_configured(monkeypatch):
    set_google_env(monkeypatch)
    app = make_app()
    assert b"Continue with Google" in app.test_client().get("/login").data


# ---------- Google OAuth: mocked flows ----------

def test_google_oauth_creates_new_user(monkeypatch):
    set_google_env(monkeypatch)
    app = make_app()
    mock_google_client(monkeypatch, GOOD_USERINFO)
    c = app.test_client()
    r = c.get("/auth/google/callback", follow_redirects=False)
    assert r.status_code == 302 and "/dashboard" in r.headers["Location"]
    with app.app_context():
        user = User.query.filter_by(email="guser@example.com").first()
        assert user is not None
        assert user.google_sub == "google-123"
        assert user.avatar_url == "https://example.com/pic.png"
        # password login must NOT work for a Google-created account
        assert not user.check_password("anything")


def test_google_oauth_links_existing_email_account(monkeypatch):
    set_google_env(monkeypatch)
    app = make_app()
    c = app.test_client()
    register_login(c, email="guser@example.com")
    c.post("/logout")
    mock_google_client(monkeypatch, GOOD_USERINFO)
    c.get("/auth/google/callback")
    with app.app_context():
        users = User.query.filter_by(email="guser@example.com").all()
        assert len(users) == 1  # never duplicated
        assert users[0].google_sub == "google-123"


def test_google_oauth_login_existing_google_user(monkeypatch):
    set_google_env(monkeypatch)
    app = make_app()
    mock_google_client(monkeypatch, GOOD_USERINFO)
    c = app.test_client()
    c.get("/auth/google/callback")
    c.post("/logout")
    r = c.get("/auth/google/callback", follow_redirects=False)
    assert r.status_code == 302 and "/dashboard" in r.headers["Location"]
    with app.app_context():
        assert User.query.filter_by(email="guser@example.com").count() == 1


def test_google_oauth_failure_redirects_to_login(monkeypatch):
    set_google_env(monkeypatch)
    app = make_app()
    mock_google = MagicMock()
    mock_google.authorize_access_token.side_effect = Exception("bad state")
    monkeypatch.setattr(unified_app.oauth, "google", mock_google, raising=False)
    c = app.test_client()
    r = c.get("/auth/google/callback", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


# ---------- GitHub integration (mocked API) ----------

class _FakeResp:
    def __init__(self, payload=None, status=200, rate_limited=False):
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = "rate limit exceeded" if rate_limited else ""
        self.headers = {"X-RateLimit-Remaining": "0" if rate_limited else "59"}

    def json(self):
        return self._payload


_FAKE_GH_USER = {"login": "octocat", "name": "The Octocat", "bio": "GitHub mascot",
                 "location": "San Francisco", "blog": "https://github.blog",
                 "company": "GitHub", "avatar_url": "https://example.com/a.png",
                 "public_repos": 8, "followers": 100, "following": 5}
_FAKE_GH_REPOS = [
    {"name": "hello-world", "stargazers_count": 50, "language": "Python",
     "pushed_at": "2026-10-01T00:00:00Z", "fork": False,
     "html_url": "https://github.com/octocat/hello-world", "description": "demo"},
    {"name": "js-tool", "stargazers_count": 10, "language": "JavaScript",
     "pushed_at": "2026-09-01T00:00:00Z", "fork": False,
     "html_url": "https://github.com/octocat/js-tool", "description": ""},
    {"name": "tiny", "stargazers_count": 0, "language": "Python",
     "pushed_at": "2025-01-01T00:00:00Z", "fork": False,
     "html_url": "https://github.com/octocat/tiny", "description": None},
    {"name": "forked-big", "stargazers_count": 999, "language": "Go",
     "pushed_at": "2026-10-01T00:00:00Z", "fork": True,
     "html_url": "https://github.com/octocat/forked-big", "description": ""},
]
_FAKE_README = {"content": base64.b64encode(
    b"# Hello\n\n## Install\n\npip install x\n\n## Usage\n\nrun it\n").decode()}


def _fake_gh_get(url, headers=None, params=None, timeout=None):
    if url.endswith("/users/octocat"):
        return _FakeResp(_FAKE_GH_USER)
    if url.endswith("/users/octocat/repos"):
        return _FakeResp(_FAKE_GH_REPOS)
    if "/readme" in url:
        return _FakeResp(_FAKE_README)
    if "/users/nonexistent-user-xyz" in url:
        return _FakeResp(None, status=404)
    return _FakeResp(None, status=404)


def test_github_analyzer_scoring_mocked(monkeypatch):
    monkeypatch.setattr(github_integration.requests, "get", _fake_gh_get)
    result = github_integration.analyze_github_profile("octocat")
    assert result["username"] == "octocat"
    assert result["breakdown"]["Profile completeness"] == 25  # bio+loc+blog+company
    assert result["breakdown"]["Repositories"] == 8  # 3 non-fork repos
    assert result["breakdown"]["Community stars"] == 15  # 60 stars total
    assert result["breakdown"]["Language diversity"] == 6  # Python + JavaScript
    assert result["score"] == sum(result["breakdown"].values())
    assert 0 <= result["score"] <= 100
    assert result["suggestions"]  # non-empty, concrete
    # forks must not inflate the score
    assert result["snapshot"]["total_stars"] == 60


def test_github_bad_username_friendly_error(monkeypatch):
    monkeypatch.setattr(github_integration.requests, "get", _fake_gh_get)
    with pytest.raises(github_integration.GithubAPIError) as e:
        github_integration.fetch_github_profile("nonexistent-user-xyz")
    assert "not found" in str(e.value).lower()


def test_github_invalid_username_rejected():
    with pytest.raises(github_integration.GithubAPIError):
        github_integration.validate_github_username("bad!!name")
    with pytest.raises(github_integration.GithubAPIError):
        github_integration.validate_github_username("-leading")


def test_github_rate_limit_friendly(monkeypatch):
    def _rl(url, headers=None, params=None, timeout=None):
        return _FakeResp(None, status=403, rate_limited=True)
    monkeypatch.setattr(github_integration.requests, "get", _rl)
    with pytest.raises(github_integration.GithubAPIError) as e:
        github_integration.fetch_github_profile("octocat")
    assert "rate limit" in str(e.value).lower()


# ---------- LeetCode integration (mocked GraphQL) ----------

_FAKE_LC = {"data": {"matchedUser": {
    "username": "testuser", "profile": {"ranking": 12345},
    "submitStatsGlobal": {"acSubmissionNum": [
        {"difficulty": "Easy", "count": 100},
        {"difficulty": "Medium", "count": 50},
        {"difficulty": "Hard", "count": 10}]},
    "badges": [{"displayName": "50 Days Badge"}]},
    "userContestRanking": {"rating": 1800.5, "globalRanking": 20000,
                          "attendedContestsCount": 12, "topPercentage": 10}}}


def _fake_lc_post(url, json=None, headers=None, timeout=None):
    if json and json.get("variables", {}).get("username") == "ghost-user-xyz":
        return _FakeResp({"data": {"matchedUser": None, "userContestRanking": None}})
    return _FakeResp(_FAKE_LC)


def test_leetcode_stats_parsing_mocked(monkeypatch):
    monkeypatch.setattr(leetcode_integration.requests, "post", _fake_lc_post)
    stats = leetcode_integration.fetch_leetcode_stats("testuser")
    assert stats["solved"] == {"easy": 100, "medium": 50, "hard": 10, "total": 160}
    assert stats["rating"] == 1800.5
    assert stats["global_rank"] == 20000
    assert stats["ranking"] == 12345
    assert stats["badges"] == ["50 Days Badge"]


def test_leetcode_bad_username_friendly_error(monkeypatch):
    monkeypatch.setattr(leetcode_integration.requests, "post", _fake_lc_post)
    with pytest.raises(leetcode_integration.LeetCodeAPIError) as e:
        leetcode_integration.fetch_leetcode_stats("ghost-user-xyz")
    assert "not found" in str(e.value).lower()


def test_leetcode_svg_card_valid():
    svg = leetcode_integration.render_leetcode_card_svg(
        {"username": "test<user>", "solved": {"easy": 1, "medium": 2, "hard": 3, "total": 6},
         "rating": 1500.0, "global_rank": 999, "contests": 5, "ranking": 1, "badges": []})
    assert svg.lstrip().startswith("<svg")
    assert "test&lt;user&gt;" in svg  # username is XML-escaped
    assert svg.rstrip().endswith("</svg>")


def test_leetcode_card_route_serves_svg(monkeypatch):
    monkeypatch.setattr(leetcode_integration.requests, "post", _fake_lc_post)
    app = make_app()
    r = app.test_client().get("/cards/leetcode/testuser.svg")
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    assert r.data.lstrip().startswith(b"<svg")


def test_leetcode_card_route_bad_user_graceful(monkeypatch):
    monkeypatch.setattr(leetcode_integration.requests, "post", _fake_lc_post)
    app = make_app()
    r = app.test_client().get("/cards/leetcode/ghost-user-xyz.svg")
    assert r.status_code == 200  # graceful error card, not a 500
    assert b"<svg" in r.data


# ---------- /profile page + connect/unlink ----------

def test_profile_requires_login(client):
    assert client.get("/profile").status_code == 302


def test_profile_connect_unlink_github(monkeypatch, client):
    register_login(client)
    monkeypatch.setattr(github_integration.requests, "get", _fake_gh_get)
    r = client.post("/profile/connect/github", data={"username": "octocat"})
    assert r.status_code == 302
    page = client.get("/profile").data
    assert b"@octocat" in page
    assert b"profile score" in page
    r = client.post("/profile/unlink/github")
    assert r.status_code == 302
    assert b"@octocat" not in client.get("/profile").data


def test_profile_connect_github_bad_user_shows_error(monkeypatch, client):
    register_login(client)
    monkeypatch.setattr(github_integration.requests, "get", _fake_gh_get)
    client.post("/profile/connect/github", data={"username": "nonexistent-user-xyz"})
    # redirected back with a flashed error; nothing was stored/connected
    page = client.get("/profile").data
    assert b"was not found" in page  # the friendly error flash
    assert b"badge on" not in page  # no "Connected" badge rendered


def test_profile_connect_unlink_leetcode(monkeypatch, client):
    register_login(client)
    monkeypatch.setattr(leetcode_integration.requests, "post", _fake_lc_post)
    r = client.post("/profile/connect/leetcode", data={"username": "testuser"})
    assert r.status_code == 302
    page = client.get("/profile").data
    assert b"testuser" in page
    assert b"/cards/leetcode/testuser.svg" in page
    client.post("/profile/unlink/leetcode")
    assert b"testuser" not in client.get("/profile").data


def test_profile_snapshot_cached_24h(monkeypatch, client):
    """A fresh snapshot is reused instead of hitting the API again."""
    register_login(client)
    calls = []
    def _counting_get(*a, **k):
        calls.append(1)
        return _fake_gh_get(*a, **k)
    monkeypatch.setattr(github_integration.requests, "get", _counting_get)
    client.post("/profile/connect/github", data={"username": "octocat"})
    first_calls = len(calls)
    assert first_calls > 0
    client.post("/profile/connect/github", data={"username": "octocat"})
    assert len(calls) == first_calls  # cached: no new API calls


def test_dashboard_shows_connection_status(client):
    register_login(client)
    assert b"Nothing connected yet." in client.get("/dashboard").data


# ---------- Schema evolution ----------

def test_schema_evolution_backfills_legacy_db(tmp_path):
    import sqlite3
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE "user" (
        id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL,
        email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL,
        created_at DATETIME NOT NULL)""")
    conn.commit()
    conn.close()
    app = create_app({"TESTING": True,
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(db_path),
                      "SECRET_KEY": "x", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        from sqlalchemy import inspect as sa_inspect
        cols = {c["name"] for c in sa_inspect(db.engine).get_columns("user")}
        assert {"google_sub", "avatar_url", "github_username", "leetcode_username"} <= cols
        u = User(name="Legacy", email="legacy@example.com", google_sub="g-1")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
        assert User.query.filter_by(google_sub="g-1").first().email == "legacy@example.com"
