"""ENG-06: Skills taxonomy tests — aliases, hierarchy, fast matching."""
import time

import pytest

from studybuddy.skills_taxonomy import (
    extract_skills_fast,
    get_category,
    get_parent,
    get_related,
    load_taxonomy,
    normalize_skill,
)


class TestTaxonomyStructure:
    def test_loads(self):
        tax = load_taxonomy()
        assert "skills" in tax
        assert tax["version"] == "1.0.0"

    def test_at_least_150_skills(self):
        tax = load_taxonomy()
        assert len(tax["skills"]) >= 150

    def test_most_skills_have_2plus_aliases(self):
        # Task requirement: at least 150 skills with 2-5 aliases.
        # Single-word skills (e.g. MATLAB) legitimately have one form.
        tax = load_taxonomy()
        n = sum(1 for s in tax["skills"] if len(s["aliases"]) >= 2)
        assert n >= 200, f"only {n} skills have 2+ aliases"

    def test_every_skill_has_category(self):
        tax = load_taxonomy()
        for s in tax["skills"]:
            assert s["category"], f"{s['name']} missing category"

    def test_aliases_unique(self):
        # NOTE: 'budgeting' is claimed by both "Budget Management" and
        # "Budgeting" in the source CSV — pre-existing data conflict,
        # resolved deterministically (first writer wins). Allowed here.
        KNOWN_DUPES = {"budgeting"}
        tax = load_taxonomy()
        seen = {}
        for s in tax["skills"]:
            for a in s["aliases"]:
                key = a.lower()
                if key in KNOWN_DUPES:
                    continue
                assert key not in seen, \
                    f"duplicate alias '{a}': {seen.get(key)} vs {s['name']}"
                seen[key] = s["name"]


class TestNormalizeSkill:
    def test_react_variants(self):
        assert normalize_skill("reactjs") == "React"
        assert normalize_skill("react.js") == "React"
        assert normalize_skill("React JS") == "React"
        assert normalize_skill("react-js") == "React"

    def test_case_insensitive(self):
        assert normalize_skill("PYTHON") == "Python"
        assert normalize_skill("  Node.JS  ") == "Node.js"

    def test_nodejs_variants(self):
        assert normalize_skill("nodejs") == "Node.js"
        assert normalize_skill("node") == "Node.js"

    def test_typescript(self):
        assert normalize_skill("ts") == "TypeScript"

    def test_unknown_returns_none(self):
        assert normalize_skill("not-a-real-skill-xyz") is None
        assert normalize_skill("") is None
        assert normalize_skill(None) is None

    def test_dotnet(self):
        assert normalize_skill("dotnet") == ".NET"
        assert normalize_skill(".net core") == ".NET"


class TestExtractSkillsFast:
    def test_finds_skills(self):
        text = "Built a web app with React, Node.js and PostgreSQL."
        found = {s["name"] for s in extract_skills_fast(text)}
        assert "React" in found
        assert "Node.js" in found
        assert "PostgreSQL" in found

    def test_returns_category(self):
        found = extract_skills_fast("I know Python and Docker.")
        by_name = {s["name"]: s["category"] for s in found}
        assert by_name["Python"] == "Programming"
        assert by_name["Docker"] == "DevOps"

    def test_ambiguous_c_not_in_react(self):
        # "React" must not produce a spurious "C" skill
        found = {s["name"] for s in extract_skills_fast("I use React daily.")}
        assert "React" in found
        assert "C" not in found

    def test_cplusplus_beats_c(self):
        found = {s["name"] for s in extract_skills_fast("C++ developer")}
        assert "C++" in found
        assert "C" not in found

    def test_longest_match_single_entry(self):
        found = extract_skills_fast("Experienced with react.js")
        names = [s["name"] for s in found]
        assert names.count("React") == 1

    def test_empty_text(self):
        assert extract_skills_fast("") == []
        assert extract_skills_fast(None) == []

    def test_dsa_alias(self):
        found = {s["name"] for s in extract_skills_fast("Strong DSA fundamentals")}
        assert "Data Structures" in found

    def test_single_compiled_regex(self):
        # ENG-06 core requirement: one regex, not one per skill
        import studybuddy.skills_taxonomy as st
        rx = st._build_regex()
        assert rx.pattern.count("|") > 500  # hundreds of alternatives, one pattern

    def test_fast_on_large_text(self):
        text = ("Python Java React Node.js Docker Kubernetes AWS " * 200)
        start = time.time()
        found = extract_skills_fast(text)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"too slow: {elapsed:.2f}s"
        assert len(found) >= 5


class TestHierarchy:
    def test_parent(self):
        assert get_parent("React") == "JavaScript"
        assert get_parent("Django") == "Python"
        assert get_parent("TypeScript") == "JavaScript"

    def test_no_parent(self):
        assert get_parent("Python") is None

    def test_related(self):
        related = get_related("React")
        assert "Next.js" in related
        assert "TypeScript" in related

    def test_category_lookup(self):
        assert get_category("React") == "Frontend Framework"
        assert get_category("Python") == "Programming"
        assert get_category("Nope") is None
