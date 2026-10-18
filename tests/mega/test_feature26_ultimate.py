"""Feature 26 ultimate: harsh tests for pipeline analytics, nudges, offer compare."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import date, timedelta

import pytest

from studybuddy.tracker_analytics import (
    compare_offers,
    followup_nudges,
    pipeline_analytics,
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
def test_pipeline_never_crashes(s):
    assert _ok(pipeline_analytics, [{"stage": s}])
    assert _ok(pipeline_analytics, s)
    assert _ok(pipeline_analytics, None)


def test_pipeline_funnel():
    apps = [{"stage": "applied"}] * 10 + [{"stage": "interview"}] * 4 + [{"stage": "offer"}] * 2
    p = pipeline_analytics(apps)
    assert p["total_applications"] == 16
    stages = {f["stage"]: f for f in p["funnel"]}
    assert stages["applied"]["count"] == 16
    assert stages["interview"]["count"] == 6
    assert stages["offer"]["count"] == 2
    assert stages["interview"]["conversion_from_prev_pct"] == 100.0  # 6/6 from OA
    assert stages["oa"]["conversion_from_prev_pct"] == round(6 / 16 * 100, 1)


def test_pipeline_rejected_conservative():
    p = pipeline_analytics([{"stage": "rejected"}])
    stages = {f["stage"]: f for f in p["funnel"]}
    assert stages["applied"]["count"] == 1
    assert stages["offer"]["count"] == 0


def test_pipeline_empty():
    p = pipeline_analytics([])
    assert p["total_applications"] == 0
    assert p["insights"]


def test_pipeline_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        pipeline_analytics("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_nudges_never_crashes(s):
    assert _ok(followup_nudges, [{"id": 1, "company": s, "stage": "applied",
                                  "stage_updated_at": "2020-01-01"}])
    assert _ok(followup_nudges, s)
    assert _ok(followup_nudges, None)


def test_nudges_finds_stale():
    old = (date.today() - timedelta(days=10)).isoformat()
    n = followup_nudges([
        {"id": 1, "company": "Acme", "role": "SDE", "stage": "applied",
         "stage_updated_at": old},
        {"id": 2, "company": "X", "role": "Y", "stage": "rejected",
         "stage_updated_at": old},
        {"id": 3, "company": "Z", "role": "W", "stage": "applied",
         "stage_updated_at": date.today().isoformat()},
    ])
    assert n["count"] == 1
    assert n["nudges"][0]["company"] == "Acme"


def test_nudges_rejects_non_list():
    with pytest.raises((ValueError, TypeError)):
        followup_nudges("nope")


@pytest.mark.parametrize("s", HARSH_STRINGS)
def test_compare_never_crashes(s):
    offers = [{"company": s, "base_lpa": 10}, {"company": "B", "base_lpa": s}]
    assert _ok(compare_offers, offers)


def test_compare_ranks():
    c = compare_offers([
        {"company": "A", "role": "SDE", "base_lpa": 12, "variable_lpa": 2},
        {"company": "B", "role": "SDE", "base_lpa": 15, "variable_lpa": 0},
    ])
    assert c["top_by_comp"] == "B"
    assert c["offers"][0]["is_top_comp"] is True


def test_compare_needs_two():
    with pytest.raises((ValueError, TypeError)):
        compare_offers([{"company": "A", "base_lpa": 10}])
    with pytest.raises((ValueError, TypeError)):
        compare_offers("nope")
