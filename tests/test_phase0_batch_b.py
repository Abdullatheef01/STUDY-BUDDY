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


def _addrinfo(*ips):
    """Fake socket.getaddrinfo result for the given IP strings."""
    out = []
    for ip in ips:
        fam = 10 if ":" in ip else 2
        out.append((fam, 1, 6, "", (ip, 0)))
    return out


class TestSafeFetch:
    """SEC-02: SSRF-safe fetcher blocks server-side request forgery."""

    def test_blocks_private_ipv4_literal(self):
        from studybuddy.safe_fetch import validate_url, SSRFError
        for bad in ("http://127.0.0.1/", "http://10.0.0.5:8080/x",
                    "http://192.168.1.1/", "http://169.254.169.254/latest/"):
            with pytest.raises(SSRFError):
                validate_url(bad)

    def test_blocks_private_ipv6_and_reserved(self):
        from studybuddy.safe_fetch import validate_url, SSRFError
        for bad in ("http://[::1]/", "http://[fc00::1]/",
                    "http://0.0.0.0/"):
            with pytest.raises(SSRFError):
                validate_url(bad)

    def test_blocks_dns_to_private_ip(self):
        import unittest.mock as mock
        from studybuddy.safe_fetch import validate_url, SSRFError
        with mock.patch("socket.getaddrinfo",
                        return_value=_addrinfo("10.1.2.3")):
            with pytest.raises(SSRFError):
                validate_url("http://internal.example.com/")

    def test_blocks_non_http_schemes(self):
        from studybuddy.safe_fetch import validate_url, SSRFError
        for bad in ("file:///etc/passwd", "ftp://x/y", "gopher://x/",
                    "http://user:pass@example.com/"):
            with pytest.raises(SSRFError):
                validate_url(bad)

    def test_allows_public_ip(self):
        import unittest.mock as mock
        from studybuddy.safe_fetch import validate_url
        with mock.patch("socket.getaddrinfo",
                        return_value=_addrinfo("93.184.216.34")):
            parsed = validate_url("https://example.com/paper.pdf")
            assert parsed.hostname == "example.com"

    def test_safe_fetch_blocks_before_network(self):
        """Validation happens before any socket is opened."""
        import unittest.mock as mock
        from studybuddy import safe_fetch as sf
        with mock.patch("socket.getaddrinfo",
                        return_value=_addrinfo("169.254.169.254")), \
             mock.patch.object(sf.requests, "request") as mreq:
            with pytest.raises(sf.SSRFError):
                sf.safe_fetch("http://169.254.169.254/latest/meta-data/")
            mreq.assert_not_called()

    def test_safe_fetch_follows_safe_redirects(self):
        import unittest.mock as mock
        from studybuddy import safe_fetch as sf

        def fake_request(method, url, **kw):
            m = mock.Mock()
            if url == "https://example.com/a":
                m.status_code = 302
                m.headers = {"Location": "https://example.com/b"}
                m.iter_content = lambda chunk_size: iter([b"x"])
                m.close = lambda: None
            else:
                m.status_code = 200
                m.headers = {}
                m.iter_content = lambda chunk_size: iter([b"ok"])
                m.close = lambda: None
            return m

        with mock.patch("socket.getaddrinfo",
                        return_value=_addrinfo("93.184.216.34")), \
             mock.patch.object(sf.requests, "request", side_effect=fake_request):
            code, body, _hdrs = sf.safe_fetch("https://example.com/a")
            assert code == 200 and body == b"ok"

    def test_safe_fetch_blocks_redirect_to_private(self):
        import unittest.mock as mock
        from studybuddy import safe_fetch as sf

        def fake_request(method, url, **kw):
            m = mock.Mock()
            m.status_code = 302
            m.headers = {"Location": "http://169.254.169.254/x"}
            m.close = lambda: None
            return m

        def fake_dns(host, *a, **k):
            if "169.254.169.254" in host or host == "169.254.169.254":
                return _addrinfo("169.254.169.254")
            return _addrinfo("93.184.216.34")

        with mock.patch("socket.getaddrinfo", side_effect=fake_dns), \
             mock.patch.object(sf.requests, "request", side_effect=fake_request):
            with pytest.raises(sf.SSRFError):
                sf.safe_fetch("https://example.com/a")

    def test_check_demo_links_never_touches_private(self):
        """Portfolio link checker must not open sockets to private IPs."""
        import unittest.mock as mock
        from studybuddy import portfolio
        with mock.patch("socket.getaddrinfo",
                        return_value=_addrinfo("127.0.0.1")), \
             mock.patch("studybuddy.safe_fetch.requests.request") as mreq:
            res = portfolio.check_demo_links(
                [{"title": "Evil", "demo_link": "http://127.0.0.1:8080/"}])
            mreq.assert_not_called()
            assert res["links"][0]["alive"] is False
            assert "ssrf" in res["links"][0]["status"].lower() or \
                   "blocked" in res["links"][0]["status"].lower()
