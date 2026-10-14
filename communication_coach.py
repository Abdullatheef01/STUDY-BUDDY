"""Communication coach: filler words, pacing, clarity (Wave 2 feature #14).

Analyzes a pasted interview answer / transcript against the committed
filler library (data/filler_words.json, 104 entries) plus structural
metrics: sentence length / pacing, passive voice, hedge density.

Output: 0-100 clarity score with a transparent breakdown, highlighted
problem spots with per-issue suggestions, a rule-based cleaned rewrite,
and practice drills. Gemini (wired in unified_app.py) can polish the
rewrite and drills; the rule-based versions below always work.
"""

import json
import os
import re

BANK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "filler_words.json")

_bank = None


def _load_bank():
    global _bank
    if _bank is None:
        with open(BANK_PATH, encoding="utf-8") as f:
            _bank = json.load(f)
    # longest phrases first so "so basically" matches before "so"
    _bank.sort(key=lambda e: len(e["word"]), reverse=True)
    return _bank


MIN_CHARS = 50
MAX_CHARS = 10000

PASSIVE_RE = re.compile(
    r"\b(was|were|am|is|are|been|be|being)\s+([a-z]+ed|built|written|done|"
    r"made|taken|given|shown|found|led|sent|paid|said|thought|brought)\b",
    re.IGNORECASE)


def _sentences(text):
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip())]
    return [s for s in parts if s]


def _words(text):
    return re.findall(r"[A-Za-z][A-Za-z0-9'\-]*", text or "")


def find_filler_hits(text):
    """Return list of {word, category, severity, alternatives, note, count, positions}."""
    lowered = (text or "").lower()
    hits = []
    for entry in _load_bank():
        w = entry["word"].lower()
        pattern = r"(?<![a-z])" + re.escape(w) + r"(?![a-z])"
        positions = [m.start() for m in re.finditer(pattern, lowered)]
        if positions:
            hits.append({
                "word": entry["word"],
                "category": entry["category"],
                "severity": entry["severity"],
                "alternatives": entry.get("alternatives") or [],
                "note": entry.get("note") or "",
                "count": len(positions),
                "positions": positions[:20],
            })
    # most severe / most frequent first
    hits.sort(key=lambda h: (-h["severity"], -h["count"]))
    return hits


def _rewrite_clean(text, hits):
    """Rule-based cleanup: drop severity-3 fillers, apply first alternatives."""
    out = text
    for h in hits:
        w = h["word"]
        alt = (h["alternatives"] or [""])[0]
        pattern = re.compile(r"(?<![a-zA-Z])" + re.escape(w) + r"(?![a-zA-Z])",
                             re.IGNORECASE)
        if h["severity"] >= 3:
            out = pattern.sub("", out)
        elif alt:
            # replace only the first occurrence to stay conservative
            out = pattern.sub(alt, out, count=1)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    return out.strip()


def analyze_transcript(text):
    """Full analysis. Returns a JSON-serializable report dict."""
    text = (text or "").strip()
    words = _words(text)
    sentences = _sentences(text)
    n_words = len(words)
    n_sent = len(sentences)

    filler_hits = find_filler_hits(text)
    filler_events = sum(h["count"] for h in filler_hits)
    filler_weighted = sum(h["count"] * h["severity"] for h in filler_hits)
    filler_per_100 = (filler_weighted / max(1, n_words)) * 100

    long_sentences = [s for s in sentences if len(_words(s)) > 30]
    avg_len = round(n_words / n_sent, 1) if n_sent else 0.0

    passive_hits = [{"match": m.group(0), "position": m.start()}
                    for m in PASSIVE_RE.finditer(text)][:20]

    hedge_hits = [h for h in filler_hits if h["category"] == "hedge"]
    hedge_events = sum(h["count"] for h in hedge_hits)

    # --- clarity score 0-100 ---
    # filler load 40 / pacing 25 / voice & hedges 20 / structure 15
    filler_score = max(0.0, 40.0 - min(40.0, filler_per_100 * 2.0))
    pacing_score = 25.0
    if n_sent:
        if avg_len > 32:
            pacing_score -= 12
        elif avg_len > 24:
            pacing_score -= 6
        if len(long_sentences) >= 3:
            pacing_score -= 7
    pacing_score = max(0.0, pacing_score)
    voice_score = 20.0 - min(20.0, len(passive_hits) * 2.5 + hedge_events * 1.5)
    voice_score = max(0.0, voice_score)
    structure_score = 15.0
    if n_sent < 2 and n_words > 40:
        structure_score -= 8  # wall of text
    if n_words < 60:
        structure_score -= 5  # too thin to judge structure
    structure_score = max(0.0, structure_score)
    clarity = round(filler_score + pacing_score + voice_score + structure_score, 1)

    cleaned = _rewrite_clean(text, filler_hits)

    # --- practice drills: 5 worst sentences ---
    drills = []
    for s in sentences:
        s_hits = find_filler_hits(s)
        score = sum(h["count"] * h["severity"] for h in s_hits)
        if len(_words(s)) > 30:
            score += 4
        if score > 0:
            drills.append({"sentence": s, "issues": [h["word"] for h in s_hits][:5]})
    drills.sort(key=lambda d: -sum(1 for _ in d["issues"]))
    drills = drills[:5]

    suggestions = []
    for h in filler_hits[:8]:
        alt = (h["alternatives"] or [""])[0]
        if alt:
            suggestions.append(f"Replace \u201c{h['word']}\u201d with \u201c{alt}\u201d "
                               f"({h['count']}x). {h['note']}".strip())
        else:
            suggestions.append(f"Delete \u201c{h['word']}\u201d ({h['count']}x). "
                               f"{h['note']}".strip())
    if long_sentences:
        suggestions.append(f"Break up {len(long_sentences)} run-on sentence(s) over 30 words "
                           "- one idea per sentence.")
    if passive_hits:
        suggestions.append(f"Rewrite {len(passive_hits)} passive construction(s) in active voice "
                           "('was built by the team' -> 'the team built').")
    if hedge_events >= 3:
        suggestions.append("You hedge a lot - replace 'I think / maybe / probably' with "
                           "evidence or a clear stance.")

    return {
        "clarity_score": clarity,
        "breakdown": {
            "filler_load": round(filler_score, 1),
            "pacing": round(pacing_score, 1),
            "voice_and_hedges": round(voice_score, 1),
            "structure": round(structure_score, 1),
        },
        "metrics": {
            "word_count": n_words,
            "sentence_count": n_sent,
            "avg_words_per_sentence": avg_len,
            "long_sentences": len(long_sentences),
            "filler_events": filler_events,
            "filler_per_100_words": round(filler_per_100, 1),
            "passive_constructions": len(passive_hits),
            "hedge_events": hedge_events,
        },
        "filler_hits": [{k: h[k] for k in ("word", "category", "severity",
                                           "alternatives", "note", "count",
                                           "positions")}
                        for h in filler_hits[:25]],
        "passive_hits": passive_hits[:10],
        "suggestions": suggestions,
        "cleaned_version": cleaned,
        "drills": drills,
    }


def validate_coach_inputs(payload):
    """Validate the analyze form. Returns (text, error)."""
    text = (payload.get("text") or "").strip()
    if len(text) < MIN_CHARS:
        return None, f"Please paste at least {MIN_CHARS} characters of your answer."
    if len(text) > MAX_CHARS:
        return None, f"Please keep your answer under {MAX_CHARS} characters."
    return text, None
