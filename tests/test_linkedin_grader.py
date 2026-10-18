"""Tests for Wave 1 feature #5: LinkedIn profile grader."""
import json

import pytest

from studybuddy.linkedin_grader import (
    MAX_FIELD_CHARS,
    generate_rule_based_summary,
    grade_linkedin_profile,
    validate_linkedin_inputs,
)
from tests.conftest import login, register
from unified_app import LinkedInReport

STRONG_PROFILE = {
    "headline": "CS Undergrad @ GEHU | Python & ML Developer | Built 5+ projects, 2 internships",
    "about": ("I'm a computer science undergraduate passionate about building ML-powered "
              "products. I built a resume analyzer that increased user engagement by 40% "
              "and led a team of 3 to ship a chatbot serving 2000+ users. I have completed "
              "2 internships where I automated data pipelines, reducing processing time "
              "by 60%. My goal is to grow into a full-stack ML engineer role."),
    "experience": (
        "ML Intern @ StartupX (2024-2025)\n"
        "Built Flask APIs serving 10k requests/day and improved model accuracy by 12%.\n\n"
        "Freelance Developer (2023-2024)\n"
        "Delivered 5 client projects, grew freelance revenue 3x, mentored 2 juniors."
    ),
    "skills": "Python, Flask, SQL, Machine Learning, Docker, Git, Data Analysis, Communication",
}

WEAK_PROFILE = {
    "headline": "Student",
    "about": "I am a student.",
    "experience": "",
    "skills": "hardworking",
}


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _fake_suggestions(*args, **kwargs):
    return ([{"section": "Headline", "fix": "test fix"}], False)


def _grade(client, monkeypatch=None, **fields):
    if monkeypatch is not None:
        monkeypatch.setattr("unified_app._linkedin_suggestions", _fake_suggestions)
    payload = dict(STRONG_PROFILE)
    payload.update(fields)
    return client.post("/linkedin-grade", data=json.dumps(payload),
                       content_type="application/json")


# ---------- Engine unit tests ----------

def test_strong_profile_scores_high():
    report = grade_linkedin_profile(**STRONG_PROFILE)
    assert report["score"] >= 70
    assert sum(report["breakdown"].values()) == pytest.approx(report["score"])
    assert report["breakdown"]["headline_strength"] <= 20
    assert report["breakdown"]["about_quality"] <= 25


def test_weak_profile_scores_low_with_suggestions():
    report = grade_linkedin_profile(**WEAK_PROFILE)
    assert report["score"] < 50
    assert len(report["suggestions"]) > 0
    sections = {s["section"] for s in report["suggestions"]}
    assert sections  # non-empty set


def test_empty_profile_scores_zero():
    report = grade_linkedin_profile("", "", "", "")
    assert report["score"] == 0
    assert report["suggestions"]


def test_breakdown_never_exceeds_maximums():
    caps = {"headline_strength": 20, "about_quality": 25,
            "experience_quantification": 25, "skills_relevance": 15,
            "completeness": 15}
    long = "x " * 5000
    report = grade_linkedin_profile(long, long, long, long)
    for key, cap in caps.items():
        assert report["breakdown"][key] <= cap
    assert report["score"] <= 100


def test_validate_inputs():
    data, err = validate_linkedin_inputs({})
    assert data is None and err
    data, err = validate_linkedin_inputs({"headline": "x" * (MAX_FIELD_CHARS + 1)})
    assert data is None and err
    data, err = validate_linkedin_inputs({"headline": "Dev"})
    assert data is None and err  # too short overall
    data, err = validate_linkedin_inputs(STRONG_PROFILE)
    assert err is None and data["headline"].startswith("CS Undergrad")


def test_summary_varies_by_score():
    assert "Recruiter" in generate_rule_based_summary({"score": 90})
    assert "serious work" in generate_rule_based_summary({"score": 20})


# ---------- Route tests ----------

def test_unauth_gets_401(client):
    r = client.post("/linkedin-grade", data=json.dumps(STRONG_PROFILE),
                    content_type="application/json")
    assert r.status_code == 401


def test_empty_payload_rejected(authed_client):
    r = authed_client.post("/linkedin-grade", data=json.dumps({}),
                           content_type="application/json")
    assert r.status_code == 400


def test_happy_path_saves_report(authed_client, monkeypatch, app):
    r = _grade(authed_client, monkeypatch)
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["report"]["score"] >= 70
    assert body["saved_url"].startswith("/linkedin/")
    with app.app_context():
        row = LinkedInReport.query.first()
        assert row is not None and row.score == body["report"]["score"]


def test_saved_report_page_renders(authed_client, monkeypatch):
    body = _grade(authed_client, monkeypatch).get_json()
    r = authed_client.get(body["saved_url"])
    assert r.status_code == 200
    assert b"LinkedIn" in r.data


def test_per_user_isolation(client, monkeypatch):
    register(client, name="A", email="a@example.com")
    login(client, email="a@example.com")
    body = _grade(client, monkeypatch).get_json()
    url = body["saved_url"]
    # Log in as a different user (logout is POST-only).
    client.post("/logout", follow_redirects=False)
    register(client, name="B", email="b@example.com")
    login(client, email="b@example.com")
    assert client.get(url).status_code == 404


def test_dashboard_lists_reports(authed_client, monkeypatch):
    _grade(authed_client, monkeypatch)
    r = authed_client.get("/dashboard")
    assert r.status_code == 200
    assert b"LinkedIn Grading Reports" in r.data


def test_gemini_failure_falls_back(authed_client, monkeypatch):
    from unified_app import GeminiError

    def boom(*args, **kwargs):
        raise GeminiError("no key")
    monkeypatch.setattr("unified_app.call_gemini_ai", boom)
    r = _grade(authed_client)  # no _linkedin_suggestions mock: real fn, Gemini raises
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["report"]["ai_powered"] is False
    assert body["report"]["suggestions"]  # rule-based fallback present
