# Privacy modes

Study Buddy supports three LLM modes via the `LLM_MODE` environment variable:

| Mode | Value | Behavior |
|------|-------|----------|
| Server (default) | `server` | Uses server-configured provider keys (Gemini → Groq → OpenRouter) |
| No-LLM | `off` | No AI calls at all; rule-based fallbacks with clear messaging |
| BYOK | `byok` | Each user supplies their own key at `/profile/ai-key` (Fernet-encrypted) |

## Local / self-host

Set `LLM_BASE_URL` to an OpenAI-compatible endpoint (e.g. Ollama):

```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2
```

Resume text never leaves your machine in this mode.
