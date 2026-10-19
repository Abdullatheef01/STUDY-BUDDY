# 20 Good First Issues for Study Buddy

Each issue is designed to be completable by a new contributor in 1-3 hours,
with clear acceptance criteria.

---

## 1. [data] Add 10 Python skill aliases
**Labels:** `good first issue`, `data`
**Description:** The skill extractor misses common Python ecosystem aliases.
Add to `data/skills.json` (or equivalent): `pandas`, `numpy`, `django`,
`flask`, `fastapi`, `pytest`, `sqlalchemy`, `celery`, `pydantic`, `poetry`
with canonical mapping to "Python".
**Acceptance:** `scripts/validate_data.py` passes; a test resume mentioning
"pandas" maps to Python skill.

## 2. [data] Add 10 JavaScript skill aliases
**Labels:** `good first issue`, `data`
Same as #1 for JavaScript: `typescript`, `react`, `vue`, `angular`,
`node.js`, `express`, `next.js`, `jest`, `webpack`, `npm`.

## 3. [docs] Fix README quickstart for Windows
**Labels:** `good first issue`, `docs`
The quickstart assumes bash. Add Windows PowerShell equivalents for
venv creation, activation, and env setup.
**Acceptance:** A Windows user can follow the README start-to-finish.

## 4. [a11y] Add aria-labels to dashboard icon buttons
**Labels:** `good first issue`, `a11y`
Find icon-only buttons in `templates/dashboard.html` (and similar) that
lack accessible names. Add `aria-label` to each.
**Acceptance:** axe-core reports zero "button-name" violations on dashboard.

## 5. [docs] Translate CONTRIBUTING.md to Hindi
**Labels:** `good first issue`, `docs`
Create `CONTRIBUTING.hi.md` — Hindi translation of CONTRIBUTING.md.
**Acceptance:** Native speaker review (maintainer will arrange).

## 6. [code] Add `lang` attribute check to CI
**Labels:** `good first issue`, `code`
Write a CI script that fails if any full-page template lacks
`<html lang="...">`. (UX-03 found partials without it.)
**Acceptance:** Script in `scripts/` + CI step; green on current tree.

## 7. [data] Add 5 sample resumes to gold set
**Labels:** `good first issue`, `data`
Create 5 challenging resumes in `benchmarks/resume_gold/`: double-column
layout (as text), fresher with no experience, career switcher, non-English
name formats, scanned-PDF-style line breaks. Follow the existing JSON schema.
**Acceptance:** `benchmarks/run.py` includes them; labels complete.

## 8. [code] Surface benchmark scores in /version
**Labels:** `good first issue`, `code`
Read `benchmarks/results.json` (if present) and include `benchmarks` key
in the `/version` endpoint response.
**Acceptance:** `/version` returns benchmark scores when the file exists;
omits gracefully when it doesn't. Test added.

## 9. [docs] Write troubleshooting guide for Render deploys
**Labels:** `good first issue`, `docs`
Document common Render deploy failures we hit: Python version mismatch,
`deprecated` package resolution, missing `psycopg`, cold starts.
Create `docs-site/docs/selfhost/render-troubleshooting.md`.
**Acceptance:** Covers at least 5 real failure modes with fixes.

## 10. [code] Add `--strict` mode to validate_data.py CI step
**Labels:** `good first issue`, `code`
Wire `scripts/validate_data.py --strict` into CI as a non-blocking
(continue-on-error) step that uploads the warning count as an artifact.
**Acceptance:** CI shows the step; artifact contains the report.

## 11. [data] Add salary data for 5 Indian cities
**Labels:** `good first issue`, `data`
Add entry-level software engineer salary ranges for Mumbai, Delhi,
Bangalore, Hyderabad, Chennai to the salary dataset, with `source_url`,
`retrieved_at`, `license`, `last_verified`, `confidence` per DATA-01.
**Acceptance:** `scripts/validate_data.py` shows no new errors.

## 12. [a11y] Keyboard navigation for flashcards
**Labels:** `good first issue`, `a11y`
Flashcard UI should support: Space/Enter to flip, ArrowRight for next,
ArrowLeft for previous. Add visible focus styles.
**Acceptance:** Full keyboard flow works; no mouse needed.

## 13. [code] Add rate-limit headers to API responses
**Labels:** `good first issue`, `code`
Flask-Limiter supports `X-RateLimit-*` headers. Enable them and add a
test asserting the headers appear on a rate-limited endpoint.
**Acceptance:** Headers present; test green.

## 14. [docs] Document LLM_MODE options
**Labels:** `good first issue`, `docs`
Expand `docs/configuration.md` with a full section on `LLM_MODE`
(off/byok/server), `LLM_BASE_URL`, and `LLM_MODEL`, with examples for
Ollama local setup.
**Acceptance:** A new user can set up local mode from the docs alone.

## 15. [code] Export: include LLM consent record
**Labels:** `good first issue`, `code`, `privacy`
`/account/export` should include the user's `LLMConsent` record
(consented_at, policy_version) in the JSON.
**Acceptance:** Export contains `llm_consent` key; test added.

## 16. [data] Add 20 aptitude questions (logical reasoning)
**Labels:** `good first issue`, `data`
Add 20 logical-reasoning questions to `data/aptitude_questions.json`
following the existing schema, with explanations.
**Acceptance:** Schema-valid; questions render in the UI.

## 17. [code] Health check: add DB latency to /readyz
**Labels:** `good first issue`, `code`
`/readyz` should measure and report DB query latency (simple SELECT 1
timing) in the JSON response.
**Acceptance:** Field present; test asserts it's a positive number.

## 18. [docs] Add architecture diagram (Mermaid)
**Labels:** `good first issue`, `docs`
Create a Mermaid diagram showing: browser → Flask → (Postgres, AI gateway
→ Gemini/Groq/OpenRouter/Ollama). Add to docs-site.
**Acceptance:** Renders correctly in MkDocs Material.

## 19. [code] CSP: report-uri beacon fallback
**Labels:** `good first issue`, `code`, `security`
If `/csp-report` POST fails (e.g. adblocker), fall back to
`navigator.sendBeacon`. Small JS snippet in base template.
**Acceptance:** Violations still logged when fetch is blocked (manual test).

## 20. [data] Add interview questions for data analyst role
**Labels:** `good first issue`, `data`
Add 15 data-analyst interview questions (SQL, Excel, statistics,
storytelling) to `data/interview_questions.json` with difficulty tags.
**Acceptance:** Schema-valid; appear in interview practice UI.
