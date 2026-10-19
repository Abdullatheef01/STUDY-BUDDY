"""DATA-04: Question bank quality validation.

Checks:
  1. Duplicate question stems (normalized)
  2. Required fields present
  3. "asked at <Company>" claims without citable source
  4. Answer index in range for MCQ banks
  5. Stats by category/difficulty

Usage:
    python scripts/validate_questions.py [--fix]

--fix removes exact-duplicate stems (keeps first occurrence) from JSON banks.
CSV banks are reported only (manual fix).
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data")

# Normalized stem -> dedupe (lowercase, strip punctuation/whitespace)
def norm_stem(text):
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


REQUIRED = {
    "aptitude": ["id", "category", "difficulty", "statement", "options", "answer"],
    "interview": ["question", "category", "difficulty"],
    "skill_quiz": ["id", "skill", "difficulty", "question", "options", "answer"],
    "coding_csv": ["company", "question", "difficulty", "topic"],
    "company_csv": ["company", "question", "category", "difficulty"],
}

COMPANY_CLAIM_RE = re.compile(
    r"\basked\s+(at|in|by)\s+([A-Z][A-Za-z&.\- ]{2,40})", re.I)


def load_json_bank(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_aptitude(questions):
    issues = []
    seen = {}
    for i, q in enumerate(questions):
        stem = norm_stem(q.get("statement"))
        # required fields
        for field in REQUIRED["aptitude"]:
            if field not in q or q[field] in (None, "", []):
                issues.append(f"apt[{q.get('id', i)}]: missing field '{field}'")
        # duplicates
        if stem in seen:
            issues.append(
                f"apt[{q.get('id', i)}]: duplicate stem of "
                f"apt[{seen[stem]}] ('{q.get('statement', '')[:60]}...')")
        else:
            seen[stem] = q.get("id", i)
        # answer index range
        opts = q.get("options") or []
        ans = q.get("answer")
        if isinstance(ans, int) and not (0 <= ans < len(opts)):
            issues.append(
                f"apt[{q.get('id', i)}]: answer index {ans} out of range "
                f"(options={len(opts)})")
        # company claims
        for text in [q.get("statement", ""), q.get("explanation", "")]:
            m = COMPANY_CLAIM_RE.search(text or "")
            if m:
                issues.append(
                    f"apt[{q.get('id', i)}]: company claim '{m.group(0)}' "
                    f"needs citable source or rephrase as 'commonly reported'")
    return issues, seen


def validate_interview(questions):
    issues = []
    seen = {}
    for i, q in enumerate(questions):
        stem = norm_stem(q.get("question"))
        for field in REQUIRED["interview"]:
            if field not in q or q[field] in (None, "", []):
                issues.append(f"iv[{i}]: missing field '{field}'")
        if stem in seen:
            issues.append(
                f"iv[{i}]: duplicate stem of iv[{seen[stem]}] "
                f"('{q.get('question', '')[:60]}...')")
        else:
            seen[stem] = i
        # company claims in question text
        m = COMPANY_CLAIM_RE.search(q.get("question") or "")
        if m:
            issues.append(
                f"iv[{i}]: company claim '{m.group(0)}' needs citable source")
    return issues, seen


def validate_skill_quiz(questions):
    issues = []
    seen = {}
    for i, q in enumerate(questions):
        stem = norm_stem(q.get("question"))
        for field in REQUIRED["skill_quiz"]:
            if field not in q or q[field] in (None, "", []):
                issues.append(f"sq[{q.get('id', i)}]: missing field '{field}'")
        if stem in seen:
            issues.append(
                f"sq[{q.get('id', i)}]: duplicate stem of "
                f"sq[{seen[stem]}] ('{q.get('question', '')[:60]}...')")
        else:
            seen[stem] = q.get("id", i)
        opts = q.get("options") or []
        ans = q.get("answer")
        if isinstance(ans, int) and not (0 <= ans < len(opts)):
            issues.append(
                f"sq[{q.get('id', i)}]: answer index {ans} out of range")
    return issues, seen


def validate_csv(path, kind):
    issues = []
    seen = {}
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, start=2):  # 1-based + header
        stem = norm_stem(row.get("question"))
        for field in REQUIRED[kind]:
            if field not in row or not (row[field] or "").strip():
                issues.append(f"{os.path.basename(path)}:{i}: missing '{field}'")
        if stem in seen:
            issues.append(
                f"{os.path.basename(path)}:{i}: duplicate stem of "
                f"line {seen[stem]} ('{row.get('question', '')[:60]}...')")
        else:
            seen[stem] = i
        m = COMPANY_CLAIM_RE.search(row.get("question") or "")
        if m:
            issues.append(
                f"{os.path.basename(path)}:{i}: company claim '{m.group(0)}'")
    return issues, rows


def stats_report(name, questions, cat_key, diff_key="difficulty"):
    cats = Counter()
    diffs = Counter()
    for q in questions:
        cats[q.get(cat_key, "?")] += 1
        diffs[q.get(diff_key, "?")] += 1
    lines = [f"\n## {name} ({len(questions)} questions)"]
    lines.append(f"  by {cat_key}: " + ", ".join(
        f"{k}={v}" for k, v in sorted(cats.items())))
    lines.append(f"  by {diff_key}: " + ", ".join(
        f"{k}={v}" for k, v in sorted(diffs.items())))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true",
                    help="Remove exact-duplicate stems from JSON banks (keep first)")
    args = ap.parse_args()

    all_issues = []
    report = ["# Question Bank Quality Report", ""]

    # Aptitude
    apt_path = os.path.join(DATA_DIR, "aptitude_questions.json")
    apt = load_json_bank(apt_path)
    issues, seen = validate_aptitude(apt)
    all_issues.extend(issues)
    report.append(stats_report("Aptitude", apt, "category"))

    # Interview
    iv_path = os.path.join(DATA_DIR, "interview_questions.json")
    iv = load_json_bank(iv_path)
    issues, seen = validate_interview(iv)
    all_issues.extend(issues)
    report.append(stats_report("Interview", iv, "category"))

    # Skill quizzes
    sq_path = os.path.join(DATA_DIR, "skill_quizzes.json")
    sq = load_json_bank(sq_path)
    issues, seen = validate_skill_quiz(sq)
    all_issues.extend(issues)
    report.append(stats_report("Skill Quizzes", sq, "skill"))

    # CSVs
    for fname, kind, label in [
            ("coding_questions.csv", "coding_csv", "Coding"),
            ("company_questions.csv", "company_csv", "Company")]:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            issues, rows = validate_csv(path, kind)
            all_issues.extend(issues)
            cats = Counter(r.get("company", "?") for r in rows)
            report.append(
                f"\n## {label} ({len(rows)} rows)\n"
                f"  companies: {len(cats)}, "
                f"top: " + ", ".join(f"{k}={v}" for k, v in cats.most_common(5)))

    # --fix: dedupe JSON banks
    if args.fix:
        for path, key in [(apt_path, "statement"), (iv_path, "question"),
                          (sq_path, "question")]:
            data = load_json_bank(path)
            seen_stems = set()
            deduped = []
            removed = 0
            for q in data:
                stem = norm_stem(q.get(key))
                if stem and stem in seen_stems:
                    removed += 1
                    continue
                seen_stems.add(stem)
                deduped.append(q)
            if removed:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(deduped, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                print(f"  FIXED {os.path.basename(path)}: removed {removed} duplicates")
            else:
                print(f"  OK {os.path.basename(path)}: no duplicates")

    print("\n".join(report))
    print(f"\n{'='*60}")
    print(f"Total issues: {len(all_issues)}")
    dupes = [i for i in all_issues if "duplicate" in i]
    missing = [i for i in all_issues if "missing" in i]
    claims = [i for i in all_issues if "company claim" in i]
    oob = [i for i in all_issues if "out of range" in i]
    print(f"  duplicates: {len(dupes)}, missing fields: {len(missing)}, "
          f"company claims: {len(claims)}, answer out-of-range: {len(oob)}")
    if all_issues:
        print(f"\nFirst 30 issues:")
        for issue in all_issues[:30]:
            print(f"  - {issue}")
        if len(all_issues) > 30:
            print(f"  ... and {len(all_issues) - 30} more")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
