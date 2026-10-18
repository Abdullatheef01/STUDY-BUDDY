"""Tests for trending research (studybuddy.trending)."""
import json
import os

from studybuddy import trending
from studybuddy.trending import fetch_all, get_freshness, get_trending


def test_fetch_all_never_raises(monkeypatch):
    """Even with all sources down, fetch_all returns [] instead of raising."""
    monkeypatch.setattr(trending, "_arxiv_fetch", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(trending, "_openalex_fetch", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert fetch_all() == []


def test_fetch_all_dedupes(monkeypatch):
    dup = {"title": "Same Title Here", "authors": [], "abstract": "",
           "published": "", "url": "", "source": "arXiv", "id": "1"}
    dup2 = dict(dup, id="2", source="OpenAlex")
    monkeypatch.setattr(trending, "_arxiv_fetch", lambda: [dup])
    monkeypatch.setattr(trending, "_openalex_fetch", lambda: [dup2])
    papers = fetch_all()
    assert len(papers) == 1


def test_refresh_writes_cache(tmp_path, monkeypatch):
    papers = [{"title": "Test Paper", "authors": ["A"], "abstract": "x",
               "published": "2026-10-14", "url": "http://x", "source": "arXiv",
               "id": "1", "category": "cs.AI"}]
    monkeypatch.setattr(trending, "fetch_all", lambda: papers)
    cache = tmp_path / "trending_papers.json"
    monkeypatch.setattr(trending, "data_path", lambda fn: str(cache))
    trending.load_trending.cache_clear()
    assert trending.refresh_trending() is True
    with open(str(cache), encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["papers"]) == 1
    assert len(data["meta"]["last_updated"]) == 10


def test_refresh_no_papers_keeps_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(trending, "fetch_all", lambda: [])
    cache = tmp_path / "trending_papers.json"
    monkeypatch.setattr(trending, "data_path", lambda fn: str(cache))
    assert trending.refresh_trending() is False
    assert not os.path.exists(str(cache))


def test_get_trending_and_freshness_use_cache():
    # Uses the real seeded cache from data/trending_papers.json
    trending.load_trending.cache_clear()
    papers = get_trending(5)
    assert isinstance(papers, list)
    f = get_freshness()
    assert "label" in f and "stale" in f
