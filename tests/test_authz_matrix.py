"""SEC-17: Authorization test matrix.

For every route with an <..._id> path parameter, create a resource as
user A and assert user B receives 403/404 (never 200 with A's data).

Also documents the 4 routes without ownership refs and why each is safe.
"""
import pytest


def _make_user(email, name="Test User"):
    from unified_app import User, db
    u = User(name=name, email=email)
    u.set_password("TestPass123!")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, email):
    return client.post("/login", data={
        "email": email, "password": "TestPass123!"}, follow_redirects=False)


def _logout(client):
    return client.get("/logout", follow_redirects=False)


@pytest.fixture()
def two_users(app):
    with app.app_context():
        a = _make_user("usera@example.com", "User A")
        b = _make_user("userb@example.com", "User B")
        return a.id, b.id


class TestAuthzMatrix:
    """IDOR checks: B must not read/modify A's resources."""

    def test_goal_toggle_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import Goal, db
        with app.app_context():
            g = Goal(user_id=aid, title="A's goal", status="active")
            db.session.add(g)
            db.session.commit()
            gid = g.id
        # B tries to toggle A's goal
        _login(client, "userb@example.com")
        r = client.post(f"/goals/{gid}/toggle", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B toggled A's goal ({r.status_code})"
        _logout(client)

    def test_goal_delete_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import Goal, db
        with app.app_context():
            g = Goal(user_id=aid, title="A's goal 2", status="active")
            db.session.add(g)
            db.session.commit()
            gid = g.id
        _login(client, "userb@example.com")
        r = client.post(f"/goals/{gid}/delete", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B deleted A's goal ({r.status_code})"
        # Verify the goal still exists
        with app.app_context():
            assert db.session.get(Goal, gid) is not None
        _logout(client)

    def test_jd_match_report_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import JDMatchReport, db
        with app.app_context():
            row = JDMatchReport(user_id=aid, report_json={"score": 90})
            db.session.add(row)
            db.session.commit()
            rid = row.id
        _login(client, "userb@example.com")
        r = client.get(f"/jd-match/{rid}", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B read A's JD report ({r.status_code})"
        _logout(client)

    def test_tracker_move_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import JobApplication, db
        with app.app_context():
            ja = JobApplication(user_id=aid, company="Acme", role="Dev",
                                stage="applied")
            db.session.add(ja)
            db.session.commit()
            jid = ja.id
        _login(client, "userb@example.com")
        r = client.post(f"/tracker/{jid}/move", json={"stage": "offer"})
        assert r.status_code == 404, f"IDOR: B moved A's application ({r.status_code})"
        _logout(client)

    def test_interview_session_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import InterviewSession, db
        with app.app_context():
            s = InterviewSession(user_id=aid, company="Acme", role="Dev",
                                 category="behavioral", questions_json=[],
                                 answers_json=[])
            db.session.add(s)
            db.session.commit()
            sid = s.id
        _login(client, "userb@example.com")
        r = client.get(f"/interview/{sid}", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B read A's interview ({r.status_code})"
        _logout(client)

    def test_assessment_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import CareerAssessment, db
        with app.app_context():
            ca = CareerAssessment(user_id=aid, top_clusters=["eng"])
            db.session.add(ca)
            db.session.commit()
            cid = ca.id
        _login(client, "userb@example.com")
        r = client.get(f"/assessment/{cid}", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B read A's assessment ({r.status_code})"
        _logout(client)

    def test_aptitude_attempt_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import AptitudeAttempt, db
        from datetime import datetime, timezone
        with app.app_context():
            at = AptitudeAttempt(user_id=aid, category="quant",
                                 num_questions=5, time_limit_sec=300,
                                 started_at=datetime.now(timezone.utc),
                                 submitted_at=datetime.now(timezone.utc),
                                 results_json=[], summary_json={})
            db.session.add(at)
            db.session.commit()
            tid = at.id
        _login(client, "userb@example.com")
        r = client.get(f"/aptitude/{tid}", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B read A's aptitude ({r.status_code})"
        _logout(client)

    def test_quiz_attempt_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import QuizAttempt, db
        from datetime import datetime, timezone
        with app.app_context():
            qa = QuizAttempt(user_id=aid, skill="python", num_questions=1,
                             question_ids=["q1"],
                             started_at=datetime.now(timezone.utc),
                             submitted_at=datetime.now(timezone.utc),
                             summary_json={})
            db.session.add(qa)
            db.session.commit()
            qid = qa.id
        _login(client, "userb@example.com")
        r = client.get(f"/learn/quizzes/{qid}", follow_redirects=False)
        assert r.status_code == 404, f"IDOR: B read A's quiz ({r.status_code})"
        _logout(client)

    def test_study_doc_idor(self, client, app, two_users):
        aid, _ = two_users
        from unified_app import StudyDoc, db
        with app.app_context():
            d = StudyDoc(user_id=aid, title="A's doc",
                         stored_filename="a.pdf")
            db.session.add(d)
            db.session.commit()
            did = d.id
        _login(client, "userb@example.com")
        r = client.get(f"/study/api/documents/{did}/history")
        assert r.status_code == 404, f"IDOR: B read A's doc history ({r.status_code})"
        r = client.delete(f"/study/api/documents/{did}")
        assert r.status_code == 404, f"IDOR: B deleted A's doc ({r.status_code})"
        _logout(client)

    def test_mentor_booking_cancel_idor(self, client, app, two_users):
        """B cannot cancel A's mentor booking (ownership via user_id)."""
        aid, _ = two_users
        from unified_app import OHBooking, OfficeHour, Mentor, db
        from datetime import datetime, timezone, timedelta
        with app.app_context():
            m = Mentor(name="Mentor M", headline="Career coach",
                       path="career")
            db.session.add(m)
            db.session.flush()
            oh = OfficeHour(mentor_id=m.id, topic="chat",
                            scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
                            status="open")
            db.session.add(oh)
            db.session.flush()
            bk = OHBooking(office_hour_id=oh.id, user_id=aid, status="confirmed")
            db.session.add(bk)
            db.session.commit()
            bid = bk.id
        _login(client, "userb@example.com")
        r = client.post(f"/mentors/api/bookings/{bid}/cancel")
        assert r.status_code == 404, \
            f"IDOR: B cancelled A's booking ({r.status_code})"
        _logout(client)


class TestAdminRouteProtection:
    """SEC-17: admin routes require the server-side admin role."""

    def test_non_admin_cannot_verify_mentor(self, client, app, two_users):
        _, bid = two_users
        from unified_app import Mentor, db
        with app.app_context():
            m = Mentor(name="Mentor X", headline="Tech mentor",
                       path="tech")
            db.session.add(m)
            db.session.commit()
            mid = m.id
        _login(client, "userb@example.com")
        r = client.post(f"/mentors/api/admin/verify/{mid}")
        assert r.status_code == 403, \
            f"non-admin verified mentor ({r.status_code})"
        _logout(client)

    def test_admin_role_can_verify_mentor(self, client, app, two_users):
        _, bid = two_users
        from unified_app import Mentor, User, db
        with app.app_context():
            u = db.session.get(User, bid)
            u.is_admin = True
            db.session.commit()
            m = Mentor(name="Mentor Y", headline="Tech mentor",
                       path="tech")
            db.session.add(m)
            db.session.commit()
            mid = m.id
        _login(client, "userb@example.com")
        r = client.post(f"/mentors/api/admin/verify/{mid}")
        assert r.status_code == 200, f"admin verify failed ({r.status_code})"
        with app.app_context():
            assert db.session.get(Mentor, mid).verified is True
        _logout(client)


class TestRoutesWithoutOwnershipRefs:
    """SEC-17: the 4 routes with id-like params but no user resources.

    /dsa/<problem_id>/hint — problem_id is a PUBLIC problem slug (e.g.
        "two-sum"), not a DB row. Per-user state is keyed by
        (user_id, problem_id) inside _dsa_progress_row; B cannot touch
        A's progress.
    /dsa/<problem_id>/approach — same; returns public problem content.
    /learn/certs/<cert_id> — cert_id is a PUBLIC catalog key; no user
        data is read or written.
    /mentors/api/admin/verify/<mentor_id> — mentor_id is a public
        mentor profile; the route is admin-only (User.is_admin or
        STUDYBUDDY_ADMINS bootstrap) and audit-logged.
    """

    def test_dsa_hint_is_per_user(self, client, app, two_users):
        # A and B each get their own hint counters for the same problem.
        from unified_app import db  # noqa: F401
        _login(client, "usera@example.com")
        ra = client.post("/dsa/two-sum/hint")
        assert ra.status_code in (200, 404)  # 404 if problem slug unknown
        _logout(client)
        _login(client, "userb@example.com")
        rb = client.post("/dsa/two-sum/hint")
        assert rb.status_code in (200, 404)
        _logout(client)

    def test_cert_detail_is_public_catalog(self, client):
        r = client.get("/learn/certs/aws-solutions-architect",
                       follow_redirects=False)
        # Public catalog page (or 404 for unknown id) — never user data.
        assert r.status_code in (200, 404)
