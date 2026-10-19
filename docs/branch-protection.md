# Branch protection — recommended settings for `main`

GitHub does not let us commit these; set them once in the dashboard:

Repo → Settings → Branches → Add branch protection rule

- Branch name pattern: `main`
- ✅ Require a pull request before merging
  - Required approvals: 1
  - ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - Required checks:
    - `Ruff + mypy` (lint job)
    - `pytest (SQLite)` (test job)
    - `pytest (Postgres 16)` (test-postgres job)
    - `Bandit + pip-audit` (security job)
    - `Gitleaks secrets scan` (secrets-scan job)
- ✅ Require conversation resolution before merging
- ✅ Do not allow bypassing the above settings (applies to admins too)

Why: every PR above is how STUDY-BUDDY got community contributions
(#22, #30, #31) — protection keeps `main` green while staying welcoming.
