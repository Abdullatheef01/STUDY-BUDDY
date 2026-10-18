"""Phase 2 Batch 2 — RAG-01 eval harness + PRIV-03 consent."""
import json
import os
import subprocess
import sys

from tests.conftest import login, register


class TestRagEval:
    def test_harness_runs(self):
        result = subprocess.run(
            [sys.executable, "benchmarks/rag_eval.py", "--quick"],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            timeout=60)
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout.split("\nWrote")[0])
        assert out["recall@1"] >= 0.8
        assert "mrr" in out
        assert "abstention_accuracy" in out
        assert "citation_validity" in out

    def test_full_eval_abstains(self):
        result = subprocess.run(
            [sys.executable, "benchmarks/rag_eval.py"],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            timeout=60)
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout.split("\nWrote")[0])
        assert out["abstention_accuracy"] >= 0.5, \
            "should abstain on unanswerable questions"


class TestLlmConsent:
    def test_consent_page_loads(self, client):
        register(client, name="C User", email="consent1@example.com",
                 password="pw123456")
        login(client, email="consent1@example.com", password="pw123456")
        r = client.get("/consent/llm")
        assert r.status_code == 200
        assert b"AI features" in r.data

    def test_consent_records(self, client, app):
        register(client, name="C User", email="consent2@example.com",
                 password="pw123456")
        login(client, email="consent2@example.com", password="pw123456")
        r = client.post("/consent/llm", data={"agree": "yes", "next": "/"})
        assert r.status_code == 302
        from unified_app import LLMConsent, User
        with app.app_context():
            u = User.query.filter_by(email="consent2@example.com").first()
            c = LLMConsent.query.filter_by(user_id=u.id).first()
            assert c is not None
            assert c.policy_version == "v1"

    def test_consent_withdraw(self, client, app):
        register(client, name="C User", email="consent3@example.com",
                 password="pw123456")
        login(client, email="consent3@example.com", password="pw123456")
        client.post("/consent/llm", data={"agree": "yes"})
        r = client.post("/consent/llm/withdraw")
        assert r.status_code == 302
        from unified_app import LLMConsent, User
        with app.app_context():
            u = User.query.filter_by(email="consent3@example.com").first()
            assert LLMConsent.query.filter_by(user_id=u.id).first() is None
