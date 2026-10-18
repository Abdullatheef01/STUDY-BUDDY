"""Tests for Wave 5 #28: peer mock interviews (rooms, rubrics, reciprocal
feedback, scheduling, safety).

Covers: room creation + token uniqueness, hub board visibility (incl.
invite-only exclusion and blocked-user exclusion), guest join (self-join
rejected, blocked rejected, post-finish rejected), question draws from the
shared interview bank, answer saving + upsert, role swap, finish + XP via
XPLedger, reciprocal feedback both directions + score validation, slot
propose/accept, report/block, auth redirects, CSRF rejection, and graceful
404/403/400 handling.
"""
from datetime import datetime, timedelta, timezone

import pytest

from unified_app import (
    N_PEER_QUESTIONS,
    PeerAnswer,
    PeerBlock,
    PeerFeedback,
    PeerRoom,
    User,
    XPLedger,
    _peer_blocked,
    _peer_parse_slot,
    _peer_questions,
    create_app,
    db,
)
from tests.conftest import register, login


UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).first().id


def _register_extra(client, name, email):
    """Register an additional user (logout first: register skips while a
    session is active)."""
    client.post("/logout", follow_redirects=False)
    return register(client, name=name, email=email)


def _login_as(client, email):
    client.post("/logout", follow_redirects=False)
    return login(client, email=email)


def _room(app, token):
    with app.app_context():
        return PeerRoom.query.filter_by(token=token).first()


def _create_room(client, role="backend", category="technical",
                 invite_only=False, scheduled_at=None):
    body = {"role": role, "category": category, "invite_only": invite_only}
    if scheduled_at:
        body["scheduled_at"] = scheduled_at
    r = client.post("/peer/api/rooms", json=body)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return r.get_json()


def _two_users_room(client, app, **kwargs):
    """Host creates a room; guest registers and joins. Returns token."""
    data = _create_room(client, **kwargs)
    _host_email = "aarav@example.com"
    _register_extra(client, "Priya Nair", "priya@example.com")
    _login_as(client, "priya@example.com")
    r = client.post("/peer/api/room/%s/join" % data["token"], json={})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return data["token"]


def _finish(client, token):
    r = client.post("/peer/api/room/%s/finish" % token, json={})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return r.get_json()


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


@pytest.fixture()
def csrf_app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "peer-csrf-test",
        "WTF_CSRF_ENABLED": True,
    })
    with app.app_context():
        db.create_all()
    yield app


# ---------------------------------------------------------------------------
# Room creation
# ---------------------------------------------------------------------------

def test_create_room_success(authed_client, app):
    data = _create_room(authed_client, role="backend", category="technical")
    assert data["success"] is True
    assert len(data["token"]) == 12
    assert data["questions"] == N_PEER_QUESTIONS
    room = _room(app, data["token"])
    assert room is not None
    assert room.status == "open"
    assert room.invite_only is False
    assert room.host_id == _uid(app, "aarav@example.com")
    assert room.interviewer_id == room.host_id
    assert room.guest_id is None
    assert len(room.question_ids) == N_PEER_QUESTIONS


def test_create_room_defaults_role_category(authed_client, app):
    r = authed_client.post("/peer/api/rooms", json={})
    assert r.status_code == 200
    room = _room(app, r.get_json()["token"])
    assert room.role == "general"
    assert room.category == "behavioral"


def test_create_room_invalid_role(authed_client):
    r = authed_client.post("/peer/api/rooms", json={"role": "astronaut"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_create_room_invalid_category(authed_client):
    r = authed_client.post("/peer/api/rooms", json={"category": "cooking"})
    assert r.status_code == 400


def test_create_room_invite_only(authed_client, app):
    data = _create_room(authed_client, invite_only=True)
    assert _room(app, data["token"]).invite_only is True


def test_create_room_bad_scheduled_at(authed_client):
    r = authed_client.post("/peer/api/rooms",
                           json={"scheduled_at": "not a date"})
    assert r.status_code == 400


def test_create_room_with_scheduled_at(authed_client, app):
    future = (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    data = _create_room(authed_client, scheduled_at=future)
    room = _room(app, data["token"])
    assert room.scheduled_at is not None
    assert room.scheduled_at.strftime("%Y-%m-%d %H:%M") == future


def test_tokens_unique(authed_client):
    tokens = {_create_room(authed_client)["token"] for _ in range(15)}
    assert len(tokens) == 15


def test_create_room_unauth_redirect(client):
    r = client.post("/peer/api/rooms", json={"role": "backend"})
    assert r.status_code == 302


# ---------------------------------------------------------------------------
# Hub board
# ---------------------------------------------------------------------------

def test_hub_renders(authed_client):
    r = authed_client.get("/peer")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Peer mock interviews" in html
    assert "csrf-token" in html


def test_hub_unauth_redirect(client):
    assert client.get("/peer").status_code == 302


def test_open_board_shows_open_room(authed_client):
    data = _create_room(authed_client)
    # a second user sees the room on the board
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    html = authed_client.get("/peer").get_data(as_text=True)
    assert data["token"] in html


def test_open_board_hides_invite_only(authed_client):
    data = _create_room(authed_client, invite_only=True)
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    html = authed_client.get("/peer").get_data(as_text=True)
    assert data["token"] not in html


def test_open_board_hides_blocked_users_rooms(authed_client, app):
    data = _create_room(authed_client)
    host_id = _uid(app, "aarav@example.com")
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    priya_id = _uid(app, "priya@example.com")
    with app.app_context():
        db.session.add(PeerBlock(blocker_id=priya_id, blocked_id=host_id,
                                 reason="test"))
        db.session.commit()
    _login_as(authed_client, "priya@example.com")
    html = authed_client.get("/peer").get_data(as_text=True)
    assert data["token"] not in html


def test_my_rooms_lists_host_room(authed_client):
    data = _create_room(authed_client)
    html = authed_client.get("/peer").get_data(as_text=True)
    assert data["token"] in html
    assert "Your room" in html


# ---------------------------------------------------------------------------
# Join flow
# ---------------------------------------------------------------------------

def test_guest_join_success(authed_client, app):
    data = _create_room(authed_client)
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["status"] == "in_progress"
    room = _room(app, data["token"])
    assert room.guest_id == _uid(app, "priya@example.com")
    assert room.status == "in_progress"


def test_self_join_rejected(authed_client):
    data = _create_room(authed_client)
    r = authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    assert r.status_code == 403
    assert "error" in r.get_json()


def test_join_invalid_token_404(authed_client):
    r = authed_client.post("/peer/api/room/doesnotexist1/join", json={})
    assert r.status_code == 404


def test_join_after_finish_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.post("/peer/api/room/%s/join" % token, json={})
    assert r.status_code == 400


def test_join_second_guest_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.post("/peer/api/room/%s/join" % token, json={})
    assert r.status_code == 400


def test_join_unauth_redirect(client):
    r = client.post("/peer/api/room/sometoken12/join", json={})
    assert r.status_code == 302


def test_join_scheduled_future_room_waits(authed_client, app):
    future = (datetime.now(UTC) + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    data = _create_room(authed_client, scheduled_at=future)
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    assert r.status_code == 200
    assert r.get_json()["status"] == "waiting"


def test_start_waiting_room(authed_client, app):
    future = (datetime.now(UTC) + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    data = _create_room(authed_client, scheduled_at=future)
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    r = authed_client.post("/peer/api/room/%s/start" % data["token"], json={})
    assert r.status_code == 200
    assert _room(app, data["token"]).status == "in_progress"


def test_start_already_live_room_idempotent(authed_client, app):
    token = _two_users_room(authed_client, app)
    r = authed_client.post("/peer/api/room/%s/start" % token, json={})
    assert r.status_code == 200
    assert r.get_json()["status"] == "in_progress"


def test_start_open_room_rejected(authed_client):
    data = _create_room(authed_client)
    r = authed_client.post("/peer/api/room/%s/start" % data["token"], json={})
    assert r.status_code == 400


def test_join_blocked_user_rejected(authed_client, app):
    data = _create_room(authed_client)
    host_id = _uid(app, "aarav@example.com")
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    priya_id = _uid(app, "priya@example.com")
    with app.app_context():
        db.session.add(PeerBlock(blocker_id=host_id, blocked_id=priya_id,
                                 reason="spam"))
        db.session.commit()
    assert _peer_blocked(host_id, priya_id) is True
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Question draws from the shared bank
# ---------------------------------------------------------------------------

def test_peer_questions_technical_backend():
    qs = _peer_questions("backend", "technical", n=6)
    assert len(qs) == 6
    for q in qs:
        assert q["category"] in ("dsa", "system_design", "puzzles")
        assert "backend" in q["roles"]


def test_peer_questions_behavioral():
    qs = _peer_questions("frontend", "behavioral", n=6)
    assert len(qs) == 6
    for q in qs:
        assert q["category"] in ("behavioral", "hr")


def test_peer_questions_data_role():
    qs = _peer_questions("data", "technical", n=10)
    assert len(qs) == 10
    for q in qs:
        assert ("data_analyst" in q["roles"] or "data_scientist" in q["roles"])


def test_peer_questions_exclude():
    first = _peer_questions("backend", "behavioral", n=6)
    ids = [q["id"] for q in first]
    second = _peer_questions("backend", "behavioral", n=6, exclude=ids)
    assert not (set(ids) & {q["id"] for q in second})


def test_peer_questions_unknown_role_falls_back():
    qs = _peer_questions("nonsense", "behavioral", n=4)
    assert len(qs) == 4


def test_peer_parse_slot():
    assert _peer_parse_slot("2026-10-20 18:00") is not None
    assert _peer_parse_slot("2026-10-20T18:00") is not None
    assert _peer_parse_slot("garbage") is None
    assert _peer_parse_slot("") is None
    assert _peer_parse_slot(None) is None


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------

def test_interviewee_saves_answer(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    qid = room.question_ids[0]
    # guest (priya) is the interviewee: host is the interviewer
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": qid,
                                 "answer_text": "My detailed answer."})
    assert r.status_code == 200
    with app.app_context():
        ans = PeerAnswer.query.filter_by(room_id=room.id).one()
        assert ans.answer_text == "My detailed answer."
        assert ans.user_id == _uid(app, "priya@example.com")
        assert ans.question_text


def test_interviewer_cannot_answer(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    _login_as(authed_client, "aarav@example.com")  # host = interviewer
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": room.question_ids[0],
                                 "answer_text": "x" * 10})
    assert r.status_code == 403


def test_answer_unknown_question_404(authed_client, app):
    token = _two_users_room(authed_client, app)
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": "nope-999",
                                 "answer_text": "hello"})
    assert r.status_code == 404


def test_answer_empty_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": room.question_ids[0],
                                 "answer_text": "   "})
    assert r.status_code == 400


def test_answer_upsert_updates(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    qid = room.question_ids[0]
    url = "/peer/api/room/%s/answer" % token
    authed_client.post(url, json={"question_id": qid, "answer_text": "v1"})
    authed_client.post(url, json={"question_id": qid, "answer_text": "v2"})
    with app.app_context():
        rows = PeerAnswer.query.filter_by(room_id=room.id,
                                          question_id=qid).all()
        assert len(rows) == 1
        assert rows[0].answer_text == "v2"


def test_answer_after_done_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    qid = room.question_ids[0]
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": qid, "answer_text": "late"})
    assert r.status_code == 400


def test_answer_non_participant_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": room.question_ids[0],
                                 "answer_text": "intruder"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Role swap
# ---------------------------------------------------------------------------

def test_swap_flips_interviewer_and_draws_fresh(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    host_id = _uid(app, "aarav@example.com")
    guest_id = _uid(app, "priya@example.com")
    old_qids = list(room.question_ids)
    assert room.interviewer_id == host_id
    _login_as(authed_client, "aarav@example.com")
    r = authed_client.post("/peer/api/room/%s/swap" % token, json={})
    assert r.status_code == 200
    body = r.get_json()
    assert body["round_no"] == 1
    assert body["interviewer_id"] == guest_id
    room = _room(app, token)
    assert room.interviewer_id == guest_id
    assert room.round_no == 1
    # fresh questions: no overlap with the previous round
    assert not (set(old_qids) & set(room.question_ids))
    assert len(room.question_ids) == N_PEER_QUESTIONS


def test_swapped_interviewee_can_now_answer(authed_client, app):
    token = _two_users_room(authed_client, app)
    _login_as(authed_client, "aarav@example.com")
    authed_client.post("/peer/api/room/%s/swap" % token, json={})
    room = _room(app, token)
    r = authed_client.post("/peer/api/room/%s/answer" % token,
                           json={"question_id": room.question_ids[0],
                                 "answer_text": "host answers now"})
    assert r.status_code == 200


def test_swap_without_guest_rejected(authed_client):
    data = _create_room(authed_client)
    r = authed_client.post("/peer/api/room/%s/swap" % data["token"], json={})
    assert r.status_code == 400


def test_swap_before_start_rejected(authed_client, app):
    future = (datetime.now(UTC) + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    data = _create_room(authed_client, scheduled_at=future)
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    r = authed_client.post("/peer/api/room/%s/swap" % data["token"], json={})
    assert r.status_code == 400


def test_swap_non_participant_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.post("/peer/api/room/%s/swap" % token, json={})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Finish + XP
# ---------------------------------------------------------------------------

def test_finish_marks_done(authed_client, app):
    token = _two_users_room(authed_client, app)
    body = _finish(authed_client, token)
    assert body["success"] is True
    assert _room(app, token).status == "done"


def test_finish_awards_xp_to_both(app, authed_client):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    guest_id = _uid(app, "priya@example.com")
    _finish(authed_client, token)
    with app.app_context():
        host_rows = XPLedger.query.filter_by(
            user_id=host_id, event_type="peer_session_completed").all()
        guest_rows = XPLedger.query.filter_by(
            user_id=guest_id, event_type="peer_session_completed").all()
        assert len(host_rows) == 1
        assert len(guest_rows) == 1
        assert host_rows[0].xp == 40


def test_finish_idempotent_no_double_xp(app, authed_client):
    token = _two_users_room(authed_client, app)
    _finish(authed_client, token)
    r = authed_client.post("/peer/api/room/%s/finish" % token, json={})
    assert r.status_code == 200
    assert r.get_json().get("already") is True
    with app.app_context():
        n = XPLedger.query.filter_by(
            event_type="peer_session_completed").count()
        assert n == 2  # one per participant, no duplicates


def test_finish_unauth_redirect(client):
    assert client.post("/peer/api/room/whatever1234/finish",
                       json={}).status_code == 302


def test_finish_non_participant_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.post("/peer/api/room/%s/finish" % token, json={})
    assert r.status_code == 403


def test_finish_invalid_token_404(authed_client):
    r = authed_client.post("/peer/api/room/nope-nope-12/finish", json={})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Reciprocal feedback
# ---------------------------------------------------------------------------

def _feedback_body(reviewee_id, **over):
    body = {"reviewee_id": reviewee_id, "clarity": 5, "structure": 4,
            "depth": 4, "relevance": 5, "confidence": 3,
            "comments": "Great structured answers."}
    body.update(over)
    return body


def test_feedback_both_directions(authed_client, app):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    guest_id = _uid(app, "priya@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    url = "/peer/api/room/%s/feedback" % token
    # guest reviews host
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post(url, json=_feedback_body(host_id))
    assert r.status_code == 200
    # host reviews guest
    _login_as(authed_client, "aarav@example.com")
    r = authed_client.post(url, json=_feedback_body(guest_id, clarity=3))
    assert r.status_code == 200
    with app.app_context():
        rows = PeerFeedback.query.filter_by(room_id=_room(app, token).id).all()
        assert len(rows) == 2
        by_reviewer = {f.reviewer_id: f for f in rows}
        assert by_reviewer[guest_id].reviewee_id == host_id
        assert by_reviewer[host_id].reviewee_id == guest_id
        assert by_reviewer[host_id].clarity == 3
        assert by_reviewer[guest_id].comments == "Great structured answers."


def test_feedback_score_validation(authed_client, app):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    _guest_id = _uid(app, "priya@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _login_as(authed_client, "priya@example.com")
    url = "/peer/api/room/%s/feedback" % token
    for bad in (0, 6, "high", None):
        r = authed_client.post(url, json=_feedback_body(host_id, depth=bad))
        assert r.status_code == 400, bad
    r = authed_client.post(url, json=_feedback_body(host_id))
    assert r.status_code == 200  # sanity: valid still works


def test_feedback_self_review_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    guest_id = _uid(app, "priya@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/feedback" % token,
                           json=_feedback_body(guest_id))
    assert r.status_code == 400


def test_feedback_non_partner_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    rohan_id = _uid(app, "rohan@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/feedback" % token,
                           json=_feedback_body(rohan_id))
    assert r.status_code == 403


def test_feedback_before_finish_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/feedback" % token,
                           json=_feedback_body(host_id))
    assert r.status_code == 400


def test_feedback_upsert(authed_client, app):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _login_as(authed_client, "priya@example.com")
    url = "/peer/api/room/%s/feedback" % token
    authed_client.post(url, json=_feedback_body(host_id, clarity=2))
    authed_client.post(url, json=_feedback_body(host_id, clarity=5,
                                                comments="Improved!"))
    with app.app_context():
        rows = PeerFeedback.query.filter_by(
            room_id=_room(app, token).id).all()
        assert len(rows) == 1
        assert rows[0].clarity == 5
        assert rows[0].comments == "Improved!"


def test_feedback_non_participant_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.post("/peer/api/room/%s/feedback" % token,
                           json=_feedback_body(host_id))
    assert r.status_code == 403


def test_feedback_summary_on_room_page(authed_client, app):
    token = _two_users_room(authed_client, app)
    host_id = _uid(app, "aarav@example.com")
    _guest_id = _uid(app, "priya@example.com")
    _login_as(authed_client, "aarav@example.com")
    _finish(authed_client, token)
    _login_as(authed_client, "priya@example.com")
    authed_client.post("/peer/api/room/%s/feedback" % token,
                       json=_feedback_body(host_id))
    html = authed_client.get("/peer/room/%s" % token).get_data(as_text=True)
    assert "Great structured answers." in html
    assert "Clarity" in html


# ---------------------------------------------------------------------------
# Scheduling: propose / accept
# ---------------------------------------------------------------------------

def test_propose_slots(authed_client, app):
    data = _create_room(authed_client)
    room = _room(app, data["token"])
    r = authed_client.post("/peer/api/rooms/%d/slots" % room.id,
                           json={"slots": "2026-10-20 18:00, 2026-10-21 18:00"})
    assert r.status_code == 200
    assert r.get_json()["slots"] == ["2026-10-20 18:00", "2026-10-21 18:00"]
    assert _room(app, data["token"]).proposed_slots == ["2026-10-20 18:00",
                                                        "2026-10-21 18:00"]


def test_propose_slots_bad_format(authed_client, app):
    data = _create_room(authed_client)
    room = _room(app, data["token"])
    r = authed_client.post("/peer/api/rooms/%d/slots" % room.id,
                           json={"slots": "tomorrow-ish"})
    assert r.status_code == 400


def test_propose_slots_non_host_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    # logged in as guest (priya)
    r = authed_client.post("/peer/api/rooms/%d/slots" % room.id,
                           json={"slots": "2026-10-20 18:00"})
    assert r.status_code == 403


def test_accept_slot_schedules_room(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    _login_as(authed_client, "aarav@example.com")
    authed_client.post("/peer/api/rooms/%d/slots" % room.id,
                       json={"slots": "2026-12-20 18:00, 2026-12-21 18:00"})
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/slot/accept" % token,
                           json={"slot": "2026-12-20 18:00"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "waiting"
    room = _room(app, token)
    assert room.scheduled_at.strftime("%Y-%m-%d %H:%M") == "2026-12-20 18:00"


def test_accept_unproposed_slot_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    _login_as(authed_client, "aarav@example.com")
    authed_client.post("/peer/api/rooms/%d/slots" % room.id,
                       json={"slots": "2026-12-20 18:00"})
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/slot/accept" % token,
                           json={"slot": "2026-12-25 18:00"})
    assert r.status_code == 400


def test_accept_slot_host_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    room = _room(app, token)
    _login_as(authed_client, "aarav@example.com")
    authed_client.post("/peer/api/rooms/%d/slots" % room.id,
                       json={"slots": "2026-12-20 18:00"})
    r = authed_client.post("/peer/api/room/%s/slot/accept" % token,
                           json={"slot": "2026-12-20 18:00"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Report + block (safety)
# ---------------------------------------------------------------------------

def test_report_creates_block(authed_client, app):
    _token = _two_users_room(authed_client, app)
    guest_id = _uid(app, "priya@example.com")
    _login_as(authed_client, "aarav@example.com")
    r = authed_client.post("/peer/api/report",
                           json={"user_id": guest_id, "reason": "rude"})
    assert r.status_code == 200
    with app.app_context():
        blk = PeerBlock.query.filter_by(
            blocker_id=_uid(app, "aarav@example.com"),
            blocked_id=guest_id).one()
        assert blk.reason == "rude"


def test_report_is_idempotent(authed_client, app):
    _token = _two_users_room(authed_client, app)
    guest_id = _uid(app, "priya@example.com")
    _login_as(authed_client, "aarav@example.com")
    for _ in range(2):
        r = authed_client.post("/peer/api/report",
                               json={"user_id": guest_id})
        assert r.status_code == 200
    with app.app_context():
        n = PeerBlock.query.filter_by(
            blocker_id=_uid(app, "aarav@example.com"),
            blocked_id=guest_id).count()
        assert n == 1


def test_report_self_rejected(authed_client, app):
    me = _uid(app, "aarav@example.com")
    r = authed_client.post("/peer/api/report", json={"user_id": me})
    assert r.status_code == 400


def test_report_unknown_user_404(authed_client):
    r = authed_client.post("/peer/api/report", json={"user_id": 999999})
    assert r.status_code == 404


def test_report_unauth_redirect(client):
    assert client.post("/peer/api/report", json={"user_id": 1}).status_code == 302


# ---------------------------------------------------------------------------
# Room page
# ---------------------------------------------------------------------------

def test_room_page_renders_for_participant(authed_client, app):
    token = _two_users_room(authed_client, app)
    _login_as(authed_client, "aarav@example.com")
    r = authed_client.get("/peer/room/%s" % token)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert token in html
    assert "Question" in html
    assert "csrf-token" in html


def test_room_page_invalid_token_404(authed_client):
    assert authed_client.get("/peer/room/xyz-not-real").status_code == 404


def test_room_page_unauth_redirect(client):
    assert client.get("/peer/room/sometoken12").status_code == 302


def test_room_page_non_participant_sees_join(authed_client, app):
    data = _create_room(authed_client)
    _register_extra(authed_client, "Rohan Mehta", "rohan@example.com")
    _login_as(authed_client, "rohan@example.com")
    r = authed_client.get("/peer/room/%s" % data["token"])
    assert r.status_code == 200
    assert "Join this session" in r.get_data(as_text=True)


def test_cancel_room(authed_client, app):
    data = _create_room(authed_client)
    r = authed_client.post("/peer/api/room/%s/cancel" % data["token"],
                           json={})
    assert r.status_code == 200
    assert _room(app, data["token"]).status == "cancelled"


def test_cancel_non_host_rejected(authed_client, app):
    token = _two_users_room(authed_client, app)
    # logged in as guest
    r = authed_client.post("/peer/api/room/%s/cancel" % token, json={})
    assert r.status_code == 403


def test_join_cancelled_room_rejected(authed_client, app):
    data = _create_room(authed_client)
    authed_client.post("/peer/api/room/%s/cancel" % data["token"], json={})
    _register_extra(authed_client, "Priya Nair", "priya@example.com")
    _login_as(authed_client, "priya@example.com")
    r = authed_client.post("/peer/api/room/%s/join" % data["token"], json={})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# CSRF: POSTs without a token must be rejected (400)
# ---------------------------------------------------------------------------

def test_csrf_rejected_on_peer_posts(csrf_app):
    # CSRFProtect runs before auth: every POST without the X-CSRFToken
    # header must 400, no login needed. Seed a room directly via the DB.
    client = csrf_app.test_client()
    token = "ab12cd34ef56"
    with csrf_app.app_context():
        u = User(name="Csrf Tester", email="csrf@example.com")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()
        room = PeerRoom(token=token, host_id=u.id, role="backend",
                        category="technical", status="open",
                        interviewer_id=u.id, question_ids=["beh-001"],
                        drawn_ids=["beh-001"])
        db.session.add(room)
        db.session.commit()
        room_id = room.id
    for url, body in (
            ("/peer/api/rooms", {"role": "backend"}),
            ("/peer/api/room/%s/join" % token, {}),
            ("/peer/api/room/%s/start" % token, {}),
            ("/peer/api/room/%s/answer" % token, {"question_id": "beh-001",
                                                 "answer_text": "y"}),
            ("/peer/api/room/%s/swap" % token, {}),
            ("/peer/api/room/%s/finish" % token, {}),
            ("/peer/api/room/%s/cancel" % token, {}),
            ("/peer/api/room/%s/feedback" % token, {}),
            ("/peer/api/rooms/%d/slots" % room_id, {"slots": "x"}),
            ("/peer/api/room/%s/slot/accept" % token, {"slot": "x"}),
            ("/peer/api/report", {"user_id": 1})):
        rr = client.post(url, json=body)
        assert rr.status_code == 400, url
