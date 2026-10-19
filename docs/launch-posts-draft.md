# Launch Posts — DRAFTS (do not post without review)

## Show HN

**Title:** Show HN: Study Buddy – privacy-first AI career copilot (no-LLM/BYOK/local modes)

**Body:**

Hi HN! I built Study Buddy, an open-source AI career assistant for students:
resume analysis, JD matching, interview practice, and research-paper Q&A
with citations.

The differentiator is privacy: most career tools send your resume to
someone's API. Study Buddy supports three modes:

- **No-LLM** — full rule-based functionality, zero AI calls
- **BYOK** — your own API key, encrypted at rest, never logged
- **Local** — point at Ollama; your text never leaves your machine

Also: honest "Resume Readiness" instead of fake ATS scores, RAG eval harness
(Recall/MRR/citation validity published), prompt-injection defense, and
self-service data export/deletion.

Stack: Flask, TF-IDF/BM25 retrieval, multi-provider LLM gateway
(Gemini → Groq → OpenRouter).

MIT licensed. I'd love feedback, especially on the privacy modes and
benchmark methodology.

[repo link] · [live demo] · [docs]

---

## Reddit (r/SideProject)

**Title:** I built a privacy-first AI resume/career assistant — no-LLM, BYOK, and local modes

**Body:**

Hey r/SideProject! After months of work, I launched **Study Buddy v1.0.0** —
an AI career copilot for students.

**What it does:** resume readiness analysis, JD matching, mock interviews,
aptitude/DSA practice, and research paper Q&A with citations.

**Why it's different:** I was uncomfortable with career tools that upload
your resume to a black-box API. So I built three privacy modes:

1. No-LLM mode — everything rule-based, no AI calls at all
2. BYOK — use your own API key (encrypted, never logged)
3. Local — run via Ollama, nothing leaves your machine

Plus honest engineering: real benchmarks published (not marketing numbers),
prompt-injection defense for uploaded documents, and one-click data
export/deletion.

It's MIT open-source. The 20 `good first issue`s are ready if anyone wants
to contribute!

[demo] · [github] · happy to answer questions

---

## Product Hunt

**Tagline:** Privacy-first AI career copilot for students

**Description:**

Study Buddy helps students go from resume to offer letter: resume readiness
(not fake ATS scores), JD matching, interview practice, and research Q&A
with citations.

Privacy-first: no-LLM mode, bring-your-own-key, or run fully local with
Ollama. Your resume never has to touch a third-party API.

Open-source (MIT). Built for students, by a student.

**Key features:**
- Resume Readiness with evidence-backed feedback
- JD matching with skill-gap analysis
- Mock interviews with structured rubrics
- Research paper Q&A with verified citations
- Full privacy controls: export/delete/consent/withdraw

---

*Notes for Vivek:*
- *Replace [repo link], [live demo], [docs] with actual URLs before posting.*
- *Post Show HN on a weekday morning US time for best visibility.*
- *Product Hunt needs a maker account + hunter; schedule the launch.*
- *Engage with every comment in the first 48 hours.*
