"""Phase 0 batch B1: SEC-06 session hardening tests."""
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["OPP_NO_AUTO_REFRESH"] = "1"

from unified_app import create_app, db, User  # noqa: E402


def _make_app(**overrides):
    cfg = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "phase0b-test-secret",
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


def _mkuser(app, email="b1@example.com", password="pw-12345"):
    with app.app_context():
        u = User(name="B1", email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
    return email, password


class TestSessionHardening:
    def test_session_protection_strong(self, app):
        from unified_app import login_manager
        assert login_manager.session_protection == "strong"

    def test_permanent_session_lifetime_12h(self, app):
        assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=12)

    def test_no_session_refresh_each_request(self, app):
        assert app.config["SESSION_REFRESH_EACH_REQUEST"] is False

    def test_session_cookie_rotates_on_login(self, client, app):
        """Session fixation defense: the session cookie must change at login."""
        email, pw = _mkuser(app)
        # Anonymous visit establishes a session cookie...
        client.get("/login")
        before = client.get_cookie("session")
        # ...then login must rotate it.
        client.post("/login", data={"email": email, "password": pw})
        after = client.get_cookie("session")
        assert before and after, "session cookie missing"
        assert before.value != after.value, \
            "session cookie did not rotate on login"

    def test_secure_cookie_flags(self, app):
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


class TestLicenseAudit:
    """LEG-01: no GPL/AGPL (strong copyleft) dependency may be added.

    Project license is MIT. LGPL (psycopg2-binary) is explicitly allowed:
    it is fine for server-side use and does not infect the MIT codebase.
    """

    # name -> reason it is allowed despite copyleft-ish metadata
    _ALLOWLIST = {
        "psycopg2-binary": "LGPL with exceptions; server-side use only, "
                           "MIT-compatible (no distribution of the lib itself).",
    }

    def test_no_strong_copyleft_dependencies(self):
        from importlib.metadata import distributions
        offenders = []
        for d in distributions():
            name = d.metadata["Name"]
            lic = (d.metadata.get("License") or "").upper()
            if "AGPL" in lic or ("GPL" in lic and "LGPL" not in lic):
                if name not in self._ALLOWLIST:
                    offenders.append(f"{name} ({lic.strip()})")
        assert not offenders, \
            f"Strong-copyleft deps conflict with MIT: {offenders}"
