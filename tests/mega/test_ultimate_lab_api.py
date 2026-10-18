"""Ultimate Lab API dispatcher tests."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ["OPP_NO_AUTO_REFRESH"] = "1"

import pytest

from studybuddy.ultimate_routes import _TOOL_INDEX, ALL_TOOLS, run_tool
from unified_app import User, create_app, db


@pytest.fixture(scope="module")
def client():
    # SEC-01 (Phase 0): the dispatcher now requires login. The old tests
    # encoded anonymous access as correct; that was the vulnerability, so
    # the fixture now creates a user and logs in before exercising endpoints.
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "lab-api-test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
        u = User(name="Lab Tester", email="lab@example.com")
        u.set_password("lab-pass-123")
        db.session.add(u)
        db.session.commit()
    c = app.test_client()
    r = c.post("/login", data={"email": "lab@example.com",
                               "password": "lab-pass-123"})
    assert r.status_code in (302, 303)
    return c


def test_registry_complete():
    assert len(ALL_TOOLS) == 91
    assert len(_TOOL_INDEX) == 91


def test_registry_fields_valid():
    for t in ALL_TOOLS:
        assert t["id"] and t["feature"] and t["name"] and t["module"] and t["function"]
        for f in t.get("fields", []):
            assert f["name"] and f["label"] and f["type"] in (
                "text", "textarea", "number", "select", "checkbox")


def test_tools_endpoint(client):
    r = client.get("/api/ultimate/tools")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] and d["count"] == 91
    # No function refs leak to frontend
    assert "function" not in d["tools"][0]


def test_run_star_convert(client):
    r = client.post("/api/ultimate/run/bullets/star-convert",
                    json={"bullet_text": "Built dashboard, cut reporting time 40%"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"]


def test_run_missing_required(client):
    r = client.post("/api/ultimate/run/bullets/star-convert", json={})
    assert r.status_code == 400
    assert not r.get_json()["ok"]


def test_run_unknown_tool(client):
    r = client.post("/api/ultimate/run/nope/nope", json={})
    assert r.status_code == 400


def test_run_bad_json_field(client):
    r = client.post("/api/ultimate/run/momentum/squad-leaderboard",
                    json={"members": "not json"})
    assert r.status_code == 400


def test_run_no_json_body(client):
    r = client.post("/api/ultimate/run/bullets/star-convert",
                    data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_lab_page_loads(client):
    r = client.get("/ultimate/lab")
    assert r.status_code == 200


def test_run_tool_direct_date_coercion():
    from datetime import date, timedelta
    r, e = run_tool("momentum/streak-freeze", {
        "last_active": (date.today() - timedelta(days=2)).isoformat(),
        "freezes_used_week": 0})
    assert e is None
    assert r["freezes_available"] == 1


def test_run_tool_direct_json_list():
    r, e = run_tool("momentum/squad-leaderboard", {
        "members": '[{"user_id": 1, "name": "A", "weekly_xp": 100}]'})
    assert e is None
    assert r["leader"] == "A"


def test_every_tool_callable():
    """Every registered function must be importable."""
    import importlib
    for t in ALL_TOOLS:
        mod = importlib.import_module(t["module"])
        assert callable(getattr(mod, t["function"])), t["id"]
