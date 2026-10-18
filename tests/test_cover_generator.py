"""Tests for Wave 1 feature #4: cover-letter + cold-outreach generator."""
import pytest

from studybuddy.cover_generator import (
    TONES,
    extract_contact,
    rule_based_cover_letter,
    rule_based_outreach,
    validate_cover_inputs,
)
from tests.conftest import login, register
from unified_app import CoverDoc


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


RESUME = ("Aarav Sharma\naarav.sharma@example.com | +91-9876543210\n"
          "Python developer, 3 years. Skills: Python, Flask, PostgreSQL, Docker.\n"
          "Built checkout APIs serving 10k orders per day.\n" * 3)
JD = ("Senior Python Backend Engineer. Must have: Python, Flask, PostgreSQL, "
      "Docker, Kubernetes. 4+ years building scalable systems. " * 6)


# ---------- Engine unit tests ----------

def test_extract_contact():
    c = extract_contact(RESUME)
    assert c["name"] == "Aarav Sharma"
    assert c["email"] == "aarav.sharma@example.com"
    assert "+91" in c["phone"]


def test_rule_based_cover_letter_tones():
    for tone in TONES:
        letter = rule_based_cover_letter(RESUME, JD, tone)
        assert "Dear Hiring Manager" in letter
        assert "Aarav Sharma" in letter
        assert len(letter) > 200


def test_rule_based_cover_letter_concise_is_shorter():
    concise = rule_based_cover_letter(RESUME, JD, "concise")
    professional = rule_based_cover_letter(RESUME, JD, "professional")
    assert len(concise) < len(professional)


def test_rule_based_outreach():
    for tone in TONES:
        msg = rule_based_outreach(RESUME, JD, tone)
        assert len(msg) > 50
        assert "15-minute" in msg or "chat" in msg


def test_validate_cover_inputs():
    data, err = validate_cover_inputs({"jd_text": JD, "tone": "enthusiastic"})
    assert err is None and data["tone"] == "enthusiastic"
    _, err = validate_cover_inputs({"jd_text": "   "})
    assert err is not None
    data, _ = validate_cover_inputs({"jd_text": JD, "tone": "bogus"})
    assert data["tone"] == "professional"


# ---------- Route tests ----------

def test_generate_requires_login(client):
    assert client.post("/generate-cover", json={"jd_text": JD}).status_code == 401
    assert client.get("/cover-docs").status_code == 401


def test_generate_happy_path_rule_based(app, authed_client):
    # No Gemini key in test env -> rule-based fallback.
    r = authed_client.post("/generate-cover",
                           json={"jd_text": JD, "tone": "professional",
                                 "resume_text": RESUME})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    data = r.get_json()
    assert data["success"] is True
    assert data["ai_powered"] is False
    assert "Dear Hiring Manager" in data["cover_letter"]
    assert len(data["outreach"]) > 50
    assert len(data["doc_ids"]) == 2
    with app.app_context():
        assert CoverDoc.query.count() == 2


def test_generate_with_version_source(app, authed_client):
    r = authed_client.post("/resume-versions",
                           json={"name": "Backend v1", "resume_text": RESUME})
    vid = r.get_json()["version"]["id"]
    r = authed_client.post("/generate-cover",
                           json={"jd_text": JD, "tone": "concise", "version_id": vid})
    assert r.status_code == 200
    assert r.get_json()["tone"] == "concise"


def test_generate_validation(authed_client):
    assert authed_client.post("/generate-cover", json={"jd_text": ""}).status_code == 400
    assert authed_client.post("/generate-cover",
                              json={"jd_text": JD, "version_id": 99999}).status_code == 400
    # No resume anywhere -> 400.
    assert authed_client.post("/generate-cover",
                              json={"jd_text": JD}).status_code == 400


def test_cover_docs_list_and_isolation(app, client, authed_client):
    authed_client.post("/generate-cover",
                       json={"jd_text": JD, "resume_text": RESUME})
    docs = client.get("/cover-docs")
    # Note: client == authed_client session here; use fresh login for Bob.
    assert docs.get_json()["success"] is True
    assert len(docs.get_json()["docs"]) == 2
    client.post("/logout", follow_redirects=False)
    register(client, name="Bob", email="bob@example.com")
    login(client, email="bob@example.com")
    assert client.get("/cover-docs").get_json()["docs"] == []
    with app.app_context():
        assert CoverDoc.query.count() == 2
