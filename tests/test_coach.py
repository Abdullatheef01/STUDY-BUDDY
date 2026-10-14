"""Tests for Wave 2 #14: communication coach."""
import json
import os

import pytest

from studybuddy.communication_coach import (analyze_transcript, find_filler_hits,
                                 validate_coach_inputs)


@pytest.fixture
def authed_client(client, app):
    from werkzeug.security import generate_password_hash
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from unified_app import db, User
    with app.app_context():
        u = User(email="coach@test.com", name="Coach Tester",
                 password_hash=generate_password_hash("password123"))
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"email": "coach@test.com",
                                "password": "password123"})
    return client


RICH_TEXT = (
    "Um, so basically I think I would say that I actually led a project, "
    "you know, and it was basically very, very successful. "
    "The system was built by our team and it was deployed quickly. "
    "I sort of managed the stakeholders and stuff, and things went well, "
    "very well indeed. I literally worked on it for like six months, "
    "and I think probably it was the best project ever, to be honest."
)


def test_filler_bank_loads():
    hits = find_filler_hits("um uh like basically actually")
    words = {h["word"] for h in hits}
    assert {"um", "uh", "like", "basically", "actually"} <= words
    for h in hits:
        assert h["severity"] in (1, 2, 3)
        assert isinstance(h["alternatives"], list)


def test_filler_positions_usable_for_highlighting():
    hits = find_filler_hits("um hello um")
    um = [h for h in hits if h["word"] == "um"][0]
    assert um["count"] == 2
    assert len(um["positions"]) == 2
    for pos in um["positions"]:
        assert "um hello um"[pos:pos + 2].lower() == "um"


def test_analyze_structure():
    r = analyze_transcript(RICH_TEXT)
    assert 0 <= r["clarity_score"] <= 100
    assert set(r["breakdown"]) == {"filler_load", "pacing",
                                   "voice_and_hedges", "structure"}
    assert r["metrics"]["word_count"] > 40
    assert r["metrics"]["filler_events"] > 5
    assert r["metrics"]["passive_constructions"] >= 1
    assert r["metrics"]["hedge_events"] >= 1
    assert r["suggestions"]
    assert r["cleaned_version"]
    assert r["drills"]


def test_clean_text_scores_higher():
    clean = ("I led a migration project for our checkout service. The team "
             "replaced a monolithic deploy with a canary pipeline. Error rates "
             "dropped from eight percent to one tenth of a percent within a week. "
             "I coordinated four engineers and presented the results to leadership.")
    messy = ("Um, so basically I think I sort of led like a project, you know, "
             "and it was basically very very successful and stuff. The system was "
             "built by us and it was deployed, and I literally think it was "
             "probably the best thing ever, to be honest.")
    assert analyze_transcript(clean)["clarity_score"] > \
        analyze_transcript(messy)["clarity_score"]


def test_cleaned_version_removes_severe_fillers():
    r = analyze_transcript(RICH_TEXT)
    low = r["cleaned_version"].lower()
    assert "um," not in low and " um " not in low
    assert "you know" not in low


def test_validation():
    t, e = validate_coach_inputs({"text": "too short"})
    assert t is None and e
    t, e = validate_coach_inputs({"text": "x" * 60})
    assert t and e is None
    t, e = validate_coach_inputs({"text": "x" * 10001})
    assert t is None and e


def test_coach_home_unauth_ok(client):
    r = client.get("/coach")
    assert r.status_code == 200
    assert b"Log in" in r.data


def test_analyze_requires_login(client):
    r = client.post("/coach/analyze", json={"text": "x" * 60})
    assert r.status_code == 401


def test_analyze_rejects_short(client, authed_client):
    r = authed_client.post("/coach/analyze", json={"text": "short"})
    assert r.status_code == 400


def test_analyze_flow(authed_client, app):
    from unified_app import CommunicationAnalysis
    r = authed_client.post("/coach/analyze", json={"text": RICH_TEXT})
    assert r.status_code == 200, r.data[:300]
    d = r.get_json()
    assert d["success"] and d["report"]["clarity_score"] < 75
    assert d["report_url"].startswith("/coach/")
    with app.app_context():
        row = CommunicationAnalysis.query.get(d["analysis_id"])
        assert row is not None
        assert abs(row.clarity_score - d["report"]["clarity_score"]) < 0.01
    # saved report page
    r = authed_client.get(d["report_url"])
    assert r.status_code == 200
    assert b"Communication Coach Report" in r.data


def test_coach_isolation(client, authed_client, app):
    from werkzeug.security import generate_password_hash
    from unified_app import db, User, CommunicationAnalysis
    with app.app_context():
        u2 = User(email="coach2@test.com", name="Other",
                  password_hash=generate_password_hash("password123"))
        db.session.add(u2)
        db.session.commit()
        row = CommunicationAnalysis(user_id=u2.id, clarity_score=10.0,
                                    analysis_json={"clarity_score": 10.0})
        db.session.add(row)
        db.session.commit()
        other_id = row.id
    r = authed_client.get(f"/coach/{other_id}")
    assert r.status_code == 404


def test_xss_safe_report(authed_client):
    payload = ("This is a reasonable length answer with some content in it, "
               "<script>alert(1)</script> and more words to reach the minimum "
               "length requirement for the coach analysis endpoint.")
    r = authed_client.post("/coach/analyze", json={"text": payload})
    assert r.status_code == 200
    d = r.get_json()
    r = authed_client.get(d["report_url"])
    assert r.status_code == 200
    assert b"<script>alert(1)</script>" not in r.data
