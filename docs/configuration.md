# Configuration

All configuration comes from environment variables, validated in
`studybuddy/app_config.py` (`AppConfig.from_env()`). Nothing else in the
codebase should read `os.environ` for config.

## Core

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | (ephemeral) | Flask session signing. **Set in production** — without it sessions reset on every restart. |
| `DATABASE_URL` | sqlite dev db | SQLAlchemy URL. Render injects the Postgres URL. |
| `FLASK_ENV` | `production` | `production` enables JSON logs, HSTS, secure cookies. |
| `PORT` | `5000` | Dev server port (`python unified_app.py`). |

## LLM providers

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini key (primary). |
| `GROQ_API_KEY` | — | Groq key (fallback 1). |
| `OPENROUTER_API_KEY` | — | OpenRouter key (fallback 2). |
| `LLM_MODE` | `server` | `off` = no LLM calls anywhere (deterministic fallbacks); `byok` = reserved; `server` = use server keys. |

## OAuth

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | Google OAuth (optional; password login always works). |

## Limits

| Variable | Default | Description |
|---|---|---|
| `ULTIMATE_RUN_LIMIT` | `30 per hour` | Rate limit for Ultimate Lab tool runs. |
| `MAX_UPLOAD_MB` | `16` | Resume/PDF upload cap. |
| `SKIP_DB_INIT` | — | `1` skips `create_all()` (used when generating migrations). |

## Feature flags

| Variable | Default | Description |
|---|---|---|
| `FEATURE_LABS` | `1` | Ultimate Lab (`/ultimate/*`). Set `0` to disable. |
| `FEATURE_PEER_MOCKS` | `1` | Peer mock interviews. |
| `FEATURE_COMMUNITY` | `1` | Community mentors board. |

## Health endpoints

- `GET /healthz` — liveness, no DB. Render health check points here.
- `GET /readyz` — readiness: DB reachable, migrations at head, secret key set. 503 when not ready. Never exposes secrets.
- `GET /version` — git SHA, schema revision, Python version.
