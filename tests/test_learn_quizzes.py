"""Tests for Wave 3 #19: skill quizzes."""
import pytest

from studybuddy.skill_quizzes import (
    quiz_skills, skill_topics, public_question, build_quiz, check_answer,
    grade_quiz, validate_start_payload, get_question)


def test_bank_size_and_schema():
    from studybuddy.skill_quizzes import _load
    bank = _load()
    assert len(bank) >= 300, f"need 300+ questions, got {len(bank)}"
    skills = {s for s, _ in quiz_skills()}
    assert len(skills) >= 15, f"need 15+ skills, got {len(skills)}"
    required = {"id", "skill", "topic", "difficulty", "question",
                "options", "answer", "explanation"}
    for q in bank:
        assert required <= set(q), q.get("id")
        assert q["difficulty"] in ("easy", "medium", "hard")
        assert len(q["options"]) == 4
        assert 0 <= q["answer"] <= 3
        assert len(q["explanation"]) > 10
        assert len(q["question"]) > 10


def test_bank_id_uniqueness():
    from studybuddy.skill_quizzes import _load
    ids = [q["id"] for q in _load()]
    assert len(ids) == len(set(ids))


def test_per_skill_counts():
    for skill, n in quiz_skills():
        assert 15 <= n <= 25, f"{skill}: {n} questions"


def test_build_quiz_stratified():
    skill = quiz_skills()[0][0]
    qs = build_quiz(skill, n=12)
    assert len(qs) == 12
    assert {q["skill"] for q in qs} == {skill}
    diffs = {q["difficulty"] for q in qs}
    assert len(diffs) >= 2, "stratified quiz should mix difficulties"
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids))


def test_build_quiz_difficulty_filter():
    skill = quiz_skills()[0][0]
    qs = build_quiz(skill, n=5, difficulties=["easy"])
    assert qs and all(q["difficulty"] == "easy" for q in qs)


def test_public_question_hides_answer():
    q = get_question(build_quiz(quiz_skills()[0][0], n=1)[0]["id"])
    pub = public_question(q)
    assert "answer" not in pub and "explanation" not in pub
    assert len(pub["options"]) == 4


def test_check_answer():
    q = build_quiz(quiz_skills()[0][0], n=1)[0]
    right = check_answer(q, q["answer"])
    assert right["correct"] is True
    assert right["explanation"] == q["explanation"]
    wrong_idx = (q["answer"] + 1) % 4
    wrong = check_answer(q, wrong_idx)
    assert wrong["correct"] is False
    assert wrong["correct_index"] == q["answer"]


def test_grade_quiz_analytics():
    skill = quiz_skills()[0][0]
    qs = build_quiz(skill, n=10, seed=42)
    # answer everything correctly
    answers = {q["id"]: q["answer"] for q in qs}
    results, summary = grade_quiz(qs, answers)
    assert summary["score"] == 10 and summary["pct"] == 100
    assert summary["weak_topics"] == []
    assert "verdict" in summary
    # answer everything wrong
    wrong = {q["id"]: (q["answer"] + 1) % 4 for q in qs}
    _, summary2 = grade_quiz(qs, wrong)
    assert summary2["score"] == 0
    assert summary2["weak_topics"], "all-wrong should flag weak topics"


def test_validate_start_payload():
    skill = quiz_skills()[0][0]
    good, err = validate_start_payload(
        {"skill": skill, "num_questions": 10, "difficulties": ["easy"],
         "timed": True, "time_limit_sec": 600})
    assert err is None and good["timed"] and good["time_limit_sec"] == 600
    _, err = validate_start_payload({"skill": "nope"})
    assert err


# ---------- route tests ----------

@pytest.fixture
def authed_client(client, app):
    from werkzeug.security import generate_password_hash
    from unified_app import db, User
    with app.app_context():
        u = User(email="learn19@test.com", name="Quizzer",
                 password_hash=generate_password_hash("password123"))
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"email": "learn19@test.com", "password": "password123"})
    return client


def _bento_ok(html):
    return 'bento.css' in html and 'b-card' in html


def test_quizzes_home_renders(client):
    r = client.get("/learn/quizzes")
    assert r.status_code == 200
    assert _bento_ok(r.get_data(as_text=True))


def test_quiz_start_requires_login(client):
    skill = quiz_skills()[0][0]
    r = client.post("/learn/quizzes/start", json={"skill": skill})
    assert r.status_code == 401


def test_quiz_full_flow(authed_client):
    skill = quiz_skills()[0][0]
    # start
    r = authed_client.post("/learn/quizzes/start", json={
        "skill": skill, "num_questions": 5, "difficulties": [], "timed": False})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"]
    aid = data["attempt_id"]
    assert len(data["questions"]) == 5
    assert all("answer" not in q for q in data["questions"])
    # instant check on first question
    q0 = data["questions"][0]
    full = get_question(q0["id"])
    r = authed_client.post(f"/learn/quizzes/{aid}/check", json={
        "question_id": q0["id"], "answer": full["answer"]})
    assert r.status_code == 200
    chk = r.get_json()
    assert chk["correct"] is True and chk["explanation"]
    # submit all correct
    answers = {q["id"]: get_question(q["id"])["answer"] for q in data["questions"]}
    r = authed_client.post(f"/learn/quizzes/{aid}/submit", json={"answers": answers})
    assert r.status_code == 200
    sub = r.get_json()
    assert sub["success"] and sub["summary"]["pct"] == 100
    assert "report_url" in sub
    # report page renders
    r = authed_client.get(sub["report_url"])
    assert r.status_code == 200
    assert _bento_ok(r.get_data(as_text=True))
    # double submit rejected
    r = authed_client.post(f"/learn/quizzes/{aid}/submit", json={"answers": answers})
    assert r.status_code == 404


def test_quiz_check_rejects_foreign_question(authed_client):
    skill = quiz_skills()[0][0]
    r = authed_client.post("/learn/quizzes/start", json={"skill": skill, "num_questions": 5})
    aid = r.get_json()["attempt_id"]
    other_skill = [s for s, _ in quiz_skills() if s != skill][0]
    foreign = build_quiz(other_skill, n=1)[0]["id"]
    r = authed_client.post(f"/learn/quizzes/{aid}/check", json={
        "question_id": foreign, "answer": 0})
    assert r.status_code == 400


def test_quiz_history_anonymous_redirect(client):
    assert client.get("/learn/quizzes/history").status_code in (301, 302)


def test_quiz_history(authed_client):
    r = authed_client.get("/learn/quizzes/history")
    assert r.status_code == 200
    assert _bento_ok(r.get_data(as_text=True))
