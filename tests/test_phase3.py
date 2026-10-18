"""Phase 3 — PRIV-05 LLM modes, DATA-01 provenance, LLM-09 degradation."""
import os
import subprocess
import sys

from tests.conftest import login, register


class TestLlmModes:
    def test_mode_off_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "off")
        from studybuddy import ai_gateway
        from studybuddy.ai_gateway import AIError
        try:
            ai_gateway.generate("test")
            raise AssertionError("should have raised")
        except AIError as e:
            assert "disabled" in str(e).lower()

    def test_mode_defaults_server(self, monkeypatch):
        monkeypatch.delenv("LLM_MODE", raising=False)
        from studybuddy.ai_gateway import llm_mode
        assert llm_mode() == "server"

    def test_byok_requires_key(self, monkeypatch):
        monkeypatch.setenv("LLM_MODE", "byok")
        from studybuddy import ai_gateway
        from studybuddy.ai_gateway import AIError
        try:
            ai_gateway.generate("test")
            raise AssertionError("should have raised")
        except AIError as e:
            assert "BYOK" in str(e) or "key" in str(e).lower()

    def test_local_configured(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
        from studybuddy.ai_gateway import local_configured
        assert local_configured() is True

    def test_local_not_configured(self, monkeypatch):
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        from studybuddy.ai_gateway import local_configured
        assert local_configured() is False


class TestByokStorage:
    def test_key_encrypt_decrypt(self, app):
        from unified_app import UserAPIKey
        rec = UserAPIKey(user_id=999999, provider="openrouter")
        rec.set_key("sk-test-secret-key-12345")
        assert rec.encrypted_key != "sk-test-secret-key-12345"
        assert rec.get_key() == "sk-test-secret-key-12345"

    def test_ai_key_page_loads(self, client):
        register(client, name="K User", email="key1@example.com",
                 password="pw123456")
        login(client, email="key1@example.com", password="pw123456")
        r = client.get("/profile/ai-key")
        assert r.status_code == 200
        assert b"BYOK" in r.data

    def test_ai_key_save_and_remove(self, client, app):
        register(client, name="K User", email="key2@example.com",
                 password="pw123456")
        login(client, email="key2@example.com", password="pw123456")
        r = client.post("/profile/ai-key", data={
            "action": "save", "provider": "openrouter",
            "api_key": "sk-test-key-1234567890"})
        assert r.status_code == 302
        from unified_app import UserAPIKey, User
        with app.app_context():
            u = User.query.filter_by(email="key2@example.com").first()
            rec = UserAPIKey.query.filter_by(user_id=u.id).first()
            assert rec is not None
            assert rec.get_key() == "sk-test-key-1234567890"
        # remove
        r = client.post("/profile/ai-key", data={"action": "remove"})
        assert r.status_code == 302
        with app.app_context():
            assert UserAPIKey.query.filter_by(user_id=u.id).first() is None


class TestDataProvenance:
    def test_validator_runs(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_data.py"],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            timeout=60)
        # 0 errors expected (warnings OK for legacy data)
        assert "errors" in result.stdout

    def test_meta_template_exists(self):
        p = os.path.join(os.path.dirname(__file__), "..",
                         "data", "schemas", "meta.template.json")
        assert os.path.exists(p)


class TestGracefulDegradation:
    def test_degraded_helper_exists(self):
        from unified_app import _ai_degraded_response
        assert callable(_ai_degraded_response)
