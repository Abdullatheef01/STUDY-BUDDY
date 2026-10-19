# Self-Hosting STUDY-BUDDY (PROD-04)

Run your own instance with one command.

## Quick Start

```bash
docker compose up
```

Open http://localhost:5000. That's it.

- **Database:** SQLite by default (data in Docker volume `studybuddy-data`)
- **AI:** `LLM_MODE=off` by default — all rule-based features work, no API keys needed
- **First run:** Create your account via the Register page (first user is a regular user; promote via `flask` shell if needed)

## With Local LLM (Ollama)

```bash
docker compose --profile ollama up
```

Then pull a model:

```bash
docker exec -it acra-ollama-1 ollama pull llama3.2
```

Set in your `.env` or compose environment:
- `LLM_MODE=server`
- `LLM_BASE_URL=http://ollama:11434/v1`
- `LLM_MODEL=llama3.2`

## With Postgres

```bash
docker compose --profile postgres up
```

Set `DATABASE_URL=postgresql://studybuddy:studybuddy@postgres:5432/studybuddy`.

Run migrations on first start:

```bash
docker compose exec app flask db upgrade head
```

## Hardware Needs

| Setup | RAM | Disk |
|-------|-----|------|
| Base (SQLite, no LLM) | 512 MB | 1 GB |
| + Ollama (llama3.2) | 8 GB | 10 GB |
| + Postgres | 1 GB | 2 GB |

## Backup

```bash
# SQLite
docker cp acra-app-1:/app/instance/studybuddy.db ./backup-$(date +%F).db

# Postgres
docker compose exec postgres pg_dump -U studybuddy studybuddy > backup.sql
```

## Upgrading

```bash
git pull
docker compose build
docker compose up -d
docker compose exec app flask db upgrade head
```

## Security Notes

- Change `SECRET_KEY` in production (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
- Change `POSTGRES_PASSWORD` if using Postgres profile
- Put behind a reverse proxy (Caddy/nginx) with HTTPS for internet exposure
- `LLM_MODE=off` is the safest default; BYOK keeps user keys encrypted
- See `docs/security/secrets.md` for key rotation
