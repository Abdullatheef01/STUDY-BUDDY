"""India salary explorer (Wave 1 feature #8).

Serves a curated, built-in dataset of indicative salary ranges
(data/salary_ranges.json): role x city-tier x experience-band -> min/median/max
in LPA. The data is curated for student guidance (October 2026) and is NOT
live-scraped; callers must surface the disclaimer and last-updated note.
"""

import json
import os
from functools import lru_cache

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "salary_ranges.json")


class SalaryDataError(Exception):
    """Raised when the salary dataset is missing or malformed."""


@lru_cache(maxsize=1)
def load_dataset():
    """Load and validate the salary dataset (cached for the process lifetime)."""
    if not os.path.exists(DATA_PATH):
        raise SalaryDataError("Salary dataset not found.")
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SalaryDataError("Salary dataset is unreadable.") from exc
    for key in ("meta", "roles", "tiers", "experience_bands", "entries"):
        if key not in data:
            raise SalaryDataError(f"Salary dataset missing key: {key}")
    for e in data["entries"]:
        for k in ("role", "tier", "experience_band", "min_lpa", "median_lpa", "max_lpa"):
            if k not in e:
                raise SalaryDataError("Salary dataset entry is malformed.")
        if not (0 < e["min_lpa"] <= e["median_lpa"] <= e["max_lpa"]):
            raise SalaryDataError("Salary dataset has an inconsistent range.")
    return data


def get_options():
    """Return filter options: roles, tiers, experience bands + meta."""
    data = load_dataset()
    return {
        "roles": list(data["roles"]),
        "tiers": {k: {"label": v["label"], "cities": list(v["cities"])}
                  for k, v in data["tiers"].items()},
        "experience_bands": list(data["experience_bands"]),
        "meta": dict(data["meta"]),
    }


def query(role=None, tier=None, band=None):
    """Return matching salary entries. All filters optional; invalid values -> []."""
    data = load_dataset()
    valid_roles = set(data["roles"])
    valid_tiers = set(data["tiers"])
    valid_bands = set(data["experience_bands"])
    if role is not None and role not in valid_roles:
        return []
    if tier is not None and tier not in valid_tiers:
        return []
    if band is not None and band not in valid_bands:
        return []
    out = []
    for e in data["entries"]:
        if role is not None and e["role"] != role:
            continue
        if tier is not None and e["tier"] != tier:
            continue
        if band is not None and e["experience_band"] != band:
            continue
        out.append({
            "role": e["role"],
            "tier": e["tier"],
            "tier_label": data["tiers"][e["tier"]]["label"],
            "cities": list(data["tiers"][e["tier"]]["cities"]),
            "experience_band": e["experience_band"],
            "min_lpa": e["min_lpa"],
            "median_lpa": e["median_lpa"],
            "max_lpa": e["max_lpa"],
        })
    return out


def lookup(role, tier, band):
    """Return the single entry for an exact role/tier/band, or None."""
    rows = query(role=role, tier=tier, band=band)
    return rows[0] if rows else None
