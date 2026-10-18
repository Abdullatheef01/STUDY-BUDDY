"""Research-gap finder (Wave 4, #23) — pure logic for the study library.

Framework-free on purpose (no Flask imports), mirroring ``pdf_qa.py``: the
route layer in ``unified_app.py`` feeds it :class:`StudyDoc` /
:class:`PaperImport` rows (or duck-typed fakes in tests) and stores the
result dict as ``GapReport.data``.

Everything here is:

- **Deterministic** — same inputs always produce the same outputs. All
  ordering is by explicit sort keys (never set/dict iteration order), and
  ties break on ``(doc_id, chunk index)``.
- **Honest** — every gap carries verbatim evidence excerpts: each
  ``excerpt`` is a substring of the real chunk text it cites, so citation
  accuracy is verifiable with ``excerpt in chunk_text``. Suggested
  questions are template-based and never invent facts. When the
  collection is too thin to analyze, the report says so explicitly.
- **Defensive** — every public function tolerates ``None``, malformed
  entries, and empty inputs; none of them ever raises, and none of them
  touches the network (``suggest_next_papers`` reads only already-cached
  citation graphs).

``GapReport.data`` contract (this module owns the shape)::

    {
      "gaps": [
        {
          "title": str,                       # human-readable gap headline
          "type": "underexplored" | "conflict" | "single-paper",
          "evidence": [                       # >= 1 item, always
            {"doc": str, "page": int, "chunk": int,
             "excerpt": str}                   # verbatim substring of the chunk
          ],
          "suggested_questions": [str, ...],  # template-based, honest
        },
        ...
      ],
      "next_papers": [
        {"title": str, "year": int | None, "reason": str},
        ...
      ],
      "note": str,   # PRESENT ONLY when the collection was too thin to
                     # analyze; then "gaps" and "next_papers" are both [].
    }

Gap ranking: ``conflict`` first, then ``underexplored``, then
``single-paper`` (alphabetical by title within each type).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from studybuddy.pdf_qa import _excerpt, _tokenize, retrieve

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

#: A term must reach this many chunk-occurrences (across >=3 chunks, 1 doc)
#: to count as an "underexplored" topic candidate.
UNDEREXPLORED_MIN_CHUNK_OCCURRENCES = 3

#: Total-mention threshold for the "concentrated in few chunks" rule.
CONCENTRATED_MIN_COUNT = 6

#: Max chunks a concentrated term may be spread over.
CONCENTRATED_MAX_CHUNKS = 2

#: A single-paper topic needs at least this many mentions in its one paper.
SINGLE_PAPER_MIN_COUNT = 2

#: Bigrams seen at least this often across the collection are indexed.
BIGRAM_MIN_COUNT = 3

#: Contrast markers that open a "however ..." sentence (case-insensitive).
CONTRAST_MARKERS = (
    r"\bhowever\b",
    r"\bin contrast\b",
    r"\bcontradicts?\b",
    r"\bcontradictory\b",
    r"\bunlike\b",
    r"\bwhereas\b",
    r"\bon the other hand\b",
    r"\bnevertheless\b",
)
_CONTRAST_RE = re.compile("|".join(CONTRAST_MARKERS), re.IGNORECASE)

#: Max gaps emitted per type (keeps reports readable; ordering is stable).
_MAX_GAPS_PER_TYPE = 15

#: Minimum score for a cross-paper sentence to count as a conflict pairing.
_CONFLICT_MIN_SHARED_TOKENS = 1

#: ~120-word stoplist for term indexing (pdf_qa's ~40 plus academic filler).
_STOPWORDS_EXTRA = frozenset(
    """
    a an the and or but if then else when at by for with about into through
    during before after above below to from up down in out on off over under
    again further once here there all any both each few more most other some
    such no nor not only own same so than too very can will just should now
    is are was were be been being have has had having do does did doing would
    could ought i me my we our you your he him his she her it its they them
    their this that these those am of as
    study studies paper papers research result results method methods model
    models data analysis analyses approach approaches propose proposes proposed
    using used based system systems figure figures table tables section sections
    chapter chapters abstract introduction background conclusion conclusions
    reference references et al also within without between among per via versus
    due may one two three first second third new novel related show shows shown
    found find use uses including include includes often many much well even
    still therefore thus hence since across because while where which what whom
    whose may might must shall although though despite introduction experimental
    experiments experiment evaluation evaluate evaluated compared comparison
    performance accuracy training trained test tests testing dataset datasets
    example examples problem problems task tasks solution solutions improve
    improved improvement increase increased state art key main primary different
    various several numerous widely commonly typically generally especially
    particularly mainly largely highly less least greater given make made makes
    """.split()
)

#: Minimum token length for an indexed term.
_TERM_MIN_LEN = 4

#: Simple sentence splitter (keeps trailing punctuation).
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|\S[^.!?]*$")

#: Word token pattern (must match pdf_qa._TOKEN_RE's alphabet).
_WORD_RE = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _normalize_entries(chunks_with_doc: Any) -> list[dict]:
    """Coerce the heterogeneous ``chunks_with_doc`` input into clean entries.

    Each entry: ``{"doc_id", "doc", "page", "chunk", "text"}``. Malformed
    entries (non-dict, missing/empty text, missing doc_id) are dropped.
    Never raises.
    """
    if not isinstance(chunks_with_doc, (list, tuple)):
        return []
    entries: list[dict] = []
    for item in chunks_with_doc:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        doc_id = item.get("doc_id")
        if doc_id is None:
            continue
        if not isinstance(doc_id, (str, int, float, bool, tuple)):
            doc_id = str(doc_id)  # keep set()/dict usage hashable
        doc = item.get("doc")
        entries.append(
            {
                "doc_id": doc_id,
                "doc": doc if isinstance(doc, str) and doc.strip() else "Untitled",
                "page": _safe_int(item.get("page"), 1),
                "chunk": _safe_int(item.get("index", item.get("chunk")), 0),
                "text": text,
            }
        )
    return entries


def _terms(text: str) -> list[str]:
    """Meaningful unigram terms: pdf_qa tokenization + length/stopword rules.

    Keeps tokenization consistent with ``pdf_qa._tokenize`` (same alphabet,
    same base stopwords) while enforcing the gap-finder's own bar: length
    >= 4, no pure numbers, and the extended ~120-word stoplist.
    """
    if not isinstance(text, str):
        return []
    out: list[str] = []
    for tok in _tokenize(text):
        if len(tok) < _TERM_MIN_LEN:
            continue
        if tok.isdigit():
            continue
        if tok in _STOPWORDS_EXTRA:
            continue
        out.append(tok)
    return out


def _bigrams(tokens: list[str]) -> list[str]:
    return ["%s %s" % (a, b) for a, b in zip(tokens, tokens[1:], strict=False)]


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.findall(text or "") if s.strip()]


def _sentence_with_term(sentence: str, term: str) -> bool:
    return term in [t for t in _terms(sentence)] or term in [
        b for b in _bigrams(_terms(sentence))
    ]


def _sort_key_entry(entry: dict) -> tuple[str, int]:
    return (str(entry.get("doc_id")), _safe_int(entry.get("chunk")))


def _entry_citation(entry: dict) -> dict:
    return {
        "doc": entry["doc"],
        "page": _safe_int(entry.get("page"), 1),
        "chunk": _safe_int(entry.get("chunk"), 0),
        "excerpt": _excerpt(entry.get("text", "")),
    }


def _title_norm(title: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _safe_str(title).lower())


def _titles_match(a: Any, b: Any) -> bool:
    """Loose title comparison (mirrors arxiv_import's sanity check)."""
    na, nb = _title_norm(a), _title_norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    longer, shorter = (na, nb) if len(na) >= len(nb) else (nb, na)
    return len(shorter) >= 20 and shorter in longer


# ---------------------------------------------------------------------------
# 1. Term statistics
# ---------------------------------------------------------------------------

def term_stats(chunks_with_doc: Any) -> dict[str, dict]:
    """Index meaningful terms (and frequent bigrams) over the collection.

    Returns ``{term: {"docs": set(doc_id), "count": int, "chunks": set}}``
    where ``count`` is the total mention count and ``chunks`` holds
    ``(doc_id, chunk)`` pairs containing the term. Unigrams need length >= 4,
    must not be pure numbers, and must survive the ~120-word stoplist;
    bigrams are additionally indexed when seen >= :data:`BIGRAM_MIN_COUNT`
    times. Never raises; bad input yields ``{}``.
    """
    entries = _normalize_entries(chunks_with_doc)
    per_entry_terms: list[tuple[dict, list[str]]] = []
    bigram_counter: Counter = Counter()
    for entry in entries:
        toks = _terms(entry["text"])
        bigr = _bigrams(toks)
        per_entry_terms.append((entry, toks + bigr))
        bigram_counter.update(bigr)

    stats: dict[str, dict] = {}
    for entry, terms in per_entry_terms:
        for term in terms:
            if " " in term and bigram_counter[term] < BIGRAM_MIN_COUNT:
                continue  # rare bigrams are noise, not topics
            rec = stats.get(term)
            if rec is None:
                rec = stats[term] = {
                    "docs": set(),
                    "count": 0,
                    "chunks": set(),
                }
            rec["docs"].add(entry["doc_id"])
            rec["count"] += 1
            rec["chunks"].add((entry["doc_id"], entry["chunk"]))
    return stats


# ---------------------------------------------------------------------------
# 2. Underexplored topics
# ---------------------------------------------------------------------------

def _underexplored_qualifies(rec: dict, min_docs: int) -> bool:
    """Shared predicate: deep-but-narrow term per the underexplored rules."""
    n_docs = len(rec["docs"])
    n_chunks = len(rec["chunks"])
    if n_docs >= min_docs:
        return False
    return (
        n_chunks >= UNDEREXPLORED_MIN_CHUNK_OCCURRENCES
        or (
            rec["count"] >= CONCENTRATED_MIN_COUNT
            and n_chunks <= CONCENTRATED_MAX_CHUNKS
        )
    )


def _term_hits(entries: list[dict], term: str) -> list[tuple[dict, int]]:
    """(entry, in-chunk mention count) for every entry containing ``term``."""
    hits: list[tuple[dict, int]] = []
    for entry in entries:
        toks = _terms(entry["text"])
        hay = toks + _bigrams(toks)
        n = hay.count(term)
        if n:
            hits.append((entry, n))
    # Strongest evidence first; deterministic tie-break.
    hits.sort(key=lambda h: (-h[1], _sort_key_entry(h[0])))
    return hits


def _term_sentence(term: str, entry: dict) -> str:
    """First sentence of the entry that actually contains the term."""
    for sent in _split_sentences(entry["text"]):
        if _sentence_with_term(sent, term):
            return sent[:220].rstrip()
    return ""


def _underexplored_questions(term: str, only_doc: str, sentence: str) -> list[str]:
    questions = [
        "Only one paper in your collection discusses '%s'. What aspects of "
        "'%s' remain unexplored?" % (term, term),
        "How does '%s' behave under conditions not covered in the available "
        "evidence?" % term,
        "What would a comparative study of '%s' against alternative "
        "approaches reveal?" % term,
    ]
    if sentence:
        questions.append(
            'The collection notes: "%s" — what further investigation of '
            "'%s' does this suggest?" % (sentence, term)
        )
    return questions[:4]


def find_underexplored(chunks_with_doc: Any, min_docs: int = 2) -> list[dict]:
    """Find topics discussed deeply but narrowly.

    A term qualifies when it appears in >= 3 chunk-occurrences but in fewer
    than ``min_docs`` documents (default: exactly one document), OR when it
    has a high total count (>= 6) concentrated in at most 2 chunks. Each
    gap cites the up to 3 strongest evidence chunks and carries honest,
    template-based suggested questions. Never raises; bad input yields
    ``[]``.
    """
    try:
        min_docs = max(1, int(min_docs))
    except (TypeError, ValueError):
        min_docs = 2
    entries = _normalize_entries(chunks_with_doc)
    if not entries:
        return []

    stats = term_stats(entries)
    gaps: list[dict] = []
    for term in sorted(stats):
        rec = stats[term]
        if not _underexplored_qualifies(rec, min_docs):
            continue
        hits = _term_hits(entries, term)
        if not hits:
            continue
        evidence = [_entry_citation(e) for e, _ in hits[:3]]
        only_doc = hits[0][0]["doc"]
        sentence = _term_sentence(term, hits[0][0])
        gaps.append(
            {
                "title": "Underexplored: '%s' — %d mentions across %d passage(s) "
                "in 1 of %d paper(s)" % (term, rec["count"], len(rec["chunks"]),
                                          len({e["doc_id"] for e in entries})),
                "type": "underexplored",
                "evidence": evidence,
                "suggested_questions": _underexplored_questions(
                    term, only_doc, sentence
                ),
            }
        )
        if len(gaps) >= _MAX_GAPS_PER_TYPE:
            break
    return gaps


# ---------------------------------------------------------------------------
# 3. Conflicts
# ---------------------------------------------------------------------------

def _best_sentence_overlap(text: str, query_tokens: set[str]) -> tuple[str, int]:
    """Sentence in ``text`` with the most query-token overlap."""
    best, best_n = "", 0
    for sent in _split_sentences(text):
        toks = {t for t in _terms(sent) if len(t) >= _TERM_MIN_LEN}
        n = len(toks.intersection(query_tokens))
        if n > best_n:
            best, best_n = sent, n
    return best, best_n


def _contrast_sentences(entry: dict) -> list[str]:
    return [s for s in _split_sentences(entry["text"]) if _CONTRAST_RE.search(s)]


def find_conflicts(chunks_with_doc: Any) -> list[dict]:
    """Detect cross-paper disagreements via contrast markers.

    A sentence containing a contrast marker ("however", "in contrast",
    "contradicts", "unlike", "whereas", "on the other hand",
    "nevertheless") in doc A is paired with a topically overlapping
    sentence from a *different* doc B — found with ``pdf_qa.retrieve`` over
    the other documents' chunks and kept only when the two sentences share
    at least one substantive term. Each conflict gap cites BOTH sides with
    verbatim excerpts. Never raises; bad input or single-doc input yields
    ``[]``.
    """
    entries = _normalize_entries(chunks_with_doc)
    if len({e["doc_id"] for e in entries}) < 2:
        return []

    # Chunk dicts shaped for retrieve(); the original entry rides along.
    chunk_dicts: list[dict] = []
    for entry in entries:
        chunk_dicts.append(
            {
                "text": entry["text"],
                "index": entry["chunk"],
                "page": entry["page"],
                "doc_id": entry["doc_id"],
                "entry": entry,
            }
        )

    gaps: list[dict] = []
    seen_topics: set[str] = set()
    for entry in sorted(entries, key=_sort_key_entry):
        for sent in _contrast_sentences(entry):
            query_tokens = {t for t in _terms(sent) if len(t) >= _TERM_MIN_LEN}
            if not query_tokens:
                continue
            others = [c for c in chunk_dicts if c["doc_id"] != entry["doc_id"]]
            if not others:
                continue
            try:
                results = retrieve(others, sent, top_k=5)
            except Exception:
                continue
            for res in results:
                other_entry = res.get("entry")
                if not isinstance(other_entry, dict):
                    continue
                other_sent, shared = _best_sentence_overlap(
                    other_entry["text"], query_tokens
                )
                if not other_sent or shared < _CONFLICT_MIN_SHARED_TOKENS:
                    continue
                topic = sorted(
                    {t for t in _terms(other_sent) if len(t) >= _TERM_MIN_LEN}
                    .intersection(query_tokens)
                )
                topic_key = (topic[0] if topic else "", str(entry["doc_id"]),
                             str(other_entry["doc_id"]))
                if topic_key in seen_topics:
                    continue
                seen_topics.add(topic_key)
                topic_word = topic[0] if topic else "these findings"
                contrast_excerpt = sent[:280].rstrip()
                other_excerpt = other_sent[:280].rstrip()
                gaps.append(
                    {
                        "title": "Conflicting findings on '%s'" % topic_word,
                        "type": "conflict",
                        "evidence": [
                            {
                                "doc": other_entry["doc"],
                                "page": _safe_int(other_entry.get("page"), 1),
                                "chunk": _safe_int(other_entry.get("chunk"), 0),
                                "excerpt": other_excerpt,
                            },
                            {
                                "doc": entry["doc"],
                                "page": _safe_int(entry.get("page"), 1),
                                "chunk": _safe_int(entry.get("chunk"), 0),
                                "excerpt": contrast_excerpt,
                            },
                        ],
                        "suggested_questions": [
                            "Which claim about '%s' has stronger support in "
                            "the evidence presented?" % topic_word,
                            "Under what conditions might both statements "
                            "about '%s' be true?" % topic_word,
                            "What additional evidence would resolve this "
                            "disagreement?",
                        ],
                    }
                )
                break  # one pairing per contrast sentence is enough
        if len(gaps) >= _MAX_GAPS_PER_TYPE:
            break
    return gaps


# ---------------------------------------------------------------------------
# 4. Single-paper topics
# ---------------------------------------------------------------------------

def find_single_paper_topics(chunks_with_doc: Any) -> list[dict]:
    """Find substantive topics covered by exactly one paper.

    A term with >= :data:`SINGLE_PAPER_MIN_COUNT` mentions that appears in a
    single document is a topic no other paper in the collection engages
    with. Each gap cites the up to 3 strongest evidence chunks and carries
    comparative suggested questions. Never raises; bad input yields ``[]``.
    """
    entries = _normalize_entries(chunks_with_doc)
    if len({e["doc_id"] for e in entries}) < 2:
        return []

    stats = term_stats(entries)
    gaps: list[dict] = []
    for term in sorted(stats):
        rec = stats[term]
        if len(rec["docs"]) != 1 or rec["count"] < SINGLE_PAPER_MIN_COUNT:
            continue
        if _underexplored_qualifies(rec, 2):
            continue  # already reported as underexplored — avoid duplicates
        hits = _term_hits(entries, term)
        if not hits:
            continue
        evidence = [_entry_citation(e) for e, _ in hits[:3]]
        only_doc = hits[0][0]["doc"]
        gaps.append(
            {
                "title": "'%s' — covered only by '%s'" % (term, only_doc),
                "type": "single-paper",
                "evidence": evidence,
                "suggested_questions": [
                    "'%s' appears only in '%s'. How would its claims hold up "
                    "against the methods in your other papers?"
                    % (term, only_doc),
                    "What head-to-head comparison would validate '%s' "
                    "beyond a single source?" % term,
                    "Which findings from your other papers agree with or "
                    "challenge the discussion of '%s'?" % term,
                ],
            }
        )
        if len(gaps) >= _MAX_GAPS_PER_TYPE:
            break
    return gaps


# ---------------------------------------------------------------------------
# 5. Next-paper suggestions (cache only — never touches the network)
# ---------------------------------------------------------------------------

def suggest_next_papers(
    user_id: Any,
    paper_imports: Any,
    library_titles: Any,
    max_n: int = 8,
) -> list[dict]:
    """Suggest follow-up papers from cached citation graphs.

    For each :class:`PaperImport`, reads ``.data["graph"]`` (the
    ``fetch_citation_graph`` shape: ``{"nodes": [...], "edges": [...]}``)
    and collects neighbor titles not already in the library (normalized
    title comparison). The reason reflects edge direction relative to the
    center node: ``{"from": center, "to": node}`` means the imported paper
    cites the neighbor → ``"Cited by '<imported title>'"``;
    ``{"from": node, "to": center}`` means the neighbor cites the imported
    paper → ``"References '<imported title>'"``. Neighbors with no edge
    info get ``"Appears in the citation graph of '<imported title>'"``.

    Never calls the network and never raises: imports without a cached
    graph contribute nothing, and no graphs at all means ``[]``.
    """
    try:
        max_n = int(max_n)
    except (TypeError, ValueError):
        max_n = 8
    if max_n <= 0:
        return []
    if not isinstance(paper_imports, (list, tuple)):
        return []
    lib_titles = (
        [library_titles]
        if isinstance(library_titles, str)
        else (list(library_titles) if isinstance(library_titles, (list, tuple)) else [])
    )

    suggestions: list[dict] = []
    seen: set[str] = set()

    for imp in paper_imports:
        if not isinstance(imp, dict) and not hasattr(imp, "title"):
            continue
        imp_uid = imp.get("user_id") if isinstance(imp, dict) else getattr(
            imp, "user_id", None)
        if user_id is not None and imp_uid is not None and imp_uid != user_id:
            continue
        imp_title = imp.get("title") if isinstance(imp, dict) else getattr(
            imp, "title", None)
        imp_title = imp_title if isinstance(imp_title, str) and imp_title.strip() \
            else "an imported paper"
        data = imp.get("data") if isinstance(imp, dict) else getattr(
            imp, "data", None)
        graph = data.get("graph") if isinstance(data, dict) else None
        if not isinstance(graph, dict):
            continue
        nodes = graph.get("nodes")
        edges = graph.get("edges")
        if not isinstance(nodes, list) or not nodes:
            continue
        if not isinstance(edges, list):
            edges = []

        center_id = None
        for node in nodes:
            if isinstance(node, dict) and node.get("is_center"):
                center_id = node.get("id")
                break

        direction: dict[Any, str] = {}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            frm, to = edge.get("from"), edge.get("to")
            if center_id is not None and frm == center_id and to != center_id:
                # Imported paper cites the neighbor.
                direction.setdefault(to, "Cited by '%s'" % imp_title)
            elif center_id is not None and to == center_id and frm != center_id:
                # Neighbor cites the imported paper.
                direction.setdefault(frm, "References '%s'" % imp_title)

        for node in nodes:
            if not isinstance(node, dict):
                continue
            if center_id is not None and node.get("id") == center_id:
                continue
            title = node.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            norm = _title_norm(title)
            if not norm or norm in seen:
                continue
            if _titles_match(title, imp_title):
                continue
            if any(_titles_match(title, lt) for lt in lib_titles):
                continue
            seen.add(norm)
            year = node.get("year")
            try:
                year = int(year) if year is not None else None
            except (TypeError, ValueError):
                year = None
            reason = direction.get(
                node.get("id"),
                "Appears in the citation graph of '%s'" % imp_title,
            )
            suggestions.append({"title": title, "year": year, "reason": reason})
            if len(suggestions) >= max_n:
                return suggestions
    return suggestions


# ---------------------------------------------------------------------------
# 6. Full report
# ---------------------------------------------------------------------------

_GAP_TYPE_RANK = {"conflict": 0, "underexplored": 1, "single-paper": 2}


def _gap_sort_key(gap: dict) -> tuple[int, str]:
    return (_GAP_TYPE_RANK.get(gap.get("type"), 99), str(gap.get("title", "")))


def generate_gap_report(
    docs: Any,
    paper_imports: Any = None,
) -> dict:
    """Build the full gap report dict (the ``GapReport.data`` contract).

    ``docs`` is a list of :class:`StudyDoc` rows (duck-typed: anything with
    ``.title``/``.id`` and ``.data["chunks"]`` works); ``paper_imports`` an
    optional list of :class:`PaperImport` rows for ``next_papers``.

    Gaps are ranked conflicts → underexplored → single-paper, and every gap
    is guaranteed >= 1 evidence item. When the collection is too thin to
    analyze (fewer than 2 documents with chunks, or no chunks at all), the
    honest empty state ``{"gaps": [], "next_papers": [], "note": ...}`` is
    returned. Never raises.
    """
    try:
        return _generate_gap_report(docs, paper_imports)
    except Exception:
        return {
            "gaps": [],
            "next_papers": [],
            "note": "The gap analysis could not run on this collection.",
        }


def _doc_chunks(doc: Any, doc_id: Any) -> tuple[str, list[dict]]:
    title = getattr(doc, "title", None)
    title = title if isinstance(title, str) and title.strip() else "Untitled"
    data = getattr(doc, "data", None)
    chunks = data.get("chunks") if isinstance(data, dict) else None
    if not isinstance(chunks, list):
        chunks = []
    return title, chunks


def _generate_gap_report(docs: Any, paper_imports: Any) -> dict:
    entries: list[dict] = []
    lib_titles: list[str] = []
    doc_list = list(docs) if isinstance(docs, (list, tuple)) else []
    for pos, doc in enumerate(doc_list):
        doc_id = getattr(doc, "id", None)
        if doc_id is None:
            doc_id = "doc-%d" % pos
        title, chunks = _doc_chunks(doc, doc_id)
        lib_titles.append(title)
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            entries.append(
                {
                    "doc_id": doc_id,
                    "doc": title,
                    "page": _safe_int(chunk.get("page"), 1),
                    "index": _safe_int(chunk.get("index"), 0),
                    "text": chunk.get("text"),
                }
            )

    docs_with_chunks = {e["doc_id"] for e in _normalize_entries(entries)}
    if len(docs_with_chunks) < 2:
        return {
            "gaps": [],
            "next_papers": [],
            "note": "Add at least 2 documents with readable text to your "
                    "study library to compare papers and find research gaps.",
        }

    conflicts = find_conflicts(entries)
    underexplored = find_underexplored(entries)
    single_paper = find_single_paper_topics(entries)
    gaps = [g for g in conflicts + underexplored + single_paper
            if isinstance(g, dict) and g.get("evidence")]
    gaps.sort(key=_gap_sort_key)

    user_id = getattr(doc_list[0], "user_id", None) if doc_list else None
    next_papers = suggest_next_papers(user_id, paper_imports or [], lib_titles)

    return {"gaps": gaps, "next_papers": next_papers}


# ================= Feature 22 Ultimate Enhancements =================
# 22.1 Trend cross-check | 22.2 Feasibility scorer | 22.3 Proposal export

import re as _re16


def _clean16(text):
    return _re16.sub(r"<[^>]*>", "", text or "")


def trend_cross_check(gap_text, trending_papers):
    """Is this gap already being filled? Check against trending papers.

    gap_text: the identified gap. trending_papers: list of {title, abstract?}.
    Returns {overlap: [...], verdict} — overlap lists papers already on it.
    """
    gap = _clean16(gap_text or "").strip().lower()
    if len(gap) < 10:
        raise ValueError("Gap description is too short to check.")
    if not isinstance(trending_papers, (list, tuple)):
        raise ValueError("trending_papers must be a list.")
    gap_terms = set(_re16.findall(r"[a-z]{4,}", gap))
    overlap = []
    for p in trending_papers:
        if not isinstance(p, dict):
            continue
        blob = (_clean16(p.get("title") or "") + " " +
                _clean16(p.get("abstract") or "")).lower()
        p_terms = set(_re16.findall(r"[a-z]{4,}", blob))
        if not p_terms:
            continue
        sim = len(gap_terms & p_terms) / len(gap_terms | p_terms)
        if sim >= 0.15:
            overlap.append({"title": _clean16(p.get("title") or "Untitled")[:100],
                            "similarity": round(sim, 2)})
    overlap.sort(key=lambda x: -x["similarity"])
    n = len(overlap)
    verdict = ("Hot zone — several recent papers touch this. Narrow your angle or move fast."
               if n >= 3 else
               "Some activity — read these first, then differentiate."
               if n >= 1 else
               "Clear field — no trending paper overlaps strongly. Good hunting ground.")
    return {"overlap": overlap[:8], "overlap_count": n, "verdict": verdict}


# Feasibility signals.
_FEAS_POSITIVE = [
    (r"\b(survey|benchmark|analysis|comparison|review)\b", 15, "Survey/benchmark work is very doable"),
    (r"\b(open (source|data)|public dataset|github)\b", 15, "Open data/code available"),
    (r"\b(small|toy|prototype|mvp)\b", 10, "Small scope"),
]
_FEAS_NEGATIVE = [
    (r"\b(large scale|massive|distributed cluster|tpu pod|million (dollar|gpu))\b", -20, "Needs heavy compute"),
    (r"\b(human (study|trial)|clinical|irb)\b", -20, "Needs human subjects approval"),
    (r"\b(proprietary|confidential|nda)\b", -15, "Needs restricted data access"),
    (r"\b(novel (architecture|hardware)|chip|asic)\b", -15, "Needs novel hardware"),
]


def feasibility_score(gap_text, skills=None):
    """Can a student actually do this in 3 months? Score 0-100.

    Returns {score, verdict, factors}.
    """
    gap = _clean16(gap_text or "").strip()
    if len(gap) < 10:
        raise ValueError("Gap description is too short to score.")
    skills = [str(s).lower() for s in (skills or []) if isinstance(s, str)]
    score = 55.0  # neutral start
    factors = []
    low = gap.lower()
    for pattern, pts, label in _FEAS_POSITIVE:
        if _re16.search(pattern, low):
            score += pts
            factors.append({"factor": label, "effect": f"+{pts}"})
    for pattern, pts, label in _FEAS_NEGATIVE:
        if _re16.search(pattern, low):
            score += pts
            factors.append({"factor": label, "effect": str(pts)})
    # Skill match: gap mentions skills the student has.
    if skills:
        hits = sum(1 for s in skills if s and s in low)
        if hits:
            bonus = min(15, hits * 5)
            score += bonus
            factors.append({"factor": f"Matches {hits} of your skills", "effect": f"+{bonus}"})
    score = max(0, min(100, round(score)))
    verdict = ("Highly feasible — start this month." if score >= 70 else
               "Feasible with scoping — narrow it down." if score >= 45 else
               "Risky for 3 months — needs resources you may not have.")
    return {"score": score, "verdict": verdict, "factors": factors,
            "tip": "Cut scope until the score crosses 70 — a finished small project beats an unfinished big one."}


def gap_to_proposal(gap_text, context=None):
    """Turn a gap into a research proposal outline.

    Returns {title, sections: [{heading, prompts}]}.
    """
    gap = _clean16(gap_text or "").strip()
    if len(gap) < 10:
        raise ValueError("Gap description is too short for a proposal.")
    context = _clean16(context or "").strip()[:500]
    # Draft a working title from the gap's key nouns.
    nouns = _re16.findall(r"[A-Z][a-z]{3,}|[a-z]{5,}", gap)
    seen = []
    for w in nouns:
        wl = w.lower()
        if wl not in seen and wl not in {"with", "from", "that", "this", "have", "more"}:
            seen.append(wl)
        if len(seen) >= 4:
            break
    title = "Towards " + " ".join(w.capitalize() for w in seen[:4]) if seen else "Research Proposal"
    sections = [
        ("Problem Statement", ["State the gap in 3 sentences", "Why does it matter? Who cares?"]),
        ("Related Work", ["3-5 closest papers", "What did each miss? (table format)"]),
        ("Research Questions", ["1 primary + 2 secondary questions", "Each must be answerable in 3 months"]),
        ("Methodology", ["Approach, datasets, baselines", "What will you build first? (MVP)"]),
        ("Evaluation", ["Metrics + baselines to beat", "Ablation plan"]),
        ("Timeline", ["Month 1: MVP", "Month 2: experiments", "Month 3: write-up"]),
        ("Risks", ["What could fail? What's plan B?"]),
    ]
    if context:
        sections.insert(1, ("Context", [context[:200]]))
    return {"title": title[:120],
            "sections": [{"heading": h, "prompts": ps} for h, ps in sections],
            "guidance": "Fill each section in 30 minutes. A rough proposal today beats a perfect one next month."}
