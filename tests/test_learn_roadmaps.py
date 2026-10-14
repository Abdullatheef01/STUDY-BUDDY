"""Tests for Wave 3 #18: skill-gap learning roadmaps."""
import pytest

from learning_roadmaps import (
    list_skills, list_domains, get_skill, list_roles, get_role, skill_ids,
    analyze_gap, build_personal_roadmap, validate_progress_payload,
    validate_gap_payload, STAGE_ORDER)


def test_bank_size_and_schema():
    from learning_roadmaps import _skills, _roles
    skills, roles = _skills(), _roles()
    assert len(skills) >= 20, f"need 20+ skills, got {len(skills)}"
    assert len(roles) >= 6, f"need 6+ roles, got {len(roles)}"
    for s in skills:
        assert {"id", "name", "domain", "summary", "stages"} <= set(s), s.get("id")
        assert [st["stage"] for st in s["stages"]] == ["beginner", "intermediate", "advanced"]
        for st in s["stages"]:
            assert 4 <= len(st["resources"]) <= 8, f"{s['id']}/{st['stage']}: resources"
            assert len(st["topics"]) >= 5, f"{s['id']}/{st['stage']}: topics"
            assert len(st["practice_tasks"]) >= 3
            assert len(st["checkpoint"]) > 20
            for r in st["resources"]:
                assert r["url"].startswith("https://"), f"bad url {r['url']}"
                assert r["type"] in ("video", "course", "docs", "article", "book", "practice")
    for r in roles:
        assert {"id", "name", "required_skills"} <= set(r)
        assert 5 <= len(r["required_skills"]) <= 8
        for req in r["required_skills"]:
            assert req["skill_id"] in skill_ids(), f"role {r['id']} bad skill {req['skill_id']}"
            assert 1 <= req["priority"] <= 5
            assert req["min_stage"] in STAGE_ORDER


def test_skill_id_uniqueness():
    ids = skill_ids()
    assert len(ids) == len(set(ids))


def test_analyze_gap_ranking():
    gaps, role = analyze_gap(
        [{"skill_id": "python", "stage": "intermediate"}],
        "data-analyst")
    assert role and role["id"] == "data-analyst"
    assert gaps, "expected gaps for a data-analyst with only python"
    prios = [g["priority"] for g in gaps]
    assert prios == sorted(prios, reverse=True), "gaps must be priority-ranked"
    # python intermediate should NOT appear as a gap if requirement <= intermediate
    for g in gaps:
        assert g["weeks_needed"] >= 0
        assert g["stages_to_cover"], "gap with no stages to cover"


def test_analyze_gap_no_gaps():
    role = get_role("frontend-dev")
    current = [{"skill_id": req["skill_id"], "stage": req["min_stage"]}
               for req in role["required_skills"]]
    gaps, _ = analyze_gap(current, "frontend-dev")
    assert gaps == []


def test_analyze_gap_unknown_role():
    gaps, role = analyze_gap([], "nope")
    assert gaps is None and role is None


def test_build_personal_roadmap_totals():
    gaps, _ = analyze_gap([], "sde")
    plan = build_personal_roadmap(gaps)
    assert plan["num_skills"] == len(gaps)
    assert plan["total_weeks"] == sum(g["weeks_needed"] for g in gaps)
    assert plan["total_weeks"] > 0


def test_validate_progress_payload():
    good, err = validate_progress_payload(
        {"skill_id": skill_ids()[0], "stage": "beginner", "status": "completed"})
    assert err is None and good["status"] == "completed"
    _, err = validate_progress_payload({"skill_id": "nope", "stage": "beginner", "status": "completed"})
    assert err
    _, err = validate_progress_payload(
        {"skill_id": skill_ids()[0], "stage": "expert", "status": "completed"})
    assert err
    _, err = validate_progress_payload(
        {"skill_id": skill_ids()[0], "stage": "beginner", "status": "done"})
    assert err


def test_validate_gap_payload():
    roles = list_roles()
    good, err = validate_gap_payload(
        {"target_role": roles[0]["id"],
         "current_skills": [{"skill_id": skill_ids()[0], "stage": "advanced"}]})
    assert err is None and good["target_role"] == roles[0]["id"]
    _, err = validate_gap_payload({"target_role": "nope", "current_skills": []})
    assert err


# ---------- route tests ----------

@pytest.fixture
def authed_client(client, app):
    from werkzeug.security import generate_password_hash
    from unified_app import db, User
    with app.app_context():
        u = User(email="learn18@test.com", name="Learner",
                 password_hash=generate_password_hash("password123"))
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"email": "learn18@test.com", "password": "password123"})
    return client


def _bento_ok(html):
    return 'bento.css' in html and 'b-card' in html and 'b-nav' in html


def test_roadmaps_home_renders(client):
    r = client.get("/learn/roadmaps")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _bento_ok(html)
    assert 'gap-run' in html


def test_roadmap_detail_renders(client):
    sid = skill_ids()[0]
    r = client.get(f"/learn/roadmaps/{sid}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _bento_ok(html)
    assert 'beginner' in html and 'checkpoint' in html.lower()
    assert client.get("/learn/roadmaps/does-not-exist").status_code == 404


def test_gap_endpoint_anonymous(client):
    roles = list_roles()
    r = client.post("/learn/roadmaps/gap", json={
        "target_role": roles[0]["id"], "current_skills": []})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] and data["total_weeks"] > 0
    assert data["gaps"] and "study_tip" in data


def test_gap_endpoint_bad_role(client):
    r = client.post("/learn/roadmaps/gap", json={"target_role": "nope"})
    assert r.status_code == 400


def test_progress_requires_login(client):
    r = client.post("/learn/roadmaps/progress", json={
        "skill_id": skill_ids()[0], "stage": "beginner", "status": "completed"})
    assert r.status_code == 401


def test_progress_roundtrip(authed_client, app):
    from unified_app import db, RoadmapProgress, User
    sid = skill_ids()[0]
    r = authed_client.post("/learn/roadmaps/progress", json={
        "skill_id": sid, "stage": "beginner", "status": "in_progress"})
    assert r.status_code == 200
    r = authed_client.post("/learn/roadmaps/progress", json={
        "skill_id": sid, "stage": "beginner", "status": "completed"})
    assert r.get_json()["status"] == "completed"
    with app.app_context():
        u = User.query.filter_by(email="learn18@test.com").first()
        rows = RoadmapProgress.query.filter_by(user_id=u.id).all()
        assert len(rows) == 1 and rows[0].status == "completed"


def test_roadmaps_dashboard_anonymous_redirect(client):
    assert client.get("/learn/roadmaps/dashboard").status_code in (301, 302)


def test_roadmaps_dashboard(authed_client):
    r = authed_client.get("/learn/roadmaps/dashboard")
    assert r.status_code == 200
    assert _bento_ok(r.get_data(as_text=True))
