"""Feature 6 ultimate: harsh tests for README grader, commit bullets, pin optimizer."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest

from studybuddy.github_integration import (
    commit_messages_to_bullets,
    grade_readme,
    pin_optimizer,
)
from tests.mega.harsh_corpus import HARSH_STRINGS


def _ok(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except (ValueError, TypeError):
        return True
    except Exception:
        return False


GOOD_README = """# ShipIt
A deployment dashboard for small teams.
## Features
- One-click deploys
- Rollback in 30 seconds
## Demo
Try it live: https://shipit-demo.example.com
![screenshot](shot.png)
## Tech Stack
Python, Flask, Redis
## Getting Started
pip install shipit
shipit run
Used by 500 users across 40 teams, p99 latency 120ms.
"""

BAD_README = "my project\ncode here"


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_readme_never_crashes(s):
    assert _ok(grade_readme, s)
    assert _ok(grade_readme, None)


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_readme_bounds(s):
    try:
        r = grade_readme(s)
    except (ValueError, TypeError):
        return
    assert 0 <= r["score"] <= 100
    assert r["grade"]


def test_readme_good_beats_bad():
    g = grade_readme(GOOD_README)
    b = grade_readme(BAD_README)
    assert g["score"] > b["score"]
    assert g["grade"].startswith("A") or g["grade"].startswith("B")


def test_readme_flags_missing_demo():
    r = grade_readme("# App\nA thing.\n## Install\npip install x\n" + "word " * 60)
    assert any("demo" in f.lower() for f in r["fixes"])


@pytest.mark.parametrize("msgs", [
    [], ["a"], ["x" * 500], [None, 123, ["x"]],
    ["merge branch 'main'", "wip", "fix typo"],
    ["Add auth"] * 30,
])
def test_commits_never_crashes(msgs):
    assert _ok(commit_messages_to_bullets, msgs, "repo")


def test_commits_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        commit_messages_to_bullets("not a list")


def test_commits_builds_bullets():
    r = commit_messages_to_bullets(
        ["Add user authentication with JWT tokens",
         "Fix race condition in the cache layer",
         "Refactor database queries for 2x speed"], "myapp")
    assert len(r["bullets"]) == 3
    assert all("[myapp]" in b for b in r["bullets"])
    assert r["skipped"] == 0


def test_commits_skips_noise():
    r = commit_messages_to_bullets(["merge branch", "wip", "x"])
    assert r["bullets"] == []
    assert r["skipped"] == 3


@pytest.mark.parametrize("repos", [
    [], "not a list",
    [{"name": "a", "description": "x", "language": "Python", "stars": "bad",
      "updated_at": None, "topics": "bad"}],
    [{"name": ""}, {"no_name": True}, "junk", None],
    [{"name": "<script>alert(1)</script>", "description": "x"}],
])
def test_pins_never_crashes(repos):
    assert _ok(pin_optimizer, repos, "Engineer")


def test_pins_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        pin_optimizer("not a list")


def test_pins_ranks_relevant_first():
    repos = [
        {"name": "old-blog", "description": "my blog", "language": "HTML",
         "stars": 0, "updated_at": "2020-01-01", "topics": []},
        {"name": "ml-pipeline", "description": "ML pipeline with live demo",
         "language": "Python", "stars": 30, "updated_at": "2026-08-01",
         "topics": ["machine-learning"]},
    ]
    r = pin_optimizer(repos, "ML Engineer")
    assert r["pinned_names"][0] == "ml-pipeline"
    assert len(r["picks"]) <= 6
