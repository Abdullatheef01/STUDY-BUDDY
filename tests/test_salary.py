"""Tests for Wave 1 feature #8: India salary explorer."""
import json

import pytest

from studybuddy.salary_data import get_options, query, lookup, load_dataset
from tests.conftest import register, login


def test_dataset_loads_and_valid():
    data = load_dataset()
    assert len(data["entries"]) == 144
    assert len(data["roles"]) == 12
    assert data["meta"]["last_updated"] == "2026-10-01"


def test_query_filters():
    rows = query(role="Software Development Engineer", tier="tier1", band="0-1")
    assert len(rows) == 1
    r = rows[0]
    assert r["min_lpa"] == 4.0 and r["median_lpa"] == 8.0 and r["max_lpa"] == 14.0
    assert "Bengaluru" in r["cities"]


def test_query_invalid_filter_returns_empty():
    assert query(role="Astronaut") == []
    assert query(tier="tier9") == []
    assert query(band="99-100") == []


def test_lookup_miss_returns_none():
    assert lookup("Nope", "tier1", "0-1") is None


def test_page_renders_public(client):
    r = client.get("/salary")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Salary Explorer" in html
    assert "Indicative market ranges" in html
    assert "last updated" in html
    # anonymous visitors get the login CTA, not the compare box
    assert "Log in</a> to compare" in html
    assert 'id="cmpVal"' not in html


def test_page_compare_visible_when_authed(client):
    register(client)
    login(client)
    html = client.get("/salary").get_data(as_text=True)
    assert 'id="cmpVal"' in html
    assert "your expected salary" in html


def test_data_api_all(client):
    r = client.get("/salary/data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert len(body["entries"]) == 144


def test_data_api_filtered(client):
    r = client.get("/salary/data", query_string={
        "role": "Data Analyst", "tier": "tier2", "band": "1-3"})
    body = r.get_json()
    assert body["success"] is True
    assert len(body["entries"]) == 1
    e = body["entries"][0]
    assert e["role"] == "Data Analyst"
    assert e["tier_label"] == "Tier 2"
    assert e["min_lpa"] <= e["median_lpa"] <= e["max_lpa"]


def test_data_api_invalid_filter_empty(client):
    r = client.get("/salary/data", query_string={"role": "'; DROP TABLE"})
    assert r.status_code == 200
    assert r.get_json()["entries"] == []


def test_options_embedded_in_page(client):
    html = client.get("/salary").get_data(as_text=True)
    assert "Software Development Engineer" in html
    assert "Tier 1" in html
