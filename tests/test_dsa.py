"""Tests for Wave 2 #15: DSA practice with hints and weak-topic diagnosis."""

import pytest

from studybuddy.dsa_practice import (
    all_problems,
    difficulties,
    filter_problems,
    get_problem,
    public_problem,
    reveal_approach,
    reveal_hint,
    topics,
    validate_status_payload,
    weak_topic_diagnosis,
)


@pytest.fixture
def authed_client(client, app):
    from werkzeug.security import generate_password_hash

    from unified_app import User, db
    with app.app_context():
        u = User(email="dsa@test.com", name="DSA Tester",
                 password_hash=generate_password_hash("password123"))
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"email": "dsa@test.com",
                                "password": "password123"})
    return client


def test_bank_size_and_schema():
    problems = all_problems()
    assert len(problems) >= 130, f"bank too small: {len(problems)}"
    required = {"id", "title", "statement", "difficulty", "topics", "hints",
                "approach", "complexity", "pitfalls"}
    for p in problems:
        assert required <= set(p), f"{p.get('id')} missing fields"
        assert p["difficulty"] in ("Easy", "Medium", "Hard")
        assert len(p["hints"]) >= 2, f"{p['id']} needs >=2 hints"
        assert len(p["topics"]) >= 1
        assert len(p["statement"]) > 30
        assert len(p["approach"]) > 30


def test_bank_id_uniqueness():
    ids = [p["id"] for p in all_problems()]
    assert len(ids) == len(set(ids))


def test_topics_and_difficulties_cover_required():
    topic_names = {t for t, _ in topics()}
    for t in ["arrays", "strings", "linked lists", "stacks", "queues",
              "trees", "graphs", "dynamic programming", "sorting",
              "searching", "heaps", "hash maps"]:
        assert t in topic_names, f"missing topic {t}"
    diffs = {d for d, _ in difficulties()}
    assert diffs == {"Easy", "Medium", "Hard"}


def test_filter_problems():
    arr = filter_problems(topic="arrays")
    assert arr and all("arrays" in p["topics"] for p in arr)
    hard = filter_problems(difficulty="Hard")
    assert hard and all(p["difficulty"] == "Hard" for p in hard)
    both = filter_problems(topic="graphs", difficulty="Easy")
    assert all("graphs" in p["topics"] and p["difficulty"] == "Easy" for p in both)
    assert len(filter_problems(topic="no-such-topic")) == 0


def test_public_problem_withholds_hints_and_approach():
    pid = all_problems()[0]["id"]
    pub = public_problem(pid, hints_revealed=1)
    assert pub["approach"] is None
    assert len(pub["hints"]) == 1
    assert pub["total_hints"] >= 2
    full = get_problem(pid)
    assert full["hints"][0] == pub["hints"][0]


def test_reveal_hint_progressive():
    pid = all_problems()[0]["id"]
    total = get_problem(pid)["hints"]
    seen = []
    n = 0
    for _ in range(len(total) + 2):
        hint, n = reveal_hint(pid, n)
        if hint:
            seen.append(hint)
    assert seen == total


def test_reveal_approach():
    pid = all_problems()[0]["id"]
    assert reveal_approach(pid) == get_problem(pid)["approach"]
    assert reveal_approach("nope") is None


def test_validate_status_payload():
    d, e = validate_status_payload({"status": "solved", "code": "x = 1"})
    assert d and e is None
    d, e = validate_status_payload({"status": "bogus"})
    assert d is None and e
    d, e = validate_status_payload({"status": "stuck", "code": "x" * 20001})
    assert d is None and e


def test_weak_topic_diagnosis():
    # solve all arrays problems, get stuck on graphs
    arr_ids = [p["id"] for p in all_problems() if "arrays" in p["topics"]][:3]
    graph_ids = [p["id"] for p in all_problems() if "graphs" in p["topics"]][:2]
    progress = ([{"problem_id": i, "status": "solved", "hints_used": 0} for i in arr_ids]
                + [{"problem_id": i, "status": "stuck", "hints_used": 3} for i in graph_ids])
    diag = weak_topic_diagnosis(progress)
    assert diag["overall"]["solved"] == len(arr_ids)
    assert diag["overall"]["stuck"] == len(graph_ids)
    by_topic = {t["topic"]: t for t in diag["topics"]}
    assert by_topic["arrays"]["solve_rate"] == 100.0
    assert by_topic["graphs"]["solve_rate"] == 0.0
    # weakest topic first
    assert diag["topics"][0]["topic"] == "graphs"
    # recommendations target the weak topic
    assert diag["recommendations"]
    assert any("graphs" in r["reason"] for r in diag["recommendations"])
    # recommended problems are not already solved
    rec_ids = {r["problem_id"] for r in diag["recommendations"]}
    assert not (rec_ids & set(arr_ids))


def test_weak_topic_diagnosis_empty():
    diag = weak_topic_diagnosis([])
    assert diag["overall"]["attempted"] == 0
    assert diag["topics"] == []
    assert diag["recommendations"] == []


def test_dsa_home_ok(client):
    r = client.get("/dsa")
    assert r.status_code == 200
    assert b"DSA" in r.data


def test_api_problem_list(client):
    r = client.get("/api/dsa/problems?topic=arrays&difficulty=Easy")
    assert r.status_code == 200
    d = r.get_json()
    assert d["count"] == len(d["problems"])
    assert all("arrays" in p["topics"] and p["difficulty"] == "Easy"
               for p in d["problems"])


def test_problem_page_ok(client):
    pid = all_problems()[0]["id"]
    r = client.get(f"/dsa/{pid}")
    assert r.status_code == 200
    assert get_problem(pid)["title"].encode() in r.data


def test_problem_page_404(client):
    assert client.get("/dsa/no-such-problem").status_code == 404


def test_hint_requires_login(client):
    pid = all_problems()[0]["id"]
    r = client.post(f"/dsa/{pid}/hint")
    assert r.status_code == 401


def test_hint_progression_persisted(authed_client, app):
    from unified_app import DSAProgress
    pid = all_problems()[0]["id"]
    r = authed_client.post(f"/dsa/{pid}/hint")
    assert r.status_code == 200
    d = r.get_json()
    assert d["success"] and d["hint"] and d["hints_used"] == 1
    r = authed_client.post(f"/dsa/{pid}/hint")
    assert r.get_json()["hints_used"] == 2
    with app.app_context():
        row = DSAProgress.query.filter_by(problem_id=pid).first()
        assert row is not None and row.hints_used == 2


def test_hint_exhaustion(authed_client):
    pid = all_problems()[1]["id"]
    total = len(get_problem(pid)["hints"])
    last = None
    for _ in range(total + 1):
        last = authed_client.post(f"/dsa/{pid}/hint").get_json()
    assert last["exhausted"] is True and last["hint"] is None


def test_approach_requires_login(client):
    pid = all_problems()[0]["id"]
    assert client.post(f"/dsa/{pid}/approach").status_code == 401


def test_approach_revealed_on_request(authed_client):
    pid = all_problems()[0]["id"]
    r = authed_client.post(f"/dsa/{pid}/approach")
    assert r.status_code == 200
    assert r.get_json()["approach"] == get_problem(pid)["approach"]


def test_status_flow(authed_client, app):
    from unified_app import DSAProgress
    pid = all_problems()[2]["id"]
    r = authed_client.post(f"/dsa/{pid}/status",
                           json={"status": "solved", "code": "def solve(): pass"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "solved"
    r = authed_client.post(f"/dsa/{pid}/status", json={"status": "bogus"})
    assert r.status_code == 400
    with app.app_context():
        row = DSAProgress.query.filter_by(problem_id=pid).first()
        assert row.status == "solved" and row.code == "def solve(): pass"


def test_diagnosis_requires_login(client):
    assert client.get("/dsa/diagnosis").status_code == 302  # login redirect


def test_diagnosis_page(authed_client):
    # mark one solved, one stuck
    arr = [p["id"] for p in all_problems() if "arrays" in p["topics"]][0]
    gr = [p["id"] for p in all_problems() if "graphs" in p["topics"]][0]
    authed_client.post(f"/dsa/{arr}/status", json={"status": "solved"})
    authed_client.post(f"/dsa/{gr}/status", json={"status": "stuck"})
    r = authed_client.get("/dsa/diagnosis")
    assert r.status_code == 200
    assert b"arrays" in r.data and b"graphs" in r.data


def test_dsa_isolation(client, authed_client, app):
    from werkzeug.security import generate_password_hash

    from unified_app import DSAProgress, User, db
    pid = all_problems()[3]["id"]
    with app.app_context():
        u2 = User(email="dsa2@test.com", name="Other",
                  password_hash=generate_password_hash("password123"))
        db.session.add(u2)
        db.session.commit()
        db.session.add(DSAProgress(user_id=u2.id, problem_id=pid,
                                   status="solved", hints_used=3))
        db.session.commit()
    # other user's progress must not leak into my problem page state
    r = authed_client.get(f"/dsa/{pid}")
    assert r.status_code == 200
    assert b"Current status" not in r.data


def test_xss_in_code_saved_safely(authed_client):
    pid = all_problems()[4]["id"]
    payload = {"status": "attempted",
               "code": "<script>alert(1)</script>def f(): pass" + "x" * 60}
    r = authed_client.post(f"/dsa/{pid}/status", json=payload)
    assert r.status_code == 200
    r = authed_client.get(f"/dsa/{pid}")
    assert r.status_code == 200
    assert b"<script>alert(1)</script>def f()" not in r.data
