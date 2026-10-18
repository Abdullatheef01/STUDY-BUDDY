"""Trending research — live paper discovery (Live Data Engine).

Two free, keyless sources (verified working 2026-10-14):

1. ArxivSource — GET https://export.arxiv.org/api/query
   Atom feed; sortBy=submitted&sortOrder=descending gives newest papers
   per category (cs.AI, cs.LG, cs.CL, ...).

2. OpenAlexSource — GET https://api.openalex.org/works
   JSON; filter=from_publication_date, sort=cited_by_count:desc gives
   most-cited recent works. No key needed.

Every fetch() NEVER raises: network/parsing errors are caught, logged,
and [] is returned. The disk cache (data/trending_papers.json) always
serves as fallback so the page never renders empty.
"""

import json
import logging
import re
import defusedxml.ElementTree as ET
from datetime import UTC, date, timedelta
from functools import lru_cache

import requests

from studybuddy.live_data import (
    atomic_write,
    data_path,
    freshness_badge,
    maybe_refresh,
    touch_updated,
)

log = logging.getLogger(__name__)

FILENAME = "trending_papers.json"
STALE_AFTER_DAYS = 1  # research moves fast — refresh daily
REQUEST_TIMEOUT = 15

ARXIV_URL = "https://export.arxiv.org/api/query"
OPENALEX_URL = "https://api.openalex.org/works"

CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.SE"]
MAX_PER_CATEGORY = 8


def _http_get(url, params=None, retries=3):
    headers = {"User-Agent": "STUDY-BUDDY/1.0 (research-discovery)"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r
        except Exception as exc:
            last_exc = exc
            log.warning("HTTP GET attempt %d/%d failed for %s: %s",
                        attempt + 1, retries, url, exc)
            if attempt < retries - 1:
                import time
                time.sleep(3 * (attempt + 1))  # arXiv asks for gentle pacing
    raise last_exc


def _arxiv_fetch():
    """Newest arXiv papers across key CS categories (single query)."""
    papers = []
    query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    try:
        # NB: no sortBy/sortOrder — arXiv rejects them (400); the default
        # order for category queries is newest-submitted first anyway.
        r = _http_get(ARXIV_URL, params={
            "search_query": query,
            "start": 0, "max_results": MAX_PER_CATEGORY * len(CATEGORIES),
        })
        root = ET.fromstring(r.text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            pid = (entry.findtext("a:id", "", ns) or "").strip()
            title = re.sub(r"\s+", " ", entry.findtext("a:title", "", ns) or "").strip()
            summary = re.sub(r"\s+", " ", entry.findtext("a:summary", "", ns) or "").strip()
            published = (entry.findtext("a:published", "", ns) or "")[:10]
            authors = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
            # arXiv category from the arxiv:primary_category element
            ns_arxiv = {"arxiv": "http://arxiv.org/schemas/atom"}
            prim = entry.find("arxiv:primary_category", {**ns, **ns_arxiv})
            cat = prim.get("term", "") if prim is not None else ""
            if not title:
                continue
            papers.append({
                "id": pid.rsplit("/", 1)[-1],
                "title": title,
                "abstract": summary[:600],
                "authors": [a for a in authors if a][:5],
                "published": published,
                "url": pid,
                "source": "arXiv",
                "category": cat,
            })
    except Exception as exc:
        log.warning("arXiv fetch failed: %s", exc)
    return papers


def _openalex_fetch():
    """Most-cited recent AI/ML works from OpenAlex (last 30 days)."""
    since = (date.today() - timedelta(days=30)).isoformat()
    try:
        r = _http_get(OPENALEX_URL, params={
            "filter": f"from_publication_date:{since}",
            "search": "machine learning artificial intelligence",
            "sort": "cited_by_count:desc",
            "per-page": 15,
        })
        data = r.json()
    except Exception as exc:
        log.warning("OpenAlex fetch failed: %s", exc)
        return []
    papers = []
    for w in data.get("results", []):
        title = w.get("title") or w.get("display_name") or ""
        if not title or title == "Unknown":
            continue
        authors = []
        for au in w.get("authorships", [])[:5]:
            name = (au.get("author") or {}).get("display_name")
            if name:
                authors.append(name)
        papers.append({
            "id": str(w.get("id", "")).rsplit("/", 1)[-1],
            "title": title,
            "abstract": "",
            "authors": authors,
            "published": w.get("publication_date", ""),
            "url": w.get("doi") or w.get("id", ""),
            "source": "OpenAlex",
            "cited_by": w.get("cited_by_count", 0),
        })
    return papers


def fetch_all():
    """Fetch from all sources. Never raises — returns [] on total failure."""
    papers = []
    try:
        papers.extend(_arxiv_fetch())
    except Exception as exc:
        log.warning("Trending arXiv source failed: %s", exc)
    try:
        papers.extend(_openalex_fetch())
    except Exception as exc:
        log.warning("Trending OpenAlex source failed: %s", exc)
    # Dedupe by normalized title
    seen, unique = set(), []
    for p in papers:
        key = re.sub(r"\W+", "", p["title"].lower())[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def refresh_trending():
    """Fetch, validate, atomically rewrite the cache. Never raises."""
    try:
        papers = fetch_all()
    except Exception as exc:
        log.warning("Trending refresh: fetch failed: %s", exc)
        return False
    if not papers:
        log.warning("Trending refresh: no papers fetched, keeping cache.")
        return False
    try:
        with open(data_path(FILENAME), encoding="utf-8") as f:
            current = json.load(f)
        meta = current.get("meta", {}) if isinstance(current, dict) else {}
    except Exception:
        meta = {}
    new_data = {
        "meta": touch_updated({
            **meta,
            "sources": ["arXiv", "OpenAlex"],
            "notice": "Live trending papers, refreshed daily. Falls back to cache when sources are unreachable.",
        }),
        "papers": papers,
    }
    try:
        atomic_write(data_path(FILENAME), new_data)
    except Exception as exc:
        log.warning("Trending refresh: write failed: %s", exc)
        return False
    load_trending.cache_clear()
    log.info("Trending refresh complete: %d papers.", len(papers))
    return True


@lru_cache(maxsize=1)
def load_trending():
    """Load cached trending papers; kicks off background refresh if stale."""
    path = data_path(FILENAME)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {"meta": {}, "papers": []}
    except Exception:
        data = {"meta": {}, "papers": []}
    maybe_refresh("trending", FILENAME, STALE_AFTER_DAYS, refresh_trending,
                  cache_clear=load_trending.cache_clear)
    return data


def get_trending(limit=30):
    limit = max(int(limit or 0), 0)
    return load_trending().get("papers", [])[:limit]


def get_freshness():
    return freshness_badge(load_trending().get("meta", {}), STALE_AFTER_DAYS)


# ================= Feature 24 Ultimate Enhancements =================
# 24.1 Personalized feed | 24.2 Paper-to-project ideas | 24.3 Weekly digest

import re as _re18


def _clean18(text):
    return _re18.sub(r"<[^>]*>", "", text or "")


def personalized_feed(papers, skills, limit=15):
    """Filter trending papers by the user's skills/interests.

    papers: list of {title, abstract?, ...}. skills: list of strings.
    Returns ranked {papers, matched_skills per paper}.
    """
    if not isinstance(papers, (list, tuple)):
        raise ValueError("papers must be a list.")
    skills = [_clean18(s).strip().lower() for s in (skills or [])
              if isinstance(s, str) and _clean18(s).strip()][:20]
    if not skills:
        raise ValueError("At least one skill/interest is needed.")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 15
    limit = max(1, min(50, limit))
    ranked = []
    for p in papers:
        if not isinstance(p, dict):
            continue
        blob = (_clean18(p.get("title") or "") + " " +
                _clean18(p.get("abstract") or p.get("summary") or "")).lower()
        if not blob.strip():
            continue
        hits = [s for s in skills if s in blob]
        if hits:
            ranked.append({"paper": {k: p.get(k) for k in
                                     ("title", "authors", "published", "link", "id")
                                     if p.get(k)},
                           "matched": hits, "relevance": len(hits)})
    ranked.sort(key=lambda x: -x["relevance"])
    return {"papers": ranked[:limit], "total": len(ranked),
            "skills": skills,
            "verdict": (f"{len(ranked)} trending papers match your skills."
                        if ranked else
                        "No trending papers match — broaden your interests or check back tomorrow.")}


def paper_to_project_ideas(paper):
    """Turn a trending paper into implementable project ideas.

    paper: {title, abstract?}. Returns {ideas: [{title, difficulty, steps}]}.
    """
    if not isinstance(paper, dict):
        raise ValueError("paper must be a dict.")
    title = _clean18(paper.get("title") or "").strip()
    if not title:
        raise ValueError("Paper title is required.")
    abstract = _clean18(paper.get("abstract") or paper.get("summary") or "")
    blob = (title + " " + abstract).lower()

    ideas = []
    # Idea 1: minimal reproduction.
    ideas.append({
        "title": f"Reproduce: {title[:60]} (minimal)",
        "difficulty": "Medium",
        "steps": ["Read the paper's method section twice",
                  "Implement the core idea on a toy dataset",
                  "Compare against the paper's reported baseline",
                  "Write up what matched / what didn't"],
    })
    # Idea 2: applied variant.
    domain = "your domain"
    for kw, dom in [("vision", "images"), ("nlp", "text"), ("language", "text"),
                    ("graph", "graphs"), ("audio", "audio"), ("robot", "robotics")]:
        if kw in blob:
            domain = dom
            break
    ideas.append({
        "title": f"Apply it: use the paper's method on {domain} you care about",
        "difficulty": "Medium-Hard",
        "steps": [f"Pick a {domain} dataset (Kaggle / HuggingFace)",
                  "Adapt the paper's method to it",
                  "Benchmark vs a simple baseline",
                  "Publish code + 2-min demo video"],
    })
    # Idea 3: extend / critique.
    ideas.append({
        "title": "Extend or stress-test the paper's claims",
        "difficulty": "Hard",
        "steps": ["Find an assumption the paper makes",
                  "Design an experiment that breaks it",
                  "Report honestly — negative results are valuable",
                  "Write it as a blog post or workshop paper"],
    })
    return {"paper": title[:100], "ideas": ideas,
            "guidance": "Start with idea 1. A reproduction that works is a portfolio piece."}


def weekly_digest(papers, skills=None, top_n=5):
    """Top-N weekly digest of trending papers for the user's field.

    Returns {digest: [...], generated_at, headline}.
    """
    try:
        top_n = int(top_n)
    except (TypeError, ValueError):
        top_n = 5
    top_n = max(1, min(10, top_n))
    if skills:
        try:
            feed = personalized_feed(papers, skills, limit=top_n)
            picks = feed["papers"]
        except (ValueError, TypeError):
            picks = []
    else:
        picks = [{"paper": p, "matched": [], "relevance": 0}
                 for p in (papers or []) if isinstance(p, dict)][:top_n]
    digest = []
    for i, item in enumerate(picks[:top_n], 1):
        p = item.get("paper", {}) if isinstance(item, dict) else {}
        digest.append({
            "rank": i,
            "title": _clean18(p.get("title") or "Untitled")[:120],
            "why": (f"Matches: {', '.join(item.get('matched', [])[:3])}"
                    if item.get("matched") else "Trending in your field"),
            "link": p.get("link") or p.get("id"),
        })
    from datetime import datetime
    return {"digest": digest, "count": len(digest),
            "generated_at": datetime.now(UTC).isoformat(),
            "headline": (f"This week's top {len(digest)} papers for you."
                         if digest else "No papers this week — check back soon.")}
