"""Tests for Wave 2 feature #13: company-specific AI mock interviews."""

import pytest

from studybuddy.mock_interview import (
    _load_bank,
    generate_rule_based_feedback,
    interview_options,
    pick_questions,
    score_answer,
    validate_interview_setup,
)
from tests.conftest import login, register
from unified_app import InterviewSession


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


# ---------- content bank sanity ----------

def test_bank_loads_with_required_fields():
    bank = _load_bank()
    assert len(bank) >= 300, f"bank too small: {len(bank)}"
    required = {"id", "question", "companies", "roles", "category",
                "difficulty", "key_points", "time_minutes"}
    for q in bank:
        assert required <= set(q.keys()), q.get("id")
        assert q["category"] in ("behavioral", "hr", "puzzles", "system_design", "dsa")
        assert q["difficulty"] in ("Easy", "Medium", "Hard")
        assert len(q["key_points"]) >= 3
        assert q["companies"] and q["roles"]


def test_bank_ids_unique():
    bank = _load_bank()
    ids = [q["id"] for q in bank]
    assert len(ids) == len(set(ids))


def test_bank_covers_companies_and_categories():
    bank = _load_bank()
    companies = {c for q in bank for c in q["companies"]}
    for want in ("Google", "Amazon", "TCS", "Flipkart"):
        assert want in companies
    cats = {q["category"] for q in bank}
    assert cats == {"behavioral", "hr", "puzzles", "system_design", "dsa"}


def test_interview_options_shape():
    opts = interview_options()
    assert len(opts["companies"]) >= 10
    assert "sde" in opts["roles"]
    assert set(opts["categories"]) == {"behavioral", "hr", "puzzles", "system_design", "dsa"}


# ---------- question picking ----------

def test_pick_questions_filters_and_count():
    qs = pick_questions("Google", "sde", "behavioral", n=5, seed=42)
    assert len(qs) == 5
    for q in qs:
        assert q["category"] == "behavioral"
        assert "sde" in q["roles"]


def test_pick_questions_seeded_deterministic():
    a = pick_questions("Amazon", "backend", "dsa", n=4, seed=7)
    b = pick_questions("Amazon", "backend", "dsa", n=4, seed=7)
    assert [q["id"] for q in a] == [q["id"] for q in b]


def test_pick_questions_falls_back_gracefully():
    # nonsense company still yields questions via fallback
    qs = pick_questions("NoSuchCo", "sde", "hr", n=3, seed=1)
    assert len(qs) == 3
    assert all(q["category"] == "hr" for q in qs)


def test_validate_setup_rejects_bad_input():
    cleaned, err = validate_interview_setup({"company": "Nope", "role": "sde",
                                             "category": "behavioral"})
    assert err and not cleaned
    cleaned, err = validate_interview_setup({"company": "Google", "role": "sde",
                                             "category": "behavioral",
                                             "num_questions": "99"})
    assert err and not cleaned


def test_validate_setup_accepts_good_input():
    cleaned, err = validate_interview_setup({"company": "Google", "role": "sde",
                                             "category": "dsa", "num_questions": "5"})
    assert not err and cleaned["n"] == 5


# ---------- rubric scoring ----------

def _sample_q():
    return {
        "id": "beh-001",
        "question": "Tell me about a time you fixed a production outage.",
        "key_points": [
            "Describe the failing state concretely with specifics",
            "List the specific actions you took to mitigate",
            "Quantify the turnaround and recovery time",
        ],
        "category": "behavioral",
    }


def test_strong_answer_scores_high():
    ans = ("Last quarter our payment service started failing concretely: error rates "
           "spiked to 12% and checkout conversions dropped. I took ownership immediately: "
           "I triaged the logs, identified a bad deploy, and rolled it back within 20 minutes. "
           "I then added a canary analysis step which reduced bad deploys by 80%. "
           "The turnaround was measured: error rates recovered to 0.1% and conversions "
           "rebounded fully. I also considered the trade-off between speed and safety, "
           "because rushing the rollback could have caused data loss. Edge cases like "
           "partial rollouts were validated with tests.")
    s = score_answer(_sample_q(), ans)
    assert s["total"] >= 55, s
    assert s["scores"]["correctness"] > 15
    assert set(s["scores"]) == {"correctness", "communication", "depth", "edge_cases"}


def test_thin_answer_scores_low():
    s = score_answer(_sample_q(), "It was bad. I fixed it.")
    assert s["total"] < 30, s


def test_empty_answer_scores_zero():
    s = score_answer(_sample_q(), "")
    assert s["total"] == 0


def test_filler_heavy_answer_loses_communication():
    clean = ("I diagnosed the outage by reading logs, identified the faulty deploy, "
             "rolled it back, and added canary analysis to prevent recurrence.")
    fillery = ("Um, so basically, you know, I was like, uh, looking at the logs and stuff, "
               "and I literally just, you know, rolled it back or whatever.")
    s_clean = score_answer(_sample_q(), clean * 3)
    s_fill = score_answer(_sample_q(), fillery * 3)
    assert s_fill["scores"]["communication"] < s_clean["scores"]["communication"]
    assert s_fill["filler_hits"]


def test_feedback_has_strengths_and_improvements():
    s = score_answer(_sample_q(), "It was bad. I fixed it.")
    fb = generate_rule_based_feedback(s, _sample_q())
    assert fb["improvements"]
    s2 = score_answer(_sample_q(), "x" * 2000 + " concretely specifics actions mitigate quantified turnaround recovery trade-off because edge cases validated tests")
    fb2 = generate_rule_based_feedback(s2, _sample_q())
    assert fb2["strengths"] or fb2["improvements"]


# ---------- routes ----------

def test_interview_page_loads(client):
    r = client.get("/interview")
    assert r.status_code == 200
    assert b"Mock Interview" in r.data


def test_start_requires_login(client):
    r = client.post("/interview/start", json={"company": "Google", "role": "sde",
                                              "category": "behavioral"})
    assert r.status_code == 401


def test_start_and_submit_flow(authed_client, app):
    r = authed_client.post("/interview/start", json={
        "company": "Google", "role": "sde", "category": "behavioral",
        "num_questions": 2})
    assert r.status_code == 200, r.data[:300]
    data = r.get_json()
    assert data["success"] and len(data["questions"]) == 2
    sid = data["session_id"]

    answers = [{"question_id": q["id"],
                "answer": "Situation: the service was failing. Action: I triaged logs and rolled back. "
                          "Result: recovered in 20 minutes, errors down 90%. I weighed the trade-off "
                          "between speed and safety because haste risks data loss. Edge cases validated."}
               for q in data["questions"]]
    r2 = authed_client.post(f"/interview/{sid}/submit", json={"answers": answers})
    assert r2.status_code == 200, r2.data[:300]
    d2 = r2.get_json()
    assert d2["success"] and d2["total_score"] >= 0
    assert len(d2["results"]) == 2
    for res in d2["results"]:
        assert "feedback" in res and res["feedback"]["improvements"] is not None

    # saved report page renders
    r3 = authed_client.get(f"/interview/{sid}")
    assert r3.status_code == 200
    assert b"Interview" in r3.data

    # persisted
    with app.app_context():
        row = InterviewSession.query.get(sid)
        assert row is not None and row.total_score == d2["total_score"]


def test_submit_rejects_empty_and_unknown(authed_client):
    r = authed_client.post("/interview/start", json={
        "company": "Google", "role": "sde", "category": "hr", "num_questions": 1})
    sid = r.get_json()["session_id"]
    r2 = authed_client.post(f"/interview/{sid}/submit", json={"answers": []})
    assert r2.status_code == 400
    r3 = authed_client.post("/interview/99999/submit", json={"answers": [{"a": 1}]})
    assert r3.status_code == 404


def test_cross_user_isolation(client):
    register(client, email="u1@example.com")
    login(client, email="u1@example.com")
    r = client.post("/interview/start", json={"company": "Google", "role": "sde",
                                              "category": "hr", "num_questions": 1})
    sid = r.get_json()["session_id"]
    client.post("/logout", follow_redirects=True)
    register(client, name="Two", email="u2@example.com")
    login(client, email="u2@example.com")
    assert client.get(f"/interview/{sid}").status_code == 404
    r2 = client.post(f"/interview/{sid}/submit", json={"answers": [{"question_id": "x", "answer": "y"}]})
    assert r2.status_code == 404


def test_dashboard_lists_interviews(authed_client):
    authed_client.post("/interview/start", json={"company": "Meta", "role": "frontend",
                                                 "category": "behavioral", "num_questions": 1})
    r = authed_client.get("/dashboard")
    assert r.status_code == 200
    assert b"Mock Interviews" in r.data
