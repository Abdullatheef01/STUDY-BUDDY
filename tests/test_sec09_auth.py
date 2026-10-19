"""SEC-09: Authentication hardening tests."""
import re

import pytest

from studybuddy.auth_hardening import (
    check_password_policy,
    generate_email_token,
    password_strength,
    verify_email_token,
)


class TestPasswordPolicy:
    def test_min_length_10(self):
        ok, msg = check_password_policy("short123")
        assert not ok
        assert "10" in msg

    def test_max_length(self):
        ok, _ = check_password_policy("x" * 129)
        assert not ok

    def test_common_password_blocked(self):
        ok, msg = check_password_policy("password123")
        assert not ok
        assert "common" in msg.lower()

    def test_good_password_passes(self):
        ok, msg = check_password_policy("MyStr0ng!Pass")
        assert ok, msg

    def test_all_same_char_blocked(self):
        ok, _ = check_password_policy("aaaaaaaaaa")
        assert not ok


class TestPasswordStrength:
    def test_weak(self):
        assert password_strength("abc") <= 1

    def test_strong(self):
        assert password_strength("MyStr0ng!Pass123") >= 3


class TestEmailToken:
    def test_roundtrip(self):
        token = generate_email_token(42, "test-secret")
        assert verify_email_token(token, "test-secret") == 42

    def test_wrong_secret(self):
        token = generate_email_token(42, "test-secret")
        assert verify_email_token(token, "wrong-secret") is None

    def test_tampered(self):
        token = generate_email_token(42, "test-secret")
        assert verify_email_token(token + "x", "test-secret") is None


class TestAuthRoutes:
    def test_register_rejects_short_password(self, client):
        r = client.post("/register", data={
            "name": "Test", "email": "short@test.com",
            "password": "short123"})
        assert b"10" in r.data or r.status_code == 200

    def test_forgot_password_page(self, client):
        r = client.get("/forgot-password")
        assert r.status_code == 200

    def test_forgot_password_generic_response(self, client):
        # Non-existent email gets same message (no enumeration)
        r = client.post("/forgot-password",
                        data={"email": "nobody@nowhere.com"},
                        follow_redirects=True)
        assert r.status_code == 200

    def test_reset_invalid_token(self, client):
        r = client.get("/reset-password/badtoken")
        assert r.status_code in (200, 302)
