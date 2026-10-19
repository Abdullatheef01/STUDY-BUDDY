# Secrets management and rotation (SEC-13)

## Policy

- **No secret is ever committed.** API keys, OAuth client secrets, database
  passwords, Fernet/encryption keys, and private tokens live only in
  environment variables (locally: `.env`, which is git-ignored) or the
  hosting platform's secret store (Render dashboard env vars).
- **One-time PAT rule:** GitHub personal access tokens are pasted for a
  single push operation and treated as spent immediately after. They are
  never stored in files, shell history, or memory.
- **`.env.example`** documents every variable the app reads. If you add a
  new secret-backed setting, add it to `.env.example` with a placeholder
  value (never a real one).

## Automated scanning

| Layer | Tool | Config |
|---|---|---|
| Pre-commit | `gitleaks` | `.pre-commit-config.yaml` (blocks the commit) |
| CI | `gitleaks/gitleaks-action@v2` | `.github/workflows/ci.yml` → `secrets-scan` job, full history (`fetch-depth: 0`) |

To scan manually:

```bash
# staged + working tree
gitleaks detect --source . -v
# full history (run once after any suspected leak)
gitleaks detect --source . --log-opts="--all" -v
```

## If a secret leaks

1. **Revoke/rotate it immediately** at the provider (GitHub token settings,
   Google Cloud console, Render dashboard, etc.). Assume it is compromised
   from the moment it touched the repo.
2. **Purge from history** with `git filter-repo` (or BFG). A plain revert
   is not enough — the secret stays in history.
3. **Force-push** the cleaned history and notify collaborators to re-clone.
4. Record the incident (date, secret type, rotation confirmation) in the
   team's private incident log — never in the repo.

## Rotation schedule

- `SECRET_KEY` / `ENCRYPTION_KEY`: rotate on any suspected exposure, and at
  least yearly. Rotating `SECRET_KEY` invalidates all sessions and signed
  tokens (users are logged out — acceptable).
- LLM provider keys: rotate per provider policy; immediately if a key
  appears in logs, error reports, or the repo.
- OAuth client secrets: rotate if the callback URL set or team changes.

## History audit

- `git filter-repo` was used in Phase 0 (ARC-06) to remove committed
  `*.db` files from history.
- `gitleaks detect --log-opts="--all"` is run in CI on every push; a clean
  scan is required for merge.
