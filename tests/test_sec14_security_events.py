"""SEC-14: structured security event logging — no PII payloads."""
import io
import logging

import pytest

from studybuddy.security_events import EVENT_TYPES, log_security_event


def _mkuser(app, email="sec14@example.com", password="longenoughpassword1"):
    from unified_app import User, db
    with app.app_context():
        u = User(name="Sec14", email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u.id, email, password


def _security_records(caplog):
    return [r for r in caplog.records if r.name == "studybuddy.security"]


class TestLogSecurityEvent:
    def test_emits_structured_record(self, caplog):
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            log_security_event("login_success", user_id=42,
                               details={"method": "form"})
        recs = _security_records(caplog)
        assert len(recs) == 1
        msg = recs[0].getMessage()
        assert "login_success" in msg
        # raw user id must not appear; only its hash
        assert "'user': '42'" not in msg

    def test_unknown_event_type_rejected(self):
        with pytest.raises(ValueError):
            log_security_event("no_such_event")

    def test_pii_details_scrubbed(self, caplog):
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            log_security_event("login_failure", details={
                "email": "someone@example.com",
                "password": "secret123",
                "url": "https://x.test/?token=abc",
                "ip": "1.2.3.4",
                "account_exists": True,
            })
        msg = _security_records(caplog)[0].getMessage()
        assert "someone@example.com" not in msg
        assert "secret123" not in msg
        assert "1.2.3.4" not in msg
        assert "account_exists" in msg  # non-PII detail survives

    def test_user_id_is_hashed(self, caplog):
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            log_security_event("admin_action", user_id=987654321,
                               details={"action": "review"})
        msg = _security_records(caplog)[0].getMessage()
        assert "987654321" not in msg

    def test_all_event_types_accepted(self, caplog):
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            for et in EVENT_TYPES:
                log_security_event(et, details={"probe": True})
        assert len(_security_records(caplog)) == len(EVENT_TYPES)


class TestSecurityEventWiring:
    def test_failed_login_logs_event(self, app, client, caplog):
        _mkuser(app)
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            r = client.post("/login",
                            data={"email": "sec14@example.com",
                                  "password": "wrongpassword!"},
                            follow_redirects=False)
        assert r.status_code == 200  # re-rendered with error
        msgs = [r.getMessage() for r in _security_records(caplog)]
        assert any("login_failure" in m for m in msgs)
        # email must never be in the security log
        assert not any("sec14@example.com" in m for m in msgs)

    def test_successful_login_logs_event(self, app, client, caplog):
        uid, email, password = _mkuser(app)
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            r = client.post("/login",
                            data={"email": email, "password": password},
                            follow_redirects=False)
        assert r.status_code in (302, 303)
        msgs = [r.getMessage() for r in _security_records(caplog)]
        assert any("login_success" in m for m in msgs)

    def test_upload_reject_logs_event(self, client, caplog):
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            r = client.post("/api/parse_preview",
                            data={"file": (io.BytesIO(b"not a pdf at all"),
                                           "evil.exe")},
                            content_type="multipart/form-data")
        assert r.status_code == 400
        msgs = [r.getMessage() for r in _security_records(caplog)]
        assert any("upload_reject" in m for m in msgs)
        assert not any("evil.exe" in m for m in msgs)

    def test_ssrf_block_logs_event(self, caplog):
        from studybuddy.safe_fetch import SSRFError, validate_url
        with caplog.at_level(logging.WARNING, logger="studybuddy.security"):
            with pytest.raises(SSRFError):
                validate_url("http://169.254.169.254/latest/meta-data/")
        msgs = [r.getMessage() for r in _security_records(caplog)]
        assert any("ssrf_block" in m for m in msgs)
        # raw target IP must not appear in the log
        assert not any("169.254.169.254" in m for m in msgs)
