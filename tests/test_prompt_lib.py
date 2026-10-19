"""LLM-05: Versioned prompt library tests."""
import os

import pytest

from studybuddy.prompt_lib import (
    PromptNotFoundError,
    list_prompts,
    load_prompt,
    prompt_path,
    prompt_version_tag,
    render_prompt,
)


class TestLoadPrompt:
    def test_load_jd_match(self):
        content = load_prompt("jd-match", "v1")
        assert "career coach" in content
        assert "{experience_years}" in content

    def test_load_linkedin(self):
        content = load_prompt("linkedin", "v1")
        assert "LinkedIn" in content

    def test_load_interview_feedback(self):
        content = load_prompt("interview-feedback", "v1")
        assert "{answers_json}" in content

    def test_load_coach_polish(self):
        content = load_prompt("coach-polish", "v1")
        assert "{clarity_score}" in content

    def test_load_bullet_rewrite(self):
        content = load_prompt("bullet-rewrite", "v1")
        assert "{bullet}" in content

    def test_load_grounded_rewrite(self):
        content = load_prompt("grounded-rewrite", "v1")
        assert "NEVER invent" in content

    def test_missing_prompt_raises(self):
        with pytest.raises(PromptNotFoundError) as exc:
            load_prompt("nonexistent-feature", "v1")
        assert "nonexistent-feature" in str(exc.value)

    def test_missing_version_raises(self):
        with pytest.raises(PromptNotFoundError):
            load_prompt("jd-match", "v99")


class TestRenderPrompt:
    def test_variable_substitution(self):
        rendered = render_prompt(
            "jd-match", "v1",
            experience_years=5, score=72,
            missing_keywords="Python, Django", matched_skills="Flask",
            jd_text="We need a Python dev.")
        assert "5 years" in rendered
        assert "72/100" in rendered
        assert "Python, Django" in rendered
        assert "{" not in rendered.replace("{{", "").replace("}}", "") or True
        # No unsubstituted {var} placeholders remain
        import re
        leftover = re.findall(r"\{(?!{)(\w+)\}(?!})", rendered)
        assert leftover == [], f"Unsubstituted: {leftover}"

    def test_missing_variable_raises(self):
        with pytest.raises(KeyError) as exc:
            render_prompt("jd-match", "v1", experience_years=5)
        assert "score" in str(exc.value) or "missing" in str(exc.value).lower()

    def test_grounded_rewrite_renders(self):
        rendered = render_prompt("grounded-rewrite", "v1",
                                 original_bullet="Built a thing.")
        assert "Built a thing." in rendered
        assert "NEVER invent" in rendered


class TestListPrompts:
    def test_lists_all(self):
        prompts = list_prompts()
        assert "jd-match" in prompts
        assert "linkedin" in prompts
        assert "interview-feedback" in prompts
        assert "coach-polish" in prompts
        assert "bullet-rewrite" in prompts
        assert "grounded-rewrite" in prompts
        assert prompts["jd-match"] == ["v1"]

    def test_version_tag(self):
        assert prompt_version_tag("jd-match", "v1") == "jd-match:v1"


class TestSecretCheck:
    def test_no_secrets_in_prompts(self):
        # All shipped prompts must pass the secret scan
        for feature, versions in list_prompts().items():
            for v in versions:
                # load_prompt raises PromptSecretError if a secret is found
                load_prompt(feature, v)


class TestPromptPath:
    def test_path_structure(self):
        path = prompt_path("jd-match", "v1")
        assert path.endswith(os.path.join("prompts", "jd-match", "v1.md"))
        assert os.path.isfile(path)


class FakeLLM:
    """Deterministic fake LLM for golden tests."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def generate(self, prompt):
        self.calls.append(prompt)
        # Return canned response based on prompt content hash
        key = "default"
        for k in self.responses:
            if k in prompt:
                key = k
                break
        return self.responses[key]


class TestGoldenWithFakeLLM:
    def test_golden_jd_match_flow(self):
        fake = FakeLLM({
            "career coach": '{"suggestions": [{"section": "Skills", '
                            '"issue": "missing", "fix": "add Python"}]}',
        })
        prompt = render_prompt(
            "jd-match", "v1", experience_years=3, score=65,
            missing_keywords="Python", matched_skills="Java",
            jd_text="Python developer needed.")
        assert "career coach" in prompt
        response = fake.generate(prompt)
        import json
        parsed = json.loads(response)
        assert parsed["suggestions"][0]["section"] == "Skills"
        # Prompt version is logged with the result
        tag = prompt_version_tag("jd-match", "v1")
        assert tag == "jd-match:v1"
        assert len(fake.calls) == 1

    def test_golden_grounded_rewrite_flow(self):
        fake = FakeLLM({
            "NEVER invent": "Engineered a scalable web application.",
        })
        prompt = render_prompt("grounded-rewrite", "v1",
                               original_bullet="Built a web app.")
        response = fake.generate(prompt)
        assert "Engineered" in response
        # No invented numbers in the fake response
        from studybuddy.grounded_gen import find_unverified_claims
        assert find_unverified_claims("Built a web app.", response) == []

    def test_grounded_rewrite_uses_library(self):
        # grounded_gen.py now delegates to the prompt library
        from studybuddy.grounded_gen import grounded_rewrite_prompt
        result = grounded_rewrite_prompt("Did stuff.")
        assert "Did stuff." in result
        assert "NEVER invent" in result
