"""Shared pytest fixtures for Phase 1 foundation tests."""
import os

import pytest

# Never let the opportunity auto-refresh fire during tests: it would hit the
# real network and rewrite data/opportunities.json mid-suite.
os.environ["OPP_NO_AUTO_REFRESH"] = "1"

from unified_app import create_app


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def make_pdf_bytes(lines):
    """Build a minimal, valid single-page PDF containing the given text lines."""
    content = b"BT /F1 12 Tf 72 740 Td 14 TL\n"
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content += b"(" + safe.encode("latin-1", "ignore") + b") Tj T*\n"
    content += b"ET"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1, xref_pos)
    return pdf


SAMPLE_RESUME_LINES = [
    "Aarav Sharma",
    "aarav.sharma@example.com | +91-9876543210",
    "SUMMARY",
    "Computer Science undergraduate with strong Python and machine learning skills.",
    "EDUCATION",
    "B.Tech Computer Science, Graphic Era Hill University, 2023 - 2027",
    "EXPERIENCE",
    "Machine Learning Intern, 6 months building Flask APIs and data pipelines.",
    "SKILLS",
    "Python, Java, SQL, Machine Learning, Flask, Git, Data Analysis, HTML, CSS, JavaScript",
    "PROJECTS",
    "Built a resume analyzer web app with Flask and NLP.",
]


@pytest.fixture()
def sample_pdf():
    return make_pdf_bytes(SAMPLE_RESUME_LINES)


def register(client, name="Aarav Sharma", email="aarav@example.com", password="password123"):
    return client.post("/register", data={
        "name": name, "email": email, "password": password,
    }, follow_redirects=False)


def login(client, email="aarav@example.com", password="password123"):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=False)

@pytest.fixture(autouse=True)
def _reset_ai_circuit():
    """Reset AI gateway circuit breaker between tests (LLM-01 isolation)."""
    from studybuddy import ai_gateway
    ai_gateway._CIRCUIT.clear()
    yield
    ai_gateway._CIRCUIT.clear()
