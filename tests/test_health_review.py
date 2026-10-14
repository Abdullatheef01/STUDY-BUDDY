"""Tests for Wave 6 #30: career health review (health_review.py + routes).

Covers: month-key validation & math (pure), each dimension's aggregation
with seeded data, honest empty states, trend vs previous month, next_action
selection, idempotent regeneration, route auth/validation/isolation,
XP awarded exactly once, and momentum opt-out handling.
"""
from datetime import datetime, timedelta, timezone

import pytest

import health_review
import momentum
from health_review import (
    DIMENSION_IDS,
    current_month_key,
    generate_review,
    prev_month_key,
    valid_month_key,
)
from momentum import XP_RULES
from unified_app import (
    AptitudeAttempt,
    CareerAssessment,
    CertPlan,
    DSAProgress,
    Goal,
    HealthReview,
    InterviewSession,
    JobApplication,
    MomentumSettings,
    OpportunityBookmark,
    PaperQuizAttempt,
    Portfolio,
    QuizAttempt,
    ResumeAnalysis,
    StreakState,
    User,
    XPLedger,
    db,
)
from tests.conftest import register, login


UTC = timezone.utc
XP_EVENT = "health_review_completed"


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


@pytest.fixture()
def uid(app):
    """A bare user row (no HTTP round-trip) for pure-logic tests."""
    with app.app_context():
        u = User(name="Review Tester", email="reviewer@example.com")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()
        return u.id


def _uid(app, email="aarav@example.com"):
    with app.app_context():
        return User.query.filter_by(email=email).first().id


def _register_extra(client, email):
    client.post("/logout", follow_redirects=False)
    register(client, name="Extra User", email=email)
    login(client, email=email)


# ---------------------------------------------------------------------------
# Seed helpers (direct model writes inside an app context).
# ---------------------------------------------------------------------------

def _add(app, *rows):
    with app.app_context():
        for r in rows:
            db.session.add(r)
        db.session.commit()


def _assessment(uid, name="Engineering"):
    return CareerAssessment(user_id=uid,
                            top_clusters=[{"name": name, "match": 88}])


def _goal(uid, title="Ship project", status="active"):
    return Goal(user_id=uid, title=title, status=status)


def _resume(uid, ats=82.0):
    return ResumeAnalysis(user_id=uid, filename="r.pdf", ats_score=ats)


def _portfolio(uid):
    return Portfolio(user_id=uid, slug="u%d" % uid, display_name="U")


def _cert(uid, cert_id="aws-saa"):
    return CertPlan(user_id=uid, cert_id=cert_id, weeks=8)


def _app(uid, stage="wishlist", company="Acme"):
    return JobApplication(user_id=uid, company=company, role="SDE",
                          stage=stage)


def _bookmark(uid, opp_id="opp-1"):
    return OpportunityBookmark(user_id=uid, opp_id=opp_id)


def _quiz(uid, pct=80, n=10):
    return QuizAttempt(user_id=uid, skill="python", num_questions=n,
                       started_at=datetime.now(UTC),
                       summary_json={"score": n * pct // 100, "total": n,
                                     "pct": pct})


def _dsa(uid, pid="two-sum"):
    return DSAProgress(user_id=uid, problem_id=pid, status="solved")


def _mock(uid, score=75.0):
    return InterviewSession(user_id=uid, company="Acme", role="SDE",
                            category="behavioral", total_score=score)


def _apt(uid, pct=70.0, submitted=True):
    return AptitudeAttempt(
        user_id=uid, category="quantitative", num_questions=10,
        time_limit_sec=600, started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC) if submitted else None,
        summary_json={"score_pct": pct} if submitted else {})


def _paper(uid, set_id=1):
    return PaperQuizAttempt(user_id=uid, set_id=set_id, score=7, total=10)


def _streak(uid, current=12, longest=40, shields=1):
    return StreakState(user_id=uid, current=current, longest=longest,
                       last_active_date=datetime.now(UTC).date(),
                       shields_used_month=shields, shields_month="2026-10")


def _optout(uid):
    return MomentumSettings(user_id=uid, momentum_opt_out=True)


def _ledger_days_ago(uid, days_ago, tag):
    return XPLedger(user_id=uid, event_type="quiz_completed", xp=20,
                    dedupe_key="%d:quiz_completed:%s" % (uid, tag),
                    created_at=datetime.now(UTC) - timedelta(days=days_ago))


def _dims(app, uid):
    with app.app_context():
        row, _ = generate_review(uid, current_month_key())
        return row.dimensions_json


# ---------------------------------------------------------------------------
# Month-key math (pure).
# ---------------------------------------------------------------------------

def test_valid_month_key_accepts():
    assert valid_month_key("2026-10")
    assert valid_month_key("1999-01")
    assert valid_month_key("2030-12")


def test_valid_month_key_rejects():
    for bad in ["2026-13", "2026-00", "2026-1", "10-2026", "2026/10",
                "202610", "", None, 202610, "abcd-ef", " 2026-10"]:
        assert not valid_month_key(bad), bad


def test_current_month_key_format():
    mk = current_month_key()
    assert valid_month_key(mk)
    now = datetime.now(UTC)
    assert mk == "%04d-%02d" % (now.year, now.month)


def test_prev_month_key():
    assert prev_month_key("2026-10") == "2026-09"
    assert prev_month_key("2026-12") == "2026-11"


def test_prev_month_key_january_rolls_back_year():
    assert prev_month_key("2026-01") == "2025-12"


def test_prev_month_key_bad_raises():
    with pytest.raises(ValueError):
        prev_month_key("nope")


# ---------------------------------------------------------------------------
# direction
# ---------------------------------------------------------------------------

def test_direction_empty_is_honest(app, uid):
    d = _dims(app, uid)["direction"]
    assert d["score"] is None
    assert any("career assessment" in e for e in d["evidence"])


def test_direction_assessment_gives_score_and_top_cluster(app, uid):
    _add(app, _assessment(uid, name="Engineering"))
    d = _dims(app, uid)["direction"]
    assert d["score"] is not None and d["score"] > 0
    assert any("Engineering" in e for e in d["evidence"])
    assert d["confidence"] > 0


def test_direction_goals_add_score_and_evidence(app, uid):
    _add(app, _assessment(uid))
    before = _dims(app, uid)["direction"]["score"]
    _add(app, _goal(uid, "Goal A"), _goal(uid, "Goal B"))
    d = _dims(app, uid)["direction"]
    assert d["score"] > before
    assert any("2 goals tracked" in e for e in d["evidence"])


def test_direction_done_goals_mentioned(app, uid):
    _add(app, _goal(uid, "Done goal", status="done"))
    d = _dims(app, uid)["direction"]
    assert d["score"] is not None
    assert any("1 goal completed" in e for e in d["evidence"])


# ---------------------------------------------------------------------------
# proof
# ---------------------------------------------------------------------------

def test_proof_empty_is_honest(app, uid):
    d = _dims(app, uid)["proof"]
    assert d["score"] is None
    assert any("resume" in e.lower() for e in d["evidence"])


def test_proof_resume_max_ats_evidence(app, uid):
    _add(app, _resume(uid, ats=60.0), _resume(uid, ats=82.0))
    d = _dims(app, uid)["proof"]
    assert d["score"] is not None
    assert any("best ATS 82" in e for e in d["evidence"])
    assert any("2 resume analyses" in e for e in d["evidence"])


def test_proof_portfolio_and_certs_boost(app, uid):
    _add(app, _resume(uid, ats=70.0))
    before = _dims(app, uid)["proof"]["score"]
    _add(app, _portfolio(uid), _cert(uid))
    d = _dims(app, uid)["proof"]
    assert d["score"] > before
    assert any("portfolio page published" in e for e in d["evidence"])
    assert any("certification" in e for e in d["evidence"])


# ---------------------------------------------------------------------------
# opportunity
# ---------------------------------------------------------------------------

def test_opportunity_empty_is_honest(app, uid):
    d = _dims(app, uid)["opportunity"]
    assert d["score"] is None
    assert any("first application" in e for e in d["evidence"])


def test_opportunity_apps_counted(app, uid):
    _add(app, _app(uid, company="A"), _app(uid, company="B"),
         _app(uid, company="C"))
    d = _dims(app, uid)["opportunity"]
    assert d["score"] is not None and d["score"] > 0
    assert any("3 applications tracked" in e for e in d["evidence"])


def test_opportunity_stages_boost_and_evidence(app, uid):
    _add(app, _app(uid, stage="wishlist", company="A"))
    before = _dims(app, uid)["opportunity"]["score"]
    _add(app, _app(uid, stage="interview", company="B"),
         _app(uid, stage="offer", company="C"))
    d = _dims(app, uid)["opportunity"]
    assert d["score"] > before
    assert any("interview" in e for e in d["evidence"])
    assert any("offer" in e for e in d["evidence"])


def test_opportunity_bookmarks_evidence(app, uid):
    _add(app, _bookmark(uid, "o1"), _bookmark(uid, "o2"))
    d = _dims(app, uid)["opportunity"]
    assert any("2 opportunities bookmarked" in e for e in d["evidence"])


# ---------------------------------------------------------------------------
# preparation
# ---------------------------------------------------------------------------

def test_preparation_empty_is_honest(app, uid):
    d = _dims(app, uid)["preparation"]
    assert d["score"] is None
    assert any("complete a quiz" in e for e in d["evidence"])


def test_preparation_quiz_avg_evidence(app, uid):
    for i in range(12):
        _add(app, _quiz(uid, pct=78))
    d = _dims(app, uid)["preparation"]
    assert d["score"] is not None
    assert any("based on 12 quizzes, avg 78%" in e for e in d["evidence"])


def test_preparation_dsa_solved_counted(app, uid):
    _add(app, _quiz(uid, pct=50))
    before = _dims(app, uid)["preparation"]["score"]
    for i in range(5):
        _add(app, _dsa(uid, pid="p-%d" % i))
    d = _dims(app, uid)["preparation"]
    assert d["score"] > before
    assert any("5 DSA problems solved" in e for e in d["evidence"])


def test_preparation_completed_mocks_only(app, uid):
    _add(app, _mock(uid, score=75.0))
    scored = _dims(app, uid)["preparation"]
    assert any("1 mock interview completed" in e for e in scored["evidence"])
    # A session without a score is not a completed mock.
    with app.app_context():
        db.session.add(InterviewSession(user_id=uid, company="X", role="Y",
                                        category="behavioral"))
        db.session.commit()
    assert _dims(app, uid)["preparation"]["score"] == scored["score"]


def test_preparation_aptitude_submitted_only(app, uid):
    _add(app, _apt(uid, pct=70.0, submitted=True),
         _apt(uid, pct=10.0, submitted=False))
    d = _dims(app, uid)["preparation"]
    assert any("1 timed aptitude test, avg 70%" in e for e in d["evidence"])


def test_preparation_paper_quiz_counted(app, uid):
    _add(app, _paper(uid))
    d = _dims(app, uid)["preparation"]
    assert d["score"] is not None
    assert any("1 paper quiz" in e for e in d["evidence"])


# ---------------------------------------------------------------------------
# wellbeing
# ---------------------------------------------------------------------------

def test_wellbeing_opt_out_is_affirming_null(app, uid):
    _add(app, _optout(uid), _streak(uid, current=30, longest=90))
    d = _dims(app, uid)["wellbeing"]
    assert d["score"] is None
    assert any("opted out" in e for e in d["evidence"])
    assert "healthy" in " ".join(d["evidence"])


def test_wellbeing_no_data_is_honest(app, uid):
    d = _dims(app, uid)["wellbeing"]
    assert d["score"] is None
    assert any("momentum" in e.lower() for e in d["evidence"])


def test_wellbeing_streak_scores_positively(app, uid):
    _add(app, _streak(uid, current=12, longest=40, shields=0))
    d = _dims(app, uid)["wellbeing"]
    assert d["score"] is not None and d["score"] > 0
    assert any("12-day current streak" in e for e in d["evidence"])


def test_wellbeing_shields_forgiven_not_penalized(app, uid):
    _add(app, _streak(uid, current=12, longest=40, shields=0))
    no_shield = _dims(app, uid)["wellbeing"]
    with app.app_context():
        st = StreakState.query.filter_by(user_id=uid).first()
        st.shields_used_month = 2
        db.session.commit()
    with_shield = _dims(app, uid)["wellbeing"]
    assert with_shield["score"] == no_shield["score"]
    assert any("forgiven by shields" in e for e in with_shield["evidence"])
    assert any("by design" in e for e in with_shield["evidence"])


def test_wellbeing_active_days_from_ledger(app, uid):
    _add(app, _streak(uid, current=1, longest=1, shields=0),
         *[_ledger_days_ago(uid, d, "t%d" % d) for d in (0, 1, 5)])
    d = _dims(app, uid)["wellbeing"]
    assert any("3 of the last 14 days active" in e for e in d["evidence"])


def test_wellbeing_score_capped_at_100(app, uid):
    _add(app, _streak(uid, current=900, longest=900, shields=2),
         *[_ledger_days_ago(uid, d, "c%d" % d) for d in range(14)])
    d = _dims(app, uid)["wellbeing"]
    assert d["score"] is not None and d["score"] <= 100


# ---------------------------------------------------------------------------
# generate_review: idempotency, trends, narrative, next_action.
# ---------------------------------------------------------------------------

def test_generate_review_persists_five_dimensions(app, uid):
    with app.app_context():
        row, created = generate_review(uid, current_month_key())
        assert created is True
        assert set(row.dimensions_json.keys()) == set(DIMENSION_IDS)
        for did in DIMENSION_IDS:
            d = row.dimensions_json[did]
            assert {"score", "trend", "confidence", "evidence"} <= set(d.keys())
            assert isinstance(d["evidence"], list) and d["evidence"]


def test_generate_review_idempotent_same_month(app, uid):
    mk = current_month_key()
    with app.app_context():
        row1, created1 = generate_review(uid, mk)
        row2, created2 = generate_review(uid, mk)
        assert created1 is True and created2 is False
        assert row1.id == row2.id
        assert HealthReview.query.filter_by(user_id=uid, month_key=mk).count() == 1


def test_generate_review_bad_month_key_raises(app, uid):
    with app.app_context():
        with pytest.raises(ValueError):
            generate_review(uid, "2026-13")
        with pytest.raises(ValueError):
            generate_review(uid, "not-a-month")


def test_trend_positive_vs_previous_month(app, uid):
    prev_mk = prev_month_key(current_month_key())
    with app.app_context():
        _add(app, _quiz(uid, pct=50))
        generate_review(uid, prev_mk)
    _add(app, *[_quiz(uid, pct=100) for _ in range(9)])
    d = _dims(app, uid)["preparation"]
    assert d["trend"] is not None and d["trend"] > 0


def test_trend_none_without_previous_review(app, uid):
    _add(app, _quiz(uid, pct=80))
    d = _dims(app, uid)["preparation"]
    assert d["trend"] is None


def test_trend_none_when_both_months_locked(app, uid):
    prev_mk = prev_month_key(current_month_key())
    with app.app_context():
        generate_review(uid, prev_mk)
        row, _ = generate_review(uid, current_month_key())
        trend = row.dimensions_json["direction"]["trend"]
    assert trend is None  # no scores on either side -> no trend


def test_narrative_plain_no_fake_precision(app, uid):
    _add(app, _assessment(uid), _quiz(uid, pct=80))
    with app.app_context():
        row, _ = generate_review(uid, current_month_key())
        n = row.narrative
    assert n and len(n.split(". ")) >= 2
    for junk in ("0.00", "NaN", "synergy", "leverage"):
        assert junk not in n


def test_narrative_all_locked_is_kind(app, uid):
    with app.app_context():
        row, _ = generate_review(uid, current_month_key())
        narrative, next_action = row.narrative, row.next_action
    assert "Not much signal yet" in narrative
    assert next_action  # fallback action still exists


def test_next_action_weakest_unlocked_dimension(app, uid):
    # Strong proof, nothing else -> opportunity is not unlocked; weakest
    # unlocked is proof -> action should be about proof.
    _add(app, _resume(uid, ats=90.0), _portfolio(uid), _cert(uid))
    with app.app_context():
        row, _ = generate_review(uid, current_month_key())
        next_action = row.next_action
    assert any(w in next_action.lower()
               for w in ("portfolio", "resume", "certification"))


def test_next_action_direction_without_assessment(app, uid):
    _add(app, _goal(uid, "Get a job"))
    with app.app_context():
        row, _ = generate_review(uid, current_month_key())
        next_action = row.next_action
    assert "career assessment" in next_action.lower()


def test_next_action_opportunity_is_weakest(app, uid):
    _add(app, *[_quiz(uid, pct=90) for _ in range(9)])  # strong preparation
    _add(app, _app(uid, stage="wishlist", company="Z"))  # weak opportunity
    with app.app_context():
        row, _ = generate_review(uid, current_month_key())
        dims = dict(row.dimensions_json)
        next_action = row.next_action
    assert dims["opportunity"]["score"] < dims["preparation"]["score"]
    assert "wishlist" in next_action  # weakest unlocked -> move it along


def test_confidence_and_score_ranges(app, uid):
    _add(app, _assessment(uid), _resume(uid, ats=95.0), _portfolio(uid),
         _cert(uid), _app(uid, stage="offer"), _bookmark(uid),
         _quiz(uid, pct=95), _dsa(uid), _mock(uid), _apt(uid),
         _paper(uid), _streak(uid))
    dims = _dims(app, uid)
    for did, d in dims.items():
        assert 0 <= d["confidence"] <= 100, did
        assert d["score"] is None or 0 <= d["score"] <= 100, did


def test_other_users_reviews_do_not_leak_trends(app, client):
    register(client)  # alice (aarav@example.com)
    alice = _uid(app)
    _register_extra(client, "bob@example.com")
    bob = _uid(app, "bob@example.com")
    mk = current_month_key()
    with app.app_context():
        generate_review(bob, prev_month_key(mk))
        row, _ = generate_review(alice, mk)
        trend = row.dimensions_json["preparation"]["trend"]
    assert trend is None


# ---------------------------------------------------------------------------
# Routes.
# ---------------------------------------------------------------------------

def test_hub_requires_login(client):
    r = client.get("/review", follow_redirects=False)
    assert r.status_code == 302


def test_hub_renders_and_creates_review(authed_client, app):
    uid = _uid(app)
    r = authed_client.get("/review")
    assert r.status_code == 200
    with app.app_context():
        assert HealthReview.query.filter_by(
            user_id=uid, month_key=current_month_key()).count() == 1
    html = r.get_data(as_text=True)
    for title in ("Direction", "Proof", "Opportunity activity",
                  "Preparation", "Wellbeing"):
        assert title in html
    assert "Career health review" in html


def test_month_route_bad_format_400(authed_client):
    for bad in ("2026-13", "nope", "2026-1", "10-2026"):
        r = authed_client.get("/review/%s" % bad)
        assert r.status_code == 400, bad


def test_month_route_missing_404(authed_client):
    assert authed_client.get("/review/2020-01").status_code == 404


def test_month_route_other_user_404(authed_client, app, client):
    uid = _uid(app)
    with app.app_context():
        generate_review(uid, current_month_key())
    _register_extra(client, "carol@example.com")
    r = client.get("/review/%s" % current_month_key())
    assert r.status_code == 404


def test_month_route_past_review_200(authed_client, app):
    uid = _uid(app)
    prev_mk = prev_month_key(current_month_key())
    with app.app_context():
        generate_review(uid, prev_mk)
    r = authed_client.get("/review/%s" % prev_mk)
    assert r.status_code == 200
    assert prev_mk in r.get_data(as_text=True)


def test_hub_history_lists_past_months(authed_client, app):
    uid = _uid(app)
    prev_mk = prev_month_key(current_month_key())
    with app.app_context():
        generate_review(uid, prev_mk)
    html = authed_client.get("/review").get_data(as_text=True)
    assert "/review/%s" % prev_mk in html


def test_hub_shows_trend_arrow_with_history(authed_client, app):
    uid = _uid(app)
    prev_mk = prev_month_key(current_month_key())
    with app.app_context():
        db.session.add(_quiz(uid, pct=50))
        db.session.commit()
        generate_review(uid, prev_mk)
    for _ in range(9):
        _add(app, _quiz(uid, pct=100))
    html = authed_client.get("/review").get_data(as_text=True)
    assert "&#9650;" in html  # up arrow for the improved preparation score


def test_hub_opt_out_wellbeing_note(authed_client, app):
    uid = _uid(app)
    _add(app, _optout(uid))
    html = authed_client.get("/review").get_data(as_text=True)
    assert "opted out" in html


def test_regenerate_requires_login(client):
    r = client.post("/review/api/regenerate", follow_redirects=False)
    assert r.status_code == 302


def test_regenerate_returns_review_json(authed_client, app):
    authed_client.get("/review")  # first generation via hub
    r = authed_client.post("/review/api/regenerate", json={})
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["ok"] is True
    assert payload["created"] is False
    assert payload["month_key"] == current_month_key()
    assert len(payload["review"]["dimensions"]) == 5
    for d in payload["review"]["dimensions"]:
        assert {"score", "trend", "confidence", "evidence"} <= set(d.keys())
        assert "signals" not in d  # internal signals stay server-side


def test_regenerate_first_call_created_and_xp_once(authed_client, app):
    uid = _uid(app)
    r1 = authed_client.post("/review/api/regenerate", json={})
    p1 = r1.get_json()
    assert p1["created"] is True
    r2 = authed_client.post("/review/api/regenerate", json={})
    p2 = r2.get_json()
    assert p2["created"] is False
    assert p2["xp_awarded"] is False
    if XP_EVENT in XP_RULES:
        assert p1["xp_awarded"] is True
        with app.app_context():
            n = XPLedger.query.filter_by(
                user_id=uid, event_type=XP_EVENT).count()
        assert n == 1, "XP must be awarded exactly once, not per regenerate"
    else:
        pytest.skip("parallel worker has not landed the XP_RULES entry yet")


def test_regenerate_updates_existing_row(authed_client, app):
    uid = _uid(app)
    authed_client.post("/review/api/regenerate", json={})
    with app.app_context():
        first_id = HealthReview.query.filter_by(
            user_id=uid, month_key=current_month_key()).first().id
    _add(app, _assessment(uid))
    authed_client.post("/review/api/regenerate", json={})
    with app.app_context():
        row = HealthReview.query.filter_by(
            user_id=uid, month_key=current_month_key()).first()
        assert row.id == first_id
        assert row.dimensions_json["direction"]["score"] is not None


def test_nav_link_present(authed_client):
    html = authed_client.get("/review").get_data(as_text=True)
    assert "Career health review" in html
