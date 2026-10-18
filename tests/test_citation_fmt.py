"""Tests for citation_fmt.py — pure logic only (no routes, no app fixture).

Covers: one golden test per style on the real paper "Attention Is All
You Need" (Vaswani et al., 2017, arXiv:1706.03762, NeurIPS 2017),
1/2/3/8-author cases per style, official et-al. thresholds per style,
arXiv preprint rendering per style, missing-field degradation,
BibTeX export/parse/round-trip, style guides, and negative paths.
"""
import re

import pytest

from studybuddy.citation_fmt import (
    STYLES,
    format_bibliography,
    format_citation,
    from_bibtex,
    style_guide,
    to_bibtex,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ATTENTION = {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar",
                "Jakob Uszkoreit", "Llion Jones", "Aidan N. Gomez",
                "\u0141ukasz Kaiser", "Illia Polosukhin"],
    "year": "2017",
    "venue": "Advances in Neural Information Processing Systems",
    "volume": "30",
    "pubtype": "inproceedings",
}

ATTENTION_PREPRINT = {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar",
                "Jakob Uszkoreit", "Llion Jones", "Aidan N. Gomez",
                "\u0141ukasz Kaiser", "Illia Polosukhin"],
    "year": "2017",
    "arxiv_id": "1706.03762",
    "pubtype": "misc",
}


def _full(authors):
    return {"title": "A Study of Structured Citations",
            "authors": authors,
            "year": "2024",
            "venue": "Journal of Testing",
            "volume": "12",
            "issue": "3",
            "pages": "45-67",
            "doi": "10.1234/test.2024.001",
            "pubtype": "article"}


ONE = _full(["Ada Lovelace"])
TWO = _full(["Ada Lovelace", "Alan Turing"])
THREE = _full(["Ada Lovelace", "Alan Turing", "Grace Hopper"])


def _many(n):
    return _full(["Given%d Family%d" % (i, i) for i in range(1, n + 1)])


# Same-character repeats only: ".," is legitimate (e.g. APA "Kaiser, \u0141.,").
DOUBLE_PUNCT = re.compile(r"([,.])\1")


def _assert_clean(out):
    assert "None" not in out, "leaked None: %r" % out
    assert not DOUBLE_PUNCT.search(out), "double punctuation: %r" % out


# ---------------------------------------------------------------------------
# Golden tests — "Attention Is All You Need", hand-verified against the
# official guides (IEEE Editorial Style Manual; APA 7th; MLA 9th;
# ICMJE/NLM Vancouver; Chicago 17th author-date).
# ---------------------------------------------------------------------------

def test_golden_ieee_attention():
    assert format_citation(ATTENTION, "ieee") == (
        'A. Vaswani et al., "Attention is all you need," '
        "in *Advances in Neural Information Processing Systems*, "
        "vol. 30, 2017."
    )


def test_golden_apa_attention():
    assert format_citation(ATTENTION, "apa") == (
        "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., "
        "Gomez, A. N., Kaiser, \u0141., & Polosukhin, I. (2017). "
        "Attention is all you need. "
        "*Advances in Neural Information Processing Systems*, *30*."
    )


def test_golden_mla_attention():
    assert format_citation(ATTENTION, "mla") == (
        'Vaswani, Ashish, et al. "Attention Is All You Need." '
        "*Advances in Neural Information Processing Systems*, vol. 30, 2017."
    )


def test_golden_vancouver_attention():
    assert format_citation(ATTENTION, "vancouver") == (
        "Vaswani A, Shazeer N, Parmar N, Uszkoreit J, Jones L, Gomez AN, "
        "et al. Attention is all you need. "
        "In: Advances in Neural Information Processing Systems. 2017;30."
    )


def test_golden_chicago_attention():
    assert format_citation(ATTENTION, "chicago") == (
        "Vaswani, Ashish, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, "
        "Llion Jones, Aidan N. Gomez, \u0141ukasz Kaiser, and "
        "Illia Polosukhin. 2017. \"Attention Is All You Need.\" "
        "In *Advances in Neural Information Processing Systems* 30."
    )


# ---------------------------------------------------------------------------
# 1-author cases (all fields present)
# ---------------------------------------------------------------------------

def test_one_author_ieee():
    assert format_citation(ONE, "ieee") == (
        'A. Lovelace, "A study of structured citations," '
        "*Journal of Testing*, vol. 12, no. 3, pp. 45\u201367, 2024, "
        "doi: 10.1234/test.2024.001."
    )


def test_one_author_apa():
    assert format_citation(ONE, "apa") == (
        "Lovelace, A. (2024). A study of structured citations. "
        "*Journal of Testing*, *12*(3), 45\u201367. "
        "https://doi.org/10.1234/test.2024.001"
    )


def test_one_author_mla():
    assert format_citation(ONE, "mla") == (
        'Lovelace, Ada. "A Study of Structured Citations." '
        "*Journal of Testing*, vol. 12, no. 3, 2024, pp. 45\u201367. "
        "doi:10.1234/test.2024.001."
    )


def test_one_author_vancouver():
    assert format_citation(ONE, "vancouver") == (
        "Lovelace A. A study of structured citations. Journal of Testing. "
        "2024;12(3):45\u201367. https://doi.org/10.1234/test.2024.001."
    )


def test_one_author_chicago():
    assert format_citation(ONE, "chicago") == (
        'Lovelace, Ada. 2024. "A Study of Structured Citations." '
        "*Journal of Testing* 12 (3): 45\u201367. "
        "https://doi.org/10.1234/test.2024.001."
    )


# ---------------------------------------------------------------------------
# 2-author cases
# ---------------------------------------------------------------------------

def test_two_author_ieee():
    out = format_citation(TWO, "ieee")
    assert out.startswith('A. Lovelace and A. Turing, "A study of structured '
                          'citations,"')
    _assert_clean(out)


def test_two_author_apa():
    assert format_citation(TWO, "apa").startswith(
        "Lovelace, A., & Turing, A. (2024).")


def test_two_author_mla():
    assert format_citation(TWO, "mla").startswith(
        'Lovelace, Ada, and Alan Turing. "A Study of Structured Citations."')


def test_two_author_vancouver():
    assert format_citation(TWO, "vancouver").startswith(
        "Lovelace A, Turing A. A study of structured citations.")


def test_two_author_chicago():
    assert format_citation(TWO, "chicago").startswith(
        'Lovelace, Ada, and Alan Turing. 2024. "A Study of Structured '
        'Citations."')


# ---------------------------------------------------------------------------
# 3-author cases (exercises et-al. thresholds for MLA)
# ---------------------------------------------------------------------------

def test_three_author_ieee():
    out = format_citation(THREE, "ieee")
    assert out.startswith('A. Lovelace, A. Turing, and G. Hopper, "A study '
                          'of structured citations,"')
    _assert_clean(out)


def test_three_author_apa():
    assert format_citation(THREE, "apa").startswith(
        "Lovelace, A., Turing, A., & Hopper, G. (2024).")


def test_three_author_mla_uses_et_al():
    assert format_citation(THREE, "mla").startswith(
        'Lovelace, Ada, et al. "A Study of Structured Citations."')


def test_three_author_vancouver():
    assert format_citation(THREE, "vancouver").startswith(
        "Lovelace A, Turing A, Hopper G. A study of structured citations.")


def test_three_author_chicago():
    assert format_citation(THREE, "chicago").startswith(
        'Lovelace, Ada, Alan Turing, and Grace Hopper. 2024. "A Study of '
        'Structured Citations."')


# ---------------------------------------------------------------------------
# Official et-al. thresholds per style
# ---------------------------------------------------------------------------

def test_ieee_six_authors_all_listed():
    out = format_citation(_many(6), "ieee")
    assert "et al." not in out
    assert "and G. Family6," in out


def test_ieee_seven_authors_et_al():
    out = format_citation(_many(7), "ieee")
    assert out.startswith("G. Family1 et al.,")
    assert "Family2" not in out


def test_apa_twenty_authors_all_listed():
    out = format_citation(_many(20), "apa")
    assert ", & Family20, G." in out
    assert "\u2026" not in out


def test_apa_twentyone_authors_ellipsis_no_ampersand():
    out = format_citation(_many(21), "apa")
    assert "\u2026" in out
    assert "Family19, G., \u2026 Family21, G." in out
    assert "Family20, G." not in out
    assert "& Family21" not in out


def test_vancouver_six_authors_all_listed():
    out = format_citation(_many(6), "vancouver")
    assert "et al." not in out
    assert "Family6 G." in out


def test_vancouver_seven_authors_first_six_plus_et_al():
    out = format_citation(_many(7), "vancouver")
    assert "Family6 G, et al." in out
    assert "Family7" not in out


def test_chicago_ten_authors_all_listed():
    out = format_citation(_many(10), "chicago")
    assert "et al." not in out
    assert "and Given10 Family10." in out


def test_chicago_eleven_authors_first_seven_plus_et_al():
    out = format_citation(_many(11), "chicago")
    assert "Given7 Family7, et al." in out
    assert "Family8" not in out


# ---------------------------------------------------------------------------
# arXiv preprint rendering per style
# ---------------------------------------------------------------------------

def test_preprint_ieee():
    assert format_citation(ATTENTION_PREPRINT, "ieee") == (
        'A. Vaswani et al., "Attention is all you need," '
        "arXiv:1706.03762, 2017."
    )


def test_preprint_apa():
    assert format_citation(ATTENTION_PREPRINT, "apa") == (
        "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., "
        "Gomez, A. N., Kaiser, \u0141., & Polosukhin, I. (2017). "
        "Attention is all you need [Preprint]. *arXiv*. "
        "https://doi.org/10.48550/arXiv.1706.03762"
    )


def test_preprint_mla():
    assert format_citation(ATTENTION_PREPRINT, "mla") == (
        'Vaswani, Ashish, et al. "Attention Is All You Need." '
        "*arXiv*, 2017. https://arxiv.org/abs/1706.03762."
    )


def test_preprint_vancouver():
    assert format_citation(ATTENTION_PREPRINT, "vancouver") == (
        "Vaswani A, Shazeer N, Parmar N, Uszkoreit J, Jones L, Gomez AN, "
        "et al. Attention is all you need [Preprint]. 2017. "
        "Available from: https://arxiv.org/abs/1706.03762."
    )


def test_preprint_chicago():
    assert format_citation(ATTENTION_PREPRINT, "chicago") == (
        "Vaswani, Ashish, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, "
        "Llion Jones, Aidan N. Gomez, \u0141ukasz Kaiser, and "
        "Illia Polosukhin. 2017. \"Attention Is All You Need.\" "
        "*arXiv*. https://arxiv.org/abs/1706.03762."
    )


# ---------------------------------------------------------------------------
# Missing-field degradation
# ---------------------------------------------------------------------------

def test_missing_optional_fields_all_styles():
    meta = {"title": "A Study of Things", "authors": ["Ada Lovelace"]}
    for style in STYLES:
        _assert_clean(format_citation(meta, style))


def test_missing_year_apa_uses_nd():
    out = format_citation({"title": "T", "authors": ["Ada Lovelace"]}, "apa")
    assert "(n.d.)" in out
    _assert_clean(out)


def test_missing_year_chicago_uses_nd():
    out = format_citation({"title": "T", "authors": ["Ada Lovelace"]},
                          "chicago")
    assert "n.d." in out
    _assert_clean(out)


def test_no_authors_apa_title_moves_to_author_position():
    out = format_citation({"title": "A Study of Things", "year": "2020"},
                          "apa")
    assert out == "A study of things. (2020)."
    _assert_clean(out)


def test_empty_authors_list_degrades():
    for style in STYLES:
        out = format_citation({"title": "T", "authors": [], "year": "2020"},
                              style)
        _assert_clean(out)
        assert out, style


def test_missing_title_degrades():
    for style in STYLES:
        out = format_citation({"authors": ["Ada Lovelace"], "year": "2020",
                               "venue": "J Test"},
                              style)
        _assert_clean(out)
        assert out, style


def test_almost_empty_meta_all_styles():
    for style in STYLES:
        out = format_citation({"title": "A study of things"}, style)
        _assert_clean(out)


def test_fully_empty_meta_all_styles():
    for style in STYLES:
        out = format_citation({}, style)
        assert "None" not in out
        assert not DOUBLE_PUNCT.search(out)


def test_none_meta():
    assert "None" not in format_citation(None, "apa")


# ---------------------------------------------------------------------------
# Bibliographies
# ---------------------------------------------------------------------------

def test_bibliography_ieee_numbered_in_order():
    out = format_bibliography([ONE, ATTENTION], "ieee")
    lines = out.split("\n")
    assert lines[0].startswith("[1] A. Lovelace,")
    assert lines[1].startswith("[2] A. Vaswani et al.,")


def test_bibliography_vancouver_numbered_in_order():
    out = format_bibliography([ONE, ATTENTION], "vancouver")
    lines = out.split("\n")
    assert lines[0].startswith("1. Lovelace A.")
    assert lines[1].startswith("2. Vaswani A,")


def test_bibliography_apa_alphabetical():
    out = format_bibliography([ATTENTION, ONE], "apa")
    lines = out.split("\n")
    assert lines[0].startswith("Lovelace, A.")
    assert lines[1].startswith("Vaswani, A.")


def test_bibliography_chicago_alphabetical():
    out = format_bibliography([ATTENTION, ONE], "chicago")
    assert out.index("Lovelace, Ada.") < out.index("Vaswani, Ashish")


def test_bibliography_empty():
    assert format_bibliography([], "apa") == ""
    assert format_bibliography([], "ieee") == ""


# ---------------------------------------------------------------------------
# BibTeX export
# ---------------------------------------------------------------------------

def test_to_bibtex_article_exact():
    assert to_bibtex(ONE) == (
        "@article{lovelace2024,\n"
        "  author = {Ada Lovelace},\n"
        "  title = {{A} {Study} of {Structured} {Citations}},\n"
        "  journal = {Journal of Testing},\n"
        "  volume = {12},\n"
        "  number = {3},\n"
        "  pages = {45--67},\n"
        "  year = {2024},\n"
        "  doi = {10.1234/test.2024.001}\n"
        "}"
    )


def test_to_bibtex_inproceedings_uses_booktitle():
    out = to_bibtex(ATTENTION)
    assert out.startswith("@inproceedings{vaswani2017,")
    assert "booktitle = {Advances in Neural Information Processing Systems},"
    assert "journal" not in out


def test_to_bibtex_key_collision_suffix():
    out = to_bibtex(ONE, existing_keys=["lovelace2024"])
    assert out.startswith("@article{lovelace2024a,")
    out2 = to_bibtex(ONE, existing_keys=["lovelace2024", "lovelace2024a"])
    assert out2.startswith("@article{lovelace2024b,")


def test_to_bibtex_escapes_special_chars():
    meta = {"title": "R&D at 100%: $5_M {deal}",
            "authors": ["Ada Lovelace"], "year": "2024"}
    out = to_bibtex(meta)
    for esc in (r"\&", r"\%", r"\$", r"\_", r"\{", r"\}"):
        assert esc in out, "missing escape %r in %r" % (esc, out)
    assert "None" not in out


def test_to_bibtex_empty_meta():
    out = to_bibtex({})
    assert out.startswith("@misc{anonxxxx,")
    assert "None" not in out


def test_to_bibtex_unicode_key_ascii_folded():
    meta = {"title": "T", "authors": ["\u0141ukasz Kaiser"], "year": "2019"}
    assert to_bibtex(meta).startswith("@misc{kaiser2019,")


# ---------------------------------------------------------------------------
# BibTeX parsing and round-trips
# ---------------------------------------------------------------------------

def test_from_bibtex_round_trip_preserves_fields():
    metas = from_bibtex(to_bibtex(ATTENTION))
    assert len(metas) == 1
    m = metas[0]
    assert m["title"] == "Attention Is All You Need"
    assert m["authors"] == ATTENTION["authors"]
    assert m["year"] == "2017"
    assert m["venue"] == "Advances in Neural Information Processing Systems"
    assert m["volume"] == "30"
    assert m["pubtype"] == "inproceedings"


def test_bibtex_export_parse_export_identical():
    for meta in (ATTENTION, ONE, ATTENTION_PREPRINT,
                 {"title": "R&D at 100%: $5_M", "authors": ["Ada Lovelace"],
                  "year": "2024", "doi": "10.1/x&y"}):
        first = to_bibtex(meta)
        parsed = from_bibtex(first)
        assert len(parsed) == 1
        assert to_bibtex(parsed[0]) == first


def test_from_bibtex_multiple_entries():
    text = to_bibtex(ONE) + "\n\n" + to_bibtex(ATTENTION_PREPRINT)
    metas = from_bibtex(text)
    assert len(metas) == 2
    assert metas[0]["pubtype"] == "article"
    assert metas[1]["pubtype"] == "misc"
    assert metas[1]["arxiv_id"] == "1706.03762"


def test_from_bibtex_quoted_values_and_comma_names():
    text = ('@article{key2024,\n'
            '  author = "Lovelace, Ada and Turing, Alan",\n'
            '  title = "Some Title",\n'
            '  journal = "J Test",\n'
            '  year = "2024"\n'
            '}')
    metas = from_bibtex(text)
    assert len(metas) == 1
    assert metas[0]["authors"] == ["Lovelace, Ada", "Turing, Alan"]
    assert metas[0]["title"] == "Some Title"
    # "Last, First" input still formats correctly downstream
    assert format_citation(metas[0], "apa").startswith(
        "Lovelace, A., & Turing, A. (2024).")


def test_from_bibtex_book_maps_to_misc():
    metas = from_bibtex("@book{b2020, title = {T}, author = {A B}}")
    assert metas[0]["pubtype"] == "misc"


def test_from_bibtex_garbage_returns_empty():
    assert from_bibtex("") == []
    assert from_bibtex("   ") == []
    assert from_bibtex("this is not bibtex at all") == []
    assert from_bibtex(None) == []


def test_from_bibtex_malformed_entries_skipped():
    assert from_bibtex("@article{broken") == []
    assert from_bibtex("@article{broken, author = {X") == []
    assert from_bibtex("@misc{x, = ,}") == []
    # one bad entry does not kill a good one
    good = to_bibtex(ONE)
    metas = from_bibtex("@article{broken, author = {X\n\n" + good)
    assert len(metas) == 1
    assert metas[0]["title"] == ONE["title"]


# ---------------------------------------------------------------------------
# Style guides
# ---------------------------------------------------------------------------

def test_style_guide_non_empty_all_styles():
    for style in STYLES:
        g = style_guide(style)
        assert g["in_text"].strip(), style
        assert isinstance(g["reference_rules"], list) and g[
            "reference_rules"], style
        assert all(r.strip() for r in g["reference_rules"]), style
        assert g["notes"].strip(), style


def test_style_guide_content_spot_checks():
    assert "[1]" in style_guide("ieee")["in_text"]
    assert "et al." in style_guide("apa")["in_text"]
    assert "(Smith 2020)" in style_guide("chicago")["in_text"]
    assert any("et al." in r for r in
               style_guide("vancouver")["reference_rules"])


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------

def test_unknown_style_raises_helpful_valueerror():
    for fn in (format_citation, format_bibliography, style_guide):
        with pytest.raises(ValueError, match="Unknown citation style"):
            if fn is format_citation:
                fn(ONE, "harvard")
            elif fn is format_bibliography:
                fn([ONE], "harvard")
            else:
                fn("harvard")
    with pytest.raises(ValueError, match="ieee.*apa.*mla.*vancouver.*chicago"):
        format_citation(ONE, "turabian")


def test_unicode_everywhere_all_styles():
    meta = {"title": "\u00c9tude sur l'apprentissage f\u00e9d\u00e9r\u00e9",
            "authors": ["\u0141ukasz Kaiser", "Zo\u00eb M\u00fcller"],
            "year": "2024",
            "venue": "Revue d'Intelligence Artificielle",
            "volume": "3", "pages": "1-9",
            "doi": "10.1/\u00e9tude", "url": "https://example.com/x",
            "pubtype": "article"}
    for style in STYLES:
        _assert_clean(format_citation(meta, style))
    assert to_bibtex(meta).startswith("@article{kaiser2024,")


def test_special_chars_all_styles():
    meta = {"title": "R&D: 100% Growth & $5M Deals",
            "authors": ["Ada Lovelace"], "year": "2024",
            "venue": "J. of A&B", "pages": "1-9", "doi": "10.1/a&b"}
    for style in STYLES:
        _assert_clean(format_citation(meta, style))


def test_styles_tuple_complete():
    assert set(STYLES) == {"ieee", "apa", "mla", "vancouver", "chicago"}
