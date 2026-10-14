"""Literature-review engine (study feature: multi-paper lit review).

Pure-logic module — no Flask imports, no network, stdlib only (plus the
``pdf_qa`` tokenizer and the ``citation_fmt`` BibTeX exporter). Everything
here is:

- **Deterministic** — identical inputs always produce identical output.
  Rankings break ties by ``(doc_id, chunk_index, sentence order)``, never by
  set/dict iteration order.
- **Honest / extractive** — every claim in a review is a verbatim sentence
  from a source chunk. Citation page numbers only ever come from the chunk
  that was actually cited, and every citation excerpt is a verbatim substring
  of that chunk's text. When the input is insufficient (fewer than two papers
  with extractable text), the review is an explicit ``{"error": ...}`` dict —
  never a fabricated review.
- **Defensive** — every public function never raises on bad input; malformed
  input yields an honest empty structure instead of crashing.

LitReview.data contract (the shape stored on ``unified_app.LitReview.data``)::

    {
      "per_paper": [
        {"doc_id": int, "title": str, "summary": str,
         "citations": [{"doc": str, "page": int, "chunk": int,
                        "excerpt": str}, ...]}
      ],
      "themes": [
        {"name": str, "terms": [str, ...], "papers": [title, ...],
         "synthesis": str,
         "citations": [{"doc": str, "page": int, "chunk": int,
                        "excerpt": str}, ...]}
      ],
      "claims_table": [
        {"claim": str, "papers": [title, ...],
         "citations": [{"doc": str, "page": int, "chunk": int,
                        "excerpt": str}, ...]}
      ],
      "coverage_gaps": str,   # honest note about single-paper coverage
      "bibtex": str           # one BibTeX entry per included paper
    }

    On insufficient input the dict is instead::

      {"error": str, "per_paper": [], "themes": [],
       "claims_table": [], "coverage_gaps": "", "bibtex": ""}

Citation dicts follow the app-wide format from ``pdf_qa``: ``"doc"`` is the
paper title, ``"page"`` the 1-based page, ``"chunk"`` the global chunk index,
and ``"excerpt"`` a verbatim substring of the chunk text.

Public surface (exactly these six functions):

    split_sentences(text) -> list[str]
    score_sentences(chunks, query_terms=None, top_n=8) -> list[dict]
    extract_claims(chunks_with_doc) -> list[dict]
    cluster_themes(chunks_with_doc, max_themes=6) -> list[dict]
    generate_review(docs, paper_metas=None, gemini_polish=None,
                    paper_imports=None) -> dict
    review_to_markdown(review) -> str
    review_to_html(review) -> str
"""

from __future__ import annotations

import html
import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from studybuddy.pdf_qa import _tokenize
from studybuddy.citation_fmt import to_bibtex

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

#: Sentences shorter than this (chars) are treated as fragments/headings.
MIN_SENTENCE_CHARS = 15

#: Weight of the early-sentence position bonus in sentence scoring.
POSITION_BONUS_WEIGHT = 0.2

#: Bonus per query term overlapping a sentence (query_terms given only).
QUERY_TERM_BONUS = 0.5

#: Maximum themes produced by cluster_themes.
DEFAULT_MAX_THEMES = 6

#: Maximum terms kept per theme (seed + attached discriminative terms).
THEME_TERMS_PER_THEME = 6

#: A chunk may belong to this many themes at most.
THEMES_PER_CHUNK = 2

#: Jaccard token similarity at/above which two claims count as duplicates.
CLAIM_DEDUP_JACCARD = 0.85

#: Jaccard chunk-set similarity at/above which two theme seeds merge.
THEME_MERGE_JACCARD = 0.6

#: Maximum characters kept in a citation excerpt (sentences are stored whole,
#: this is a safety cap only).
EXCERPT_MAX = 500

#: Citation marker rendered after quoted sentences, e.g. "[Paper A, p.2]".
CITATION_MARKER = "[{title}, p.{page}]"

# ---------------------------------------------------------------------------
# Abbreviation-aware sentence splitting
# ---------------------------------------------------------------------------

#: Abbreviations whose trailing dot must not end a sentence.
_ABBREVIATIONS = (
    "e.g.", "i.e.", "vs.", "etc.", "Fig.", "Eq.", "Sec.",
    "Dr.", "Mr.", "Mrs.", "Ms.", "St.", "Jr.", "Sr.",
    "approx.", "al.", "No.", "Vol.", "Ch.", "Ref.",
)

#: Placeholder used while splitting so abbreviation dots survive intact.
_DOT_PLACEHOLDER = "\x00"

#: A sentence boundary: sentence-ending punctuation, then whitespace, then
#: what looks like the start of a new sentence (capital letter / digit,
#: optionally after an opening quote or bracket).
_SENT_BOUNDARY_RE = re.compile(
    r'(?<=[.!?])\s+(?=["\'\u201c\u201d\u2018\u2019\(\[]?[A-Z0-9])'
)


def _mask_abbreviations(text: str) -> str:
    """Replace the dots inside known abbreviations with a placeholder."""
    masked = text
    for abbr in _ABBREVIATIONS:
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(abbr),
                             re.IGNORECASE)
        masked = pattern.sub(
            lambda m: m.group(0).replace(".", _DOT_PLACEHOLDER), masked)
    return masked


def split_sentences(text: str) -> List[str]:
    """Split text into sentences.

    Abbreviation-aware (``e.g.``, ``Fig.``, ``et al.`` do not split), keeps
    the trailing punctuation with each sentence, and drops fragments shorter
    than :data:`MIN_SENTENCE_CHARS`. Each returned sentence is a verbatim
    substring of the input text (outer whitespace stripped).

    Never raises: non-string input yields ``[]``.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    masked = _mask_abbreviations(text)
    sentences: List[str] = []
    start = 0
    for match in _SENT_BOUNDARY_RE.finditer(masked):
        piece = masked[start:match.start()].replace(
            _DOT_PLACEHOLDER, ".").strip()
        if len(piece) >= MIN_SENTENCE_CHARS:
            sentences.append(piece)
        start = match.end()
    tail = masked[start:].replace(_DOT_PLACEHOLDER, ".").strip()
    if len(tail) >= MIN_SENTENCE_CHARS:
        sentences.append(tail)
    return sentences


# ---------------------------------------------------------------------------
# Chunk normalisation helpers
# ---------------------------------------------------------------------------

def _norm_chunk(chunk: Any) -> Dict[str, Any]:
    """Return a defensive copy of a chunk dict with guaranteed keys."""
    if not isinstance(chunk, dict):
        return {"page": 1, "index": 0, "text": "", "heading": "",
                "doc_id": None, "doc_title": ""}
    text = chunk.get("text")
    page = chunk.get("page")
    index = chunk.get("index")
    return {
        "page": page if isinstance(page, int) and page >= 1 else 1,
        "index": index if isinstance(index, int) and index >= 0 else 0,
        "text": text if isinstance(text, str) else "",
        "heading": chunk.get("heading")
        if isinstance(chunk.get("heading"), str) else "",
        "doc_id": chunk.get("doc_id"),
        "doc_title": chunk.get("doc_title")
        if isinstance(chunk.get("doc_title"), str) else "",
    }


def _sentences_of(chunk: Dict[str, Any]) -> List[Tuple[str, int]]:
    """(sentence, position-in-chunk) pairs for a normalised chunk."""
    return list(enumerate(split_sentences(chunk["text"])))


# ---------------------------------------------------------------------------
# Sentence scoring (TF-IDF weighted + position bonus)
# ---------------------------------------------------------------------------

def _smooth_idf(tokenized_chunks: List[List[str]]) -> Dict[str, float]:
    """Smoothed IDF over chunk token lists: log((1+N)/(1+df)) + 1."""
    n = len(tokenized_chunks)
    df: Dict[str, int] = {}
    for tokens in tokenized_chunks:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    return {t: math.log((1.0 + n) / (1.0 + c)) + 1.0 for t, c in df.items()}


def _score_all(chunks: List[Dict[str, Any]],
               query_terms: Optional[List[str]] = None) -> List[Dict]:
    """Score every sentence of every chunk; fully sorted, no truncation."""
    normed = [_norm_chunk(c) for c in chunks]
    tokenized_chunks = [_tokenize(c["text"]) for c in normed]
    idf = _smooth_idf(tokenized_chunks)

    query_set = set()
    if query_terms:
        try:
            query_set = set(_tokenize(" ".join(str(t) for t in query_terms)))
        except Exception:
            query_set = set()

    scored: List[Dict] = []
    for chunk, _ in zip(normed, tokenized_chunks):
        for pos, sentence in _sentences_of(chunk):
            tokens = _tokenize(sentence)
            if tokens:
                counts: Dict[str, int] = {}
                for t in tokens:
                    counts[t] = counts.get(t, 0) + 1
                tfidf = sum((counts[t] / len(tokens)) * idf.get(t, 0.0)
                            for t in counts)
            else:
                tfidf = 0.0
            position_bonus = POSITION_BONUS_WEIGHT / (1.0 + pos)
            query_bonus = (QUERY_TERM_BONUS *
                           len(query_set.intersection(tokens))) if query_set else 0.0
            scored.append({
                "sentence": sentence,
                "chunk_index": chunk["index"],
                "page": chunk["page"],
                "score": tfidf + position_bonus + query_bonus,
                "doc_id": chunk["doc_id"],
                "doc_title": chunk["doc_title"],
                "_order": pos,
            })
    # Deterministic: (-score, doc_id, chunk_index, sentence order).
    scored.sort(key=lambda s: (-s["score"],
                               s["doc_id"] if s["doc_id"] is not None else -1,
                               s["chunk_index"], s["_order"]))
    for s in scored:
        del s["_order"]
    return scored


def score_sentences(chunks: List[Dict],
                    query_terms: Optional[List[str]] = None,
                    top_n: int = 8) -> List[Dict]:
    """Score sentences across chunks and return the top ``top_n``.

    Score = TF-IDF-weighted term importance (IDF computed over the chunk
    set) + a small position bonus for early sentences in a chunk + an
    optional per-term bonus for ``query_terms`` overlap. Ties are broken
    deterministically by ``(doc_id, chunk_index, sentence order)``.

    Each result is ``{"sentence", "chunk_index", "page", "score",
    "doc_id", "doc_title"}``.

    Never raises: bad input yields ``[]``.
    """
    try:
        if chunks is None:
            return []
        chunks = list(chunks)
    except TypeError:
        return []
    if not chunks:
        return []
    try:
        limit = int(top_n) if top_n is not None else None
    except (TypeError, ValueError):
        limit = 8
    try:
        scored = _score_all(chunks, query_terms)
    except Exception:
        return []
    if limit is None:
        return scored
    if limit <= 0:
        return []
    return scored[:limit]


# ---------------------------------------------------------------------------
# Claim extraction (finding-verb sentences)
# ---------------------------------------------------------------------------

_FINDING_VERBS = (
    r"find|finds|finding|found|show|shows|showed|shown|showing|"
    r"demonstrate|demonstrates|demonstrated|demonstrating|"
    r"reveal|reveals|revealed|revealing|"
    r"indicate|indicates|indicated|indicating|"
    r"suggest|suggests|suggested|suggesting|"
    r"conclude|concludes|concluded|concluding|"
    r"report|reports|reported|reporting|"
    r"observe|observes|observed|observing|"
    r"achieve|achieves|achieved|achieving|"
    r"improve|improves|improved|improving|"
    r"outperform|outperforms|outperformed|outperforming|"
    r"reduce|reduces|reduced|reducing"
)
_FINDING_RE = re.compile(r"\b(%s)\b" % _FINDING_VERBS, re.IGNORECASE)


def _normalize_claim(text: str) -> str:
    """Lowercased, punctuation-stripped, whitespace-collapsed claim text."""
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]", "", text.lower())).strip()


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_claims(chunks_with_doc: List[Dict]) -> List[Dict]:
    """Extract claim sentences (those containing finding-verbs).

    Each result is ``{"claim", "doc_id", "doc_title", "chunk_index",
    "page"}`` where ``claim`` is the verbatim sentence. Near-identical
    claims (Jaccard token similarity >= :data:`CLAIM_DEDUP_JACCARD`) are
    deduplicated, keeping the first occurrence in deterministic
    ``(doc_id, chunk_index, sentence order)`` order.

    Never raises: bad input yields ``[]``.
    """
    try:
        if not chunks_with_doc:
            return []
        chunks = [_norm_chunk(c) for c in chunks_with_doc]
    except Exception:
        return []
    chunks.sort(key=lambda c: (c["doc_id"] if c["doc_id"] is not None else -1,
                               c["index"]))
    claims: List[Dict] = []
    seen: List[set] = []  # token sets of kept claims, for near-dup detection
    seen_exact: set = set()
    try:
        for chunk in chunks:
            for _pos, sentence in _sentences_of(chunk):
                if not _FINDING_RE.search(sentence):
                    continue
                norm = _normalize_claim(sentence)
                if not norm or norm in seen_exact:
                    continue
                tokens = set(norm.split())
                if any(_jaccard(tokens, prev) >= CLAIM_DEDUP_JACCARD
                       for prev in seen):
                    continue
                seen_exact.add(norm)
                seen.append(tokens)
                claims.append({
                    "claim": sentence,
                    "doc_id": chunk["doc_id"],
                    "doc_title": chunk["doc_title"],
                    "chunk_index": chunk["index"],
                    "page": chunk["page"],
                })
    except Exception:
        return claims
    return claims


# ---------------------------------------------------------------------------
# Theme clustering (discriminative-term seeding + overlap assignment)
# ---------------------------------------------------------------------------

#: ~160-word stoplist for theme-term mining (function words + generic
#: academic filler that would otherwise dominate every theme).
_THEME_STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because
    been before being below between both but by can could did do does doing
    down during each few for from further had has have having he her here hers
    herself him himself his how i if in into is it its itself just like me
    more most my myself no nor not now of off on once only or other ought our
    ours ourselves out over own same she should so some such than that the
    their theirs them themselves then there these they this those through to
    too under until up very was we were what when where which while who whom
    why with would you your yours yourself yourselves shall may might must
    paper papers study studies research result results finding findings method
    methods methodology approach approaches model models data dataset using
    used use uses based via within without also however therefore thus hence
    well much many one two three four five first second third new novel
    proposed propose present presents described describes discussed discusses
    show shown et al fig figure figures table tables section sections
    conclude concludes concluded demonstrate demonstrates demonstrated find
    finds found report reports reported reveal reveals revealed suggest
    suggests suggested indicate indicates indicated observe observes observed
    achieve achieves achieved improve improves improved outperform study
    investigate investigates evaluate evaluates analyze analyses compare
    compares examine examines explore explores test tests tested assess
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _theme_tokens(text: str) -> List[str]:
    """Lowercased alphanumeric tokens minus the theme stoplist."""
    if not isinstance(text, str):
        return []
    return [t for t in _TOKEN_RE.findall(text.lower())
            if t not in _THEME_STOPWORDS and len(t) > 2 and not t.isdigit()]


def cluster_themes(chunks_with_doc: List[Dict],
                   max_themes: int = DEFAULT_MAX_THEMES) -> List[Dict]:
    """Cluster chunks into themes from discriminative terms.

    Term document-frequencies are computed across chunks; terms are ranked by
    summed TF-IDF (TF within chunk x smoothed IDF across chunks). The top
    terms seed themes (seeds whose chunk sets overlap heavily are merged into
    one theme), and each chunk is assigned to its best theme(s) by weighted
    term overlap — a chunk may join up to :data:`THEMES_PER_CHUNK` themes.

    Each theme is ``{"name", "terms", "members"}`` where ``name`` is the top
    2-3 terms joined with spaces and ``members`` are ``{"doc_id",
    "doc_title", "chunk_index", "page"}`` dicts. Fully deterministic.

    Never raises: bad input yields ``[]``.
    """
    try:
        if not chunks_with_doc:
            return []
        chunks = [_norm_chunk(c) for c in chunks_with_doc]
        max_themes = max(1, int(max_themes))
    except (TypeError, ValueError):
        return []
    except Exception:
        return []

    try:
        tokenized = [_theme_tokens(c["text"]) for c in chunks]
        n = len(chunks)
        df: Dict[str, int] = {}
        for tokens in tokenized:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1
        idf = {t: math.log((1.0 + n) / (1.0 + c)) + 1.0
               for t, c in df.items()}

        # Term score: summed TF-IDF over chunks.
        term_score: Dict[str, float] = {}
        for tokens in tokenized:
            if not tokens:
                continue
            counts: Dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            for t, c in counts.items():
                term_score[t] = term_score.get(t, 0.0) + \
                    (c / len(tokens)) * idf[t]
        ranked = sorted(term_score, key=lambda t: (-term_score[t], t))
        if not ranked:
            return []

        # Chunk-id set per candidate term (for seed merging).
        term_chunks: Dict[str, set] = {}
        for i, tokens in enumerate(tokenized):
            for term in set(tokens):
                term_chunks.setdefault(term, set()).add(i)

        # Greedy seeding: merge a candidate into an accepted theme when its
        # chunk set overlaps an existing seed's set heavily.
        themes: List[Dict] = []  # {"seed", "terms", "chunk_set"}
        for term in ranked[:max_themes * 3]:
            cset = term_chunks.get(term, set())
            if not cset:
                continue
            best, best_j = None, 0.0
            for th in themes:
                j = _jaccard(cset, th["chunk_set"])
                if j > best_j:
                    best, best_j = th, j
            if best is not None and best_j >= THEME_MERGE_JACCARD:
                if term not in best["terms"]:
                    best["terms"].append(term)
                best["chunk_set"] |= cset
            elif len(themes) < max_themes:
                themes.append({"seed": term, "terms": [term],
                               "chunk_set": set(cset)})
        if not themes:
            return []

        # Per-theme term weights (idf) for overlap scoring.
        theme_term_weights = [
            {t: idf.get(t, 0.0) for t in th["terms"]
             [:THEME_TERMS_PER_THEME]}
            for th in themes
        ]
        token_sets = [set(t) for t in tokenized]

        # Assign each chunk to up to THEMES_PER_CHUNK best themes.
        assignments: List[List[int]] = [[] for _ in themes]
        for i, tset in enumerate(token_sets):
            scored_th = []
            for ti, weights in enumerate(theme_term_weights):
                overlap = sum(w for t, w in weights.items() if t in tset)
                if overlap > 0:
                    scored_th.append((ti, overlap))
            scored_th.sort(key=lambda x: (-x[1], x[0]))
            for ti, _ in scored_th[:THEMES_PER_CHUNK]:
                assignments[ti].append(i)

        result = []
        for ti, th in enumerate(themes):
            member_idx = sorted(assignments[ti])
            if not member_idx:
                continue
            terms = sorted(th["terms"][:THEME_TERMS_PER_THEME],
                           key=lambda t: (-term_score.get(t, 0.0), t))
            name = " ".join(terms[:3])
            members = [{
                "doc_id": chunks[i]["doc_id"],
                "doc_title": chunks[i]["doc_title"],
                "chunk_index": chunks[i]["index"],
                "page": chunks[i]["page"],
            } for i in member_idx]
            # Deterministic member order.
            members.sort(key=lambda m: (
                m["doc_id"] if m["doc_id"] is not None else -1,
                m["chunk_index"]))
            result.append({"name": name, "terms": terms, "members": members})
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Review generation
# ---------------------------------------------------------------------------

def _empty_error(message: str) -> Dict:
    """Honest empty review shape for insufficient input."""
    return {"error": message, "per_paper": [], "themes": [],
            "claims_table": [], "coverage_gaps": "", "bibtex": ""}


def _norm_title(title: Any) -> str:
    """Normalized title for best-effort PaperImport matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()


def _citation(title: str, page: int, chunk_index: int,
              excerpt: str) -> Dict:
    """App-standard citation dict; excerpt is a verbatim chunk substring."""
    if not isinstance(excerpt, str):
        excerpt = ""
    return {"doc": title, "page": page, "chunk": chunk_index,
            "excerpt": excerpt[:EXCERPT_MAX]}


def _cite_marker(title: str, page: int) -> str:
    return CITATION_MARKER.format(title=title, page=page)


def _doc_chunks(doc: Any) -> List[Dict]:
    """Extract chunk dicts from a StudyDoc-like object (duck-typed)."""
    try:
        data = getattr(doc, "data", None) or {}
        chunks = data.get("chunks") if isinstance(data, dict) else None
        if not isinstance(chunks, list):
            return []
        return [c for c in chunks if isinstance(c, dict)]
    except Exception:
        return []


def _build_bibtex(docs: List[Tuple[Any, str]],
                  paper_metas: Optional[Dict[int, dict]],
                  paper_imports: Optional[List[dict]]) -> str:
    """One BibTeX entry per paper.

    Metadata precedence per paper: ``paper_metas[doc.id]`` first, then a
    best-effort PaperImport match by normalized title (first match wins,
    deterministic), else title-only. Key collisions across entries are
    resolved deterministically via ``to_bibtex``'s ``existing_keys``.
    """
    import_lookup: Dict[str, dict] = {}
    try:
        imports = list(paper_imports or [])
    except TypeError:
        imports = []
    for imp in sorted(
            [i for i in imports if isinstance(i, dict)],
            key=lambda i: _norm_title(i.get("title"))):
        key = _norm_title(imp.get("title"))
        if key and key not in import_lookup:
            import_lookup[key] = imp

    entries: List[str] = []
    used_keys: set = set()
    for doc, title in docs:
        meta: Dict = {}
        try:
            raw = (paper_metas or {}).get(getattr(doc, "id", None))
            if isinstance(raw, dict):
                meta = dict(raw)
        except Exception:
            meta = {}
        if not meta:
            imp = import_lookup.get(_norm_title(title))
            if imp:
                meta = dict(imp)
        if not isinstance(meta.get("title"), str) or not meta.get("title"):
            meta["title"] = title
        try:
            entry = to_bibtex(meta, used_keys)
        except Exception:
            entry = to_bibtex({"title": title}, used_keys)
        entries.append(entry)
        m = re.search(r"@\w+\{([^,\s]+)", entry)
        if m:
            used_keys.add(m.group(1))
    return "\n\n".join(entries)


def generate_review(docs: List[Any],
                    paper_metas: Optional[Dict[int, dict]] = None,
                    gemini_polish: Optional[Callable[[str], str]] = None,
                    paper_imports: Optional[List[dict]] = None) -> Dict:
    """Build the full literature-review dict for a set of StudyDoc rows.

    ``docs`` are duck-typed StudyDoc objects (``.id``, ``.title``,
    ``.data["chunks"]``). ``paper_metas`` maps doc id -> citation metadata
    dict for the BibTeX section. ``paper_imports`` is a list of PaperImport
    metadata dicts (title/authors/year/venue/doi/...) matched to papers by
    normalized title, best-effort. ``gemini_polish`` is an optional
    ``callable(text) -> str`` used ONLY to rephrase theme synthesis
    paragraphs — never to add claims; any exception falls back to the
    extractive synthesis silently.

    Docs are processed in ``(title, id)`` order for determinism. Returns the
    ``LitReview.data`` contract documented at the top of this module, or the
    honest ``{"error": ...}`` shape when fewer than two docs carry
    extractable text.

    Never raises on bad input.
    """
    try:
        doc_list = list(docs) if docs is not None else []
    except TypeError:
        return _empty_error("No documents were provided for the review.")
    if len(doc_list) < 2:
        return _empty_error(
            "A literature review needs at least 2 papers; "
            "%d provided." % len(doc_list))

    # (doc, title) pairs with extractable chunks, deterministic order.
    usable: List[Tuple[Any, str, List[Dict]]] = []
    excluded_titles: List[str] = []
    for doc in doc_list:
        try:
            title = getattr(doc, "title", None)
            title = title if isinstance(title, str) and title.strip() \
                else "Untitled paper"
            chunks = _doc_chunks(doc)
            with_text = [c for c in chunks
                         if isinstance(c.get("text"), str)
                         and c.get("text").strip()]
            if with_text:
                usable.append((doc, title, with_text))
            else:
                excluded_titles.append(title)
        except Exception:
            continue
    if len(usable) < 2:
        return _empty_error(
            "Only %d of %d papers contain extractable text; a literature "
            "review needs at least 2." % (len(usable), len(doc_list)))

    usable.sort(key=lambda u: (u[1].lower(),
                               getattr(u[0], "id", None) or 0))

    # Enriched chunk list shared by every stage.
    all_chunks: List[Dict] = []
    per_doc_chunks: Dict[int, List[Dict]] = {}
    for pos, (doc, title, chunks) in enumerate(usable):
        doc_id = getattr(doc, "id", None)
        enriched = []
        for c in chunks:
            nc = _norm_chunk(c)
            nc["doc_id"] = doc_id
            nc["doc_title"] = title
            enriched.append(nc)
            all_chunks.append(nc)
        per_doc_chunks[pos] = enriched

    try:
        # ---- per-paper extractive summaries (top 5 sentences per doc) ----
        per_paper = []
        for pos, (doc, title, _chunks) in enumerate(usable):
            top = score_sentences(per_doc_chunks[pos], top_n=5)
            parts = []
            citations = []
            for s in top:
                parts.append("%s %s" % (s["sentence"],
                                        _cite_marker(title, s["page"])))
                citations.append(_citation(title, s["page"],
                                           s["chunk_index"], s["sentence"]))
            per_paper.append({
                "doc_id": getattr(doc, "id", None),
                "title": title,
                "summary": " ".join(parts),
                "citations": citations,
            })

        # ---- themes + per-theme synthesis ----
        raw_themes = cluster_themes(all_chunks)
        scored_all = _score_all(all_chunks)
        themes = []
        for th in raw_themes:
            member_chunk_idx = {m["chunk_index"] for m in th["members"]}
            papers = sorted({m["doc_title"] for m in th["members"]})
            synth_parts = []
            synth_cites = []
            for paper in papers:
                paper_sents = [
                    s for s in scored_all
                    if s["doc_title"] == paper
                    and s["chunk_index"] in member_chunk_idx
                ][:2]
                for s in paper_sents:
                    synth_parts.append("%s %s" % (
                        s["sentence"], _cite_marker(paper, s["page"])))
                    synth_cites.append(_citation(
                        paper, s["page"], s["chunk_index"], s["sentence"]))
            synthesis = " ".join(synth_parts)
            if callable(gemini_polish) and synthesis:
                try:
                    polished = gemini_polish(synthesis)
                    if isinstance(polished, str) and polished.strip():
                        synthesis = polished
                except Exception:
                    pass  # fall back to the extractive synthesis silently
            themes.append({
                "name": th["name"],
                "terms": th["terms"],
                "papers": papers,
                "synthesis": synthesis,
                "citations": synth_cites,
            })

        # ---- claims table (grouped by normalized claim text) ----
        raw_claims = extract_claims(all_chunks)
        grouped: Dict[str, Dict] = {}
        for cl in raw_claims:
            key = _normalize_claim(cl["claim"])
            if key not in grouped:
                grouped[key] = {"claim": cl["claim"], "papers": [],
                                "citations": [], "_seen": set()}
            g = grouped[key]
            if cl["doc_title"] not in g["_seen"]:
                g["_seen"].add(cl["doc_title"])
                g["papers"].append(cl["doc_title"])
            g["citations"].append(_citation(
                cl["doc_title"], cl["page"], cl["chunk_index"], cl["claim"]))
        claims_table = []
        for key in sorted(grouped,
                          key=lambda k: (-len(grouped[k]["papers"]), k)):
            g = grouped[key]
            g["papers"].sort()
            g["citations"].sort(key=lambda c: (c["doc"], c["chunk"]))
            del g["_seen"]
            claims_table.append(g)

        # ---- coverage gaps (honest single-paper-coverage note) ----
        gap_notes = []
        for th in themes:
            if len(th["papers"]) == 1:
                gap_notes.append(
                    "Only '%s' discusses %s — consider adding sources that "
                    "address %s to strengthen this part of the review."
                    % (th["papers"][0], th["name"], th["name"]))
        for title in sorted(set(excluded_titles)):
            gap_notes.append(
                "'%s' contained no extractable text and was excluded from "
                "the review." % title)
        coverage_gaps = "\n".join(gap_notes) if gap_notes else (
            "Every identified theme is covered by at least two papers — "
            "no single-paper coverage gaps detected.")

        bibtex = _build_bibtex([(d, t) for d, t, _ in usable],
                                paper_metas, paper_imports)

        return {"per_paper": per_paper, "themes": themes,
                "claims_table": claims_table,
                "coverage_gaps": coverage_gaps, "bibtex": bibtex}
    except Exception as exc:  # absolute last resort: never raise
        return _empty_error(
            "Could not build the review from these documents (%s)."
            % type(exc).__name__)


# ---------------------------------------------------------------------------
# Export: Markdown and HTML
# ---------------------------------------------------------------------------

def _safe_review(review: Any) -> Dict:
    if not isinstance(review, dict):
        return _empty_error("No review data.")
    return review


def review_to_markdown(review: Dict) -> str:
    """Render a review dict as Markdown. Never raises."""
    try:
        r = _safe_review(review)
        lines = ["# Literature Review", ""]
        if r.get("error"):
            lines.append("*Could not generate a review: %s*" % r["error"])
            return "\n".join(lines) + "\n"

        lines.append("## Per-paper summaries")
        lines.append("")
        for p in r.get("per_paper") or []:
            title = p.get("title") or "Untitled paper"
            lines.append("### %s" % title)
            lines.append("")
            lines.append(p.get("summary") or "_No summary._")
            lines.append("")

        lines.append("## Themes")
        lines.append("")
        for th in r.get("themes") or []:
            lines.append("### %s" % (th.get("name") or "Untitled theme"))
            lines.append("")
            papers = th.get("papers") or []
            if papers:
                lines.append("_Papers:_ %s" % "; ".join(papers))
                lines.append("")
            lines.append(th.get("synthesis") or "_No synthesis._")
            lines.append("")

        lines.append("## Claims table")
        lines.append("")
        claims = r.get("claims_table") or []
        if claims:
            lines.append("| Claim | Papers |")
            lines.append("| --- | --- |")
            for c in claims:
                claim = (c.get("claim") or "").replace("|", "\\|")
                papers = "; ".join(c.get("papers") or [])
                lines.append("| %s | %s |" % (claim, papers))
        else:
            lines.append("_No claims extracted._")
        lines.append("")

        lines.append("## Coverage gaps")
        lines.append("")
        lines.append(r.get("coverage_gaps") or "_None reported._")
        lines.append("")

        lines.append("## BibTeX")
        lines.append("")
        lines.append("```bibtex")
        lines.append(r.get("bibtex") or "")
        lines.append("```")
        lines.append("")
        return "\n".join(lines)
    except Exception:
        return "# Literature Review\n\n*Could not render this review.*\n"


def review_to_html(review: Dict) -> str:
    """Render a review dict as an HTML fragment.

    Every user/doc-supplied string is passed through ``html.escape`` —
    doc text can never inject markup. Never raises.
    """
    try:
        r = _safe_review(review)
        e = html.escape
        parts = ['<div class="lit-review">', "<h1>Literature Review</h1>"]
        if r.get("error"):
            parts.append("<p><em>Could not generate a review: %s</em></p>"
                         % e(str(r["error"]), quote=True))
            parts.append("</div>")
            return "\n".join(parts)

        parts.append("<h2>Per-paper summaries</h2>")
        for p in r.get("per_paper") or []:
            title = p.get("title") or "Untitled paper"
            parts.append("<h3>%s</h3>" % e(str(title), quote=True))
            parts.append("<p>%s</p>"
                         % e(str(p.get("summary") or ""), quote=True))

        parts.append("<h2>Themes</h2>")
        for th in r.get("themes") or []:
            parts.append("<h3>%s</h3>"
                         % e(str(th.get("name") or ""), quote=True))
            papers = th.get("papers") or []
            if papers:
                parts.append("<p><em>Papers:</em> %s</p>"
                             % e("; ".join(str(x) for x in papers),
                                  quote=True))
            parts.append("<p>%s</p>"
                         % e(str(th.get("synthesis") or ""), quote=True))

        parts.append("<h2>Claims table</h2>")
        claims = r.get("claims_table") or []
        if claims:
            parts.append('<table><thead><tr><th>Claim</th><th>Papers</th>'
                         "</tr></thead><tbody>")
            for c in claims:
                parts.append("<tr><td>%s</td><td>%s</td></tr>" % (
                    e(str(c.get("claim") or ""), quote=True),
                    e("; ".join(str(x) for x in (c.get("papers") or [])),
                      quote=True)))
            parts.append("</tbody></table>")
        else:
            parts.append("<p><em>No claims extracted.</em></p>")

        parts.append("<h2>Coverage gaps</h2>")
        parts.append("<p>%s</p>"
                     % e(str(r.get("coverage_gaps") or ""), quote=True))

        parts.append("<h2>BibTeX</h2>")
        parts.append("<pre>%s</pre>"
                     % e(str(r.get("bibtex") or ""), quote=True))
        parts.append("</div>")
        return "\n".join(parts)
    except Exception:
        return ("<div class=\"lit-review\"><h1>Literature Review</h1>"
                "<p><em>Could not render this review.</em></p></div>")
