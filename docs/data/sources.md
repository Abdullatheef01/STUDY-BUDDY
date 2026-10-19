# External Data Sources — ToS & Rate Limits (LEG-02)

Every third-party API, feed, or dataset STUDY-BUDDY calls. Reviewed 2026-10-19.
Re-check annually or when a source changes its terms.

| Source | What we use it for | ToS / API terms | Rate limits | Auth | Notes |
|---|---|---|---|---|---|
| arXiv API (`export.arxiv.org/api/query`) | Paper metadata + PDF download for research features | https://arxiv.org/help/api/tou | 3s delay between requests requested; bulk use via S3 | None | Respectful single-request pattern; PDFs cached |
| OpenAlex (`api.openalex.org`) | Paper metadata, citation graph | https://docs.openalex.org/how-to-use-the-api/ | 10 req/s (100k/day pool); polite pool with `mailto` | None (mailto param) | CC0 data |
| GitHub REST API (`api.github.com`) | Repo analysis for paper constructor | https://docs.github.com/en/site-policy/github-terms/github-terms-of-service | 60 req/hr unauth; 5,000 req/hr with token | Optional PAT | Token recommended for production |
| Google OAuth 2.0 (`accounts.google.com`) | Sign-in with Google | https://developers.google.com/terms | Per-project quotas | OAuth client | Requires `email_verified`; no silent account takeover |
| LeetCode GraphQL (`leetcode.com/graphql`) | Public profile stats cards | https://leetcode.com/terms/ (no public API; unofficial use) | Undocumented — keep low volume, cache aggressively | None | Unofficial endpoint; may break without notice. Displayed data is the user's own public profile |
| Google Gemini API | LLM provider (server key or BYOK) | https://ai.google.dev/gemini-api/terms | Per-key quotas (free tier) | API key | Prompts not stored by default; see consent notice |
| Groq API (`api.groq.com`) | LLM fallback provider | https://groq.com/terms-of-service/ | Per-key rate limits | API key | OpenAI-compatible endpoint |
| OpenRouter (`openrouter.ai/api`) | LLM fallback provider | https://openrouter.ai/terms | Per-key limits; `:free` models | API key | BYOK supported; user keys never logged |
| Devpost API (`devpost.com/api/hackathons`) | Hackathon listings | https://devpost.com/terms | Undocumented — cache, low frequency | None | Read-only listing data |
| SimplifyJobs Summer2027 list (`raw.githubusercontent.com/SimplifyJobs/...`) | Internship listings (curated markdown) | Repo license (check upstream) | GitHub raw limits | None | Community-curated; verify before applying |

## Data licensing summary

- **In-house datasets** (`data/skills_db.csv`, `data/taxonomy/skills_taxonomy.json`,
  question banks, `benchmarks/` gold sets): curated by the STUDY-BUDDY team,
  released under the repository's MIT license. See `docs/data/ATTRIBUTION.md`.
- **ESCO / O*NET**: NOT used. If adopted in future, CC BY 4.0 attribution will
  be added here and in the app footer.
- **No third-party copyrighted question text** is shipped. Interview questions
  are original phrasings of commonly reported themes.
- **No scraped content** is stored or redistributed.

## LLM provider terms (LEG-04 note)

Provider terms above were reviewed 2026-10-19 for the free-tier / BYOK usage
pattern. Key points: user-supplied keys are used only for the requesting
user's calls and never logged; server keys are used only for consented
features; prompts/responses are not stored by default. A qualified legal
review is recommended before public launch (see `docs/TERMS.md`).
