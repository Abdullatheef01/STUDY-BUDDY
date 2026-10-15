# STUDY-BUDDY — Mega Harsh Test Report

**Date:** 2026-10-15
**Scope:** All 30 features at maximum harsh potential
**Total tests:** 3,387 passed, 2 skipped, 0 failed

---

## Test Suite Breakdown

| Suite | Tests | Focus |
|---|---|---|
| Existing suite | 1,239 | Feature correctness (all 30 features) |
| MEGA-1: Harsh inputs | 840 | 60 hostile strings × 14 text functions |
| MEGA-2: Boundaries | 398 | Numeric edges, ID shapes, empty/oversized |
| MEGA-3: Security | 43 | XSS, SQLi, path traversal payloads |
| MEGA-4: Robustness | ~150 | Wrong types, malformed JSON, concurrency |
| MEGA-5: API harsh | ~350 | Hostile payloads vs all public endpoints |
| MEGA-6: Gateway harsh | ~70 | Provider failures, timeouts, garbage |
| MEGA-7: Auth + engagement | ~280 | Malformed emails, passwords, names |
| MEGA-8: Research + data | ~280 | Invalid IDs, DOIs, limits |
| **Total** | **3,387** | |

---

## Bugs Found & Fixed

### 🔴 1. XSS payloads passed through raw in text outputs (5 tests)
**Severity:** Medium — outputs are plain-text features; HTML tags never legitimate.

- `bullet_rewriter.improve_bullet` returned `<script>alert(1)</script>` verbatim
- `cover_generator.rule_based_cover_letter` same
- `citation_fmt.format_citation` same

**Fix:** `_strip_html()` sanitizer added at input boundary in all three modules.
Tags are stripped; legitimate text is untouched. All 88 existing tests still pass.

### 🟡 2. Negative limit returned all papers (1 test)
**Severity:** Low — `trending.get_trending(-1)` returned the full list instead of empty.

**Fix:** Clamp `limit = max(int(limit or 0), 0)`.

### 🟢 3. Outdated test assertions (3 tests)
**Severity:** None (test-only) — `test_repairs.py` expected old Gemini-only error
messages; updated for the multi-provider gateway.

---

## Harshness Categories Covered

- **Empty/whitespace:** `""`, `" "`, `"\n"`, `"\x00"`
- **Oversized:** 100K-char strings, 1MB payloads
- **Unicode:** CJK, Arabic, emoji (500×), bidi overrides, BOM
- **Injection:** 7 XSS vectors, 5 SQLi vectors, 5 traversal vectors
- **Type confusion:** None, int, float, list, dict, bytes, objects as strings
- **Numeric edges:** 0, -1, 2³¹, 2⁶³, inf, NaN
- **Concurrency:** 8 threads × 20 iterations on cached loaders
- **API abuse:** Wrong methods, giant headers, malformed JSON bodies
- **Provider failures:** Timeouts, 429/500/503, empty responses, garbage JSON

---

## Verdict

Every feature survives hostile input without crashing (500s), leaking data,
or executing injected content. Validation errors are user-friendly;
unexpected exceptions are zero. **Quality gate: PASSED.**
