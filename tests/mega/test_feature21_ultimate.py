"""Feature 21 ultimate: harsh tests for theme clustering, gap mode, length presets."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.lit_review import cluster_by_theme, gap_highlight_review, length_preset
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
    {"id": 1, "title": "BERT for NLP", "abstract": "Language model. Future work: multilingual.", "year": 2019},
    {"id": 2, "title": "CNN image segmentation", "abstract": "Vision model on small dataset.", "year": 2020},
    {"id": 3, "title": "Cooking recipes", "abstract": "How to bake bread.", "year": 2021},
]

@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_cluster_never_crashes(s):
    assert _ok(cluster_by_theme, [{"id": 1, "title": s, "abstract": s}])
    assert _ok(cluster_by_theme, s)
    assert _ok(cluster_by_theme, None)


def test_cluster_groups():
    c = cluster_by_theme(PAPERS)
    themes = [x["theme"] for x in c["clusters"]]
    assert "NLP" in themes
    assert c["total"] == 3
    assert len(c["unclustered"]) == 1  # cooking paper


def test_cluster_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        cluster_by_theme("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_gap_never_crashes(s):
    assert _ok(gap_highlight_review, [{"id": 1, "title": s, "abstract": s}])
    assert _ok(gap_highlight_review, s)


def test_gap_finds_signals():
    g = gap_highlight_review(PAPERS)
    assert g["papers_with_gaps"] >= 2
    assert g["framing"]


def test_gap_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        gap_highlight_review("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_preset_never_crashes(s):
    assert _ok(length_preset, s)


def test_preset_all():
    for preset, words, nsec in [("survey", 500, 3), ("standard", 1500, 5), ("chapter", 3000, 7)]:
        p = length_preset(preset)
        assert p["target_words"] == words
        assert len(p["sections"]) == nsec


def test_preset_rejects_unknown():
    with pytest.raises((ValueError, TypeError)):
        length_preset("novel")
