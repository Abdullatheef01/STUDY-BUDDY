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
- ## LLM Configuration

STUDY-BUDDY supports three LLM modes controlled by the `LLM_MODE` environment variable.

| Variable | Default | Description |
|---|---|---|
| `LLM_MODE` | `server` | Selects the LLM operating mode: `off`, `byok`, or `server`. |
| `LLM_BASE_URL` | Not set | Base URL of a local OpenAI-compatible LLM endpoint, such as Ollama. |
| `LLM_MODEL` | `llama3.2` | Model name sent to the local LLM endpoint. |

### LLM Modes

- **`off`** — Disables LLM calls. The application uses rule-based fallbacks where available.
- **`byok`** — Uses the user's own API key configured in Profile → AI Settings. Requests are sent through OpenRouter.
- **`server`** — Uses configured providers in this order: local endpoint, Gemini, Groq, then OpenRouter. Providers without configured keys are skipped.

### Local Setup with Ollama

1. Install Ollama from [https://ollama.com/](https://ollama.com/).
2. Download the model and start the Ollama server:

   ```bash
   ollama pull llama3.2
   ollama serve
   ```

3. Set the environment variables.

**Linux/macOS:**

```bash
export LLM_MODE=server
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=llama3.2
```

**Windows PowerShell:**

```powershell
$env:LLM_MODE="server"
$env:LLM_BASE_URL="http://localhost:11434/v1"
$env:LLM_MODEL="llama3.2"
```

4. Keep Ollama running while using STUDY-BUDDY. The application sends chat-completion requests to the local endpoint.

### Important Notes

- `LLM_BASE_URL` should point to the OpenAI-compatible API base URL, including `/v1` for a standard Ollama setup.
- `LLM_MODEL` must match a model available in Ollama.
- In `server` mode, configured cloud providers can be used as fallbacks if the local endpoint fails.
- For local-only operation, leave cloud provider API keys unset and ensure Ollama is running with the selected model available.
- `byok` and `off` modes do not use the server-mode provider chain.
- Environment variables set in a terminal apply to processes launched from that terminal.

