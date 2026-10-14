"""Tests for flashcards.py — flashcards & paper-quiz generation (Wave 4 #26).

Pure-logic tests only (no Flask, no routes): key-term extraction, QA/cloze/
MCQ card generation, deck assembly, MCQ grading, and mastery stats.

Split per the zero-error protocol:
  - HAPPY-PATH: extraction quality, golden cards, provenance, grading.
  - ERROR-PATH: every public function is exercised with invalid input and
    must return a clean failure value — no function may raise unhandled.
"""
import pytest

from studybuddy import flashcards
from studybuddy.flashcards import (
    generate_deck,
    grade_mcq,
    key_terms,
    make_cloze_cards,
    make_mcq_cards,
    make_qa_cards,
    mastery_stats,
)


# ---------------------------------------------------------------------------
# Helpers (test-only)
# ---------------------------------------------------------------------------

class FakeDoc:
    """Duck-typed stand-in for unified_app.StudyDoc."""

    def __init__(self, title, chunks, doc_id=7):
        self.id = doc_id
        self.title = title
        self.data = {"chunks": chunks}


def _chunk(i, page, text, heading=None):
    return {"page": page, "index": i, "text": text, "heading": heading}


def make_synth_doc():
    """A small synthetic paper about cell biology used across tests."""
    chunks = [
        _chunk(
            0, 1,
            "Photosynthesis is the process by which plants convert light energy "
            "into chemical energy. Chlorophyll is the green pigment that "
            "captures light energy for photosynthesis.",
        ),
        _chunk(
            1, 2,
            "Mitochondria are the powerhouse of the cell. Cellular respiration "
            "refers to the process of breaking down glucose to release energy.",
        ),
        _chunk(
            2, 3,
            "DNA replication is the process by which a cell makes an exact copy "
            "of its DNA. The nucleus is the control center of the cell.",
        ),
    ]
    return FakeDoc("Cell Biology Notes", chunks)


def synth_meta():
    doc = make_synth_doc()
    return [(c, doc.title) for c in doc.data["chunks"]]


def chunk_by_index(doc, idx):
    for c in doc.data["chunks"]:
        if c["index"] == idx:
            return c
    raise AssertionError("no chunk with index %r" % idx)


# ---------------------------------------------------------------------------
# 1. key_terms
# ---------------------------------------------------------------------------

class TestKeyTerms:
    def test_returns_ranked_term_score_pairs(self):
        terms = key_terms(synth_meta_chunks(), top_n=10)
        assert isinstance(terms, list) and len(terms) == 10
        for term, score in terms:
            assert isinstance(term, str) and term.strip()
            assert isinstance(score, float)
        scores = [s for _, s in terms]
        assert scores == sorted(scores, reverse=True)

    def test_prefers_multiword_phrases(self):
        terms = [t for t, _ in key_terms(synth_meta_chunks(), top_n=40)]
        lowered = [t.lower() for t in terms]
        assert "light energy" in lowered  # appears twice, bigram boosted

    def test_top_terms_are_content_words(self):
        terms = [t.lower() for t, _ in key_terms(synth_meta_chunks(), top_n=40)]
        assert "photosynthesis" in terms
        for filler in ("the", "is", "and", "process", "paper"):
            assert filler not in terms

    def test_deterministic(self):
        chunks = synth_meta_chunks()
        assert key_terms(chunks, top_n=40) == key_terms(chunks, top_n=40)

    def test_top_n_respected(self):
        chunks = synth_meta_chunks()
        assert len(key_terms(chunks, top_n=5)) == 5
        assert len(key_terms(chunks, top_n=1000)) <= 1000

    def test_bad_input_returns_empty(self):
        assert key_terms(None) == []
        assert key_terms([]) == []
        assert key_terms([{"text": 123}, None, "nope"]) == []
        assert key_terms(synth_meta_chunks(), top_n=0) == []
        assert key_terms(synth_meta_chunks(), top_n=-3) == []
        assert key_terms("not-a-chunk-list") == []

    def test_stoplist_has_about_120_words(self):
        assert len(flashcards._STOPWORDS) >= 100


def synth_meta_chunks():
    return [c for c, _ in synth_meta()]


# ---------------------------------------------------------------------------
# 2. make_qa_cards
# ---------------------------------------------------------------------------

class TestQaCards:
    def test_golden_photosynthesis_card(self):
        cards = make_qa_cards(synth_meta(), max_n=12)
        matches = [c for c in cards if "Photosynthesis" in c["question"]]
        assert matches, "expected a Photosynthesis QA card"
        card = matches[0]
        assert card["question"] == "What is Photosynthesis?"
        assert card["answer"] == (
            "Photosynthesis is the process by which plants convert light "
            "energy into chemical energy."
        )
        assert card["kind"] == "qa"
        assert card["options"] == []
        # Provenance
        assert card["chunk"] == 0
        assert card["page"] == 1
        assert card["doc_title"] == "Cell Biology Notes"

    def test_refers_to_pattern(self):
        cards = make_qa_cards(synth_meta(), max_n=12)
        matches = [c for c in cards if "Cellular respiration" in c["question"]]
        assert matches
        assert matches[0]["question"] == "What does Cellular respiration refer to?"

    def test_is_are_was_were_variants(self):
        meta = [({"page": 1, "index": 0,
                  "text": "Mitochondria are the powerhouse of the cell. "
                          "The ribosome was the site of protein synthesis.",
                  "heading": None}, "T")]
        cards = make_qa_cards(meta, max_n=12)
        questions = [c["question"] for c in cards]
        assert "What is Mitochondria?" in questions
        assert "What is ribosome?" in questions

    def test_max_n_respected_and_ids_assigned(self):
        cards = make_qa_cards(synth_meta(), max_n=2)
        assert len(cards) == 2
        assert [c["id"] for c in cards] == ["qa-0", "qa-1"]

    def test_skips_pronoun_subjects(self):
        meta = [({"page": 1, "index": 0,
                  "text": "This is very important for the exam. "
                          "It is a key concept to remember always.",
                  "heading": None}, "T")]
        assert make_qa_cards(meta, max_n=12) == []

    def test_empty_and_garbage_input(self):
        assert make_qa_cards([], max_n=5) == []
        assert make_qa_cards(None) == []
        assert make_qa_cards("nope") == []
        assert make_qa_cards([{"text": None}], max_n=5) == []
        assert make_qa_cards(synth_meta(), max_n=0) == []
        # Bare chunk dicts (no tuple wrapper) are accepted too
        cards = make_qa_cards(synth_meta_chunks(), max_n=12)
        assert cards and cards[0]["doc_title"] == ""


# ---------------------------------------------------------------------------
# 3. make_cloze_cards
# ---------------------------------------------------------------------------

class TestClozeCards:
    def test_blanks_first_occurrence_only(self):
        meta = [({"page": 4, "index": 9,
                  "text": "The cell membrane protects the cell from harm "
                          "because every cell needs a boundary.",
                  "heading": None}, "Bio")]
        cards = make_cloze_cards(meta, [("cell", 9.0)], max_n=5)
        assert len(cards) == 1
        card = cards[0]
        assert card["question"].count("_____") == 1
        assert card["question"].startswith("The _____ membrane protects")
        assert card["question"].endswith("(from p. 4)")
        assert card["answer"] == "cell"
        assert card["kind"] == "cloze"
        assert card["chunk"] == 9 and card["page"] == 4
        assert card["doc_title"] == "Bio"
        assert card["id"] == "cloze-0"

    def test_word_boundary_no_substring_blanking(self):
        # "cell" must not be blanked inside "cellular".
        meta = [({"page": 1, "index": 0,
                  "text": "Cellular organization underlies cellular biology "
                          "in every known cellular system today.",
                  "heading": None}, "T")]
        cards = make_cloze_cards(meta, [("cell", 9.0)], max_n=5)
        assert cards == []

    def test_skips_short_terms(self):
        meta = synth_meta()
        cards = make_cloze_cards(meta, [("at", 5.0), ("dna", 4.0), ("an", 3.0)],
                                 max_n=5)
        assert cards == []

    def test_terms_accepted_as_plain_strings(self):
        cards = make_cloze_cards(synth_meta(), ["photosynthesis"], max_n=5)
        assert cards and cards[0]["answer"] == "photosynthesis"

    def test_each_sentence_used_once(self):
        meta = synth_meta()
        terms = key_terms([c for c, _ in meta], top_n=40)
        cards = make_cloze_cards(meta, terms, max_n=12)
        questions = [c["question"] for c in cards]
        assert len(questions) == len(set(questions))

    def test_max_n_and_garbage_input(self):
        meta = synth_meta()
        terms = key_terms([c for c, _ in meta], top_n=40)
        assert len(make_cloze_cards(meta, terms, max_n=1)) == 1
        assert make_cloze_cards(None, terms) == []
        assert make_cloze_cards(meta, None) == []
        assert make_cloze_cards(meta, "junk") == []
        assert make_cloze_cards(meta, terms, max_n=0) == []


# ---------------------------------------------------------------------------
# 4. make_mcq_cards
# ---------------------------------------------------------------------------

class TestMcqCards:
    def _mcq_cards(self):
        meta = synth_meta()
        terms = key_terms([c for c, _ in meta], top_n=40)
        return make_mcq_cards(meta, terms, max_n=12)

    def test_option_integrity(self):
        cards = self._mcq_cards()
        assert cards, "expected MCQ cards from the synthetic doc"
        for card in cards:
            assert card["kind"] == "mcq"
            options = card["options"]
            assert len(options) == 4
            assert len(set(o.lower() for o in options)) == 4  # unique
            assert card["answer"] in options  # correct answer present
            assert options[card["correct_index"]] == card["answer"]
            distractors = [o for o in options if o != card["answer"]]
            assert len(distractors) == 3
            stem = card["question"]
            assert "_____" in stem
            for d in distractors:
                assert d != card["answer"]
                assert d.lower() not in stem.lower()  # absent from stem
                assert d.lower() not in card["answer"].lower()
                assert card["answer"].lower() not in d.lower()

    def test_distractors_come_from_same_doc(self):
        cards = self._mcq_cards()
        doc_text = " ".join(c["text"] for c in synth_meta_chunks()).lower()
        for card in cards:
            for opt in card["options"]:
                assert opt.lower() in doc_text

    def test_deterministic_shuffle(self):
        first = self._mcq_cards()
        second = self._mcq_cards()
        assert [c["options"] for c in first] == [c["options"] for c in second]
        assert [c["correct_index"] for c in first] == \
               [c["correct_index"] for c in second]

    def test_ids_and_provenance(self):
        cards = self._mcq_cards()
        assert [c["id"] for c in cards] == \
               ["mcq-%d" % i for i in range(len(cards))]
        for card in cards:
            assert isinstance(card["chunk"], int)
            assert isinstance(card["page"], int) and card["page"] >= 1
            assert card["doc_title"] == "Cell Biology Notes"

    def test_insufficient_distractors_skipped(self):
        meta = synth_meta()
        # Only 3 usable terms -> cannot build a 4-option card.
        cards = make_mcq_cards(meta, [("alpha", 1.0), ("beta", 1.0),
                                      ("gamma", 1.0)], max_n=5)
        assert cards == []

    def test_garbage_input(self):
        meta = synth_meta()
        assert make_mcq_cards(None, [("abcd", 1.0)]) == []
        assert make_mcq_cards(meta, None) == []
        assert make_mcq_cards(meta, []) == []
        assert make_mcq_cards(meta, [("abcd", 1.0)], max_n=0) == []


# ---------------------------------------------------------------------------
# 5. generate_deck
# ---------------------------------------------------------------------------

class TestGenerateDeck:
    def test_deck_shape_and_progress(self):
        deck = generate_deck(make_synth_doc(), max_per_kind=10)
        assert set(deck.keys()) == {"cards", "progress"}
        assert deck["cards"], "expected cards from the synthetic doc"
        kinds = {c["kind"] for c in deck["cards"]}
        assert kinds <= {"qa", "cloze", "mcq"}
        for card in deck["cards"]:
            for key in ("id", "kind", "question", "answer", "options",
                        "chunk", "page", "doc_title"):
                assert key in card, "card missing %r" % key
            assert card["options"] == [] or len(card["options"]) == 4
        # Progress initialized for every card
        assert set(deck["progress"].keys()) == {c["id"] for c in deck["cards"]}
        for entry in deck["progress"].values():
            assert entry == {"known": False, "reviews": 0}

    def test_ids_deterministic_per_kind(self):
        deck = generate_deck(make_synth_doc(), max_per_kind=10)
        for kind in ("qa", "cloze", "mcq"):
            ids = [c["id"] for c in deck["cards"] if c["kind"] == kind]
            assert ids == ["%s-%d" % (kind, i) for i in range(len(ids))]

    def test_max_per_kind_respected(self):
        deck = generate_deck(make_synth_doc(), max_per_kind=2)
        for kind in ("qa", "cloze", "mcq"):
            assert sum(1 for c in deck["cards"] if c["kind"] == kind) <= 2

    def test_traceability_every_card(self):
        doc = make_synth_doc()
        deck = generate_deck(doc, max_per_kind=10)
        assert deck["cards"]
        for card in deck["cards"]:
            chunk = chunk_by_index(doc, card["chunk"])
            assert chunk["page"] == card["page"], \
                "card %s page mismatch" % card["id"]
            text = chunk["text"]
            answer = card["answer"]
            assert answer.lower() in text.lower(), \
                "card %s answer not in chunk text" % card["id"]

    def test_dedupes_near_identical_questions(self):
        text = ("Photosynthesis is the process by which plants convert light "
                "energy into chemical energy. "
                "Photosynthesis is the process by which plants convert light "
                "energy into chemical energy.")
        doc = FakeDoc("Dup", [_chunk(0, 1, text)])
        deck = generate_deck(doc, max_per_kind=10)
        questions = [flashcards._qkey(c["question"]) for c in deck["cards"]]
        assert len(questions) == len(set(questions))

    def test_none_doc_gives_empty_deck(self):
        assert generate_deck(None) == {"cards": [], "progress": {}}

    def test_doc_with_no_chunks_gives_empty_deck(self):
        assert generate_deck(FakeDoc("Empty", [])) == {"cards": [], "progress": {}}
        assert generate_deck(FakeDoc("None", None)) == {"cards": [], "progress": {}}

    def test_doc_with_no_extractable_sentences(self):
        doc = FakeDoc("Gibberish", [_chunk(0, 1, "a b c. a b c. a b c.")])
        assert generate_deck(doc) == {"cards": [], "progress": {}}

    def test_malformed_chunks_never_raise(self):
        doc = FakeDoc("Messy", [None, "nope", {"text": 123},
                                {"page": "x", "index": "y"}])
        assert generate_deck(doc) == {"cards": [], "progress": {}}
        weird = FakeDoc("Weird", None)
        weird.data = "not-a-dict"
        assert generate_deck(weird) == {"cards": [], "progress": {}}

    def test_garbage_doc_object_never_raises(self):
        assert generate_deck(object()) == {"cards": [], "progress": {}}
        assert generate_deck(42) == {"cards": [], "progress": {}}


# ---------------------------------------------------------------------------
# 6. grade_mcq
# ---------------------------------------------------------------------------

class TestGradeMcq:
    def _deck_mcq_cards(self):
        deck = generate_deck(make_synth_doc(), max_per_kind=10)
        return [c for c in deck["cards"] if c["kind"] == "mcq"]

    def test_perfect_score(self):
        cards = self._deck_mcq_cards()
        assert cards
        answers = {c["id"]: c["correct_index"] for c in cards}
        result = grade_mcq(cards, answers)
        assert result["score"] == len(cards)
        assert result["total"] == len(cards)
        assert all(d["correct"] for d in result["details"])

    def test_partial_score(self):
        cards = self._deck_mcq_cards()
        answers = {}
        for i, c in enumerate(cards):
            if i == 0:
                answers[c["id"]] = c["correct_index"]
            else:
                wrong = (c["correct_index"] + 1) % 4
                answers[c["id"]] = wrong
        result = grade_mcq(cards, answers)
        assert result["score"] == 1
        assert result["total"] == len(cards)

    def test_details_shape(self):
        cards = self._deck_mcq_cards()
        answers = {cards[0]["id"]: cards[0]["correct_index"]}
        result = grade_mcq(cards, answers)
        assert set(result.keys()) == {"answers", "details", "score", "total"}
        assert result["answers"] == answers  # echoed for known ids only
        assert len(result["details"]) == len(cards)
        first = result["details"][0]
        assert first["card_id"] == cards[0]["id"]
        assert first["correct"] is True
        assert first["chosen"] == cards[0]["answer"]
        assert first["answer"] == cards[0]["answer"]

    def test_unknown_ids_ignored(self):
        cards = self._deck_mcq_cards()
        answers = {"nope-99": 0, "bogus": 2,
                   cards[0]["id"]: cards[0]["correct_index"]}
        result = grade_mcq(cards, answers)
        assert result["answers"] == {cards[0]["id"]: cards[0]["correct_index"]}
        assert result["total"] == len(cards)
        assert result["score"] == 1

    def test_out_of_range_and_bad_indices_count_wrong(self):
        cards = self._deck_mcq_cards()
        n = len(cards)
        answers = {
            cards[0]["id"]: 99,        # out of range
            cards[1]["id"]: -1,        # negative
            cards[2]["id"]: "1",       # wrong type
            cards[3]["id"]: True,      # bool is not a valid index
            cards[4]["id"]: 1.5,       # float
        } if n >= 5 else {}
        result = grade_mcq(cards, answers)
        assert result["score"] == 0
        assert all(not d["correct"] for d in result["details"][:5])

    def test_only_mcq_cards_scored(self):
        deck = generate_deck(make_synth_doc(), max_per_kind=10)
        assert any(c["kind"] != "mcq" for c in deck["cards"])
        result = grade_mcq(deck["cards"], {})
        mcq_count = sum(1 for c in deck["cards"] if c["kind"] == "mcq")
        assert result["total"] == mcq_count
        assert result["score"] == 0  # unanswered counts as wrong

    def test_garbage_input_never_raises(self):
        assert grade_mcq(None, None) == \
            {"answers": {}, "details": [], "score": 0, "total": 0}
        assert grade_mcq("nope", "nope")["total"] == 0
        assert grade_mcq([None, 42, {"kind": "mcq"}], None)["total"] == 1
        assert grade_mcq([], {}) == \
            {"answers": {}, "details": [], "score": 0, "total": 0}


# ---------------------------------------------------------------------------
# 7. mastery_stats
# ---------------------------------------------------------------------------

class TestMasteryStats:
    def test_empty_progress(self):
        stats = mastery_stats({"cards": [], "progress": {}})
        assert stats == {"total": 0, "reviewed": 0, "known": 0,
                         "unknown": 0, "mastery_pct": 0}

    def test_none_and_garbage_input(self):
        empty = {"total": 0, "reviewed": 0, "known": 0,
                 "unknown": 0, "mastery_pct": 0}
        assert mastery_stats(None) == empty
        assert mastery_stats({}) == empty
        assert mastery_stats("nope") == empty
        assert mastery_stats({"cards": None, "progress": None}) == empty

    def test_computes_from_progress_map(self):
        set_data = {
            "cards": [{"id": "qa-0"}, {"id": "qa-1"}, {"id": "mcq-0"},
                      {"id": "mcq-1"}],
            "progress": {
                "qa-0": {"known": True, "reviews": 3},
                "qa-1": {"known": False, "reviews": 1},
                "mcq-0": {"known": False, "reviews": 0},  # not reviewed
                "mcq-1": {"known": True, "reviews": 2},
            },
        }
        stats = mastery_stats(set_data)
        assert stats["total"] == 4
        assert stats["reviewed"] == 3
        assert stats["known"] == 2
        assert stats["unknown"] == 1
        assert stats["mastery_pct"] == 67  # round(100 * 2/3)

    def test_malformed_progress_entries_ignored(self):
        set_data = {
            "cards": [{"id": "qa-0"}],
            "progress": {
                "qa-0": {"known": True, "reviews": 1},
                "junk": "not-a-dict",
                "junk2": {"known": True, "reviews": "many"},
                "junk3": {"known": True, "reviews": True},
            },
        }
        stats = mastery_stats(set_data)
        assert stats["reviewed"] == 1
        assert stats["known"] == 1
        assert stats["mastery_pct"] == 100


# ---------------------------------------------------------------------------
# 8. Cross-cutting: nothing raises on hostile input
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn,args", [
    (key_terms, (None,)),
    (key_terms, ([{"text": 123}],)),
    (make_qa_cards, (None,)),
    (make_qa_cards, ([{"text": None}],)),
    (make_cloze_cards, (None, None)),
    (make_cloze_cards, ([], "junk")),
    (make_mcq_cards, (None, None)),
    (make_mcq_cards, ([], [])),
    (generate_deck, (None,)),
    (generate_deck, (object(),)),
    (grade_mcq, (None, None)),
    (grade_mcq, ("x", "y")),
    (mastery_stats, (None,)),
    (mastery_stats, ([],)),
])
def test_public_functions_never_raise(fn, args):
    fn(*args)  # must not raise
