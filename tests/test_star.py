"""Tests for Wave 2 feature #17: STAR answer builder."""
import pytest

from studybuddy.star_builder import (
    COMPETENCIES,
    COMPETENCY_IDS,
    SECTION_GUIDE,
    SECTIONS,
    all_examples,
    examples_for,
    score_draft,
    score_section,
    validate_draft,
)
from tests.conftest import login, register


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _draft(**kw):
    d = {"competency": "leadership",
         "situation": "Our fest app had no working build three weeks out.",
         "task": "As tech lead, I had to ship it for 2000 attendees.",
         "action": "I split work into daily deliverables and unblocked the payment integration myself.",
         "result": "We shipped early and handled 1800 registrations with zero downtime."}
    d.update(kw)
    return d


# ---------- content bank sanity ----------

def test_bank_loads_with_required_fields():
    bank = all_examples()
    assert len(bank) >= 40, f"bank too small: {len(bank)}"
    required = {"id", "competency", "title", "situation", "task",
                "action", "result", "why_it_works"}
    for e in bank:
        assert required <= set(e.keys()), e.get("id")
        assert e["competency"] in COMPETENCY_IDS
        assert len(e["why_it_works"]) >= 2
        assert all(len(e[s]) > 20 for s in SECTIONS)


def test_bank_ids_unique_and_competencies_covered():
    bank = all_examples()
    ids = [e["id"] for e in bank]
    assert len(ids) == len(set(ids))
    covered = {e["competency"] for e in bank}
    assert len(covered) >= 10
    for comp in covered:
        assert len(examples_for(comp)) >= 3


def test_competencies_shape():
    assert len(COMPETENCIES) >= 10
    assert set(COMPETENCY_IDS) >= {"leadership", "teamwork", "ownership"}
    for sec in SECTIONS:
        g = SECTION_GUIDE[sec]
        assert g["tip"] and g["good"] and g["bad"] and g["why_bad"]


# ---------- draft validation ----------

def test_validate_draft_ok():
    cleaned, err = validate_draft(_draft())
    assert err is None
    assert cleaned["competency"] == "leadership"


def test_validate_draft_rejects_bad():
    for payload in ({"competency": "nope", "situation": "x"},
                    {"competency": "leadership"},
                    {"competency": "leadership", "situation": "x" * 4001},
                    "not-a-dict"):
        cleaned, err = validate_draft(payload)
        assert cleaned is None and err, payload


# ---------- scoring ----------

def test_score_section_empty():
    sc, sug = score_section("action", "")
    assert sc == 0 and sug


def test_score_draft_discrimination():
    strong = score_draft({
        "situation": "Our college tech fest was three weeks away and the event app had no working build for 2000 attendees.",
        "task": "As the elected tech lead, I had to ship a working app on time.",
        "action": "I split work into one-day deliverables. I ran daily standups. I unblocked the payment integration myself and paired juniors with seniors.",
        "result": "We shipped 2 days early and handled 1800 registrations with zero downtime. I learned that small daily goals beat big vague plans."})
    weak = score_draft({
        "situation": "It was hard.", "task": "",
        "action": "We did stuff.", "result": "It went well."})
    assert strong["overall"] > weak["overall"] + 20
    assert strong["overall"] <= 100
    assert set(strong["sections"]) == set(SECTIONS)


def test_score_section_we_vs_i():
    sc_we, _ = score_section("action", "We worked together and we finished the project.")
    sc_i, _ = score_section("action", "I designed the schema. I wrote the migration. I led the rollout.")
    assert sc_i >= sc_we


# ---------- routes ----------

def test_star_home_renders(client):
    r = client.get("/star")
    assert r.status_code == 200
    assert b"STAR" in r.data


def test_examples_api(client):
    r = client.get("/api/star/examples")
    assert r.status_code == 200
    assert r.get_json()["count"] >= 40
    r2 = client.get("/api/star/examples?competency=leadership")
    assert r2.status_code == 200
    assert r2.get_json()["count"] >= 3
    r3 = client.get("/api/star/examples?competency=nope")
    assert r3.status_code == 400


def test_score_requires_login(client):
    r = client.post("/star/score", json=_draft())
    assert r.status_code == 401


def test_score_happy_path(authed_client):
    r = authed_client.post("/star/score", json=_draft(),
                           headers={"X-CSRFToken": "test"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["success"]
    assert 0 <= d["scores"]["overall"] <= 100
    assert set(d["suggestions"]) == set(SECTIONS)
    assert isinstance(d["ai_powered"], bool)


def test_score_validation_error(authed_client):
    r = authed_client.post("/star/score", json={"competency": "nope"},
                           headers={"X-CSRFToken": "test"})
    assert r.status_code == 400


def test_save_and_list_drafts(authed_client):
    # score first to attach scores
    r = authed_client.post("/star/score", json=_draft(),
                           headers={"X-CSRFToken": "test"})
    scored = r.get_json()
    payload = _draft()
    payload["scores"] = scored["scores"]
    payload["suggestions"] = scored["suggestions"]
    payload["ai_powered"] = scored["ai_powered"]
    r2 = authed_client.post("/star/save", json=payload,
                            headers={"X-CSRFToken": "test"})
    assert r2.status_code == 200
    draft_id = r2.get_json()["draft_id"]

    r3 = authed_client.get("/star/drafts")
    assert r3.status_code == 200
    assert b"Leadership" in r3.data

    r4 = authed_client.get("/dashboard")
    assert r4.status_code == 200
    assert b"STAR Answer Drafts" in r4.data

    # delete
    r5 = authed_client.post(f"/star/drafts/{draft_id}/delete",
                            headers={"X-CSRFToken": "test"})
    assert r5.status_code == 200
    assert r5.get_json()["success"]


def test_draft_isolation(authed_client, app):
    r = authed_client.post("/star/save", json=_draft(),
                           headers={"X-CSRFToken": "test"})
    draft_id = r.get_json()["draft_id"]
    other = app.test_client()
    register(other, email="other2@x.com")
    login(other, email="other2@x.com")
    r2 = other.post(f"/star/drafts/{draft_id}/delete",
                    headers={"X-CSRFToken": "test"})
    assert r2.status_code == 404
