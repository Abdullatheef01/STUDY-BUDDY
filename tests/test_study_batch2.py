"""Route-level tests for Wave 4 batch 2: lit reviews (#22), gap finder (#23),
flashcards & paper quizzes (#26).

Happy paths + the zero-error protocol: auth, invalid input, missing CSRF
(where enabled), empty library, cross-user isolation, malformed payloads.
"""
import json

import pytest

from unified_app import db, User, StudyDoc, LitReview, GapReport, FlashcardSet
from conftest import register, login  # noqa: F401


def _authed(client):
    register(client)
    login(client)


def _as_second_user(client):
    client.post("/logout")
    register(client, name="Second", email="second@example.com",
             password="password123")
    login(client, email="second@example.com", password="password123")


def _seed_doc(app, title, texts):
    """Insert a StudyDoc with the given chunk texts; returns the doc."""
    with app.app_context():
        user = User.query.filter_by(email="aarav@example.com").first()
        chunks = [{"page": i + 1, "index": i, "text": t, "heading": None}
                  for i, t in enumerate(texts)]
        doc = StudyDoc(user_id=user.id, title=title, num_pages=len(texts),
                       num_chunks=len(chunks),
                       char_count=sum(len(t) for t in texts),
                       data={"chunks": chunks})
        db.session.add(doc)
        db.session.commit()
        return doc.id


PAPER_A = [
    "Dropout is a regularization technique for neural networks. "
    "Our experiments demonstrate that dropout improves generalization on image classification tasks. "
    "We find that a dropout rate of 0.5 yields the best validation accuracy.",
    "The results indicate that dropout reduces overfitting significantly compared to weight decay. "
    "We conclude that dropout should be applied to fully connected layers.",
]
PAPER_B = [
    "Batch normalization accelerates deep network training. "
    "Our study shows that batch normalization improves convergence speed dramatically. "
    "However, batch normalization interacts poorly with dropout in some settings, "
    "and we observe that dropout harms convergence when combined naively.",
    "We suggest that practitioners tune both techniques jointly for best results.",
]


# ================= #22: literature reviews =================

def test_litreview_home_requires_login(client):
    r = client.get("/research/review")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_litreview_home_renders_bento(client):
    _authed(client)
    r = client.get("/research/review")
    assert r.status_code == 200
    assert b"b-card" in r.data and b"data-theme" in r.data


def test_litreview_generate_requires_auth(client):
    r = client.post("/research/api/review/generate", json={"doc_ids": [1, 2]})
    assert r.status_code == 401
    assert r.get_json()["error"]


def test_litreview_generate_needs_two_docs(client):
    _authed(client)
    r = client.post("/research/api/review/generate", json={"doc_ids": [1]})
    assert r.status_code == 400
    r = client.post("/research/api/review/generate", json={})
    assert r.status_code == 400


def test_litreview_generate_bad_ids(client):
    _authed(client)
    r = client.post("/research/api/review/generate", json={"doc_ids": ["x", "y"]})
    assert r.status_code == 400
    r = client.post("/research/api/review/generate", json={"doc_ids": "nope"})
    assert r.status_code == 400


def test_litreview_generate_unknown_docs(client):
    _authed(client)
    r = client.post("/research/api/review/generate", json={"doc_ids": [999, 1000]})
    assert r.status_code == 400


def test_litreview_full_flow(client, app):
    _authed(client)
    a = _seed_doc(app, "Dropout Paper", PAPER_A)
    b = _seed_doc(app, "BatchNorm Paper", PAPER_B)
    r = client.post("/research/api/review/generate",
                    json={"doc_ids": [a, b], "title": "Regularization survey"})
    assert r.status_code == 200, r.get_json()
    rid = r.get_json()["id"]
    # view page renders with bento
    v = client.get("/research/review/%d" % rid)
    assert v.status_code == 200 and b"b-card" in v.data
    # exports
    m = client.get("/research/review/%d/export?format=md" % rid)
    assert m.status_code == 200 and b"Dropout Paper" in m.data
    h = client.get("/research/review/%d/export?format=html" % rid)
    assert h.status_code == 200 and b"<" in h.data
    # unknown format falls back to markdown
    x = client.get("/research/review/%d/export?format=bogus" % rid)
    assert x.status_code == 200
    # delete
    d = client.delete("/research/api/review/%d" % rid)
    assert d.status_code == 200 and d.get_json()["success"]
    assert client.get("/research/review/%d" % rid).status_code == 404
    d2 = client.delete("/research/api/review/%d" % rid)
    assert d2.status_code == 404


def test_litreview_cross_user_isolation(client, app):
    _authed(client)
    a = _seed_doc(app, "Dropout Paper", PAPER_A)
    b = _seed_doc(app, "BatchNorm Paper", PAPER_B)
    rid = client.post("/research/api/review/generate",
                      json={"doc_ids": [a, b]}).get_json()["id"]
    # second user cannot see it
    _as_second_user(client)
    assert client.get("/research/review/%d" % rid).status_code == 404
    assert client.delete("/research/api/review/%d" % rid).status_code == 404


# ================= #23: gap finder =================

def test_gaps_home_requires_login(client):
    r = client.get("/research/gaps")
    assert r.status_code == 302


def test_gaps_home_renders_bento(client):
    _authed(client)
    r = client.get("/research/gaps")
    assert r.status_code == 200 and b"b-card" in r.data


def test_gaps_analyze_requires_auth(client):
    r = client.post("/research/api/gaps/analyze", json={})
    assert r.status_code == 401


def test_gaps_analyze_empty_library(client):
    _authed(client)
    r = client.post("/research/api/gaps/analyze", json={})
    assert r.status_code == 400


def test_gaps_analyze_bad_ids(client, app):
    _authed(client)
    _seed_doc(app, "Dropout Paper", PAPER_A)
    r = client.post("/research/api/gaps/analyze", json={"doc_ids": ["zzz"]})
    assert r.status_code == 400


def test_gaps_full_flow(client, app):
    _authed(client)
    a = _seed_doc(app, "Dropout Paper", PAPER_A)
    b = _seed_doc(app, "BatchNorm Paper", PAPER_B)
    r = client.post("/research/api/gaps/analyze", json={"doc_ids": [a, b]})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert "report" in body and "gaps" in body["report"]
    gid = body["id"]
    g = client.get("/research/api/gaps/%d" % gid)
    assert g.status_code == 200
    assert "gaps" in g.get_json()["report"]
    # whole-library mode (empty doc_ids)
    r2 = client.post("/research/api/gaps/analyze", json={})
    assert r2.status_code == 200


def test_gaps_cross_user(client, app):
    _authed(client)
    a = _seed_doc(app, "Dropout Paper", PAPER_A)
    b = _seed_doc(app, "BatchNorm Paper", PAPER_B)
    gid = client.post("/research/api/gaps/analyze",
                      json={"doc_ids": [a, b]}).get_json()["id"]
    _as_second_user(client)
    assert client.get("/research/api/gaps/%d" % gid).status_code == 404


# ================= #26: flashcards =================

def test_flashcards_home_requires_login(client):
    r = client.get("/research/flashcards")
    assert r.status_code == 302


def test_flashcards_home_renders_bento(client):
    _authed(client)
    r = client.get("/research/flashcards")
    assert r.status_code == 200 and b"b-card" in r.data


def test_flashcards_generate_requires_auth(client):
    r = client.post("/research/api/flashcards/generate", json={"doc_id": 1})
    assert r.status_code == 401


def test_flashcards_generate_bad_input(client):
    _authed(client)
    r = client.post("/research/api/flashcards/generate", json={"doc_id": "x"})
    assert r.status_code == 400
    r = client.post("/research/api/flashcards/generate", json={})
    assert r.status_code == 404
    r = client.post("/research/api/flashcards/generate", json={"doc_id": 999})
    assert r.status_code == 404


def test_flashcards_full_flow(client, app):
    _authed(client)
    did = _seed_doc(app, "ML Notes",
                    ["Gradient descent is an optimization algorithm used to minimize loss functions. "
                     "Backpropagation is the algorithm used to compute gradients in neural networks. "
                     "Overfitting occurs when a model memorizes training data and fails to generalize. "
                     "Regularization is a technique that reduces overfitting by penalizing complexity. "
                     "Cross validation is a method for estimating model performance on unseen data."])
    r = client.post("/research/api/flashcards/generate", json={"doc_id": did})
    assert r.status_code == 200, r.get_json()
    sid = r.get_json()["id"]
    assert r.get_json()["cards"] > 0
    # review page renders
    v = client.get("/research/flashcards/%d" % sid)
    assert v.status_code == 200 and b"b-card" in v.data
    # stats
    s = client.get("/research/api/flashcards/%d/stats" % sid)
    assert s.status_code == 200 and s.get_json()["stats"]["total"] > 0
    # progress: missing card_id -> 400, unknown card -> 400
    p = client.post("/research/api/flashcards/%d/progress" % sid, json={})
    assert p.status_code == 400
    p = client.post("/research/api/flashcards/%d/progress" % sid,
                    json={"card_id": "nope", "known": True})
    assert p.status_code == 400
    # progress on a real card
    with app.app_context():
        fs = FlashcardSet.query.filter_by(id=sid).first()
        card_id = fs.data["cards"][0]["id"]
        mcq = next((c for c in fs.data["cards"] if c["kind"] == "mcq"), None)
    p = client.post("/research/api/flashcards/%d/progress" % sid,
                    json={"card_id": card_id, "known": True})
    assert p.status_code == 200
    assert p.get_json()["stats"]["known"] == 1
    # quiz submit
    q = client.post("/research/api/flashcards/%d/quiz" % sid, json={"answers": "bad"})
    assert q.status_code == 400
    if mcq:
        answers = {mcq["id"]: mcq["options"].index(mcq["answer"])}
        q = client.post("/research/api/flashcards/%d/quiz" % sid,
                        json={"answers": answers})
        assert q.status_code == 200
        assert q.get_json()["score"] == 1
    # cross-user isolation
    _as_second_user(client)
    assert client.get("/research/flashcards/%d" % sid).status_code == 404
    assert client.get("/research/api/flashcards/%d/stats" % sid).status_code == 404
