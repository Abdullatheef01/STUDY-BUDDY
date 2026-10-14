"""Tests for Wave 1 feature #9: opportunity radar."""
import json
from datetime import date

import pytest

from opportunities import (load_dataset, list_opportunities, get_opportunity,
                           opp_exists, CLOSING_SOON_DAYS)
from unified_app import create_app, db, OpportunityBookmark
from tests.conftest import register, login


@pytest.fixture()
def authed_client(client):
    register(client)
    login(client)
    return client


def _bm(client, opp_id="gate-2027", remove=False):
    url = "/opportunities/bookmark/remove" if remove else "/opportunities/bookmark"
    return client.post(url, data=json.dumps({"opp_id": opp_id}),
                       content_type="application/json")


def test_dataset_loads():
    data = load_dataset()
    curated = [o for o in data["opportunities"] if o.get("curated", True)]
    assert len(curated) == 20
    assert set(o["type"] for o in curated) == {
        "internship", "scholarship", "exam"}
    # auto-refresh may have added hackathon/competition/internship entries;
    # every type in the file must still be a known type.
    from opportunities import TYPES
    assert set(o["type"] for o in data["opportunities"]) <= set(TYPES)
    import re
    # last_updated changes whenever the auto-refresh runs; just check format.
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["meta"]["last_updated"])


def test_closing_soon_logic_fixed_today():
    opps = list_opportunities(today=date(2026, 10, 14))
    by_id = {o["id"]: o for o in opps}
    assert by_id["gate-2027"]["closing_soon"] is True       # 6 days
    assert by_id["gate-2027"]["days_left"] == 6
    assert by_id["ms-engage-2026"]["closing_soon"] is True   # 11 days
    assert by_id["reliance-foundation-ug-2026"]["closing_soon"] is True  # 14 days, inclusive
    assert by_id["aicte-pragati-2026"]["closing_soon"] is False          # 17 days
    assert by_id["upsc-cse-2027"]["closing_soon"] is False


def test_sorted_by_deadline_nulls_not_present():
    # Curated slice keeps the original deterministic fixture for sort checks.
    data = load_dataset()
    curated_ids = {o["id"] for o in data["opportunities"] if o.get("curated", True)}
    opps = [o for o in list_opportunities(today=date(2026, 10, 14))
            if o["id"] in curated_ids]
    deadlines = [o["deadline"] for o in opps]
    assert deadlines == sorted(deadlines)


def test_type_filter_and_invalid():
    data = load_dataset()
    curated = [o for o in data["opportunities"] if o.get("curated", True)]
    counts = {}
    for o in curated:
        counts[o["type"]] = counts.get(o["type"], 0) + 1
    assert counts.get("exam") == 7
    assert counts.get("scholarship") == 6
    assert counts.get("internship") == 7
    # filtered listing returns only that type (auto entries included)
    for o in list_opportunities(opp_type="hackathon"):
        assert o["type"] == "hackathon"
    assert list_opportunities(opp_type="lottery") == []


def test_opp_exists():
    assert opp_exists("gate-2027") is True
    assert opp_exists("nope") is False
    assert get_opportunity("nope") is None


def test_board_renders_public(client):
    r = client.get("/opportunities")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Opportunity" in html and "Radar" in html
    assert "Curated starter set" in html
    assert "GATE 2027" in html
    assert "opportunities.py" in html  # schema pointer


def test_board_type_filter(client):
    html = client.get("/opportunities?type=exam").get_data(as_text=True)
    assert "GATE 2027" in html
    assert "Google STEP" not in html


def test_board_invalid_type_defaults_to_all(client):
    html = client.get("/opportunities?type=hack").get_data(as_text=True)
    assert "GATE 2027" in html and "Google STEP" in html


def test_board_anon_no_bookmark_buttons(client):
    html = client.get("/opportunities").get_data(as_text=True)
    assert '<button class="opp-bm' not in html
    assert "Log in</a> to bookmark" in html


def test_unauth_bookmark_401(client):
    assert _bm(client).status_code == 401
    assert _bm(client, remove=True).status_code == 401


def test_bookmark_add_remove(authed_client, app):
    r = _bm(authed_client)
    assert r.status_code == 201
    assert r.get_json()["opp_id"] == "gate-2027"
    # idempotent re-add
    assert _bm(authed_client).status_code == 201
    with app.app_context():
        assert OpportunityBookmark.query.count() == 1
    # shows as saved on the board
    html = authed_client.get("/opportunities").get_data(as_text=True)
    assert "★ Saved" in html
    # saved-only filter
    html = authed_client.get("/opportunities?saved=1").get_data(as_text=True)
    assert "GATE 2027" in html and "Google STEP" not in html
    # remove
    assert _bm(authed_client, remove=True).status_code == 200
    with app.app_context():
        assert OpportunityBookmark.query.count() == 0
    assert _bm(authed_client, remove=True).status_code == 404


def test_bookmark_invalid_opp_404(authed_client):
    assert _bm(authed_client, opp_id="no-such-opp").status_code == 404


def test_bookmark_isolation(client, app):
    register(client, email="a@a.com")
    login(client, email="a@a.com")
    _bm(client, opp_id="gate-2027")
    # second user (logout is POST-only)
    client.post("/logout", follow_redirects=False)
    register(client, name="Bee", email="b@b.com")
    login(client, email="b@b.com")
    html = client.get("/opportunities").get_data(as_text=True)
    assert "★ Saved" not in html  # B sees nothing saved
    assert _bm(client, opp_id="gate-2027", remove=True).status_code == 404  # can't remove A's
    with app.app_context():
        assert OpportunityBookmark.query.count() == 1
