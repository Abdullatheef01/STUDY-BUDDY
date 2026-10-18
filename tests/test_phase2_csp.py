"""Phase 2 — SEC-05 CSP report-only + nonces."""
class TestCSPHeaders:
    def test_csp_report_only_header_present(self, client):
        r = client.get("/")
        # Report-only by default (CSP_ENFORCE not set in tests)
        assert "Content-Security-Policy-Report-Only" in r.headers
        csp = r.headers["Content-Security-Policy-Report-Only"]
        assert "report-uri /csp-report" in csp
        assert "object-src 'none'" in csp
        assert "nonce-" in csp  # per-request nonce present

    def test_permissions_policy_present(self, client):
        r = client.get("/")
        assert "Permissions-Policy" in r.headers
        assert "camera=()" in r.headers["Permissions-Policy"]

    def test_csp_report_endpoint(self, client):
        r = client.post("/csp-report",
                        json={"csp-report": {"violated-directive": "script-src",
                                            "blocked-uri": "https://evil.com/x.js"}})
        assert r.status_code == 204

    def test_csp_nonce_available_in_templates(self, client):
        # nonce changes per request (not static)
        r1 = client.get("/")
        r2 = client.get("/")
        n1 = r1.headers["Content-Security-Policy-Report-Only"]
        n2 = r2.headers["Content-Security-Policy-Report-Only"]
        # extract nonce values
        import re
        m1 = re.search(r"nonce-([A-Za-z0-9_-]+)", n1)
        m2 = re.search(r"nonce-([A-Za-z0-9_-]+)", n2)
        assert m1 and m2
        assert m1.group(1) != m2.group(1), "nonce must be per-request"
