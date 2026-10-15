"""Resume Versions ultimate: diff-with-impact, auto-tailor per JD, app linkage.

Feature 3 x3:
  3.1 diff_resume_versions / compare_versions_for_jd — visual diff + which
      version scores higher against a JD.
  3.2 tailor_resume_for_jd — one-click JD-specific variant.
  3.3 version_performance — which version actually got interviews/offers.
"""
import difflib
import re

MAX_VERSION_CHARS = 60000
DIFF_CONTEXT_LINES = 2


def _clean(text):
    text = re.sub(r"<[^>]*>", "", text or "")
    return text.strip()


def diff_resume_versions(text_a, text_b, name_a="A", name_b="B"):
    """Word-aware line diff between two resume versions.

    Returns {added, removed, changed_lines, stats, unified_diff}.
    Never raises on hostile input (ValueError only for empty inputs).
    """
    a = _clean(text_a)
    b = _clean(text_b)
    if not a or not b:
        raise ValueError("Both versions need text to compare.")
    if len(a) > MAX_VERSION_CHARS or len(b) > MAX_VERSION_CHARS:
        raise ValueError("Version text too long to diff.")

    a_lines = a.splitlines()
    b_lines = b.splitlines()
    sm = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False)

    added, removed, changed = [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            added.extend(b_lines[j1:j2])
        elif tag == "delete":
            removed.extend(a_lines[i1:i2])
        elif tag == "replace":
            removed.extend(a_lines[i1:i2])
            added.extend(b_lines[j1:j2])
            changed.append({"from": a_lines[i1:i2], "to": b_lines[j1:j2]})

    ratio = round(sm.ratio() * 100, 1)
    unified = "\n".join(difflib.unified_diff(
        a_lines, b_lines, fromfile=name_a, tofile=name_b,
        n=DIFF_CONTEXT_LINES, lineterm=""))[:20000]
    return {
        "added": added, "removed": removed, "changed": changed,
        "stats": {"similarity_pct": ratio,
                  "lines_a": len(a_lines), "lines_b": len(b_lines),
                  "added_count": len(added), "removed_count": len(removed)},
        "unified_diff": unified,
        "verdict": ("Nearly identical" if ratio >= 95 else
                    "Minor tweaks" if ratio >= 80 else
                    "Meaningfully different" if ratio >= 50 else
                    "Substantially rewritten"),
    }


def compare_versions_for_jd(text_a, text_b, jd_text, name_a="A", name_b="B",
                             resume_skill_names=None, experience_years=0,
                             sections=None, contact=None):
    """Score both versions against a JD; declare the winner.

    Returns {winner, scores: {a, b}, delta, recommendation}.
    """
    from studybuddy.jd_matcher import score_jd_match
    a = _clean(text_a)
    b = _clean(text_b)
    jd = _clean(jd_text)
    if not a or not b:
        raise ValueError("Both versions need text to compare.")
    if not jd:
        raise ValueError("A job description is needed for comparison.")

    ra = score_jd_match(a, resume_skill_names, experience_years,
                        sections or {}, contact or {}, jd)
    rb = score_jd_match(b, resume_skill_names, experience_years,
                        sections or {}, contact or {}, jd)
    sa, sb = ra["score"], rb["score"]
    winner = name_a if sa >= sb else name_b
    delta = round(abs(sa - sb), 1)
    if delta < 2:
        rec = "Effectively tied — pick the one that reads better to a human."
    elif winner == name_a:
        rec = f"Use {name_a}: it matches this JD {delta} points better."
    else:
        rec = f"Use {name_b}: it matches this JD {delta} points better."
    return {"winner": winner, "scores": {"a": sa, "b": sb},
            "delta": delta, "recommendation": rec,
            "missing_a": ra["missing_keywords"][:5],
            "missing_b": rb["missing_keywords"][:5]}


def tailor_resume_for_jd(resume_text, jd_text, version_name=None):
    """Generate a JD-tailored resume variant.

    - Injects top missing JD keywords into a tailored Summary opener.
    - Reorders experience bullets so keyword-rich ones come first.
    - Returns {tailored_text, changes_made, missing_still}.
    """
    from studybuddy.jd_matcher import score_jd_match, extract_jd_keywords
    resume = _clean(resume_text)
    jd = _clean(jd_text)
    if not resume:
        raise ValueError("Resume text is required.")
    if not jd:
        raise ValueError("Job description is required.")

    report = score_jd_match(resume, [], 0, {}, {}, jd)
    missing = [k for k in report["missing_keywords"] if k and len(k) > 1][:8]
    title = report.get("job_title") or "this role"

    changes = []
    lines = resume.splitlines()

    # 1. Tailored summary opener injected at the top.
    opener_bits = []
    if missing[:5]:
        opener_bits.append("Skilled in " + ", ".join(missing[:5]))
    opener = (f"Targeting {title}"
              + (f" — {opener_bits[0]}." if opener_bits else "."))
    tailored = [opener, ""]
    changes.append(f"Added JD-targeted summary opener ({len(missing[:5])} keywords).")

    # 2. Reorder bullet lines: keyword-rich bullets first (stable).
    jd_kw = {k["keyword"].lower() for k in extract_jd_keywords(jd)}
    bullets, others = [], []
    for ln in lines:
        s = ln.strip()
        if s.startswith(("•", "-", "*", "·")) and len(s) > 10:
            hits = sum(1 for kw in jd_kw if kw in s.lower())
            bullets.append((hits, ln))
        else:
            others.append(ln)
    bullets_sorted = [ln for _, ln in sorted(bullets, key=lambda x: -x[0])]
    if [ln for _, ln in bullets] != bullets_sorted and bullets:
        changes.append(f"Reordered {len(bullets)} bullets: most JD-relevant first.")
    tailored.extend(others)
    tailored.extend(bullets_sorted)

    tailored_text = "\n".join(tailored)
    return {"tailored_text": tailored_text,
            "name": version_name or f"Tailored — {title}",
            "changes_made": changes,
            "keywords_added": missing[:5],
            "missing_still": missing[5:],
            "original_score": report["score"]}


def version_performance(applications):
    """Which resume version actually converts? Pure function over app dicts.

    Each application dict: {version_id, version_name, stage}.
    Interview+ stages: interview, offer, accepted. Returns per-version stats
    sorted by interview rate desc.
    """
    ADVANCED = {"interview", "offer", "accepted", "hired"}
    stats = {}
    for app in applications or []:
        if not isinstance(app, dict):
            continue
        vid = app.get("version_id")
        if vid is None:
            continue
        s = stats.setdefault(vid, {"version_id": vid,
                                   "version_name": app.get("version_name") or f"v{vid}",
                                   "applications": 0, "interviews": 0, "offers": 0})
        s["applications"] += 1
        stage = str(app.get("stage") or "").lower()
        if stage in ADVANCED:
            s["interviews"] += 1
        if stage in {"offer", "accepted", "hired"}:
            s["offers"] += 1
    out = []
    for s in stats.values():
        n = s["applications"]
        s["interview_rate"] = round(s["interviews"] / n * 100, 1) if n else 0.0
        s["offer_rate"] = round(s["offers"] / n * 100, 1) if n else 0.0
        out.append(s)
    out.sort(key=lambda x: (-x["interview_rate"], -x["applications"]))
    if out:
        out[0]["is_best"] = True
    return out
