"""Tests for Wave 1 feature #3: multiple saved resume versions."""

import pytest

from tests.conftest import login, register
from unified_app import ResumeVersion, db


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


LONG_TEXT = ("Aarav Sharma\nSenior Python developer with 5 years of experience "
             "building scalable backends.\nSkills: Python, Flask, PostgreSQL, Docker.\n"
             "Built payment APIs serving 10k requests per day.\n" * 3)
LONG_TEXT_V2 = LONG_TEXT.replace("5 years", "6 years").replace(
    "10k requests", "50k requests") + "\nLed a team of 4 engineers.\n"


def _create(authed_client, name="Backend v1", text=LONG_TEXT):
    return authed_client.post("/resume-versions",
                              json={"name": name, "resume_text": text})


def test_versions_require_login(client):
    assert client.get("/resume-versions").status_code == 401
    assert client.post("/resume-versions", json={}).status_code == 401


def test_create_version_happy_path(app, authed_client):
    r = _create(authed_client)
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["version"]["name"] == "Backend v1"
    assert data["version"]["is_default"] is True  # first version = default
    with app.app_context():
        assert ResumeVersion.query.count() == 1


def test_create_version_validation(authed_client):
    assert _create(authed_client, name="").status_code == 400
    assert _create(authed_client, text="too short").status_code == 400
    assert _create(authed_client, name="x" * 121).status_code == 400


def test_second_version_not_default(app, authed_client):
    _create(authed_client, name="v1")
    r = _create(authed_client, name="v2")
    assert r.get_json()["version"]["is_default"] is False
    with app.app_context():
        assert ResumeVersion.query.count() == 2


def test_list_versions(app, authed_client):
    _create(authed_client, name="Backend v1")
    _create(authed_client, name="ML intern")
    r = authed_client.get("/resume-versions")
    data = r.get_json()
    assert data["success"] is True
    assert [v["name"] for v in data["versions"]] == ["ML intern", "Backend v1"]
    assert "resume_text" not in data["versions"][0]  # preview only


def test_get_single_version(app, authed_client):
    vid = _create(authed_client).get_json()["version"]["id"]
    r = authed_client.get(f"/resume-versions/{vid}")
    data = r.get_json()
    assert data["success"] is True
    assert "Python developer" in data["version"]["resume_text"]


def test_set_default(app, authed_client):
    v1 = _create(authed_client, name="v1").get_json()["version"]["id"]
    v2 = _create(authed_client, name="v2").get_json()["version"]["id"]
    r = authed_client.post(f"/resume-versions/{v2}/set-default")
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(ResumeVersion, v1).is_default is False
        assert db.session.get(ResumeVersion, v2).is_default is True


def test_delete_version(app, authed_client):
    v1 = _create(authed_client, name="v1").get_json()["version"]["id"]
    v2 = _create(authed_client, name="v2").get_json()["version"]["id"]
    # v1 is default; deleting it promotes v2.
    r = authed_client.post(f"/resume-versions/{v1}/delete")
    assert r.status_code == 200
    with app.app_context():
        assert ResumeVersion.query.count() == 1
        assert db.session.get(ResumeVersion, v2).is_default is True


def test_delete_missing_version(authed_client):
    assert authed_client.post("/resume-versions/9999/delete").status_code == 404


def test_diff_versions(authed_client):
    _create(authed_client, name="v1", text=LONG_TEXT)
    v2 = _create(authed_client, name="v2", text=LONG_TEXT_V2).get_json()["version"]["id"]
    r = authed_client.get(f"/resume-versions/{v2}/diff")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["summary"]["added"] >= 1
    assert data["summary"]["removed"] >= 1
    types = {ln["type"] for ln in data["lines"]}
    assert "add" in types and "del" in types


def test_diff_needs_two_versions(authed_client):
    v1 = _create(authed_client, name="v1").get_json()["version"]["id"]
    r = authed_client.get(f"/resume-versions/{v1}/diff")
    assert r.status_code == 400


def test_versions_isolated_between_users(app, client, authed_client):
    _create(authed_client, name="Secret v1")
    client.post("/logout", follow_redirects=False)
    register(client, name="Bob", email="bob@example.com")
    login(client, email="bob@example.com")
    assert client.get("/resume-versions").get_json()["versions"] == []
    with app.app_context():
        assert ResumeVersion.query.count() == 1


def test_jd_match_with_version_source(app, authed_client, monkeypatch):
    import unified_app
    monkeypatch.setattr(unified_app, "_jd_match_suggestions",
                        lambda *a, **k: ([], False))
    vid = _create(authed_client, name="Backend v1").get_json()["version"]["id"]
    jd = ("Python backend engineer, 3+ years. Must have: Python, Flask, "
          "PostgreSQL, Docker. " * 6)
    r = authed_client.post("/jd-match", json={
        "jd_text": jd, "resume_source": "version", "version_id": vid})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    data = r.get_json()
    assert data["success"] is True
    assert 0 <= data["report"]["score"] <= 100


def test_jd_match_version_source_rejects_foreign_version(client, authed_client):
    _create(authed_client, name="v1")
    client.post("/logout", follow_redirects=False)
    register(client, name="Bob", email="bob@example.com")
    login(client, email="bob@example.com")
    jd = "Python developer role. " * 20
    r = client.post("/jd-match", json={
        "jd_text": jd, "resume_source": "version", "version_id": 1})
    assert r.status_code == 400
