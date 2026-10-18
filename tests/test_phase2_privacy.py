"""Phase 2 — PRIV-02 delete/export my data."""
import json

from tests.conftest import login, register


class TestAccountExport:
    def test_export_requires_login(self, client):
        r = client.get("/account/export")
        assert r.status_code in (302, 401)

    def test_export_returns_json(self, client):
        register(client, name="Exp User", email="exp2@example.com",
                 password="pw123456")
        login(client, email="exp2@example.com", password="pw123456")
        r = client.get("/account/export")
        assert r.status_code == 200
        assert "attachment" in r.headers["Content-Disposition"]
        data = json.loads(r.data)
        assert data["user"]["email"] == "exp2@example.com"
        assert "resume_analyses" in data


class TestAccountDelete:
    def test_delete_page_loads(self, client):
        register(client, name="Del User", email="del3@example.com",
                 password="pw123456")
        login(client, email="del3@example.com", password="pw123456")
        r = client.get("/account/delete")
        assert r.status_code == 200
        assert b"Delete Your Account" in r.data

    def test_delete_requires_confirmation(self, client):
        register(client, name="Del User", email="del4@example.com",
                 password="pw123456")
        login(client, email="del4@example.com", password="pw123456")
        r = client.post("/account/delete",
                        data={"password": "pw123456", "confirm": "NO"})
        assert r.status_code == 200
        assert b"Type DELETE" in r.data

    def test_delete_wrong_password(self, client):
        register(client, name="Del User", email="del5@example.com",
                 password="pw123456")
        login(client, email="del5@example.com", password="pw123456")
        r = client.post("/account/delete",
                        data={"password": "wrongpass", "confirm": "DELETE"})
        assert r.status_code == 200
        assert b"Incorrect password" in r.data

    def test_delete_removes_user(self, client, app):
        from unified_app import User, db
        register(client, name="Del2 User", email="del6@example.com",
                 password="pw123456")
        login(client, email="del6@example.com", password="pw123456")
        r = client.post("/account/delete",
                        data={"password": "pw123456", "confirm": "DELETE"},
                        follow_redirects=False)
        # 302 on success (redirect to index after logout)
        assert r.status_code == 302, f"got {r.status_code}"
        with app.app_context():
            db.session.expire_all()
            assert User.query.filter_by(email="del6@example.com").first() is None
