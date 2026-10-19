"""LLM-05: Versioned prompt library.

Prompts live in prompts/<feature>/<version>.md with {variables}.
The prompt version is logged with results for reproducibility.

Prompts must never contain secrets (API keys, tokens, passwords).
"""
import logging
import os
import re

log = logging.getLogger("acra")

_PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
)

# Heuristic secret patterns — prompts must not contain these.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),           # OpenAI-style keys
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),        # Google API keys
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}"),
]


class PromptNotFoundError(FileNotFoundError):
    """Raised when a prompt file does not exist."""


class PromptSecretError(ValueError):
    """Raised when a prompt appears to contain a secret."""


def prompt_path(feature, version="v1"):
    """Return the filesystem path for a prompt."""
    return os.path.join(_PROMPTS_DIR, feature, f"{version}.md")


def load_prompt(feature, version="v1"):
    """Load a prompt template. Raises PromptNotFoundError if missing."""
    path = prompt_path(feature, version)
    if not os.path.isfile(path):
        raise PromptNotFoundError(
            f"Prompt not found: {feature}/{version} "
            f"(expected at {path})")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    _check_no_secrets(content, feature, version)
    log.info("prompt_loaded feature=%s version=%s", feature, version)
    return content


def _check_no_secrets(content, feature, version):
    for pat in _SECRET_PATTERNS:
        if pat.search(content):
            raise PromptSecretError(
                f"Prompt {feature}/{version} appears to contain a secret. "
                "Prompts must never contain secrets.")


def render_prompt(feature, version="v1", **variables):
    """Load and render a prompt with {variables} substituted.

    Raises KeyError listing missing variables, PromptNotFoundError
    for unknown prompts.
    """
    template = load_prompt(feature, version)
    try:
        return template.format(**variables)
    except KeyError as e:
        # Find all placeholders to give a helpful error
        needed = set(re.findall(r"\{(\w+)\}", template))
        missing = needed - set(variables.keys())
        raise KeyError(
            f"Prompt {feature}/{version} missing variables: "
            f"{sorted(missing)}") from e


def list_prompts():
    """Return {feature: [versions]} for all prompts on disk."""
    result = {}
    if not os.path.isdir(_PROMPTS_DIR):
        return result
    for feature in sorted(os.listdir(_PROMPTS_DIR)):
        fdir = os.path.join(_PROMPTS_DIR, feature)
        if not os.path.isdir(fdir):
            continue
        versions = sorted(
            fn[:-3] for fn in os.listdir(fdir) if fn.endswith(".md"))
        if versions:
            result[feature] = versions
    return result


def prompt_version_tag(feature, version="v1"):
    """Short tag to log alongside LLM results, e.g. 'jd-match:v1'."""
    return f"{feature}:{version}"
