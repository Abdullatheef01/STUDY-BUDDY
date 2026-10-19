# Study Buddy v1.0.0

**The privacy-first AI career copilot for students — from resume to offer letter, from paper to publication.**

## What's new in v1.0.0

This is the first stable release after completing Phases 0–4 of our
world-class roadmap: security hardening, foundation (CI/migrations/
observability), trust & quality, differentiation, and launch readiness.

### Privacy-first AI (our differentiator)
- **No-LLM mode** (`LLM_MODE=off`) — full rule-based functionality, zero AI calls
- **BYOK** — bring your own API key, Fernet-encrypted at rest, never logged
- **Local mode** — point `LLM_BASE_URL` at Ollama; your text never leaves your machine
- **Consent UX** — transparent notice before first AI use, withdraw anytime
- **Delete/export my data** — self-service GDPR/DPDP rights

### Trust & quality
- **Resume Readiness** (not fake "ATS scores") with gold-set benchmarks
- **RAG eval harness** — Recall@k, MRR, citation validity, abstention accuracy
- **Prompt-injection defense** — hostile instructions in documents are sanitized
- **CSP** with per-request nonces, security headers, rate limiting
- **Accessibility** — skip links, focus states, reduced-motion, WCAG 2.2 AA target

### Foundation
- Hash-pinned dependencies, Alembic migrations, structured logging
- GitHub Actions CI (lint, tests, security audit)
- `/healthz`, `/readyz`, `/version` observability endpoints

### Benchmarks (honest, on synthetic gold sets)
| Benchmark | Score |
|-----------|-------|
| Field extraction accuracy | 1.00 |
| Skill F1 | 1.00 |
| RAG Recall@1 / MRR | 1.00 |
| Citation validity / Abstention | 1.00 |

*Real-world documents score lower — help us expand the gold sets!*

## Installation

```bash
git clone <repo-url>
cd <repo>
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add keys
python unified_app.py
```

Or try the [live demo](https://ai-career-research-assistant-resume.onrender.com).

## What's next

See [ROADMAP](docs/) and our 20 `good first issue`s — contributions welcome!

---

**Full changelog:** Phases 0–4 (see commit history).
**License:** MIT
