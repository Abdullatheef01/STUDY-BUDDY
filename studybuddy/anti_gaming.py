"""ENG-04: Anti-gaming and hidden-text detection.

Detects resume gaming tactics:
1. Hidden text (white-on-white, tiny fonts) — via character-level PDF data
2. Abnormal keyword density (keyword stuffing)
3. Keyword count caps and de-duplication
"""
import re
from collections import Counter


def detect_keyword_stuffing(text, threshold=0.03, min_tokens=50):
    """Flag tokens exceeding threshold% of all tokens (outside skills section).

    Returns list of (token, ratio) for suspicious tokens.
    """
    # Remove skills section to avoid false positives
    text_no_skills = re.sub(
        r"(?is)^\s*(skills|technical skills)[^\n]*\n(.*?)(?=^\s*[a-z ]+:?$|\Z)",
        "", text)
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]*", text_no_skills.lower())
    if len(tokens) < min_tokens:
        return []  # too short to judge
    total = len(tokens)
    counts = Counter(tokens)
    # Ignore common stopwords
    stopwords = frozenset({
        "the", "and", "for", "with", "from", "that", "this", "have",
        "been", "were", "are", "was", "had", "has", "will", "would",
        "can", "could", "should", "may", "might", "must", "shall",
        "a", "an", "of", "to", "in", "on", "at", "by", "as", "is",
    })
    suspicious = []
    for token, count in counts.most_common():
        if token in stopwords or len(token) < 3:
            continue
        ratio = count / total
        if ratio > threshold:
            suspicious.append((token, round(ratio, 4)))
    return suspicious


def cap_keyword_counts(skill_counts, max_per_skill=5):
    """Cap and de-duplicate keyword counts (ENG-01/ENG-04).

    Returns (capped_dict, was_capped_bool).
    """
    capped = {}
    was_capped = False
    for skill, count in skill_counts.items():
        if count > max_per_skill:
            capped[skill] = max_per_skill
            was_capped = True
        else:
            capped[skill] = count
    return capped, was_capped


def detect_hidden_text_chars(chars):
    """Detect hidden text from pdfplumber/pdfium character data.

    Args:
        chars: list of dicts with keys: text, size, color (RGB tuple or None),
               x0, y0, x1, y1, page_width, page_height

    Returns:
        dict with hidden_char_count, reasons (list of strings)
    """
    hidden = 0
    reasons = set()
    for ch in chars:
        text = ch.get("text", "")
        if not text.strip():
            continue
        size = ch.get("size", 12)
        color = ch.get("color")  # (r, g, b) 0-1 or None
        x0, y0 = ch.get("x0", 0), ch.get("y0", 0)
        pw, ph = ch.get("page_width", 612), ch.get("page_height", 792)

        is_hidden = False
        # Tiny font
        if size < 4:
            is_hidden = True
            reasons.add(f"Tiny font ({size:.1f}pt < 4pt)")
        # White or near-white text
        if color and all(c > 0.95 for c in color[:3]):
            is_hidden = True
            reasons.add("White/near-white text color")
        # Outside page bounds
        if x0 < -10 or y0 < -10 or x0 > pw + 10 or y0 > ph + 10:
            is_hidden = True
            reasons.add("Text outside page bounds")
        if is_hidden:
            hidden += 1
    return {
        "hidden_char_count": hidden,
        "reasons": sorted(reasons),
        "has_hidden_text": hidden > 10,  # threshold to avoid false positives
    }


def gaming_risk_report(text, skill_counts=None, pdf_chars=None):
    """Generate a gaming risk report for a resume.

    Returns dict with warnings list and risk_level (low/medium/high).
    """
    warnings = []

    # Keyword stuffing
    stuffed = detect_keyword_stuffing(text)
    for token, ratio in stuffed[:5]:
        warnings.append(
            f"Keyword '{token}' appears {ratio:.1%} of all words "
            f"(possible keyword stuffing)")

    # Count caps
    if skill_counts:
        _, was_capped = cap_keyword_counts(skill_counts)
        if was_capped:
            warnings.append(
                "Some skill mentions exceeded the cap and were "
                "de-duplicated (possible keyword stuffing)")

    # Hidden text
    if pdf_chars:
        hidden = detect_hidden_text_chars(pdf_chars)
        if hidden["has_hidden_text"]:
            warnings.append(
                f"Hidden text detected ({hidden['hidden_char_count']} chars): "
                f"{'; '.join(hidden['reasons'])}. "
                "Invisible text can be flagged by recruiters and parsers.")

    risk = "low"
    if len(warnings) >= 3:
        risk = "high"
    elif warnings:
        risk = "medium"

    return {"warnings": warnings, "risk_level": risk}
