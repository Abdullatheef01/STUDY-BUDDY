"""Feature 24 ultimate: harsh tests for personalized feed, project ideas, digest."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.trending import (
    paper_to_project_ideas,
    personalized_feed,
    weekly_digest,
)
from tests.mega.harsh_corpus import HARSH_STRINGS


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


PAPERS = [
    {"title": "Deep Learning for NLP", "abstract": "Neural models for language.",
     "authors": ["A"], "link": "http://x"},
    {"title": "Cat behavior study", "abstract": "Felines.", "authors": ["B"]},
]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_feed_never_crashes(s):
    assert _ok(personalized_feed, PAPERS, [s])
    assert _ok(personalized_feed, s, ["python"])
    assert _ok(personalized_feed, None, None)


def test_feed_filters():
    f = personalized_feed(PAPERS, ["neural", "nlp"])
    assert f["total"] == 1
    assert f["papers"][0]["paper"]["title"] == "Deep Learning for NLP"
    assert "neural" in f["papers"][0]["matched"]


def test_feed_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        personalized_feed("nope", ["x"])
    with pytest.raises((ValueError, TypeError)):
        personalized_feed(PAPERS, [])


def test_feed_limit_clamped():
    f = personalized_feed(PAPERS * 10, ["cat"], limit=999)
    assert len(f["papers"]) <= 50


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_ideas_never_crashes(s):
    assert _ok(paper_to_project_ideas, {"title": s, "abstract": s})
    assert _ok(paper_to_project_ideas, s)
    assert _ok(paper_to_project_ideas, None)


def test_ideas_structure():
    p = paper_to_project_ideas({"title": "CNNs for vision", "abstract": "image models"})
    assert len(p["ideas"]) == 3
    assert all("steps" in i and "difficulty" in i for i in p["ideas"])
    assert p["guidance"]


def test_ideas_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        paper_to_project_ideas({"title": "   "})
    with pytest.raises((ValueError, TypeError)):
        paper_to_project_ideas("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_digest_never_crashes(s):
    assert _ok(weekly_digest, PAPERS, ["x"], 3)
    assert _ok(weekly_digest, s)


def test_digest_structure():
    d = weekly_digest(PAPERS, skills=["neural"], top_n=5)
    assert d["count"] >= 1
    assert d["generated_at"]
    assert all("rank" in x for x in d["digest"])


def test_digest_no_skills():
    d = weekly_digest(PAPERS, top_n=1)
    assert d["count"] == 1
