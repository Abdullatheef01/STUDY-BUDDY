"""Tests for Wave 1 feature #2: AI bullet rewriter."""

import pytest

from studybuddy.bullet_rewriter import (
    BULLET_MAX_CHARS,
    concise_version,
    improve_bullet,
    quantified_version,
    strengthen_verbs,
)
from tests.conftest import login, register
from unified_app import BulletRewrite


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _fake_ai_rewrites(*args, **kwargs):
    return ([{"label": "AI", "text": "AI polished bullet.", "tip": "t"}], True)


# ---------- Engine unit tests ----------

def test_strengthen_verbs_swaps_weak_openers():
    assert strengthen_verbs("Worked on the payments API").startswith("Engineered")
    assert strengthen_verbs("Responsible for ETL pipelines").startswith("Owned")
    assert strengthen_verbs("Helped the team ship faster").startswith("Collaborated")


def test_strengthen_verbs_keeps_strong_openers():
    assert strengthen_verbs("Built a real-time dashboard") == "Built a real-time dashboard"


def test_quantified_version_adds_placeholder_when_missing():
    out = quantified_version("Built the search service")
    assert "[" in out and "]" in out  # metric placeholder present


def test_quantified_version_keeps_existing_metric():
    out = quantified_version("Reduced latency by 40% across 5 services")
    assert "[" not in out


def test_concise_version_strips_filler():
    out = concise_version("Basically built a very fast API for payments")
    assert "very" not in out.split()
    assert out.endswith(".")
    assert len(out.split()) <= 28


def test_improve_bullet_returns_three_variants():
    variants = improve_bullet("Worked on the checkout flow and helped reduce errors")
    assert len(variants) == 3
    for v in variants:
        assert v["label"] and v["text"] and v["tip"]


def test_improve_bullet_rejects_empty_and_short():
    with pytest.raises(ValueError):
        improve_bullet("   ")
    with pytest.raises(ValueError):
        improve_bullet("too short")


def test_improve_bullet_rejects_oversized():
    with pytest.raises(ValueError):
        improve_bullet("x" * (BULLET_MAX_CHARS + 1))


# ---------- Route tests ----------

def test_rewrite_requires_login(client):
    r = client.post("/rewrite-bullet", json={"bullet_text": "Built an API for search"})
    assert r.status_code == 401
    assert "log in" in r.get_json()["error"].lower()


def test_rewrite_happy_path_rule_based(app, authed_client):
    # No GEMINI_API_KEY in the test env, so the rule-based fallback runs.
    r = authed_client.post("/rewrite-bullet",
                           json={"bullet_text": "Worked on the search API and made it faster"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert len(data["rewrites"]) == 3
    assert data["ai_powered"] is False
    with app.app_context():
        row = BulletRewrite.query.first()
        assert row is not None
        assert row.original.startswith("Worked on")


def test_rewrite_validation(authed_client):
    for bad, code in [("", 400), ("short", 400), ("x" * 1001, 400)]:
        r = authed_client.post("/rewrite-bullet", json={"bullet_text": bad})
        assert r.status_code == code, bad[:10]


def test_rewrite_per_user_isolation(app, client, authed_client):
    authed_client.post("/rewrite-bullet", json={"bullet_text": "Built the billing pipeline"})
    with app.app_context():
        assert BulletRewrite.query.count() == 1
    # A second user sees none of the first user's rewrites.
    client.post("/logout", follow_redirects=False)  # logout is POST-only
    register(client, name="Bob", email="bob@example.com")
    login(client, email="bob@example.com")
    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Built the billing pipeline" not in html
