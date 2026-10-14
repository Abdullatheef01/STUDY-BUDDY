"""Tests for Wave 3 #20: certification guidance."""
import pytest

from studybuddy.cert_guide import (
    all_certs, get_cert, domains, filter_certs, recommend, build_study_plan,
    validate_recommend_payload, validate_plan_payload)


def test_bank_size_and_schema():
    certs = all_certs()
    assert len(certs) >= 40, f"need 40+ certs, got {len(certs)}"
    required = {"id", "name", "provider", "domain", "cost_inr", "cost_note",
                "validity_years", "difficulty", "prerequisites", "exam_format",
                "official_url", "prep_resources", "career_value", "roles"}
    for c in certs:
        assert required <= set(c), c.get("id")
        assert c["difficulty"] in ("Beginner", "Intermediate", "Advanced")
        assert c["official_url"].startswith("https://")
        assert 3 <= len(c["prep_resources"]) <= 5
        assert "pproximat" in c["cost_note"], f"{c['id']} must mark cost approximate"
        assert isinstance(c["cost_inr"], (int, float)) and c["cost_inr"] > 0


def test_bank_id_uniqueness():
    ids = [c["id"] for c in all_certs()]
    assert len(ids) == len(set(ids))


def test_domain_coverage():
    names = {d for d, _ in domains()}
    for d in ("Cloud", "Data", "Programming", "Cybersecurity",
              "Project Management", "Networking", "DevOps", "AI/ML"):
        assert d in names, f"missing domain {d}"


def test_recommend_ranking():
    recs = recommend(skills=["python", "sql"], target_role="data-analyst",
                     budget_inr=30000, top_n=8)
    assert len(recs) == 8
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    for r in recs:
        assert r["reasons"], "each recommendation needs ROI reasoning"
        assert r["cert"]["cost_inr"] <= 30000 or \
            any("budget" in x.lower() for x in r["reasons"])


def test_recommend_budget_penalty():
    # The most expensive cert must score strictly lower under a tiny
    # budget than under a huge budget (budget overrun is penalized).
    # CEH (costliest) matches the cybersecurity-analyst role, so it ranks
    # in the top 20 under both budgets.
    costly_id = max(all_certs(), key=lambda c: c["cost_inr"])["id"]
    score_under = {r["cert"]["id"]: r["score"] for r in recommend(
        target_role="cybersecurity-analyst", budget_inr=5000, top_n=20)}
    score_over = {r["cert"]["id"]: r["score"] for r in recommend(
        target_role="cybersecurity-analyst", budget_inr=1000000, top_n=20)}
    assert costly_id in score_under and costly_id in score_over
    assert score_under[costly_id] < score_over[costly_id]


def test_build_study_plan_shape():
    cid = all_certs()[0]["id"]
    plan, err = build_study_plan(cid, weeks=6)
    assert err is None
    assert plan["weeks"] == 6 and len(plan["plan"]) == 6
    assert plan["plan"][0]["focus"] == "Foundations & exam blueprint"
    assert plan["plan"][-1]["focus"] == "Mock exams & revision"
    for w in plan["plan"]:
        assert w["tasks"], "each week needs tasks"
    plan2, err = build_study_plan("nope", weeks=6)
    assert plan2 is None and err


def test_validate_payloads():
    good, err = validate_recommend_payload(
        {"skills": ["python"], "target_role": "sde", "budget_inr": 20000, "top_n": 5})
    assert err is None and good["top_n"] == 5
    _, err = validate_recommend_payload({"budget_inr": -5})
    assert err
    cid = all_certs()[0]["id"]
    good, err = validate_plan_payload({"cert_id": cid, "weeks": 8})
    assert err is None and good["weeks"] == 8
    _, err = validate_plan_payload({"cert_id": "nope"})
    assert err


# ---------- route tests ----------

@pytest.fixture
def authed_client(client, app):
    from werkzeug.security import generate_password_hash
    from unified_app import db, User
    with app.app_context():
        u = User(email="learn20@test.com", name="CertSeeker",
                 password_hash=generate_password_hash("password123"))
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"email": "learn20@test.com", "password": "password123"})
    return client


def _bento_ok(html):
    return 'bento.css' in html and 'b-card' in html


def test_learn_hub_renders(client):
    r = client.get("/learn")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _bento_ok(html)
    assert '/learn/roadmaps' in html and '/learn/quizzes' in html and '/learn/certs' in html


def test_certs_home_renders(client):
    r = client.get("/learn/certs")
    assert r.status_code == 200
    assert _bento_ok(r.get_data(as_text=True))


def test_cert_detail_renders(client):
    cid = all_certs()[0]["id"]
    r = client.get(f"/learn/certs/{cid}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _bento_ok(html)
    assert '&#8377;' in html  # INR symbol rendered
    assert client.get("/learn/certs/nope").status_code == 404


def test_certs_browse(client):
    r = client.get("/learn/certs/browse?domain=Cloud")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] and data["certifications"]
    assert all(c["domain"] == "Cloud" for c in data["certifications"])
    r = client.get("/learn/certs/browse?max_cost=10000")
    data = r.get_json()
    assert all(c["cost_inr"] <= 10000 for c in data["certifications"])


def test_recommend_endpoint(client):
    r = client.post("/learn/certs/recommend", json={
        "skills": ["python"], "target_role": "ml-engineer",
        "budget_inr": 50000, "top_n": 5})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] and len(data["recommendations"]) == 5


def test_plan_requires_login(client):
    cid = all_certs()[0]["id"]
    r = client.post("/learn/certs/plan", json={"cert_id": cid, "weeks": 8})
    assert r.status_code == 401


def test_plan_roundtrip(authed_client, app):
    from unified_app import db, CertPlan, User
    cid = all_certs()[0]["id"]
    r = authed_client.post("/learn/certs/plan", json={"cert_id": cid, "weeks": 6})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] and len(data["plan"]["plan"]) == 6
    with app.app_context():
        u = User.query.filter_by(email="learn20@test.com").first()
        rows = CertPlan.query.filter_by(user_id=u.id).all()
        assert len(rows) == 1 and rows[0].weeks == 6


def test_certs_plans_anonymous_redirect(client):
    assert client.get("/learn/certs/plans").status_code in (301, 302)


def test_certs_plans_page(authed_client):
    r = authed_client.get("/learn/certs/plans")
    assert r.status_code == 200
    assert _bento_ok(r.get_data(as_text=True))


def test_main_dashboard_learning_section(authed_client):
    from studybuddy.learning_roadmaps import skill_ids
    sid = skill_ids()[0]
    authed_client.post("/learn/roadmaps/progress", json={
        "skill_id": sid, "stage": "beginner", "status": "completed"})
    r = authed_client.get("/dashboard")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Learning" in html and "roadmap" in html.lower()
