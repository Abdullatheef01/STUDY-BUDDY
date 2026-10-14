"""Tests for Wave 1 feature #12: portfolio one-page builder."""
import json

import pytest

from studybuddy.portfolio import validate_portfolio_payload, slugify, unique_slug
from unified_app import create_app, db, Portfolio
from tests.conftest import register, login


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _payload(**kw):
    p = {
        "display_name": "Aarav Sharma",
        "headline": "CS undergrad",
        "bio": "I build things.",
        "skills": ["Python", "Flask"],
        "projects": [{"title": "Resume AI", "description": "NLP app",
                      "link": "https://github.com/aarav/resume-ai"}],
        "links": [{"label": "GitHub", "url": "https://github.com/aarav"}],
        "show_github": False,
        "show_leetcode": False,
        "is_published": True,
    }
    p.update(kw)
    return p


def _save(client, **kw):
    return client.post("/portfolio/save", data=json.dumps(_payload(**kw)),
                       content_type="application/json")


# --- unit: validation ---

def test_slugify():
    assert slugify("Aarav Sharma") == "aarav-sharma"
    assert slugify("  ") == "portfolio"
    assert slugify("<b>x</b>") == "b-x-b"


def test_unique_slug():
    assert unique_slug("Aarav", set()) == "aarav"
    assert unique_slug("Aarav", {"aarav"}) == "aarav-2"
    assert unique_slug("Aarav", {"aarav", "aarav-2"}) == "aarav-3"


def test_validate_rejects_bad_payload():
    _, err = validate_portfolio_payload({"display_name": ""})
    assert err and "Display name" in err
    _, err = validate_portfolio_payload({"display_name": "x" * 81})
    assert err
    _, err = validate_portfolio_payload(_payload(headline="x" * 141))
    assert err
    _, err = validate_portfolio_payload(
        _payload(links=[{"label": "X", "url": "javascript:alert(1)"}]))
    assert err and "https://" in err
    _, err = validate_portfolio_payload(
        _payload(projects=[{"title": "", "description": "", "link": ""}],
                 links=[{"label": "", "url": ""}]))
    assert err is None  # empty rows are skipped, not errors
    data, err = validate_portfolio_payload(
        _payload(skills=[f"skill-{i}" for i in range(31)]))
    assert err and "30" in err


# --- routes ---

def test_builder_requires_login(client):
    assert client.get("/portfolio").status_code == 302
    assert client.get("/portfolio/download").status_code == 302


def test_unauth_save_401(client):
    r = client.post("/portfolio/save", data=json.dumps(_payload()),
                    content_type="application/json")
    assert r.status_code == 401


def test_save_happy_path(authed_client, app):
    r = _save(authed_client)
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["slug"] == "aarav-sharma"
    assert body["is_published"] is True
    assert body["public_url"].endswith("/p/aarav-sharma")
    with app.app_context():
        row = Portfolio.query.one()
        assert row.skills == ["Python", "Flask"]
        assert row.projects[0]["title"] == "Resume AI"


def test_save_validation_400(authed_client):
    assert _save(authed_client, display_name="").status_code == 400
    assert _save(authed_client,
                 links=[{"label": "X", "url": "ftp://x"}]).status_code == 400


def test_save_upserts_same_row(authed_client, app):
    _save(authed_client)
    _save(authed_client, headline="New headline")
    with app.app_context():
        assert Portfolio.query.count() == 1
        assert Portfolio.query.one().headline == "New headline"


def test_slug_unique_across_users(client, app):
    register(client, email="a@a.com")
    login(client, email="a@a.com")
    assert _save(client).get_json()["slug"] == "aarav-sharma"
    client.post("/logout")
    register(client, name="Aarav Sharma", email="b@b.com")
    login(client, email="b@b.com")
    assert _save(client).get_json()["slug"] == "aarav-sharma-2"


def test_github_flag_forced_off_when_unlinked(authed_client, app):
    _save(authed_client, show_github=True, show_leetcode=True)
    with app.app_context():
        row = Portfolio.query.one()
        assert row.show_github is False and row.show_leetcode is False


def test_public_page_unpublished_404(authed_client):
    _save(authed_client, is_published=False)
    assert authed_client.get("/p/aarav-sharma").status_code == 404
    assert authed_client.get("/p/nope").status_code == 404


def test_public_page_renders_published(authed_client):
    _save(authed_client)
    html = authed_client.get("/p/aarav-sharma").get_data(as_text=True)
    assert "Aarav Sharma" in html and "Resume AI" in html and "Python" in html


def test_public_page_xss_escaped(authed_client):
    _save(authed_client, display_name="<script>alert(1)</script>",
          bio="<img src=x onerror=alert(2)>",
          projects=[{"title": "<b>bold</b>", "description": "", "link": ""}])
    # slug is derived from the raw name; fetch it from the save response instead
    with authed_client.application.app_context():
        slug = Portfolio.query.one().slug
    html = authed_client.get(f"/p/{slug}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html
    assert "<b>bold</b>" not in html


def test_download(authed_client):
    _save(authed_client)
    r = authed_client.get("/portfolio/download")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    assert "portfolio-aarav-sharma.html" in r.headers["Content-Disposition"]
    assert "<!DOCTYPE html>" in r.get_data(as_text=True)
