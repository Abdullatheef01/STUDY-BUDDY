"""Feature 29 ultimate: harsh tests for pattern alerts, experiments, win library."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.retro_insights import pattern_alerts, track_experiment, win_library


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_alerts_never_crashes(s):
    assert _ok(pattern_alerts, [{"notes": s, "feedback": s}])
    assert _ok(pattern_alerts, s)
    assert _ok(pattern_alerts, None)


def test_alerts_detects_bottleneck():
    retros = [{"notes": "DSA too slow"}, {"notes": "failed coding round, algorithms"},
              {"notes": "great behavioral round"}]
    p = pattern_alerts(retros)
    assert p["alerts"][0]["theme"] == "dsa"
    assert p["alerts"][0]["mentions"] == 2


def test_alerts_min_mentions():
    p = pattern_alerts([{"notes": "dsa hard"}], min_mentions=2)
    assert p["alerts"] == []


def test_alerts_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        pattern_alerts("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_experiment_never_crashes(s):
    v = [{"name": s, "sent": 10, "callbacks": 2}, {"name": "B", "sent": 10, "callbacks": 3}]
    assert _ok(track_experiment, s, v)


def test_experiment_winner():
    e = track_experiment("Resume test", [
        {"name": "A", "sent": 20, "callbacks": 2},
        {"name": "B", "sent": 20, "callbacks": 6},
    ])
    assert e["winner"] == "B"
    assert e["lift"] == 20.0
    assert e["variants"][0]["is_winner"] is True


def test_experiment_small_sample_caution():
    e = track_experiment("T", [{"name": "A", "sent": 5, "callbacks": 1},
                               {"name": "B", "sent": 5, "callbacks": 2}])
    assert "Small sample" in e["caution"]


def test_experiment_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        track_experiment("T", [{"name": "A", "sent": 1, "callbacks": 0}])
    with pytest.raises((ValueError, TypeError)):
        track_experiment("T", "nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_wins_never_crashes(s):
    assert _ok(win_library, [{"title": s, "what_worked": s}])
    assert _ok(win_library, s)
    assert _ok(win_library, None)


def test_wins_playbook():
    w = win_library([
        {"title": "W1", "what_worked": "I tailored my resume and followed up."},
        {"title": "W2", "what_worked": "I tailored my cover letter too."},
    ])
    assert w["count"] == 2
    assert any("tailored" in p for p in w["playbook"])


def test_wins_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        win_library("nope")
