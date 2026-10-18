"""Phase 0 (Stop the bleeding) security tests: SEC-01, SEC-03, SEC-11, ENG-08.

Rule 0.2.4: every fix below was written against a failing test first.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OPP_NO_AUTO_REFRESH"] = "1"

from unified_app import create_app, db, User, StudyDoc, FlashcardSet  # noqa: E402


def _make_app(**overrides):
    cfg = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "phase0-test-secret",
        "WTF_CSRF_ENABLED": False,
    }
    cfg.update(overrides)
    app = create_app(cfg)
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture()
def app():
    return _make_app()


@pytest.fixture()
def client(app):
    return app.test_client()


def _mkuser(app, email="vivek@example.com", password="correct-horse-9"):
    with app.app_context():
        u = User(name="Vivek", email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u.id, email, password


def _login(client, email, password):
    r = client.post("/login", data={"email": email, "password": password},
                    follow_redirects=False)
    assert r.status_code in (302, 303), r.status_code
    return r


# ---------------------------------------------------------------- SEC-11
class TestDebugGating:
    def test_debug_off_by_default(self):
        from unified_app import _resolve_debug
        assert _resolve_debug({}) is False

    def test_debug_opt_in_dev(self):
        from unified_app import _resolve_debug
        assert _resolve_debug({"FLASK_DEBUG": "1"}) is True

    def test_debug_refused_in_production(self):
        from unified_app import _resolve_debug
        with pytest.raises(RuntimeError):
            _resolve_debug({"FLASK_DEBUG": "1", "FLASK_ENV": "production"})

    def test_debug_refused_on_render(self):
        from unified_app import _resolve_debug
        with pytest.raises(RuntimeError):
            _resolve_debug({"FLASK_DEBUG": "1", "RENDER": "true"})


# ---------------------------------------------------------------- SEC-01
class TestUltimateDispatcherLockdown:
    def test_run_anonymous_401(self, client):
        r = client.post("/api/ultimate/run/bullets/star-convert",
                        json={"bullet_text": "Built X, cut Y 40%"})
        assert r.status_code == 401
        assert r.get_json()["ok"] is False

    def test_tools_anonymous_401(self, client):
        r = client.get("/api/ultimate/tools")
        assert r.status_code == 401

    def test_lab_anonymous_redirects_to_login(self, client):
        r = client.get("/ultimate/lab")
        assert r.status_code in (302, 401)

    def test_run_authenticated_200(self, client, app):
        _uid, email, pw = _mkuser(app)
        _login(client, email, pw)
        r = client.post("/api/ultimate/run/bullets/star-convert",
                        json={"bullet_text": "Built X, cut Y 40%"})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_tools_authenticated_200(self, client, app):
        _uid, email, pw = _mkuser(app)
        _login(client, email, pw)
        r = client.get("/api/ultimate/tools")
        assert r.status_code == 200
        assert r.get_json()["count"] == 91

    def test_run_body_too_large_413(self, client, app):
        _uid, email, pw = _mkuser(app)
        _login(client, email, pw)
        big = "x" * (70 * 1024)
        r = client.post("/api/ultimate/run/bullets/star-convert",
                        json={"bullet_text": big})
        assert r.status_code == 413

    def test_run_rate_limited(self):
        # NOTE: create_app() disables the limiter when TESTING=True (existing
        # suite convention so tests are never throttled). This test opts back
        # in explicitly to prove the SEC-01 rate limit enforces.
        from unified_app import limiter as _limiter
        cfg = {"ULTIMATE_RUN_LIMIT": "2 per minute", "TESTING": False}
        app = _make_app(**cfg)
        _limiter.enabled = True
        try:
            client = app.test_client()
            _uid, email, pw = _mkuser(app)
            _login(client, email, pw)
            payload = {"bullet_text": "Built X, cut Y 40%"}
            assert client.post("/api/ultimate/run/bullets/star-convert",
                               json=payload).status_code == 200
            assert client.post("/api/ultimate/run/bullets/star-convert",
                               json=payload).status_code == 200
            r = client.post("/api/ultimate/run/bullets/star-convert",
                            json=payload)
            assert r.status_code == 429
        finally:
            _limiter.enabled = False  # restore suite convention


# ---------------------------------------------------------------- SEC-03
class TestFlashcardsXSS:
    PAYLOAD = "</script><script>alert('pwned')</script>"

    def _deck_with_payload(self, app, user_id):
        with app.app_context():
            doc = StudyDoc(user_id=user_id, title="XSS doc",
                           stored_filename="x.pdf")
            db.session.add(doc)
            db.session.flush()
            cards = [{"id": "c1", "kind": "qa",
                      "question": "What is " + self.PAYLOAD + " ?",
                      "answer": "safe", "options": []}]
            fs = FlashcardSet(user_id=user_id, doc_id=doc.id,
                              card_count=1, data={"cards": cards})
            db.session.add(fs)
            db.session.commit()
            return fs.id

    def test_payload_cannot_break_out_of_script(self, client, app):
        _uid, email, pw = _mkuser(app)
        sid = self._deck_with_payload(app, _uid)
        _login(client, email, pw)
        r = client.get(f"/research/flashcards/{sid}")
        assert r.status_code == 200
        html = r.data
        # The raw breakout sequence must not appear anywhere in the page.
        assert b"</script><script>alert" not in html
        # ...but the (escaped) card content must still reach the UI.
        assert b"pwned" in html


# ---------------------------------------------------------------- ENG-08
class TestOfferProbabilityRemoved:
    def test_no_probability_pct_in_output(self):
        from studybuddy.jd_matcher import competitiveness_checklist
        out = competitiveness_checklist({"score": 82}, applicants_estimate=500)
        blob = str(out).lower()
        assert "probability_pct" not in out
        assert "probability" not in blob or "not a prediction" in blob
        assert "%" not in blob

    def test_checklist_is_explicitly_illustrative(self):
        from studybuddy.jd_matcher import competitiveness_checklist
        out = competitiveness_checklist({"score": 82})
        assert out.get("illustrative") is True
        assert out["checklist"], "checklist must not be empty"
        for item in out["checklist"]:
            assert item.get("item") and item.get("note")

    def test_tool_registry_points_at_honest_tool(self):
        from studybuddy.ultimate_routes import _TOOL_INDEX
        tool = _TOOL_INDEX["jd/offer-odds"]
        assert tool["function"] == "competitiveness_checklist"
        assert "honest" in tool["description"].lower() \
            or "illustrative" in tool["description"].lower()

    def test_run_tool_has_no_fabricated_numbers(self):
        from studybuddy.ultimate_routes import run_tool
        import json as _json
        r, e = run_tool("jd/offer-odds",
                       {"report": _json.dumps({"score": 82})})
        assert e is None
        assert "probability_pct" not in r
