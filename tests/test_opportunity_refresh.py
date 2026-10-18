"""Tests for the auto-refreshing Opportunity Radar.

Covers: source parsing (from saved real fixtures), deadline/age parsing edge
cases, merge rules (dedupe, curated protection, expiry, cap), stale-check +
lock-file behavior, source failure tolerance, and atomic writes.
"""
import json
import os
import time
from datetime import date, datetime
from unittest.mock import patch

import pytest

from studybuddy import opportunities
from studybuddy.opportunities import (
    MAX_AUTO_ENTRIES,
    STALE_AFTER_DAYS,
    TYPES,
    _is_curated,
    _is_stale,
    freshness_label,
    merge_opportunities,
    refresh_opportunities,
)
from studybuddy.opportunity_sources import (
    DevpostSource,
    SimplifyJobsSource,
    fetch_all,
    parse_age_days,
    parse_devpost_deadline,
)

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


# ---------- deadline parsing ----------

def test_parse_devpost_deadline_cross_month():
    assert parse_devpost_deadline("Aug 31 - Oct 23, 2026") == "2026-10-23"


def test_parse_devpost_deadline_same_range():
    assert parse_devpost_deadline("Oct 01 - Nov 12, 2026") == "2026-11-12"


def test_parse_devpost_deadline_year_rollover():
    assert parse_devpost_deadline("Dec 15, 2026 - Jan 15, 2027") == "2027-01-15"


def test_parse_devpost_deadline_single_date():
    assert parse_devpost_deadline("Oct 23, 2026") == "2026-10-23"


@pytest.mark.parametrize("bad", [None, "", "TBD", "soon",
                                  "Foo 01 - Bar 02, 2026", 123])
def test_parse_devpost_deadline_garbage_returns_none(bad):
    assert parse_devpost_deadline(bad) is None


def test_parse_devpost_deadline_ignores_garbage_start():
    # Only the end date matters; a mangled start date doesn't invalidate it.
    assert parse_devpost_deadline("Aug 99 - Oct 23, 2026") == "2026-10-23"


# ---------- age parsing ----------

@pytest.mark.parametrize("age,expected", [
    ("0d", 0), ("1d", 1), ("29d", 29), ("30d", 30), ("1mo", 30), ("2mo", 60),
])
def test_parse_age_days(age, expected):
    assert parse_age_days(age) == expected


@pytest.mark.parametrize("bad", [None, "", "today", "1w", "abc", "1.5d"])
def test_parse_age_days_garbage_returns_none(bad):
    assert parse_age_days(bad) is None


# ---------- source parsing from fixtures ----------

def test_devpost_source_parses_fixture():
    raw = open(os.path.join(FIX, "devpost_sample.json")).read()
    with patch("studybuddy.opportunity_sources._http_get") as mock_get:
        mock_get.return_value.json.return_value = json.loads(raw)
        out = DevpostSource().fetch()
    # 5 in fixture: 3 open real + 1 closed (skipped) + 1 year-rollover open
    assert len(out) == 4
    assert all(o["type"] == "hackathon" for o in out)
    assert all(o["curated"] is False and o["source"] == "devpost" for o in out)
    by_title = {o["title"]: o for o in out}
    assert by_title["Build, Ship, Shape: Amazon Developer Hackathon"]["deadline"] == "2026-10-23"
    assert by_title["New Year Build-a-thon"]["deadline"] == "2027-01-15"
    assert all(o["link"].startswith("https://") for o in out)
    assert all(len(o["eligibility"]) <= 300 for o in out)


def test_devpost_source_never_raises():
    with patch("studybuddy.opportunity_sources._http_get", side_effect=RuntimeError("boom")):
        assert DevpostSource().fetch() == []
    with patch("studybuddy.opportunity_sources._http_get") as mock_get:
        mock_get.return_value.json.side_effect = ValueError("bad json")
        assert DevpostSource().fetch() == []


def test_simplify_source_parses_fixture():
    raw = open(os.path.join(FIX, "simplify_sample.html")).read()
    with patch("studybuddy.opportunity_sources._http_get") as mock_get:
        mock_get.return_value.text = raw
        out = SimplifyJobsSource().fetch()
    # fixture: 0d x2, 5d, 29d, 30d kept; 1mo (30d) kept; rows > 30d skipped
    assert len(out) == 6
    assert all(o["type"] == "internship" for o in out)
    assert all(o["deadline"] is None for o in out)  # rolling
    assert all(o["curated"] is False and o["source"] == "simplifyjobs"
               for o in out)
    assert all(o["link"].startswith("http") for o in out)
    assert all("posted_days_ago" in o for o in out)
    # company fire-emoji stripped
    assert not any(o["organization"].startswith("🔥") for o in out)


def test_simplify_source_skips_old_rows():
    html = ("<table><tr><th>C</th><th>R</th><th>L</th><th>A</th><th>Age</th></tr>"
            "<tr><td>Old Co</td><td>Intern</td><td>Remote</td>"
            '<td><a href="https://example.com/apply">x</a></td><td>2mo</td></tr>'
            "</table>")
    with patch("studybuddy.opportunity_sources._http_get") as mock_get:
        mock_get.return_value.text = html
        assert SimplifyJobsSource().fetch() == []


def test_simplify_source_never_raises():
    with patch("studybuddy.opportunity_sources._http_get", side_effect=RuntimeError("x")):
        assert SimplifyJobsSource().fetch() == []
    with patch("studybuddy.opportunity_sources._http_get") as mock_get:
        mock_get.side_effect = Exception("nope")
        assert fetch_all() == []


# ---------- merge rules ----------

def _curated(oid, link="https://example.com/a", deadline="2027-01-01",
             otype="exam"):
    return {"id": oid, "title": "T", "organization": "Org", "type": otype,
            "deadline": deadline, "eligibility": "E", "link": link,
            "curated": True, "source": "curated"}


def _auto(oid, link, deadline="2027-06-01", otype="hackathon"):
    return {"id": oid, "title": "Auto T", "organization": "AutoOrg",
            "type": otype, "deadline": deadline, "eligibility": "Auto elig",
            "link": link, "curated": False, "source": "devpost"}


def test_merge_dedupes_by_normalized_link():
    existing = [_curated("c1", link="https://Devpost.com/ABC/")]
    fetched = [_auto("a1", link="https://devpost.com/abc")]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    assert [o["id"] for o in merged] == ["c1"]


def test_merge_caps_total_auto_pool_not_just_new():
    # Regression: the cap must apply to the TOTAL auto pool, otherwise the
    # file grows on every refresh (existing auto + new auto each time).
    existing = [_curated("c1")] + [
        _auto(f"old{i}", f"https://x.com/old{i}", deadline=None)
        for i in range(MAX_AUTO_ENTRIES)]
    fetched = [_auto(f"new{i}", f"https://x.com/new{i}", deadline=None)
               for i in range(20)]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    auto = [o for o in merged if not _is_curated(o)]
    assert len(auto) == MAX_AUTO_ENTRIES
    assert len(merged) == MAX_AUTO_ENTRIES + 1


def test_merge_prunes_expired_existing_auto():
    existing = [_curated("c1"),
                _auto("exp", "https://x.com/exp", deadline="2026-01-01"),
                _auto("keep", "https://x.com/keep", deadline="2027-01-01")]
    merged = merge_opportunities(existing, [], today=date(2026, 10, 14))
    assert [o["id"] for o in merged] == ["c1", "keep"]


def test_merge_never_touches_curated():
    existing = [_curated("c1", deadline="2020-01-01")]  # long expired
    fetched = [_auto("a1", "https://x.com/1")]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    c1 = next(o for o in merged if o["id"] == "c1")
    assert c1["deadline"] == "2020-01-01"  # expired curated kept verbatim


def test_merge_prunes_expired_auto():
    existing = [_curated("c1")]
    fetched = [_auto("old", "https://x.com/old", deadline="2026-01-01"),
               _auto("new", "https://x.com/new", deadline="2027-01-01")]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    ids = [o["id"] for o in merged]
    assert "old" not in ids and "new" in ids and "c1" in ids


def test_merge_caps_auto_entries_soonest_first():
    existing = [_curated("c1")]
    fetched = [_auto(f"a{i}", f"https://x.com/{i}",
                     deadline=f"2027-{(i % 12) + 1:02d}-15")
               for i in range(MAX_AUTO_ENTRIES + 20)]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    auto = [o for o in merged if not _is_curated(o)]
    assert len(auto) == MAX_AUTO_ENTRIES
    deadlines = [o["deadline"] for o in auto]
    assert deadlines == sorted(deadlines)


def test_merge_drops_invalid_entries_without_crashing():
    existing = [_curated("c1")]
    fetched = [
        _auto("badtype", "https://x.com/1", otype="nope"),
        {"id": "notype", "title": "x"},  # missing keys
        _auto("baddate", "https://x.com/2", deadline="not-a-date"),
        _auto("good", "https://x.com/3"),
    ]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    ids = [o["id"] for o in merged]
    assert ids == ["c1", "good"]


def test_merge_handles_rolling_null_deadlines():
    existing = [_curated("c1")]
    fetched = [_auto("r1", "https://x.com/r1", deadline=None),
               _auto("r2", "https://x.com/r2", deadline="2027-01-01")]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    assert {o["id"] for o in merged} == {"c1", "r1", "r2"}


def test_merge_makes_ids_unique():
    existing = [_curated("dup")]
    fetched = [_auto("dup", "https://x.com/1"), _auto("dup", "https://x.com/2")]
    merged = merge_opportunities(existing, fetched, today=date(2026, 10, 14))
    ids = [o["id"] for o in merged]
    assert len(ids) == len(set(ids)) == 3
    assert "dup" in ids  # curated keeps its id


def test_is_curated_missing_flag_defaults_true():
    assert _is_curated({"id": "x"}) is True
    assert _is_curated({"curated": False}) is False


# ---------- staleness + lock ----------

def test_is_stale_logic():
    assert _is_stale({"last_updated": date.today().isoformat()}) is False
    old = (date.today().toordinal() - STALE_AFTER_DAYS)
    assert _is_stale({"last_updated": date.fromordinal(old).isoformat()}) is True
    assert _is_stale({"last_updated": "garbage"}) is True
    assert _is_stale({}) is True


def test_stale_triggers_refresh_exactly_once(tmp_path, monkeypatch):
    calls = []

    def fake_refresh():
        calls.append(1)
        return True

    # conftest sets OPP_NO_AUTO_REFRESH=1 globally; opt back in for this test.
    monkeypatch.delenv("OPP_NO_AUTO_REFRESH", raising=False)
    monkeypatch.setattr(opportunities, "refresh_opportunities", fake_refresh)
    monkeypatch.setattr(opportunities, "_LOCK_PATH", str(tmp_path / "lock"))
    data = {"meta": {"last_updated": "2020-01-01"}}
    opportunities._maybe_trigger_refresh(data)
    time.sleep(0.3)
    opportunities._maybe_trigger_refresh(data)  # lock held -> no 2nd trigger
    time.sleep(0.3)
    assert len(calls) == 1


def test_fresh_data_does_not_trigger(monkeypatch):
    calls = []
    monkeypatch.setattr(opportunities, "refresh_opportunities",
                        lambda: calls.append(1))
    data = {"meta": {"last_updated": date.today().isoformat()}}
    opportunities._maybe_trigger_refresh(data)
    assert calls == []


def test_no_auto_refresh_env_disables(monkeypatch):
    calls = []
    monkeypatch.setattr(opportunities, "refresh_opportunities",
                        lambda: calls.append(1))
    monkeypatch.setenv("OPP_NO_AUTO_REFRESH", "1")
    data = {"meta": {"last_updated": "2020-01-01"}}
    opportunities._maybe_trigger_refresh(data)
    assert calls == []


def test_refresh_never_raises_on_source_failure(monkeypatch, tmp_path):
    def _boom():
        raise RuntimeError("down")
    monkeypatch.setattr("studybuddy.opportunity_sources.fetch_all", _boom)
    assert refresh_opportunities() is False


# ---------- atomic write ----------

def test_atomic_write_leaves_valid_json(tmp_path, monkeypatch):
    target = tmp_path / "opps.json"
    monkeypatch.setattr(opportunities, "DATA_PATH", str(target))
    target.write_text(json.dumps({"meta": {}, "opportunities": []}))
    opportunities._atomic_write({"meta": {"a": 1}, "opportunities": []})
    assert json.loads(target.read_text())["meta"] == {"a": 1}
    assert not os.path.exists(str(target) + ".tmp")


def test_refresh_rewrites_file_atomically(tmp_path, monkeypatch):
    data_path = tmp_path / "opportunities.json"
    seed = {"meta": {"last_updated": "2020-01-01", "notice": "n",
                     "schema_doc": "d"},
            "opportunities": [_curated("c1")]}
    data_path.write_text(json.dumps(seed))
    monkeypatch.setattr(opportunities, "DATA_PATH", str(data_path))
    monkeypatch.setattr("studybuddy.opportunity_sources.fetch_all",
                        lambda: [_auto("a1", "https://x.com/a1")])
    assert refresh_opportunities() is True
    out = json.loads(data_path.read_text())
    assert out["meta"]["last_updated"] == date.today().isoformat()
    assert {o["id"] for o in out["opportunities"]} == {"c1", "a1"}
    assert not os.path.exists(str(data_path) + ".tmp")


# ---------- freshness label ----------

def test_freshness_label_formats():
    now = datetime(2026, 10, 14, 12, 0, 0)
    assert freshness_label({"last_updated": "2026-10-14"}, now).startswith(
        "Updated ")
    assert "2 days" in freshness_label({"last_updated": "2026-10-12"}, now)
    assert "1 hour" in freshness_label(
        {"last_updated": "2026-10-14"}, datetime(2026, 10, 14, 1, 30))
    assert "unknown" in freshness_label({"last_updated": "xx"}, now)
    assert "auto-refreshes every 2 days" in freshness_label(
        {"last_updated": "2026-10-14"}, now)


# ---------- types ----------

def test_new_types_registered():
    assert "hackathon" in TYPES and "competition" in TYPES
    assert len(TYPES) == 5
