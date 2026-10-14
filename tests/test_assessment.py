"""Tests for Wave 1 feature #7: career-discovery assessment."""
import json

import pytest

from unified_app import create_app, db, CareerAssessment
from career_assessment import (score_assessment, validate_assessment_inputs,
                               rule_based_why, QUESTIONS, CLUSTERS,
                               TOP_N_CLUSTERS)
from tests.conftest import register, login


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _all_answers(option=0):
    return {q["id"]: option for q in QUESTIONS}


def _design_answers():
    ans = {}
    for q in QUESTIONS:
        for i, o in enumerate(q["options"]):
            if o["weights"].get("design", 0) == 2:
                ans[q["id"]] = i
                break
        else:
            ans[q["id"]] = 0
    return ans


def _submit(client, answers, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr("unified_app._assessment_explanations",
                            lambda clusters: ([{**c, "why": "test why",
                                                "ai_powered": False} for c in clusters], False))
    return client.post("/assessment/submit", data=json.dumps({"answers": answers}),
                       content_type="application/json")


# ---------- Engine unit tests ----------

def test_engine_returns_top_clusters():
    results = score_assessment(_all_answers(0))
    assert len(results) == TOP_N_CLUSTERS
    for r in results:
        assert 0 <= r["match"] <= 100
        assert r["skills"] and r["tools"] and r["tool_links"]
    matches = [r["match"] for r in results]
    assert matches == sorted(matches, reverse=True)


def test_engine_discriminates():
    assert score_assessment(_all_answers(0))[0]["id"] == "swe"
    assert score_assessment(_design_answers())[0]["id"] == "design"


def test_engine_ignores_invalid_answers():
    results = score_assessment({"q1": 99, "bogus": 0})
    assert len(results) == TOP_N_CLUSTERS
    assert all(r["match"] >= 0 for r in results)


def test_rule_based_why_mentions_signals():
    clusters = score_assessment(_design_answers())
    why = rule_based_why(clusters[0])
    assert clusters[0]["name"] in why


def test_validate_inputs():
    data, err = validate_assessment_inputs({})
    assert data is None and err
    data, err = validate_assessment_inputs({"answers": "nope"})
    assert data is None and err
    partial = _all_answers()
    del partial["q1"]
    data, err = validate_assessment_inputs({"answers": partial})
    assert data is None and "q1" in err
    bad = _all_answers()
    bad["q2"] = 9
    data, err = validate_assessment_inputs({"answers": bad})
    assert data is None and err
    data, err = validate_assessment_inputs({"answers": _all_answers()})
    assert err is None and len(data) == len(QUESTIONS)


# ---------- Route tests ----------

def test_unauth_submit_401(client):
    r = client.post("/assessment/submit",
                    data=json.dumps({"answers": _all_answers()}),
                    content_type="application/json")
    assert r.status_code == 401


def test_unauth_quiz_redirects(client):
    assert client.get("/assessment").status_code == 302


def test_quiz_page_renders(authed_client):
    html = authed_client.get("/assessment").get_data(as_text=True)
    assert "__ASSESSMENT_QUESTIONS__" in html
    assert "Which weekend project sounds most fun?" in html  # embedded question JSON
    assert 'id="asQuiz"' in html


def test_incomplete_answers_400(authed_client):
    r = authed_client.post("/assessment/submit", data=json.dumps({"answers": {}}),
                           content_type="application/json")
    assert r.status_code == 400


def test_happy_path_saves_result(authed_client, monkeypatch, app):
    r = _submit(authed_client, _all_answers(), monkeypatch)
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert len(body["result"]["clusters"]) == TOP_N_CLUSTERS
    assert body["result"]["clusters"][0]["id"] == "swe"
    assert body["saved_url"].startswith("/assessment/")
    with app.app_context():
        row = CareerAssessment.query.first()
        assert row is not None
        assert row.top_clusters[0]["id"] == "swe"


def test_retake_creates_new_row(authed_client, monkeypatch, app):
    _submit(authed_client, _all_answers(), monkeypatch)
    _submit(authed_client, _design_answers(), monkeypatch)
    with app.app_context():
        assert CareerAssessment.query.count() == 2


def test_saved_result_page_renders(authed_client, monkeypatch):
    body = _submit(authed_client, _all_answers(), monkeypatch).get_json()
    r = authed_client.get(body["saved_url"])
    assert r.status_code == 200
    assert b"__ASSESSMENT_RESULT__" in r.data


def test_per_user_isolation(client, monkeypatch, app):
    register(client, name="A", email="a@example.com")
    login(client, email="a@example.com")
    url = _submit(client, _all_answers(), monkeypatch).get_json()["saved_url"]
    client.post("/logout", follow_redirects=False)
    register(client, name="B", email="b@example.com")
    login(client, email="b@example.com")
    assert client.get(url).status_code == 404
    with app.app_context():
        assert CareerAssessment.query.count() == 1


def test_dashboard_lists_assessments(authed_client, monkeypatch):
    _submit(authed_client, _all_answers(), monkeypatch)
    html = authed_client.get("/dashboard").get_data(as_text=True)
    assert "Career Assessments" in html


def test_gemini_failure_falls_back(authed_client, monkeypatch):
    from unified_app import GeminiError
    monkeypatch.setattr("unified_app.call_gemini_ai",
                        lambda *a, **k: (_ for _ in ()).throw(GeminiError("no key")))
    r = _submit(authed_client, _all_answers())  # real _assessment_explanations
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["result"]["ai_powered"] is False
    assert body["result"]["clusters"][0]["why"]  # rule-based fallback
