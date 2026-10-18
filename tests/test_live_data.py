"""Tests for the Live Data Engine (studybuddy.live_data)."""
import json
import os

from studybuddy import live_data
from studybuddy.live_data import (
    acquire_lock,
    atomic_write,
    freshness_badge,
    is_stale,
    release_lock,
    touch_updated,
)


def test_is_stale():
    assert is_stale("2000-01-01", 30) is True
    assert is_stale("2999-01-01", 30) is False
    assert is_stale("", 30) is True
    assert is_stale(None, 30) is True
    assert is_stale("not-a-date", 30) is True


def test_touch_updated():
    meta = touch_updated({"a": 1})
    assert meta["a"] == 1
    assert len(meta["last_updated"]) == 10  # YYYY-MM-DD


def test_freshness_badge():
    b = freshness_badge({"last_updated": "2999-01-01"}, 30)
    assert b["stale"] is False
    assert "2999-01-01" in b["label"]
    b = freshness_badge({"last_updated": "2000-01-01"}, 30)
    assert b["stale"] is True
    assert "stale" in b["label"].lower()


def test_atomic_write(tmp_path):
    p = str(tmp_path / "data.json")
    atomic_write(p, {"x": 1})
    with open(p, encoding="utf-8") as f:
        assert json.load(f) == {"x": 1}
    # Overwrite is also atomic
    atomic_write(p, {"x": 2})
    with open(p, encoding="utf-8") as f:
        assert json.load(f) == {"x": 2}
    # No temp files left behind
    assert os.listdir(str(tmp_path)) == ["data.json"]


def test_lock(tmp_path):
    lp = str(tmp_path / "test.lock")
    assert acquire_lock(lp) is True
    assert acquire_lock(lp) is False  # already held
    release_lock(lp)
    assert acquire_lock(lp) is True
    release_lock(lp)


def test_maybe_refresh_disabled(monkeypatch):
    monkeypatch.setenv("LIVE_REFRESH_DISABLED", "1")
    called = []
    result = live_data.maybe_refresh("x", "nonexistent.json", 1,
                                     lambda: called.append(1))
    assert result is False
    assert called == []
