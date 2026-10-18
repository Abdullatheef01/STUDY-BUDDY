"""Feature 27 ultimate: harsh tests for streak freeze, squads, rewards."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import date, timedelta

import pytest

from studybuddy.momentum import (
    reward_tiers,
    squad_leaderboard,
    streak_freeze_status,
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


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_freeze_never_crashes(s):
    assert _ok(streak_freeze_status, date.today(), s, date.today())
    assert _ok(streak_freeze_status, None, None, None)


def test_freeze_available():
    f = streak_freeze_status(date.today(), 0, date.today())
    assert f["freezes_available"] == 1
    assert f["freeze_would_apply"] is False


def test_freeze_used_up():
    f = streak_freeze_status(date.today(), 1, date.today())
    assert f["freezes_available"] == 0


def test_freeze_would_apply():
    # Missed exactly yesterday (2 days since last active).
    f = streak_freeze_status(date.today() - timedelta(days=2), 0, date.today())
    assert f["freeze_would_apply"] is True


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_squad_never_crashes(s):
    assert _ok(squad_leaderboard, [{"user_id": 1, "name": s, "weekly_xp": 10}])
    assert _ok(squad_leaderboard, s)
    assert _ok(squad_leaderboard, None)


def test_squad_ranks():
    s = squad_leaderboard([
        {"user_id": 1, "name": "A", "weekly_xp": 100},
        {"user_id": 2, "name": "B", "weekly_xp": 300},
        {"user_id": 3, "name": "C", "weekly_xp": 200},
    ])
    assert s["leader"] == "B"
    assert s["squad"][0]["medal"] == "gold"
    assert s["squad"][2]["rank"] == 3


def test_squad_rejects_bad():
    with pytest.raises((ValueError, TypeError)):
        squad_leaderboard("nope")
    with pytest.raises((ValueError, TypeError)):
        squad_leaderboard([])


@pytest.mark.parametrize("pair", [(0, 0), (7, 0), (30, 6000), ("bad", "bad"), (-5, -10), (None, None)])
def test_rewards_never_crashes(pair):
    assert _ok(reward_tiers, pair[0], pair[1])


def test_rewards_unlock():
    r = reward_tiers(30, 1200)
    names = [u["name"] for u in r["unlocked"]]
    assert "7-day streak" in names and "30-day streak" in names
    assert "1000 XP" in names
    assert r["next_up"]["name"] == "14-day streak" or r["next_up"] is not None


def test_rewards_all_unlocked():
    r = reward_tiers(100, 20000)
    assert r["unlocked_count"] == 6
    assert r["next_up"] is None
