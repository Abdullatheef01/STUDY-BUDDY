"""Internship / scholarship / exam opportunity radar (Wave 1 feature #9).

Serves a curated, built-in dataset (data/opportunities.json) of opportunities
with deadlines. The dataset is a curated starter set — deadlines are indicative
and the UI must tell users to verify on official sites.

OPPORTUNITY JSON SCHEMA (for extending data/opportunities.json):
{
    "meta": {
        "last_updated": "YYYY-MM-DD",   # required, ISO date
        "notice": "string",              # required, shown on the board
        "schema_doc": "string"           # required, pointer to this docstring
    },
    "opportunities": [                   # required, non-empty list
        {
            "id": "kebab-case-unique",   # required, unique across the file
            "title": "string",           # required, <= 120 chars
            "organization": "string",    # required, <= 120 chars
            "type": "internship|scholarship|exam",  # required
            "deadline": "YYYY-MM-DD",    # required ISO date, or null = rolling
            "eligibility": "string",     # required, <= 300 chars
            "link": "https://..."        # required, http(s) URL
        }
    ]
}
"""

import json
import os
from datetime import date
from functools import lru_cache

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "opportunities.json")

TYPES = ("internship", "scholarship", "exam")
CLOSING_SOON_DAYS = 14


class OpportunityDataError(Exception):
    """Raised when the opportunity dataset is missing or malformed."""


def _parse_deadline(value, opp_id):
    if value is None:
        return None
    try:
        year, month, day = (int(p) for p in str(value).split("-"))
        return date(year, month, day)
    except (ValueError, TypeError) as exc:
        raise OpportunityDataError(
            f"Opportunity {opp_id!r} has an invalid deadline.") from exc


@lru_cache(maxsize=1)
def load_dataset():
    """Load and validate the opportunity dataset (cached for process lifetime)."""
    if not os.path.exists(DATA_PATH):
        raise OpportunityDataError("Opportunity dataset not found.")
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise OpportunityDataError("Opportunity dataset is unreadable.") from exc
    meta = data.get("meta") or {}
    for key in ("last_updated", "notice", "schema_doc"):
        if key not in meta:
            raise OpportunityDataError(f"Opportunity dataset meta missing: {key}")
    opps = data.get("opportunities")
    if not isinstance(opps, list) or not opps:
        raise OpportunityDataError("Opportunity dataset has no opportunities.")
    seen = set()
    for o in opps:
        for key in ("id", "title", "organization", "type", "deadline",
                    "eligibility", "link"):
            if key not in o:
                raise OpportunityDataError(
                    f"Opportunity {o.get('id', '?')!r} missing key: {key}")
        if o["id"] in seen:
            raise OpportunityDataError(f"Duplicate opportunity id: {o['id']!r}")
        seen.add(o["id"])
        if o["type"] not in TYPES:
            raise OpportunityDataError(
                f"Opportunity {o['id']!r} has invalid type: {o['type']!r}")
        if len(o["title"]) > 120 or len(o["organization"]) > 120:
            raise OpportunityDataError(
                f"Opportunity {o['id']!r} title/organization too long.")
        if len(o["eligibility"]) > 300:
            raise OpportunityDataError(
                f"Opportunity {o['id']!r} eligibility too long.")
        if not (o["link"].startswith("https://") or o["link"].startswith("http://")):
            raise OpportunityDataError(
                f"Opportunity {o['id']!r} link must be http(s).")
        _parse_deadline(o["deadline"], o["id"])
    return data


def get_meta():
    return dict(load_dataset()["meta"])


def _enrich(o, today):
    """Return the public dict for one opportunity with countdown fields."""
    deadline = _parse_deadline(o["deadline"], o["id"])
    days_left = (deadline - today).days if deadline else None
    return {
        "id": o["id"],
        "title": o["title"],
        "organization": o["organization"],
        "type": o["type"],
        "deadline": o["deadline"],          # ISO string or None (rolling)
        "days_left": days_left,             # int or None
        "closing_soon": days_left is not None and 0 <= days_left <= CLOSING_SOON_DAYS,
        "is_past": days_left is not None and days_left < 0,
        "eligibility": o["eligibility"],
        "link": o["link"],
    }


def list_opportunities(opp_type=None, today=None, include_past=False):
    """List opportunities, optionally filtered by type, sorted by deadline.

    Rolling-deadline (null) entries sort last. Unknown type -> [].
    """
    if opp_type is not None and opp_type not in TYPES:
        return []
    today = today or date.today()
    out = []
    for o in load_dataset()["opportunities"]:
        if opp_type is not None and o["type"] != opp_type:
            continue
        e = _enrich(o, today)
        if e["is_past"] and not include_past:
            continue
        out.append(e)
    out.sort(key=lambda e: (e["deadline"] is None, e["deadline"] or "9999"))
    return out


def get_opportunity(opp_id):
    """Return the enriched opportunity dict, or None if unknown."""
    for o in load_dataset()["opportunities"]:
        if o["id"] == opp_id:
            return _enrich(o, date.today())
    return None


def opp_exists(opp_id):
    return any(o["id"] == opp_id for o in load_dataset()["opportunities"])
