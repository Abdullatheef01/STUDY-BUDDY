"""ENG-13: Grounded generation — prevent LLM from inventing achievements.

Post-processes LLM output to detect numbers/entities not present in the
input, flags them as unverified claims.
"""
import re

from studybuddy.prompt_lib import render_prompt


def extract_numbers(text):
    """Extract all numbers (with units/context) from text."""
    # Matches: 30%, $50k, 10,000, 3.5x, 2024, Rs. 5 lakh, etc.
    patterns = [
        r"\d+(?:,\d{3})*(?:\.\d+)?\s*%",           # percentages
        r"[$₹]\s*\d+(?:,\d{3})*(?:\.\d+)?[kmb]?",  # currency
        r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:x|times)",  # multipliers
        r"\b\d+(?:,\d{3})+\b",                     # thousands (10,000)
        r"\b(?:19|20)\d{2}\b",                     # years
        r"\b\d+(?:\.\d+)?\s*(?:lakh|crore|thousand|million|billion)\b",  # Indian units
    ]
    numbers = set()
    for pat in patterns:
        numbers.update(re.findall(pat, text, re.I))
    # Also bare numbers (but not too aggressively)
    for m in re.findall(r"\b\d+(?:\.\d+)?\b", text):
        # Skip if it's part of a larger already-captured number
        if not any(m in n for n in numbers):
            numbers.add(m)
    return numbers


def normalize_number(n):
    """Normalize for comparison (strip commas, lowercase, strip)."""
    return re.sub(r"[,\s]", "", n.lower())


def find_unverified_claims(input_text, output_text):
    """Find numbers in output that don't appear in input.

    Returns list of unverified number strings.
    """
    input_numbers = {normalize_number(n) for n in extract_numbers(input_text)}
    output_numbers = extract_numbers(output_text)
    unverified = []
    for num in output_numbers:
        norm = normalize_number(num)
        # Check if this number (or a variant) appears in input
        if norm not in input_numbers:
            # Also check without units (e.g. "30" vs "30%")
            bare = re.sub(r"[^0-9.]", "", norm)
            input_bares = {re.sub(r"[^0-9.]", "", n) for n in input_numbers}
            if bare not in input_bares:
                unverified.append(num)
    return sorted(set(unverified))


def flag_unverified_claims(input_text, output_text):
    """Wrap unverified numbers in [UNVERIFIED] markers.

    Returns (flagged_text, unverified_list).
    """
    unverified = find_unverified_claims(input_text, output_text)
    flagged = output_text
    for num in unverified:
        # Wrap first occurrence
        flagged = flagged.replace(
            num, f"[UNVERIFIED: {num} — edit or remove]", 1)
    return flagged, unverified


def grounded_rewrite_prompt(original_bullet):
    """Generate a prompt that instructs the model to stay grounded.

    Uses the versioned prompt library (prompts/grounded-rewrite/v1.md).
    """
    return render_prompt("grounded-rewrite", "v1",
                         original_bullet=original_bullet)
