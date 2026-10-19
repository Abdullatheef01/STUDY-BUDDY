# Contributing to Study Buddy

Thanks for your interest! This guide gets you from zero to your first PR in under 10 minutes.

## Quick setup

```bash
git clone https://github.com/Vivek492005/AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform
cd AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then add your keys
STUDYBUDDY_NO_PARSE_SANDBOX=1 .venv/bin/python -m pytest tests/ -x -q
```

## Branch & commit conventions

- Branch: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`
- Commits: imperative mood, task id prefix when applicable — e.g. `OSS-04: add SECURITY.md`
- One logical change per PR. Keep PRs small and reviewable.

## How to run tests

```bash
# Fast (no sandbox parsing)
STUDYBUDDY_NO_PARSE_SANDBOX=1 .venv/bin/python -m pytest tests/ -q

# Lint
.venv/bin/ruff check --no-cache .

# Benchmarks
.venv/bin/python benchmarks/run.py --quick
.venv/bin/python benchmarks/rag_eval.py --quick
```

## Definition of Done (every PR)

- [ ] Tests added/updated and green (`pytest`, `ruff`)
- [ ] No secrets committed (run `git diff --cached | grep -iE 'key|token|secret'` before pushing)
- [ ] Docs updated if behavior changed
- [ ] Honest: no fabricated numbers, no fake claims

## Ways to contribute

- **Code:** pick a `good first issue` or propose a feature
- **Data:** add skill aliases, salary data, question banks (see `scripts/validate_data.py`)
- **Docs:** fix typos, improve guides, translate
- **Benchmarks:** contribute challenging gold-set examples

## Code of Conduct

Be kind and constructive. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
