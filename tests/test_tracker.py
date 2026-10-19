"""Tests for Wave 1 feature #6: application-tracker Kanban."""
import json

import pytest

from tests.conftest import login, register
from unified_app import JobApplication


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _add(client, **kw):
    payload = {"company": "Acme Corp", "role": "Backend Intern"}
    payload.update(kw)
    return client.post("/tracker/add", data=json.dumps(payload),
                       content_type="application/json",
                       headers={"X-CSRFToken": "test"})


def test_unauth_add_401(client):
    r = client.post("/tracker/add", data=json.dumps({"company": "X", "role": "Y"}),
                    content_type="application/json")
    assert r.status_code == 401


def test_unauth_board_redirects_to_login(client):
    r = client.get("/tracker")
    assert r.status_code == 302


def test_add_happy_path(authed_client, app):
    r = _add(authed_client, stage="applied", jd_url="https://example.com/jd",
             notes="Referral from Aarav", applied_date="2026-10-01")
    assert r.status_code == 201
    body = r.get_json()
    assert body["success"] is True
    assert body["application"]["company"] == "Acme Corp"
    assert body["application"]["stage"] == "applied"
    with app.app_context():
        assert JobApplication.query.count() == 1


def test_add_validation(authed_client):
    assert _add(authed_client, company="").status_code == 400
    assert _add(authed_client, role="").status_code == 400
    assert _add(authed_client, stage="hired").status_code == 400
    assert _add(authed_client, jd_url="not-a-url").status_code == 400
    assert _add(authed_client, applied_date="yesterday").status_code == 400
    assert _add(authed_client, company="x" * 201).status_code == 400


def test_board_renders(authed_client):
    _add(authed_client)
    r = authed_client.get("/tracker")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "<h4>Acme Corp</h4>" in html
    assert "Wishlist" in html and "Offer" in html


def test_move_stage(authed_client, app):
    app_id = _add(authed_client).get_json()["application"]["id"]
    r = authed_client.post(f"/tracker/{app_id}/move",
                           data=json.dumps({"stage": "interview"}),
                           content_type="application/json")
    assert r.status_code == 200
    assert r.get_json()["application"]["stage"] == "interview"
    r = authed_client.post(f"/tracker/{app_id}/move",
                           data=json.dumps({"stage": "nope"}),
                           content_type="application/json")
    assert r.status_code == 400


def test_edit_and_delete(authed_client, app):
    app_id = _add(authed_client).get_json()["application"]["id"]
    r = authed_client.post(f"/tracker/{app_id}/edit",
                           data=json.dumps({"company": "Beta Inc", "role": "SDE Intern",
                                            "notes": "Updated"}),
                           content_type="application/json")
    assert r.status_code == 200
    body = r.get_json()["application"]
    assert body["company"] == "Beta Inc" and body["notes"] == "Updated"
    r = authed_client.post(f"/tracker/{app_id}/delete", data=json.dumps({}),
                           content_type="application/json")
    assert r.status_code == 200
    with app.app_context():
        assert JobApplication.query.count() == 0


def test_stats_math(authed_client):
    _add(authed_client, stage="applied")
    _add(authed_client, stage="interview", company="B")
    _add(authed_client, stage="rejected", company="C")
    _add(authed_client, stage="wishlist", company="D")
    r = authed_client.get("/tracker/stats")
    body = r.get_json()["stats"]
    assert body["total"] == 4
    # responded (interview) / in_pipeline (applied+interview+rejected) = 1/3
    assert body["response_rate"] == pytest.approx(33.3, abs=0.1)
    assert body["counts"]["applied"] == 1
    assert body["avg_days_in_stage"]["applied"] >= 0


def test_per_user_isolation(client, app):
    register(client, name="A", email="a@example.com")
    login(client, email="a@example.com")
    app_id = _add(client).get_json()["application"]["id"]
    client.post("/logout", follow_redirects=False)
    register(client, name="B", email="b@example.com")
    login(client, email="b@example.com")
    assert client.get("/tracker").status_code == 200
    assert "<h4>Acme Corp</h4>" not in client.get("/tracker").get_data(as_text=True)
    for path, _method in [(f"/tracker/{app_id}/move", "move"),
                         (f"/tracker/{app_id}/edit", "edit"),
                         (f"/tracker/{app_id}/delete", "delete")]:
        r = client.post(path, data=json.dumps({"stage": "offer"}),
                        content_type="application/json")
        assert r.status_code == 404, path
    with app.app_context():
        assert JobApplication.query.count() == 1  # untouched


def test_dashboard_tracker_section(authed_client):
    _add(authed_client)
    html = authed_client.get("/dashboard").get_data(as_text=True)
    assert "Application Tracker" in html
