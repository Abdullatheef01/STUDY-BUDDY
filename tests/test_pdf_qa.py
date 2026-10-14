"""Tests for pdf_qa.py — source-grounded PDF Q&A logic (feature #21).

Split per the zero-error protocol:
  - HAPPY-PATH tests: parsing, chunking, hybrid retrieval, honest answering.
  - ERROR-PATH tests: every logic function is exercised with invalid input
    and must return a clean failure value — no function may raise unhandled.

Routes are NOT tested here (they don't exist yet); this file covers the pure
logic module only.
"""
import io
import os
import tempfile

import pytest

from conftest import make_pdf_bytes
from studybuddy.pdf_qa import (
    CHUNK_CAP,
    NO_RESULT_ANSWER,
    ChunkList,
    answer_question,
    chunk_pages,
    parse_pdf_pages,
    retrieve,
    validate_upload,
)


# ---------------------------------------------------------------------------
# Helpers (test-only)
# ---------------------------------------------------------------------------

class FakeUpload:
    """Duck-typed stand-in for Werkzeug FileStorage."""

    def __init__(self, filename, stream, mimetype=None):
        self.filename = filename
        self.stream = stream
        self.mimetype = mimetype


class FakeBigStream:
    """Seekable stream that reports a huge size without allocating it."""

    def __init__(self, size):
        self._size = size
        self._pos = 0

    def tell(self):
        return self._pos

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self._pos = offset
        elif whence == os.SEEK_CUR:
            self._pos += offset
        elif whence == os.SEEK_END:
            self._pos = self._size + offset
        return self._pos

    def read(self, n=-1):
        return b"%PDF-1.4\n"


class BrokenStream:
    def tell(self):
        raise OSError("nope")

    def seek(self, *a, **k):
        raise OSError("nope")

    def read(self, *a, **k):
        raise OSError("nope")


def make_two_page_pdf_bytes(pages_lines):
    """Build a valid multi-page PDF; pages_lines[i] = lines for page i."""
    contents = []
    for lines in pages_lines:
        content = b"BT /F1 12 Tf 72 740 Td 14 TL\n"
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content += b"(" + safe.encode("latin-1", "ignore") + b") Tj T*\n"
        content += b"ET"
        contents.append(content)

    n_pages = len(pages_lines)
    # Object layout: 1=catalog, 2=pages, then per page (page, content), then font.
    # So page i -> obj 3+2*i, content i -> obj 4+2*i, font -> obj 3+2*n_pages.
    font_obj = 3 + 2 * n_pages
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join("%d 0 R" % (3 + 2 * i) for i in range(n_pages))
    objects.append(("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages)).encode())
    for i, content in enumerate(contents):
        page_obj, content_obj = 3 + 2 * i, 4 + 2 * i
        objects.append(
            ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
             "/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>"
             % (content_obj, font_obj)).encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1, xref_pos)
    return pdf


def make_zero_page_pdf_bytes():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [] /Count 0 >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1, xref_pos)
    return pdf


PAGE1_LINES = [
    "Introduction",
    "Photosynthesis is the process by which green plants convert sunlight",
    "into chemical energy using chlorophyll pigments in the leaves.",
    "The overall equation uses carbon dioxide and water to make glucose.",
]
PAGE2_LINES = [
    "Cellular Respiration",
    "Mitochondria generate ATP through oxidative phosphorylation in cells.",
    "The Krebs cycle produces electron carriers for the transport chain.",
    "Cellular respiration releases energy stored in glucose molecules.",
]


@pytest.fixture()
def two_page_pdf():
    return make_two_page_pdf_bytes([PAGE1_LINES, PAGE2_LINES])


@pytest.fixture()
def two_pages(two_page_pdf):
    return parse_pdf_pages(two_page_pdf)


@pytest.fixture()
def two_page_chunks(two_pages):
    return chunk_pages(two_pages)


# ===========================================================================
# HAPPY PATH
# ===========================================================================

class TestParseHappy:
    def test_single_page_pdf(self):
        pages = parse_pdf_pages(make_pdf_bytes(["Hello world", "Second line"]))
        assert len(pages) == 1
        assert "Hello world" in pages[0]
        assert "Second line" in pages[0]

    def test_two_page_pdf_per_page(self, two_page_pdf):
        pages = parse_pdf_pages(two_page_pdf)
        assert len(pages) == 2
        # page i -> pages[i]: each page's text is distinct and correctly placed
        assert "Photosynthesis" in pages[0]
        assert "Mitochondria" not in pages[0]
        assert "Mitochondria" in pages[1]
        assert "Photosynthesis" not in pages[1]

    def test_accepts_bytes_stream_and_path(self, two_page_pdf, tmp_path):
        as_stream = parse_pdf_pages(io.BytesIO(two_page_pdf))
        as_bytes = parse_pdf_pages(bytes(two_page_pdf))
        path = tmp_path / "doc.pdf"
        path.write_bytes(two_page_pdf)
        as_path = parse_pdf_pages(str(path))
        assert as_stream == as_bytes == as_path
        assert len(as_path) == 2

    def test_scanned_style_empty_page_yields_empty_string(self):
        pages = parse_pdf_pages(make_pdf_bytes([]))
        assert pages == [""]


class TestChunkHappy:
    def test_chunk_provenance_page_numbers(self, two_pages):
        chunks = chunk_pages(two_pages)
        assert len(chunks) >= 2
        p1 = [c for c in chunks if c["page"] == 1]
        p2 = [c for c in chunks if c["page"] == 2]
        assert p1 and p2
        assert any("Photosynthesis" in c["text"] for c in p1)
        assert any("Mitochondria" in c["text"] for c in p2)
        # global index is sequential across pages
        assert [c["index"] for c in chunks] == list(range(len(chunks)))

    def test_never_empty_chunks_and_empty_pages_skipped(self):
        chunks = chunk_pages(["", "   ", "Real content here for chunking."])
        assert chunks
        assert all(c["text"].strip() for c in chunks)
        assert all(c["page"] == 3 for c in chunks)

    def test_sentence_boundary_cuts(self):
        text = " ".join(
            "Sentence number %d explains an important concept clearly." % i
            for i in range(30)
        )
        chunks = chunk_pages([text], chunk_chars=200, overlap=50)
        assert len(chunks) > 2
        for c in chunks[:-1]:
            assert c["text"].rstrip().endswith((".", "!", "?")), c["text"][-40:]

    def test_overlap_shares_text(self):
        text = " ".join("word%d" % i for i in range(400))
        chunks = chunk_pages([text], chunk_chars=200, overlap=100)
        assert len(chunks) >= 3
        first_words = set(chunks[0]["text"].split())
        second_words = set(chunks[1]["text"].split())
        assert first_words & second_words  # overlap => shared tokens

    def test_heading_detection(self):
        pages = [
            "# Introduction\nThis is the intro paragraph about testing methods.\n"
            "METHODS\nWe ran three experiments with careful controls in place.\n"
            "2. Results\nThe results show a clear improvement over baseline."
        ]
        chunks = chunk_pages(pages)
        headings = {c["heading"] for c in chunks}
        assert "Introduction" in headings
        assert any("method" in h.lower() for h in headings)
        assert any("result" in h.lower() for h in headings)
        assert all("heading" in c for c in chunks)

    def test_heading_text_stays_searchable(self):
        pages = ["# Quantum Tunneling\nParticles cross barriers they classically cannot."]
        chunks = chunk_pages(pages)
        assert any("Quantum Tunneling" in c["text"] for c in chunks)

    def test_chunk_cap_truncation(self):
        big = "word " * 3000  # ~15000 chars per page
        chunks = chunk_pages([big] * 10, chunk_chars=50, overlap=0)
        assert isinstance(chunks, ChunkList)
        assert len(chunks) <= CHUNK_CAP
        assert chunks.truncated is True

    def test_no_truncation_flag_normally(self, two_page_chunks):
        assert two_page_chunks.truncated is False

    def test_unicode_text(self):
        pages = ["Caf\u00e9 na\u00efve r\u00e9sum\u00e9 \u2014 Universit\u00e4t M\u00fcnchen. " * 20]
        chunks = chunk_pages(pages)
        assert chunks
        results = retrieve(chunks, "universit\u00e4t m\u00fcnchen")
        assert results  # no crash, finds the unicode content


class TestRetrieveHappy:
    def test_ranks_right_chunk(self, two_page_chunks):
        results = retrieve(two_page_chunks, "mitochondria ATP oxidative phosphorylation")
        assert results
        assert results[0]["page"] == 2
        assert "Mitochondria" in results[0]["text"]

    def test_known_paragraph_in_top3(self):
        paras = [
            "Apples are red fruits that grow on trees in temperate orchards.",
            "Bicycles have two wheels and are powered by pedaling riders.",
            "The Eiffel Tower in Paris was completed in 1889 for the exposition.",
            "Octopuses have eight arms and remarkable camouflage abilities.",
            "Volcanoes erupt when magma pressure exceeds the crust strength.",
            "Libraries lend books and provide quiet study spaces downtown.",
        ]
        chunks = chunk_pages(paras, chunk_chars=500, overlap=0)
        results = retrieve(chunks, "which structure was completed in Paris in 1889")
        top3_texts = [r["text"] for r in results[:3]]
        assert any("Eiffel Tower" in t for t in top3_texts)

    def test_deterministic(self, two_page_chunks):
        q = "glucose energy plants"
        first = retrieve(two_page_chunks, q)
        second = retrieve(two_page_chunks, q)
        assert [r["index"] for r in first] == [r["index"] for r in second]
        assert [r["score"] for r in first] == [r["score"] for r in second]

    def test_debug_field_explains_score(self, two_page_chunks):
        results = retrieve(two_page_chunks, "chlorophyll sunlight plants")
        assert results
        debug = results[0]["debug"]
        for key in ("bm25", "tfidf_cosine", "bm25_norm", "tfidf_norm",
                    "combined", "matched_terms"):
            assert key in debug, key
        assert abs(debug["combined"] - results[0]["score"]) < 1e-9
        assert abs(debug["combined"]
                   - (0.5 * debug["bm25_norm"] + 0.5 * debug["tfidf_norm"])) < 1e-9
        assert "chlorophyll" in debug["matched_terms"]

    def test_top_k_respected(self, two_page_chunks):
        assert len(retrieve(two_page_chunks, "plants glucose energy", top_k=1)) <= 1

    def test_result_preserves_chunk_fields(self, two_page_chunks):
        r = retrieve(two_page_chunks, "photosynthesis")[0]
        assert {"page", "index", "text", "heading", "score", "debug"} <= set(r)


class TestAnswerHappy:
    def test_cites_real_pages(self, two_pages, two_page_chunks):
        result = answer_question("what is cellular respiration", "Bio Notes", two_page_chunks)
        assert result["citations"]
        parsed_pages = {i + 1 for i, t in enumerate(two_pages) if t.strip()}
        for cit in result["citations"]:
            assert cit["page"] in parsed_pages  # never an invented page
            assert cit["doc"] == "Bio Notes"

    def test_excerpts_are_verbatim_substrings(self, two_page_chunks):
        result = answer_question("mitochondria ATP energy", "Bio Notes", two_page_chunks)
        assert result["citations"]
        by_index = {c["index"]: c["text"] for c in two_page_chunks}
        for cit in result["citations"]:
            chunk_text = by_index[cit["chunk"]]
            assert cit["excerpt"] in chunk_text  # verbatim, not paraphrased
            assert len(cit["excerpt"]) <= 280

    def test_every_claim_has_citation_marker(self, two_page_chunks):
        result = answer_question("photosynthesis chlorophyll sunlight", "Bio", two_page_chunks)
        answer = result["answer"]
        assert result["citations"]
        assert answer.count("[doc, p.") == len(result["citations"])
        for cit in result["citations"]:
            assert "[doc, p.%d]" % cit["page"] in answer

    def test_synthesis_is_2_to_4_sentences(self, two_page_chunks):
        result = answer_question("photosynthesis glucose plants", "Bio", two_page_chunks)
        # one intro sentence + one quoted claim sentence per cited passage
        num_sentences = 1 + result["answer"].count('" [doc, p.')
        assert 2 <= num_sentences <= 4
        assert 1 <= len(result["citations"]) <= 3

    def test_passages_mirror_citations(self, two_page_chunks):
        result = answer_question("krebs cycle electron carriers", "Bio", two_page_chunks)
        assert result["passages"] == result["citations"]
        assert result["passages"]  # non-empty on a good query

    def test_answer_uses_document_phrases(self, two_page_chunks):
        result = answer_question("mitochondria generate ATP", "Bio", two_page_chunks)
        assert "Mitochondria generate ATP" in result["answer"] or \
               "mitochondria" in result["answer"].lower()


class TestValidateHappy:
    def test_accepts_real_pdf_upload(self, two_page_pdf):
        stream = io.BytesIO(two_page_pdf)
        ok, error = validate_upload(FakeUpload("notes.pdf", stream))
        assert ok is True and error == ""

    def test_accepts_uppercase_extension(self, two_page_pdf):
        ok, _ = validate_upload(FakeUpload("NOTES.PDF", io.BytesIO(two_page_pdf)))
        assert ok is True

    def test_restores_stream_position(self, two_page_pdf):
        stream = io.BytesIO(two_page_pdf)
        stream.read(10)
        ok, _ = validate_upload(FakeUpload("notes.pdf", stream))
        assert ok is True
        assert stream.tell() == 10

    def test_accepts_pdf_mime(self, two_page_pdf):
        ok, _ = validate_upload(
            FakeUpload("n.pdf", io.BytesIO(two_page_pdf), mimetype="application/pdf"))
        assert ok is True


# ===========================================================================
# ERROR PATH — no function may raise unhandled
# ===========================================================================

class TestValidateErrors:
    def test_none_upload(self):
        ok, error = validate_upload(None)
        assert ok is False and error

    def test_missing_filename(self):
        ok, error = validate_upload(FakeUpload("", io.BytesIO(b"%PDF-1.4")))
        assert ok is False and "No file" in error

    def test_rejects_txt_extension(self):
        ok, error = validate_upload(FakeUpload("notes.txt", io.BytesIO(b"hello")))
        assert ok is False and "PDF" in error

    def test_rejects_png_extension(self):
        ok, error = validate_upload(FakeUpload("img.png", io.BytesIO(b"\x89PNG")))
        assert ok is False and "PDF" in error

    def test_rejects_no_extension(self):
        ok, error = validate_upload(FakeUpload("notes", io.BytesIO(b"%PDF")))
        assert ok is False

    def test_rejects_empty_file(self):
        ok, error = validate_upload(FakeUpload("empty.pdf", io.BytesIO(b"")))
        assert ok is False and "empty" in error.lower()

    def test_rejects_oversize(self):
        big = FakeBigStream(26 * 1024 * 1024)
        ok, error = validate_upload(FakeUpload("big.pdf", big))
        assert ok is False and "25 MB" in error

    def test_rejects_bad_magic_bytes(self):
        ok, error = validate_upload(
            FakeUpload("fake.pdf", io.BytesIO(b"<html>not a pdf</html>")))
        assert ok is False and "%PDF" in error

    def test_rejects_bad_mime(self, two_page_pdf):
        ok, error = validate_upload(
            FakeUpload("n.pdf", io.BytesIO(two_page_pdf), mimetype="image/png"))
        assert ok is False and "content type" in error

    def test_rejects_unreadable_stream(self):
        ok, error = validate_upload(FakeUpload("n.pdf", BrokenStream()))
        assert ok is False and error

    def test_rejects_no_stream(self):
        ok, error = validate_upload(FakeUpload("n.pdf", None))
        assert ok is False and error


class TestParseErrors:
    def test_malformed_bytes(self):
        assert parse_pdf_pages(b"this is not a pdf at all") == []

    def test_truncated_pdf(self):
        assert parse_pdf_pages(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog") == []

    def test_none_input(self):
        assert parse_pdf_pages(None) == []

    def test_zero_page_pdf(self):
        assert parse_pdf_pages(make_zero_page_pdf_bytes()) == []

    def test_unicode_garbage_bytes(self):
        garbage = "za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144".encode("utf-8") * 50
        assert parse_pdf_pages(garbage) == []

    def test_random_binary(self):
        assert parse_pdf_pages(bytes(range(256)) * 10) == []


class TestChunkErrors:
    def test_none_pages(self):
        chunks = chunk_pages(None)
        assert isinstance(chunks, ChunkList) and len(chunks) == 0

    def test_non_string_entries_skipped(self):
        chunks = chunk_pages([None, 123, "valid text for a chunk here"])
        assert len(chunks) == 1
        assert chunks[0]["page"] == 3

    def test_zero_chunk_chars_no_hang(self):
        chunks = chunk_pages(["some text to chunk safely"], chunk_chars=0, overlap=0)
        assert isinstance(chunks, ChunkList)  # terminates, never hangs

    def test_negative_params_no_hang(self):
        chunks = chunk_pages(["some text to chunk safely"], chunk_chars=-5, overlap=-10)
        assert isinstance(chunks, ChunkList)

    def test_garbage_params_no_raise(self):
        chunks = chunk_pages(["some text"], chunk_chars="bogus", overlap=None)
        assert isinstance(chunks, ChunkList)


class TestRetrieveErrors:
    def test_empty_query(self, two_page_chunks):
        assert retrieve(two_page_chunks, "") == []

    def test_whitespace_query(self, two_page_chunks):
        assert retrieve(two_page_chunks, "   \n\t ") == []

    def test_stopwords_only_query(self, two_page_chunks):
        assert retrieve(two_page_chunks, "the and of a to in") == []

    def test_non_string_query(self, two_page_chunks):
        assert retrieve(two_page_chunks, None) == []
        assert retrieve(two_page_chunks, 12345) == []

    def test_empty_chunks(self):
        assert retrieve([], "photosynthesis") == []

    def test_none_chunks(self):
        assert retrieve(None, "photosynthesis") == []

    def test_none_entries_in_chunks(self):
        chunks = [None, {"page": 1, "index": 0, "heading": "", "text": "mitochondria ATP"}]
        results = retrieve(chunks, "mitochondria")
        assert len(results) == 1 and results[0]["index"] == 0

    def test_zero_top_k(self, two_page_chunks):
        assert retrieve(two_page_chunks, "plants", top_k=0) == []
        assert retrieve(two_page_chunks, "plants", top_k=-3) == []


class TestAnswerErrors:
    def test_unrelated_query_abstains_exactly(self, two_page_chunks):
        result = answer_question(
            "quantum chromodynamics zebra migration patterns", "Bio", two_page_chunks)
        assert result["answer"] == NO_RESULT_ANSWER
        assert result["answer"] == "I couldn't find this in your documents."
        assert result["citations"] == []
        assert result["passages"] == []

    def test_no_chunks_abstains(self):
        result = answer_question("anything at all", "Doc", [])
        assert result["answer"] == "I couldn't find this in your documents."
        assert result["citations"] == [] and result["passages"] == []

    def test_scanned_pdf_no_text_abstains(self):
        # scanned/image PDF -> pages with no text -> zero chunks -> abstain
        pages = parse_pdf_pages(make_pdf_bytes([]))
        assert pages == [""]
        chunks = chunk_pages(pages)
        assert chunks == []
        result = answer_question("what is this document about", "Scan", chunks)
        assert result["answer"] == "I couldn't find this in your documents."
        assert result["citations"] == []

    def test_none_query_abstains(self, two_page_chunks):
        result = answer_question(None, "Doc", two_page_chunks)
        assert result["answer"] == "I couldn't find this in your documents."

    def test_none_chunks_abstains(self):
        result = answer_question("q", "Doc", None)
        assert result["answer"] == "I couldn't find this in your documents."

    def test_none_title_no_raise(self, two_page_chunks):
        result = answer_question("mitochondria", None, two_page_chunks)
        assert result["citations"]  # still cites; doc label just empty
        assert all(c["doc"] == "" for c in result["citations"])

    def test_zero_citations_ever_on_abstention(self, two_page_chunks):
        for q in ["", "   ", "xyzzy plugh qwerty asdf"]:
            r = answer_question(q, "Doc", two_page_chunks)
            if r["answer"] == "I couldn't find this in your documents.":
                assert r["citations"] == [] and r["passages"] == []


class TestNoTempFileLeaks:
    def test_pipeline_creates_no_temp_files(self, two_page_pdf):
        tmpdir = tempfile.gettempdir()
        before = set(os.listdir(tmpdir))
        pages = parse_pdf_pages(two_page_pdf)
        chunks = chunk_pages(pages)
        retrieve(chunks, "mitochondria ATP")
        answer_question("what is cellular respiration", "Bio", chunks)
        validate_upload(FakeUpload("n.pdf", io.BytesIO(two_page_pdf)))
        after = set(os.listdir(tmpdir))
        assert after - before == set()
