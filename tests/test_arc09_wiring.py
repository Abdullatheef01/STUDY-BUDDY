"""ARC-09: custom exceptions wired into the app."""
import pytest


class TestARC09Handler:
    def test_api_json_error(self, client):
        # Register a route that raises ValidationError
        from studybuddy.exceptions import ValidationError
        from unified_app import create_app
        app = client.application

        @app.route("/api/_test_validation")
        def _test_validation():
            raise ValidationError("Bad field XYZ")

        r = client.get("/api/_test_validation")
        assert r.status_code == 400
        assert r.is_json
        assert "error" in r.get_json()

    def test_gemini_error_is_external_service_error(self):
        from unified_app import GeminiError
        from studybuddy.exceptions import ExternalServiceError, StudyBuddyError
        assert issubclass(GeminiError, ExternalServiceError)
        assert issubclass(GeminiError, StudyBuddyError)
        assert GeminiError.status_code == 502

    def test_github_error_is_external_service_error(self):
        from unified_app import GithubRepoError
        from studybuddy.exceptions import ExternalServiceError
        assert issubclass(GithubRepoError, ExternalServiceError)

    def test_unhandled_gemini_error_returns_502(self, client):
        from unified_app import GeminiError
        app = client.application

        @app.route("/api/_test_gemini_boom")
        def _boom():
            raise GeminiError("AI is down")

        r = client.get("/api/_test_gemini_boom")
        assert r.status_code == 502
        assert r.is_json

    def test_not_found_error(self, client):
        from studybuddy.exceptions import NotFoundError
        app = client.application

        @app.route("/api/_test_nf")
        def _nf():
            raise NotFoundError()

        r = client.get("/api/_test_nf")
        assert r.status_code == 404

    def test_quota_exceeded(self, client):
        from studybuddy.exceptions import QuotaExceeded
        app = client.application

        @app.route("/api/_test_quota")
        def _quota():
            raise QuotaExceeded()

        r = client.get("/api/_test_quota")
        assert r.status_code == 429
