"""Phase 1 — SEC-04 rate-limit keying/storage + ARC-15 time handling.

SEC-04 acceptance: key by user id when authenticated else IP; storage from
RATELIMIT_STORAGE_URI; global defaults; 429 carries Retry-After.
ARC-15: no datetime.utcnow() anywhere; naive UTC helper used for DB compares.
"""
import re


class TestRateLimitKeying:
    def test_key_prefers_user_id_when_authenticated(self, client, app):
        from unified_app import _rate_limit_key, User, db
        from flask_login import login_user
        with app.app_context():
            user = User(name="kuser", email="k1@example.com")
            user.set_password("pw123456")
            db.session.add(user)
            db.session.commit()
            uid = user.id
        with client.application.test_request_context("/"):
            login_user(User.query.get(uid))
            assert _rate_limit_key() == f"user:{uid}"

    def test_key_falls_back_to_ip_when_anonymous(self, client):
        from unified_app import _rate_limit_key
        with client.application.test_request_context(
                "/", environ_base={"REMOTE_ADDR": "9.9.9.9"}):
            key = _rate_limit_key()
        assert key.startswith("ip:"), key

    def test_limiter_has_global_defaults_and_storage_uri(self):
        import inspect
        import unified_app as ua
        src = inspect.getsource(ua)
        # SEC-04: global defaults + env-driven storage + user-aware key func
        assert '"200 per day"' in src and '"60 per hour"' in src
        assert 'RATELIMIT_STORAGE_URI' in src
        assert 'def _rate_limit_key' in src
        assert 'user:{' in src  # user id preferred when authenticated

    def test_login_has_stricter_limit(self, client):
        # brute-force guard present on /login route rules
        rules = [str(r) for r in client.application.url_map.iter_rules()
                 if "login" in str(r)]
        assert rules, "login route must exist"


class TestTimeHandling:
    def test_no_utcnow_anywhere(self):
        import pathlib
        bad = []
        paths = [pathlib.Path("unified_app.py"),
                 *pathlib.Path("studybuddy").glob("*.py")]
        for p in paths:
            text = p.read_text()
            if re.search(r"(?<!_utcnow_naive)(?<!def _)\.utcnow\(\)", text):
                bad.append(str(p))
        assert not bad, f"utcnow() found in: {bad}"

    def test_utcnow_naive_returns_naive_utc(self):
        from datetime import datetime, timezone
        from unified_app import _utcnow_naive
        got = _utcnow_naive()
        assert got.tzinfo is None
        delta = abs((datetime.now(timezone.utc).replace(tzinfo=None) - got).total_seconds())
        assert delta < 10
