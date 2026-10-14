"""Source-grounded PDF Q&A (feature #21) — pure logic for the study library.

This module is intentionally framework-free (no Flask imports) so it can be
unit-tested in isolation and reused anywhere. Everything here is:

- **Deterministic** — same inputs always produce the same outputs. Retrieval
  breaks score ties by chunk index, never by set/dict iteration order.
- **Honest** — answers are extractive syntheses of retrieved passages only.
  Every factual claim carries a ``[doc, p.X]`` citation, and page numbers only
  ever come from the chunks that were actually retrieved. Citation excerpts
  are verbatim substrings of the real chunk text. No LLM, no invented facts,
  no invented page numbers, no hallucinated citations — when nothing relevant
  is found, the answer is exactly the abstention string below.
- **Defensive** — ``parse_pdf_pages`` never raises; scanned/image PDFs (no
  extractable text) yield empty page strings and flow into the honest
  abstention answer instead of crashing.

Retrieval is a hybrid of BM25-style keyword scoring and TF-IDF cosine
similarity (both implemented with the stdlib only — ``math``/``re``/
``collections``; no sklearn/numpy). Each retrieved chunk carries a ``debug``
dict explaining its score, so ranking decisions are auditable.

Public surface (exactly these five functions):

    validate_upload(file_storage) -> (ok, error)
    parse_pdf_pages(file_stream_or_path) -> list[str]
    chunk_pages(pages, chunk_chars=500, overlap=100) -> ChunkList[dict]
    retrieve(chunks, query, top_k=5) -> list[dict]
    answer_question(query, doc_title, chunks, top_k=5) -> dict
"""

from __future__ import annotations

import io
import math
import os
import re
import unicodedata
from collections import Counter
from typing import BinaryIO, Dict, List, Tuple, Union

import pypdf

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

#: Uploads larger than this are rejected by :func:`validate_upload`.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

#: Hard cap on chunks per document — protects memory on huge PDFs.
CHUNK_CAP = 2000

#: Minimum combined relevance score for a passage to count as "supporting".
RELEVANCE_THRESHOLD = 0.05

#: Maximum characters kept in a citation excerpt.
EXCERPT_MAX = 280

#: Honest abstention answer — returned verbatim when nothing relevant is found.
NO_RESULT_ANSWER = "I couldn't find this in your documents."

#: Blend weights for the hybrid score: 0.5 * BM25 + 0.5 * TF-IDF cosine.
HYBRID_BM25_WEIGHT = 0.5
HYBRID_TFIDF_WEIGHT = 0.5

#: ~40 common English stopwords stripped before scoring.
_STOPWORDS = frozenset(
    """
    a an the and or but if then else when at by for with about into through
    during before after above below to from up down in out on off over under
    again further once here there all any both each few more most other some
    such no nor not only own same so than too very can will just should now
    is are was were be been being have has had having do does did doing would
    could ought i me my we our you your he him his she her it its they them
    their this that these those am of as
    """.split()
)

#: Alphanumeric tokens on lowercased text.
_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: Sentence splitter (keeps the trailing punctuation with the sentence).
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|\S[^.!?]*$")

#: Sentence-boundary positions: punctuation followed by whitespace or end.
_SENT_END_RE = re.compile(r"[.!?](?=\s|$)")


# ---------------------------------------------------------------------------
# 1. Upload validation
# ---------------------------------------------------------------------------

def validate_upload(file_storage) -> Tuple[bool, str]:
    """Validate an uploaded file before any PDF parsing is attempted.

    Accepts any object with a ``filename`` attribute and either a ``stream``
    attribute or a file-like interface (the shape Flask/Werkzeug
    ``FileStorage`` provides, but duck-typed so tests can use fakes).

    Rules: must exist, must be named ``*.pdf`` (case-insensitive), must
    declare a PDF-ish MIME type when one is declared, must be non-empty, must
    not exceed :data:`MAX_UPLOAD_BYTES` (25 MB), and must start with the PDF
    magic bytes (``%PDF`` within the first 1024 bytes — extension alone is
    not trusted).

    The stream position is restored after the checks so downstream code can
    read the upload from the start. Never raises: every failure mode returns
    ``(False, <helpful message>)``.
    """
    if file_storage is None:
        return False, "No file was uploaded."

    filename = getattr(file_storage, "filename", None) or ""
    filename = os.path.basename(filename).strip()
    if not filename:
        return False, "No file was uploaded."
    if not filename.lower().endswith(".pdf"):
        return False, "Only PDF files are accepted."

    # MIME check (best-effort: only enforced when a type is actually declared).
    mimetype = (
        getattr(file_storage, "mimetype", None)
        or getattr(file_storage, "content_type", "")
        or ""
    )
    mimetype = str(mimetype).split(";")[0].strip().lower()
    if mimetype and "pdf" not in mimetype and mimetype != "application/octet-stream":
        return False, "Expected a PDF file (declared content type: '%s')." % mimetype

    stream = getattr(file_storage, "stream", None)
    if stream is None and hasattr(file_storage, "read"):
        stream = file_storage
    if stream is None:
        return False, "Could not read the uploaded file."

    try:
        try:
            pos = stream.tell()
        except (OSError, AttributeError, ValueError):
            pos = None
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
    except (OSError, AttributeError, ValueError):
        return False, "Could not read the uploaded file."

    if size is None or size <= 0:
        return False, "The file is empty."
    if size > MAX_UPLOAD_BYTES:
        return (
            False,
            "File exceeds the 25 MB limit (%s MB)." % round(size / (1024 * 1024), 1),
        )

    # Magic-byte check: %PDF must appear within the first 1024 bytes.
    try:
        stream.seek(0)
        header = stream.read(1024)
    except (OSError, AttributeError, ValueError):
        return False, "Could not read the uploaded file."
    finally:
        if pos is not None:
            try:
                stream.seek(pos)
            except (OSError, ValueError):
                pass
    if isinstance(header, str):  # pragma: no cover — uploads are binary
        header = header.encode("latin-1", "ignore")
    if not isinstance(header, (bytes, bytearray)) or b"%PDF" not in bytes(header):
        return False, "The file is not a valid PDF (missing %PDF header)."

    return True, ""


# ---------------------------------------------------------------------------
# 2. PDF parsing
# ---------------------------------------------------------------------------

def parse_pdf_pages(file_stream_or_path: Union[str, os.PathLike, BinaryIO, bytes]) -> List[str]:
    """Extract text per PDF page.

    Accepts a filesystem path, raw ``bytes``, or a binary file-like object
    (including Flask ``FileStorage``). Returns one string per page, so
    ``pages[i]`` is always the text of page ``i`` (0-based). Pages with no
    extractable text (scanned/image PDFs, blank pages) come back as ``""`` —
    they are skipped later by :func:`chunk_pages`, and a document with *no*
    text at all flows into the honest abstention answer instead of an error.

    Never raises: any failure (corrupt PDF, unreadable stream, encrypted
    file) yields ``[]``.
    """
    try:
        if isinstance(file_stream_or_path, (bytes, bytearray)):
            reader = pypdf.PdfReader(io.BytesIO(bytes(file_stream_or_path)))
        elif isinstance(file_stream_or_path, (str, os.PathLike)):
            reader = pypdf.PdfReader(str(file_stream_or_path))
        else:
            stream = file_stream_or_path
            try:
                stream.seek(0)
            except (OSError, AttributeError, ValueError):
                pass
            reader = pypdf.PdfReader(stream)

        pages: List[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                # One bad page must not kill the whole document.
                text = ""
            # Unicode-normalize so combining characters can't split tokens.
            pages.append(unicodedata.normalize("NFC", text).strip())
        return pages
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 3. Chunking (500-char overlapping windows, sentence-boundary cuts, headings)
# ---------------------------------------------------------------------------

class ChunkList(list):
    """A list of chunk dicts with a ``truncated`` flag.

    ``chunk_pages`` caps output at :data:`CHUNK_CAP` (2000) chunks for huge
    documents; when the cap bites, ``truncated`` is ``True`` so the UI can
    tell the user only the first 2000 chunks were indexed.
    """

    def __init__(self, *args, truncated: bool = False):
        super().__init__(*args)
        self.truncated = truncated


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_heading(line: str) -> Union[str, None]:
    """Best-effort section-heading detection. Returns the heading text or None.

    Recognizes, in order:
    - Markdown headings (``# Title``)
    - Numbered headings (``1. Introduction``, ``2.3 Methods``)
    - ALL-CAPS short lines (``RESULTS``, ``LITERATURE REVIEW``)
    - Short title-case lines ending in a colon (``Conclusion:``)
    """
    s = line.strip()
    if not s or len(s) > 80:
        return None

    m = re.match(r"^#{1,6}\s+(.+?)\s*$", s)
    if m and len(m.group(1)) >= 2:
        return m.group(1)

    m = re.match(r"^(\d+(?:\.\d+)*\.?)\s+([A-Z][^.!?]{1,70})$", s)
    if m:
        return s

    if s.endswith(":") and len(s) <= 60 and re.match(r"^[A-Z][^.!?]*:$", s):
        return s[:-1].strip() or None

    # ALL CAPS: at least 2 chars, mostly uppercase letters, no sentence end.
    if (
        2 <= len(s) <= 60
        and not s.endswith((".", "!", "?", ":", ";"))
        and re.search(r"[A-Z]", s)
        and not re.search(r"[a-z]", s)
    ):
        return s.title() if len(s) <= 40 else s

    return None


def _split_by_headings(raw_text: str) -> List[Tuple[str, str]]:
    """Split page text into (heading, text) segments at heading boundaries.

    The heading line itself stays at the start of its segment's text so its
    words remain searchable. Text before the first detected heading gets
    ``heading == ""``.
    """
    segments: List[Tuple[str, List[str]]] = []
    current_heading = ""
    current_lines: List[str] = []
    for line in raw_text.splitlines():
        heading = _is_heading(line)
        if heading is not None:
            if current_lines or current_heading:
                segments.append((current_heading, current_lines))
            current_heading = heading
            current_lines = [line.strip()]
        else:
            current_lines.append(line)
    if current_lines or current_heading:
        segments.append((current_heading, current_lines))
    return [(h, "\n".join(lines)) for h, lines in segments]


def _split_text(text: str, chunk_chars: int, overlap: int) -> List[str]:
    """Sentence-aware sliding-window split. Never returns empty strings.

    The window edge prefers a sentence boundary (``.``/``!``/``?``) so chunks
    rarely cut mid-sentence; it falls back to a word boundary when no
    sentence end fits inside the window.
    """
    text = _normalize_whitespace(text)
    n = len(text)
    out: List[str] = []
    start = 0
    while start < n:
        end = min(start + chunk_chars, n)
        if end < n:
            # Prefer cutting at a sentence boundary ...
            sent_cut = None
            for m in _SENT_END_RE.finditer(text, start, end):
                sent_cut = m.end()
            if sent_cut is not None and sent_cut > start + 20:
                end = sent_cut
            else:
                # ... otherwise fall back to a word boundary.
                cut = text.rfind(" ", start, end)
                if cut > start:
                    end = cut
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        nxt = end - overlap
        if nxt <= start:
            nxt = end  # overlap too large to advance — step to end instead
        if nxt <= start:
            break  # cannot advance; avoids an infinite loop
        start = nxt
    return out


def chunk_pages(
    pages: List[str],
    chunk_chars: int = 500,
    overlap: int = 100,
) -> ChunkList:
    """Split per-page text into overlapping, page-attributed chunks.

    Each chunk is ``{"page": 1-based, "index": global chunk idx,
    "heading": best-effort section heading ("" if none detected),
    "text": str}``. Empty/whitespace-only pages are skipped, and no chunk is
    ever an empty string. Chunks from page *p* always carry ``"page": p`` so
    citations can never point at a wrong page.

    Output is capped at :data:`CHUNK_CAP` (2000) chunks; the returned
    :class:`ChunkList` sets ``truncated=True`` when the cap was hit.

    Never raises: ``None`` or malformed input yields an empty
    :class:`ChunkList`; invalid ``chunk_chars``/``overlap`` values are
    coerced to safe minimums.
    """
    try:
        chunk_chars = int(chunk_chars)
    except (TypeError, ValueError):
        chunk_chars = 500
    try:
        overlap = int(overlap)
    except (TypeError, ValueError):
        overlap = 100
    chunk_chars = max(1, chunk_chars)
    overlap = max(0, min(overlap, chunk_chars - 1)) if chunk_chars > 1 else 0

    chunks: List[Dict] = []
    truncated = False
    index = 0
    for page_no, page_text in enumerate(pages or [], start=1):
        if not isinstance(page_text, str) or not page_text.strip():
            continue
        for heading, segment in _split_by_headings(page_text.strip()):
            for piece in _split_text(segment, chunk_chars, overlap):
                if len(chunks) >= CHUNK_CAP:
                    truncated = True
                    break
                chunks.append(
                    {"page": page_no, "index": index, "heading": heading, "text": piece}
                )
                index += 1
            if truncated:
                break
        if truncated:
            break
    return ChunkList(chunks, truncated=truncated)


# ---------------------------------------------------------------------------
# 4. Hybrid retrieval: BM25-ish keyword scoring + TF-IDF cosine (stdlib only)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric unigrams with stopwords removed."""
    if not isinstance(text, str):
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _smooth_idf(tokenized_docs: List[List[str]]) -> Dict[str, float]:
    """Smoothed IDF for TF-IDF: log((N+1)/(df+1)) + 1, always positive."""
    n = len(tokenized_docs)
    df = Counter()
    for tokens in tokenized_docs:
        df.update(set(tokens))
    return {tok: math.log((n + 1) / (freq + 1)) + 1.0 for tok, freq in df.items()}


def _bm25_idf(tokenized_docs: List[List[str]]) -> Dict[str, float]:
    """BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1), always non-negative."""
    n = len(tokenized_docs)
    df = Counter()
    for tokens in tokenized_docs:
        df.update(set(tokens))
    return {
        tok: math.log((n - freq + 0.5) / (freq + 0.5) + 1.0)
        for tok, freq in df.items()
    }


def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    """L2-normalized sparse TF-IDF vector as a token->weight dict."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    length = len(tokens)
    vec = {tok: (cnt / length) * idf.get(tok, 0.0) for tok, cnt in counts.items()}
    norm = math.sqrt(sum(w * w for w in vec.values()))
    if norm == 0.0:
        return {}
    return {tok: w / norm for tok, w in vec.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(tok, 0.0) for tok, w in a.items())


def _bm25_score(
    query_tokens: List[str],
    doc_tokens: List[str],
    avgdl: float,
    idf: Dict[str, float],
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    """BM25-ish keyword score (no external deps)."""
    if not doc_tokens or not query_tokens:
        return 0.0
    tf = Counter(doc_tokens)
    dl = len(doc_tokens)
    score = 0.0
    for tok in set(query_tokens):
        freq = tf.get(tok, 0)
        if freq == 0:
            continue
        idf_t = idf.get(tok, 0.0)
        denom = freq + k1 * (1 - b + b * dl / avgdl)
        score += idf_t * (freq * (k1 + 1)) / denom
    return score


def _minmax_normalize(values: List[float]) -> List[float]:
    """Scale to [0, 1]; all-equal input maps to all zeros (no signal)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.0] * len(values)
    span = hi - lo
    return [(v - lo) / span for v in values]


def retrieve(chunks: List[Dict], query: str, top_k: int = 5) -> List[Dict]:
    """Rank chunks with a hybrid BM25 + TF-IDF-cosine score.

    ``score`` is ``0.5 * norm(BM25) + 0.5 * norm(TF-IDF cosine)`` where each
    component is min-max normalized over the corpus, so the final score is in
    ``[0, 1]``. Deterministic: ties break on chunk ``index`` ascending.

    Empty/blank queries, queries with no indexable tokens, and empty corpora
    all return ``[]``. Only chunks with a positive score are returned (up to
    ``top_k``). When min-max normalization erases all signal (uniform corpus,
    e.g. a single chunk), ranking falls back to raw hybrid scores.

    Each result is a copy of the chunk dict plus:

    - ``"score"`` — the combined hybrid score (float)
    - ``"debug"`` — ``{"bm25": raw BM25, "tfidf_cosine": raw cosine,
      "bm25_norm": ..., "tfidf_norm": ..., "combined": ...,
      "matched_terms": [query terms found in the chunk]}`` explaining the
      ranking decision.

    Never raises: bad input (``None`` chunks, non-string query, ``None``
    entries) yields ``[]``.
    """
    if (
        not chunks
        or not isinstance(query, str)
        or not query.strip()
        or not isinstance(top_k, int)
        or top_k <= 0
    ):
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    corpus_tokens = [
        _tokenize(c.get("text", "") if isinstance(c, dict) else "") for c in chunks
    ]
    smooth_idf = _smooth_idf(corpus_tokens)
    bm25_idf = _bm25_idf(corpus_tokens)
    avgdl = sum(len(t) for t in corpus_tokens) / max(len(corpus_tokens), 1)

    query_vec = _tfidf_vector(query_tokens, smooth_idf)

    raw_bm25: List[float] = []
    raw_cosine: List[float] = []
    doc_vecs: List[Dict[str, float]] = []
    for tokens in corpus_tokens:
        raw_bm25.append(_bm25_score(query_tokens, tokens, avgdl, bm25_idf))
        vec = _tfidf_vector(tokens, smooth_idf)
        doc_vecs.append(vec)
        raw_cosine.append(_cosine(query_vec, vec) if query_vec else 0.0)

    norm_bm25 = _minmax_normalize(raw_bm25)
    norm_cosine = _minmax_normalize(raw_cosine)

    query_set = set(query_tokens)
    norm_signal = any(v > 0.0 for v in norm_bm25) or any(v > 0.0 for v in norm_cosine)
    scored = []
    for i, chunk in enumerate(chunks):
        if norm_signal:
            combined = (
                HYBRID_BM25_WEIGHT * norm_bm25[i]
                + HYBRID_TFIDF_WEIGHT * norm_cosine[i]
            )
        else:
            # Uniform corpus (e.g. a single chunk): min-max normalization maps
            # every score to 0.0, erasing the signal. Fall back to raw scores
            # so a lone matching chunk is still retrievable. Chunks with no
            # term overlap still score exactly 0.0 and stay excluded.
            combined = (
                HYBRID_BM25_WEIGHT * raw_bm25[i]
                + HYBRID_TFIDF_WEIGHT * raw_cosine[i]
            )
        if combined > 0.0:
            matched = sorted(query_set.intersection(corpus_tokens[i]))
            scored.append(
                (
                    combined,
                    {
                        "bm25": raw_bm25[i],
                        "tfidf_cosine": raw_cosine[i],
                        "bm25_norm": norm_bm25[i],
                        "tfidf_norm": norm_cosine[i],
                        "combined": combined,
                        "matched_terms": matched,
                    },
                    chunk,
                )
            )

    # Sort by combined score descending, then chunk index ascending — fully
    # deterministic.
    def _sort_key(item):
        chunk = item[2]
        idx = chunk.get("index", 0) if isinstance(chunk, dict) else 0
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            idx = 0
        return (-item[0], idx)

    scored.sort(key=_sort_key)

    results = []
    for combined, debug, chunk in scored[:top_k]:
        result = dict(chunk)
        result["score"] = float(combined)
        result["debug"] = {k: (float(v) if isinstance(v, float) else v)
                           for k, v in debug.items()}
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# 5. Extractive, citation-honest answering
# ---------------------------------------------------------------------------

def _best_sentence(text: str, query_tokens: List[str]) -> str:
    """Pick the sentence in ``text`` with the most query-token overlap."""
    sentences = [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]
    if not sentences:
        return _normalize_whitespace(text)[:200]
    query_set = set(query_tokens)
    best, best_overlap = sentences[0], -1
    for sent in sentences:
        overlap = len(query_set.intersection(_tokenize(sent)))
        if overlap > best_overlap:
            best, best_overlap = sent, overlap
    return best


def _excerpt(text: str, max_chars: int = EXCERPT_MAX) -> str:
    """Verbatim excerpt: a word-boundary prefix of the chunk text.

    Because the excerpt is a strict prefix (cut at a word boundary, no
    ellipsis appended), ``excerpt in chunk_text`` always holds — citation
    accuracy is verifiable by substring check.
    """
    text = _normalize_whitespace(text)
    if len(text) <= max_chars:
        return text
    cut = text.rfind(" ", 0, max_chars)
    if cut <= 0:
        cut = max_chars
    return text[:cut].rstrip()


def _citation(chunk: Dict, doc_title: str) -> Dict:
    return {
        "doc": doc_title,
        "page": int(chunk.get("page", 0)),
        "chunk": int(chunk.get("index", 0)),
        "excerpt": _excerpt(chunk.get("text", "")),
    }


def answer_question(
    query: str,
    doc_title: str,
    chunks: List[Dict],
    top_k: int = 5,
) -> Dict:
    """Answer ``query`` extractively from ``chunks``, with honest citations.

    The answer is a 2–4 sentence synthesis composed ONLY of key phrases quoted
    from the retrieved passages — every claim is immediately followed by a
    ``[doc, p.X]`` marker whose page number comes straight from the retrieved
    chunk. Nothing is invented: if no passage clears
    :data:`RELEVANCE_THRESHOLD`, or there are no chunks at all (e.g. a
    scanned PDF with no extractable text), the answer is exactly
    ``"I couldn't find this in your documents."`` with empty citations.

    Returns ``{"answer": str, "citations": [...], "passages": [...]}`` where
    ``passages`` mirrors ``citations`` (kept as a separate key for UI
    convenience — the expandable "supporting passages" panel).
    """
    retrieved = retrieve(chunks, query, top_k=top_k)
    if not retrieved or retrieved[0]["score"] < RELEVANCE_THRESHOLD:
        return {"answer": NO_RESULT_ANSWER, "citations": [], "passages": []}

    query_tokens = _tokenize(query)
    # Use up to 3 top passages so the synthesis stays focused and citable.
    selected = retrieved[:3]

    doc_label = doc_title if isinstance(doc_title, str) else ""

    claims: List[str] = []
    citations: List[Dict] = []
    for chunk in selected:
        sentence = _normalize_whitespace(_best_sentence(chunk.get("text", ""), query_tokens))
        if len(sentence) > 400:
            sentence = sentence[:397].rstrip() + "…"
        claims.append('"%s" [doc, p.%d]' % (sentence, int(chunk.get("page", 0))))
        citations.append(_citation(chunk, doc_label))

    intro = "Here is what the document says:"
    answer = intro + " " + " ".join(claims)
    return {"answer": answer, "citations": citations, "passages": list(citations)}
