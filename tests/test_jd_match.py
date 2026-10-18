"""Tests for Wave 1 feature #1: JD-matched ATS scoring."""
import io

import pytest

from studybuddy.jd_matcher import (
    JD_MAX_CHARS,
    extract_jd_keywords,
    generate_rule_based_suggestions,
    parse_jd_requirements,
    score_jd_match,
)
from tests.conftest import SAMPLE_RESUME_LINES, login, make_pdf_bytes, register
from unified_app import JDMatchReport

SAMPLE_JD = """Senior Python Developer - Backend Team

We are looking for a Senior Python Developer with 3+ years of experience
building scalable backend systems.

Responsibilities:
- Design and develop REST APIs using Python and Flask
- Work with PostgreSQL and SQL databases
- Deploy services with Docker and Kubernetes
- Collaborate with the frontend team on JavaScript integrations

Required skills:
- Python, Flask, SQL, PostgreSQL, Docker, REST APIs, Git
- Strong understanding of machine learning fundamentals
- Bachelor's degree in Computer Science

Nice to have: Kubernetes, AWS, CI/CD pipelines.
"""


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _fake_suggestions(*args, **kwargs):
    return ([{"section": "Skills", "issue": "test issue", "fix": "test fix"}],
            True)


def _jd_match(client, jd_text=SAMPLE_JD, resume_source="upload",
              pdf_lines=SAMPLE_RESUME_LINES, monkeypatch=None):
    """POST /jd-match with an uploaded PDF resume."""
    if monkeypatch is not None:
        monkeypatch.setattr("unified_app._jd_match_suggestions",
                            _fake_suggestions)
    pdf = make_pdf_bytes(pdf_lines)
    data = {
        "jd_text": jd_text,
        "resume_source": resume_source,
        "resume": (io.BytesIO(pdf), "resume.pdf"),
    }
    return client.post("/jd-match", data=data,
                       content_type="multipart/form-data")


# ---------------------------------------------------------------------------
# Keyword extraction sanity
# ---------------------------------------------------------------------------

def test_extract_jd_keywords_finds_tech_terms():
    kws = extract_jd_keywords(SAMPLE_JD)
    words = {k["keyword"] for k in kws}
    assert "python" in words
    assert "flask" in words
    assert "docker" in words
    # stopwords and noise are filtered
    assert "the" not in words
    assert "and" not in words
    assert len(kws) <= 60
    # ordered by frequency
    counts = [k["count"] for k in kws]
    assert counts == sorted(counts, reverse=True)


def test_parse_jd_requirements_experience_and_title():
    req = parse_jd_requirements(SAMPLE_JD)
    assert req["experience_years_required"] == 3
    assert "Senior Python Developer" in req["job_title"]


def test_parse_jd_requirements_no_years():
    req = parse_jd_requirements("We need a designer who loves Figma and creativity.")
    assert req["experience_years_required"] is None


# ---------------------------------------------------------------------------
# Deterministic scoring sanity
# ---------------------------------------------------------------------------

def test_score_jd_match_structure_and_ranges():
    resume_text = " ".join(SAMPLE_RESUME_LINES)
    report = score_jd_match(resume_text, ["Python", "Flask", "SQL"], 2,
                            {"experience": "x", "skills": "y", "education": "z"},
                            {"email": "a@b.com", "phone": "123"},
                            SAMPLE_JD)
    assert 0 <= report["score"] <= 100
    assert set(report["breakdown"]) == {
        "keyword_coverage", "skills_hit_rate",
        "experience_alignment", "ats_friendliness"}
    for key, cat in report["breakdown"].items():
        assert 0 <= cat["score"] <= cat["max"], key
    total = sum(c["score"] for c in report["breakdown"].values())
    assert abs(total - report["score"]) < 0.2
    assert "python" in {w.lower() for w in report["matched_keywords"]}
    assert report["missing_skills"]  # e.g. kubernetes/aws not on resume


def test_rule_based_suggestions_fallback():
    resume_text = "junior dev"
    report = score_jd_match(resume_text, [], 0, {}, {}, SAMPLE_JD)
    suggs = generate_rule_based_suggestions(report)
    assert 1 <= len(suggs) <= 6
    for s in suggs:
        assert {"section", "issue", "fix"} <= set(s)
        assert s["issue"] and s["fix"]


# ---------------------------------------------------------------------------
# Endpoint: validation + auth
# ---------------------------------------------------------------------------

def test_jd_match_requires_login(client):
    r = client.post("/jd-match", json={"jd_text": SAMPLE_JD})
    assert r.status_code == 401
    assert "log in" in r.get_json()["error"].lower()


def test_jd_match_empty_jd_rejected(authed_client):
    r = authed_client.post("/jd-match", json={"jd_text": "   ",
                                              "resume_source": "upload"})
    assert r.status_code == 400


def test_jd_match_too_short_jd_rejected(authed_client):
    r = authed_client.post("/jd-match", json={"jd_text": "Python dev needed",
                                              "resume_source": "upload"})
    assert r.status_code == 400
    assert "too short" in r.get_json()["error"]


def test_jd_match_oversized_jd_rejected(authed_client):
    r = authed_client.post("/jd-match", json={"jd_text": "x" * (JD_MAX_CHARS + 1),
                                              "resume_source": "upload"})
    assert r.status_code == 400
    assert "too long" in r.get_json()["error"]


def test_jd_match_missing_file_rejected(authed_client, monkeypatch):
    monkeypatch.setattr("unified_app._jd_match_suggestions", _fake_suggestions)
    r = authed_client.post("/jd-match",
                           data={"jd_text": SAMPLE_JD, "resume_source": "upload"},
                           content_type="multipart/form-data")
    assert r.status_code == 400


def test_jd_match_invalid_file_type_rejected(authed_client, monkeypatch):
    monkeypatch.setattr("unified_app._jd_match_suggestions", _fake_suggestions)
    data = {"jd_text": SAMPLE_JD, "resume_source": "upload",
            "resume": (io.BytesIO(b"not a resume"), "evil.exe")}
    r = authed_client.post("/jd-match", data=data,
                           content_type="multipart/form-data")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Endpoint: happy paths
# ---------------------------------------------------------------------------

def test_jd_match_upload_happy_path(authed_client, monkeypatch, app):
    r = _jd_match(authed_client, monkeypatch=monkeypatch)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    payload = r.get_json()
    assert payload["success"] is True
    report = payload["report"]
    assert 0 <= report["score"] <= 100
    assert report["suggestions"]
    assert report["suggestions"][0]["section"] == "Skills"  # mocked
    assert report["ai_powered"] is True
    assert payload["saved_url"].endswith(
        "/jd-match/{}".format(payload["report_id"]))
    with app.app_context():
        row = JDMatchReport.query.get(payload["report_id"])
        assert row is not None
        assert row.score == report["score"]
        assert row.job_title


def test_jd_match_gemini_failure_falls_back(authed_client, monkeypatch):
    """No Gemini key / API failure -> rule-based suggestions, still 200."""
    def _boom(*a, **k):
        from unified_app import GeminiError
        raise GeminiError("no key")
    monkeypatch.setattr("unified_app.call_gemini_ai", _boom)
    r = _jd_match(authed_client)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    report = r.get_json()["report"]
    assert report["ai_powered"] is False
    assert report["suggestions"]  # rule-based fallback present


def test_jd_match_uses_latest_saved_analysis(authed_client, monkeypatch, app):
    # First create a saved analysis via /analyze.
    pdf = make_pdf_bytes(SAMPLE_RESUME_LINES)
    r = authed_client.post("/analyze",
                           data={"resume": (io.BytesIO(pdf), "resume.pdf")},
                           content_type="multipart/form-data")
    assert r.status_code == 200
    monkeypatch.setattr("unified_app._jd_match_suggestions", _fake_suggestions)
    r = authed_client.post("/jd-match",
                           json={"jd_text": SAMPLE_JD,
                                 "resume_source": "latest"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    report = r.get_json()["report"]
    assert 0 <= report["score"] <= 100


def test_jd_match_latest_without_saved_resume_errors(authed_client):
    r = authed_client.post("/jd-match",
                           json={"jd_text": SAMPLE_JD,
                                 "resume_source": "latest"})
    assert r.status_code == 400
    assert "upload" in r.get_json()["error"].lower()


def test_jd_match_report_visible_in_dashboard(authed_client, monkeypatch, app):
    _jd_match(authed_client, monkeypatch=monkeypatch)
    r = authed_client.get("/dashboard")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "JD Match Reports" in html
    assert "Senior Python Developer" in html


def test_jd_match_saved_report_page(authed_client, monkeypatch):
    r = _jd_match(authed_client, monkeypatch=monkeypatch)
    rid = r.get_json()["report_id"]
    r = authed_client.get(f"/jd-match/{rid}")
    assert r.status_code == 200
    assert "jdSavedReport" in r.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Per-user isolation
# ---------------------------------------------------------------------------

def test_jd_match_reports_isolated_between_users(client, monkeypatch, app):
    register(client, name="User One", email="one@example.com")
    login(client, email="one@example.com")
    r = _jd_match(client, monkeypatch=monkeypatch)
    rid = r.get_json()["report_id"]
    client.post("/logout", follow_redirects=False)  # logout is POST-only

    register(client, name="User Two", email="two@example.com")
    login(client, email="two@example.com")
    # User two cannot see user one's report.
    assert client.get(f"/jd-match/{rid}").status_code == 404
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Senior Python Developer" not in html
    with app.app_context():
        assert JDMatchReport.query.count() == 1


def test_jd_match_resume_page_shows_form_for_logged_in(authed_client):
    html = authed_client.get("/resume").get_data(as_text=True)
    assert "jdMatchForm" in html
    assert "Match My Resume" in html


def test_jd_match_resume_page_prompts_login_for_anonymous(client):
    html = client.get("/resume").get_data(as_text=True)
    assert "jdMatchForm" not in html
    assert "Log in to start matching" in html


# ---------------------------------------------------------------------------
# Schema evolution: resume_text backfill on a legacy DB
# ---------------------------------------------------------------------------

