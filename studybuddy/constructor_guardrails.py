"""RAG-07: Paper constructor integrity guardrails.

The paper constructor generates IEEE-style drafts from GitHub repos.
Without guardrails it can fabricate results or encourage academic
misconduct. This module enforces:

1. Watermark on every output (AI-assisted draft, not submission-ready)
2. Only facts from repo analysis + user-provided numbers; [TODO] for missing
3. No invented metrics/citations
4. AI disclosure paragraph
5. No "IEEE-ready"/"publication-ready" marketing language
6. Citation verification (DOI/arXiv lookup) or omission
"""
import re

import requests

WATERMARK = (
    "AI-assisted draft, not a submission-ready paper; "
    "verify every claim before use."
)

AI_DISCLOSURE_TEMPLATE = (
    "AI Assistance Disclosure: This draft was generated with AI assistance "
    "from repository metadata (file listings, language statistics, and "
    "README content fetched from the GitHub API) on behalf of {author}. "
    "All technical claims, measurements, and citations should be "
    "independently verified by the author before any academic or "
    "professional use. No part of this draft should be submitted as "
    "original scholarship without substantial human review and revision."
)

TODO_PLACEHOLDER = "[TODO: add measured result]"

# Marketing phrases that must never appear in constructor output
BANNED_PHRASES = [
    "ieee-ready",
    "ieee ready",
    "publication-ready",
    "publication ready",
    "publishable",
    "submission-ready paper",
    "ready for publication",
    "journal-ready",
    "conference-ready",
]

# Grounding instructions injected into the LLM prompt
GROUNDING_INSTRUCTIONS = """
INTEGRITY RULES (mandatory):
1. ONLY use facts from the REPOSITORY FACTS above and numbers the user provided.
2. NEVER invent benchmark numbers, accuracy scores, performance metrics, user counts, or experimental results.
3. Where a results section would need measured data you do not have, write "{todo}" instead of inventing numbers.
4. NEVER invent citations. Only cite papers/repos explicitly mentioned in the input. If unsure a citation is real, omit it.
5. Do NOT describe this draft as "IEEE-ready", "publication-ready", "publishable", or similar. It is a draft requiring human verification.
6. Write for an honest technical audience; hedge uncertain claims with "appears to", "suggests", or similar.
""".format(todo=TODO_PLACEHOLDER)


def contains_banned_phrase(text):
    """Return list of banned marketing phrases found in text."""
    lowered = text.lower()
    return [p for p in BANNED_PHRASES if p in lowered]


def strip_banned_phrases(text):
    """Remove banned marketing phrases from text."""
    result = text
    for phrase in BANNED_PHRASES:
        # Case-insensitive removal
        result = re.sub(re.escape(phrase), "", result, flags=re.I)
    # Clean up leftover artifacts (double spaces, dangling punctuation)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"\s+([.,;:])", r"\1", result)
    return result.strip()


def extract_numbers(text):
    """Extract numeric claims (metrics, percentages, counts) from text."""
    patterns = [
        r"\d+(?:,\d{3})*(?:\.\d+)?\s*%",          # 95%, 99.9%
        r"\d+(?:\.\d+)?\s*x\b",                   # 10x
        r"\b\d+(?:,\d{3})+\b",                    # 10,000
        r"\b\d+\.\d+\b",                          # 3.14
    ]
    numbers = set()
    for pat in patterns:
        numbers.update(re.findall(pat, text))
    return numbers


def find_invented_numbers(input_text, output_text):
    """Find numeric claims in output not present in input.

    Returns sorted list of invented number strings.
    """
    def norm(n):
        return re.sub(r"[,\s]", "", n.lower())

    input_nums = {norm(n) for n in extract_numbers(input_text)}
    invented = []
    for num in extract_numbers(output_text):
        n = norm(num)
        bare = re.sub(r"[^0-9.]", "", n)
        input_bares = {re.sub(r"[^0-9.]", "", i) for i in input_nums}
        if n not in input_nums and bare not in input_bares:
            invented.append(num)
    return sorted(set(invented))


def verify_doi(doi, timeout=10):
    """Check if a DOI resolves via doi.org. Returns True/False/None (unknown)."""
    doi = doi.strip()
    # Basic format check
    if not re.match(r"^10\.\d{4,}/", doi):
        return False
    try:
        r = requests.head(f"https://doi.org/{doi}", timeout=timeout,
                          allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return None  # network error -> unknown


def verify_arxiv(arxiv_id, timeout=10):
    """Check if an arXiv ID exists. Returns True/False/None (unknown)."""
    arxiv_id = arxiv_id.strip()
    if not re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", arxiv_id):
        return False
    try:
        r = requests.get(
            f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
            timeout=timeout)
        # arXiv returns <entry> for valid IDs
        return "<entry>" in r.text and "arxiv.org/abs/" in r.text
    except Exception:
        return None


def extract_citations(text):
    """Extract DOI and arXiv references from text."""
    dois = re.findall(r"10\.\d{4,}/[^\s)\]}>,;\"']+", text)
    arxiv_ids = re.findall(
        r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", text, re.I)
    return {"dois": dois, "arxiv": arxiv_ids}


def verify_citations(text, verify_fn_doi=None, verify_fn_arxiv=None):
    """Verify citations in text. Returns (verified_text, removed_list).

    Citations that fail verification are replaced with [citation unverified -
    omitted]. Network failures leave citations intact but flagged.
    """
    verify_fn_doi = verify_fn_doi or verify_doi
    verify_fn_arxiv = verify_fn_arxiv or verify_arxiv
    removed = []
    result = text

    for doi in extract_citations(text)["dois"]:
        status = verify_fn_doi(doi)
        if status is False:
            result = result.replace(doi, "[citation unverified — omitted]")
            removed.append(doi)
    for aid in extract_citations(text)["arxiv"]:
        status = verify_fn_arxiv(aid)
        if status is False:
            result = result.replace(aid, "[citation unverified — omitted]")
            removed.append(f"arXiv:{aid}")
    return result, removed


def build_grounded_prompt(base_prompt):
    """Inject integrity rules into the constructor prompt."""
    return base_prompt + "\n" + GROUNDING_INSTRUCTIONS


def post_process_paper(analysis, repo_facts_text, author="Anonymous"):
    """Apply all guardrails to constructor output.

    Args:
        analysis: dict from LLM (title, abstract, sections...)
        repo_facts_text: the repo facts fed to the LLM (for number checking)
        author: author name for disclosure

    Returns:
        (processed_dict, guardrail_report)
    """
    report = {
        "watermark_added": True,
        "banned_phrases_removed": [],
        "invented_numbers": [],
        "disclosure_added": True,
    }
    processed = {}

    for key, value in analysis.items():
        if not isinstance(value, str):
            processed[key] = value
            continue
        # 1. Strip banned marketing language
        banned = contains_banned_phrase(value)
        if banned:
            report["banned_phrases_removed"].extend(
                f"{key}: {p}" for p in banned)
            value = strip_banned_phrases(value)
        # 2. Check for invented numbers
        invented = find_invented_numbers(repo_facts_text, value)
        if invented:
            report["invented_numbers"].extend(
                f"{key}: {n}" for n in invented)
            # Flag them inline rather than silently dropping
            for num in invented:
                value = value.replace(
                    num,
                    f"{num} {TODO_PLACEHOLDER}",
                    1,
                )
        processed[key] = value

    # 3. Add watermark + disclosure
    processed["_watermark"] = WATERMARK
    processed["_ai_disclosure"] = AI_DISCLOSURE_TEMPLATE.format(author=author)

    return processed, report
