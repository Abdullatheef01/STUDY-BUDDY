"""Feature 15 ultimate: harsh tests for agentic track, milestones, weekly planner."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from tests.mega.harsh_corpus import HARSH_STRINGS
from studybuddy.learning_roadmaps import (
    agentic_ai_track, project_milestones, weekly_planner,
)


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


def test_track_structure():
    t = agentic_ai_track()
    assert t["id"] == "agentic-ai"
    assert t["total_weeks"] == 14
    assert len(t["stages"]) == 4
    assert all("project" in s and "skills" in s for s in t["stages"])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_milestones_never_crashes(s):
    assert _ok(project_milestones, [{"stage": s, "weeks": 2}])
    assert _ok(project_milestones, s)
    assert _ok(project_milestones, None)


def test_milestones_fills_gaps():
    m = project_milestones([{"stage": "Basics", "weeks": 2},
                            {"stage": "Advanced", "weeks": 3}])
    assert m["total_projects"] == 2
    assert all(s["project"] for s in m["stages"])
    assert all("GitHub" in s["deliverable"] for s in m["stages"])


def test_milestones_keeps_existing():
    m = project_milestones([{"stage": "X", "project": "My custom project"}])
    assert m["stages"][0]["project"] == "My custom project"


def test_milestones_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        project_milestones("nope")
    with pytest.raises((ValueError, TypeError)):
        project_milestones([])


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_planner_never_crashes(s):
    assert _ok(weekly_planner, [{"stage": "X", "weeks": 2}], 6, s)


def test_planner_structure():
    w = weekly_planner([{"stage": "A", "weeks": 2}, {"stage": "B", "weeks": 1}],
                       hours_per_week=5)
    assert w["total_weeks"] == 3
    assert w["total_hours"] == 15.0
    assert w["weeks"][0]["week"] == 1
    assert w["weeks"][-1]["focus"] == "B"


def test_planner_clamps_hours():
    w = weekly_planner([{"stage": "A", "weeks": 1}], hours_per_week=999)
    assert w["weeks"][0]["hours"] == 40


def test_planner_rejects_empty():
    with pytest.raises((ValueError, TypeError)):
        weekly_planner([])
    with pytest.raises((ValueError, TypeError)):
        weekly_planner("nope")
