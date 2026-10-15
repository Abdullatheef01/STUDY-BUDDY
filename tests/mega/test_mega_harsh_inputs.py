"""MEGA-1: Harsh text inputs across all text-processing features.

Every harsh string is fed to every text function. Functions must never
raise on hostile input — they return safe defaults or validation errors.
~700 tests.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy import (
    bullet_rewriter, jd_matcher, communication_coach, cover_generator,
    linkedin_grader, career_assessment, mock_interview, citation_fmt,
    gap_finder,
)


def _safe_call(fn, *args):
    """Returns (ok, result_or_exc).

    ValueError = intentional input validation (GOOD, not a crash).
    Anything else raising = real bug.
    """
    try:
        return True, fn(*args)
    except ValueError as e:
        return True, ("validation", str(e))
    except Exception as e:  # noqa: BLE001
        return False, e


# ---- bullet_rewriter ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_bullet_improve_never_crashes(s):
    ok, res = _safe_call(bullet_rewriter.improve_bullet, s)
    assert ok, f"improve_bullet crashed on {s[:30]!r}: {res}"
    assert isinstance(res, (dict, list, tuple))  # tuple = validation path


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_bullet_concise_never_crashes(s):
    ok, res = _safe_call(bullet_rewriter.concise_version, s)
    assert ok, f"concise_version crashed on {s[:30]!r}: {res}"
    assert isinstance(res, (str, list, tuple))


# ---- jd_matcher ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_jd_keywords_never_crashes(s):
    ok, res = _safe_call(jd_matcher.extract_jd_keywords, s)
    assert ok, f"extract_jd_keywords crashed on {s[:30]!r}: {res}"
    assert isinstance(res, (list, dict, set))


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_jd_parse_never_crashes(s):
    ok, res = _safe_call(jd_matcher.parse_jd_requirements, s)
    assert ok, f"parse_jd_requirements crashed on {s[:30]!r}: {res}"


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_score_jd_match_never_crashes(s):
    ok, res = _safe_call(jd_matcher.score_jd_match, s, ["python"], 2, [], {}, s)
    assert ok, f"score_jd_match crashed on {s[:30]!r}: {res}"


# ---- communication_coach ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_coach_analyze_never_crashes(s):
    ok, res = _safe_call(communication_coach.analyze_transcript, s)
    assert ok, f"analyze_transcript crashed on {s[:30]!r}: {res}"


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_coach_filler_never_crashes(s):
    ok, res = _safe_call(communication_coach.find_filler_hits, s)
    assert ok, f"find_filler_hits crashed on {s[:30]!r}: {res}"


# ---- cover_generator ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_cover_letter_never_crashes(s):
    ok, res = _safe_call(cover_generator.rule_based_cover_letter, s, s)
    assert ok, f"rule_based_cover_letter crashed on {s[:30]!r}: {res}"
    assert isinstance(res, (str, tuple))


# ---- linkedin_grader ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_linkedin_grade_never_crashes(s):
    ok, res = _safe_call(linkedin_grader.grade_linkedin_profile,
                         s, s, [], [])
    assert ok, f"grade_linkedin_profile crashed on {s[:30]!r}: {res}"


# ---- career_assessment ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_assessment_score_never_crashes(s):
    ok, res = _safe_call(career_assessment.score_assessment, {"q1": s})
    assert ok, f"score_assessment crashed on {s[:30]!r}: {res}"


# ---- mock_interview ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_interview_score_never_crashes(s):
    ok, res = _safe_call(mock_interview.score_answer,
                         {"question": s}, s)
    assert ok, f"score_answer crashed on {s[:30]!r}: {res}"


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_interview_pick_never_crashes(s):
    ok, res = _safe_call(mock_interview.pick_questions, s, s, s, 2)
    assert ok, f"pick_questions crashed on {s[:30]!r}: {res}"


# ---- citation_fmt ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_citation_format_never_crashes(s):
    for style in ["ieee", "apa", "mla", "vancouver", "chicago"]:
        ok, res = _safe_call(citation_fmt.format_citation,
                             {"title": s, "authors": [s], "year": s}, style)
        assert ok, f"format_citation[{style}] crashed on {s[:30]!r}: {res}"


# ---- gap_finder ----
@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_gap_report_never_crashes(s):
    ok, res = _safe_call(gap_finder.generate_gap_report, s)
    # May raise on empty input by design, but never on hostile non-empty
    if s.strip():
        assert ok, f"generate_gap_report crashed on {s[:30]!r}: {res}"
