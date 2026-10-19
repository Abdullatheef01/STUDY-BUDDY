"""ENG-06: Skills taxonomy with aliases, hierarchy, and fast matching.

Replaces the one-regex-per-skill loop in models/skill_extractor.py with a
single compiled alternation regex over all aliases (803 unique aliases).

Public API:
    load_taxonomy()        -> the parsed taxonomy dict
    normalize_skill(text)  -> canonical skill name or None
    extract_skills_fast(text) -> [{"name": ..., "category": ...}, ...]
    get_parent(name)       -> parent skill name or None
    get_related(name)      -> list of related skill names
"""
import json
import os
import re

_TAXONOMY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "taxonomy", "skills_taxonomy.json")

_taxonomy = None
_alias_index = None   # alias (lower) -> canonical name
_skill_index = None   # canonical name -> skill entry
_compiled_re = None


def load_taxonomy():
    """Load (and cache) the taxonomy JSON."""
    global _taxonomy
    if _taxonomy is None:
        with open(_TAXONOMY_PATH, encoding="utf-8") as f:
            _taxonomy = json.load(f)
    return _taxonomy


def _build_indexes():
    global _alias_index, _skill_index
    if _alias_index is not None:
        return
    tax = load_taxonomy()
    _alias_index = {}
    _skill_index = {}
    for skill in tax["skills"]:
        name = skill["name"]
        _skill_index[name] = skill
        for alias in skill["aliases"]:
            # first writer wins (deterministic, CSV order)
            _alias_index.setdefault(alias.lower(), name)


def _build_regex():
    global _compiled_re
    if _compiled_re is not None:
        return _compiled_re
    _build_indexes()
    # longest-first so "react.js" beats "react", "c++" beats "c"
    aliases = sorted(_alias_index.keys(), key=len, reverse=True)
    pattern = (r"(?<![a-zA-Z0-9+#.])("
               + "|".join(re.escape(a) for a in aliases)
               + r")(?![a-zA-Z0-9])")
    _compiled_re = re.compile(pattern, re.IGNORECASE)
    return _compiled_re


def normalize_skill(text):
    """Map any alias/variant to the canonical skill name. None if unknown.

    >>> normalize_skill("reactjs")
    'React'
    >>> normalize_skill("  REACT.JS  ")
    'React'
    >>> normalize_skill("not-a-real-skill-xyz") is None
    True
    """
    if not text or not isinstance(text, str):
        return None
    _build_indexes()
    return _alias_index.get(text.strip().lower())


def extract_skills_fast(text):
    """Extract skills with ONE compiled regex (not one per skill).

    Returns a list of {"name", "category"} dicts with canonical names,
    sorted by category then name — same shape as
    models.skill_extractor.extract_skills for drop-in compatibility.
    """
    if not text:
        return []
    rx = _build_regex()
    found = {}
    for m in rx.finditer(text):
        canonical = _alias_index.get(m.group(1).lower())
        if canonical:
            entry = _skill_index[canonical]
            found[canonical] = entry["category"]
    result = [{"name": name, "category": cat}
              for name, cat in found.items()]
    result.sort(key=lambda x: (x["category"], x["name"]))
    return result


def get_parent(name):
    """Return the parent skill name, or None."""
    _build_indexes()
    entry = _skill_index.get(name)
    return entry.get("parent") if entry else None


def get_related(name):
    """Return related skill names (may be empty)."""
    _build_indexes()
    entry = _skill_index.get(name)
    return list(entry.get("related", [])) if entry else []


def get_category(name):
    """Return the category of a canonical skill name, or None."""
    _build_indexes()
    entry = _skill_index.get(name)
    return entry.get("category") if entry else None
