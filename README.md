<div align="center">

<img src="static/img/study-buddy-logo.png" alt="STUDY-BUDDY logo" width="180"/>

# STUDY-BUDDY 🦉

**The AI-powered career & research intelligence platform for students — from resume to offer letter, and from paper to publication.**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)](https://flask.palletsprojects.com/)
[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen?logo=render)](https://ai-career-research-assistant-resume.onrender.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Vivek492005/AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Vivek492005/AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform/actions/workflows/ci.yml)

[Live Demo](https://ai-career-research-assistant-resume.onrender.com) · [Features](#-features) · [Setup](#-installation--setup) · [Contributing](#-contributing)

</div>

---

## 📖 Overview

**STUDY-BUDDY** is an all-in-one platform that helps students navigate their entire career journey: discovering the right career path, building a standout resume, preparing for interviews, finding opportunities, learning new skills, conducting research, and staying motivated — all in one place.

Built as a Flask monolith, it pairs **Google Gemini** (with automatic fallback to Groq and OpenRouter) with **classic retrieval (TF-IDF/BM25)** and large curated content banks (hundreds of interview questions, aptitude drills, DSA problems, and learning resources) so students get AI-powered guidance backed by real substance — not empty chat. Semantic embeddings via sentence-transformers are supported where installed; production currently uses the keyword/retrieval path.

### Why STUDY-BUDDY?

- **One profile, every tool** — resume, applications, practice scores, learning progress and research library all connected
- **Evidence over hype** — research answers carry citations, rejection advice is labeled as hypothesis, health scores show their data
- **Humane by design** — streaks with forgiveness shields, opt-out gamification, no pay-to-win, no dark patterns
- **Free & student-first** — every core feature works without payment

---

## 🚀 Live Demo

👉 **https://ai-career-research-assistant-resume.onrender.com**

> Hosted on Render's free tier — the first load may take ~30 seconds while the service wakes up.

---

## ✨ Features

### 📄 Resume & Career Intelligence

| Feature | What it does |
|---|---|
| AI Resume Analysis | Upload your resume for ATS scoring with section-by-section feedback and improvement suggestions |
| JD-Matched ATS Scoring | Paste a job description to see exactly how well your resume matches it, with gap analysis |
| Bullet Impact Rewriter | Rewrite weak resume bullets into quantified, impact-driven statements (AI-polished alternatives) |
| Cover Letter Generator | Generate tailored cover letters from your resume + the target job posting |
| LinkedIn Profile Grader | Grade your LinkedIn profile with actionable fixes for headline, about, and experience sections |
| GitHub / LeetCode Integration | Pull your real coding profile data into your career dashboard |
| Portfolio Builder | Build and publish a personal portfolio site from your profile data |
| Career Discovery Assessment | Answer a guided assessment to discover career clusters that fit your interests and strengths |
| Application Tracker | Kanban pipeline for every application — wishlist → applied → screening → interview → offer / rejected — linked to the exact resume version used |

### 🎯 Interview & Placement Prep

| Feature | What it does |
|---|---|
| Mock Interviews | **339-question** bank of role-specific mock interviews with rubric-scored AI feedback and weak-area re-drills |
| Communication Coach | **104-entry** coach for delivery: pace, filler words, clarity, structure, and confidence signals |
| DSA Practice | **132 DSA problems** with a hint ladder, worked reflections, and a mastery map |
| Aptitude Tests | **338 questions** in timed test mode — quantitative, logical, and verbal reasoning |
| STAR Story Builder | Build behavioral interview stories with **44 examples** across **11 competencies** |

### 📚 Learning Hub

| Feature | What it does |
|---|---|
| Skill Roadmaps | **24 skills × 3 stages** (beginner → advanced) with **349 free resources** — courses, docs, and practice |
| Skill Quizzes | **320 quiz questions** across **16 skills** to test and certify your knowledge |
| Certification Guides | **44 certifications** with guidance on what to take, when, and how to prepare |

### 🔬 Research Intelligence

| Feature | What it does |
|---|---|
| Source-Grounded PDF Q&A | Ask questions across your PDFs — every answer points back to supporting passages with page/chunk provenance; honest abstention when evidence is absent |
| arXiv / DOI Import | Import papers directly from arXiv or DOI with metadata, plus an interactive citation graph |
| Citation Formatter | One-click citations in **IEEE, APA 7th, MLA 9th, Vancouver, Chicago**, and **BibTeX** export |
| Literature Review Generator | Synthesize multiple papers into a structured, evidence-linked literature review |
| Research-Gap Finder | Surface recurring limitations, conflicts, under-studied populations, and method gaps — labeled as hypotheses until reviewed |
| Flashcards & Paper Quizzes | Auto-generated from your documents: TF-IDF key terms, definition cards, cloze deletions, and MCQs with server-side grading |

### 🔥 Engagement

| Feature | What it does |
|---|---|
| XP & Streaks | Earn XP only for meaningful career actions (never raw screen time); daily streaks keep momentum visible |
| Forgiveness Shields | Miss a day? Two streak shields per month auto-repair it — progress without guilt trips |
| Weekly Leagues | Small opt-in cohorts competing on consistency, not prestige — winnable resets, no pay-to-win |
| Weekly Quests | Scheduled challenges (e.g. "complete 3 quizzes") with bonus XP on completion |
| Opt-Out | Turn off all gamification any time — the platform respects your choice |

### 👥 Community

| Feature | What it does |
|---|---|
| Peer Mock Interviews | Create a room, share the link, and practice with a friend — question cards from the 339-question bank, timers, role swap, and reciprocal 5-dimension rubric feedback |
| Mentor & Alumni Office Hours | Book group sessions with mentors across domains — sample profiles ship with the app; real mentors apply and are marked verified only after review. Structured question templates keep conversations useful, with post-session action notes |

### 📊 Review & Analytics

| Feature | What it does |
|---|---|
| Rejection Retrospectives | Funnel analytics show where applications stall; a guided wizard turns each rejection into observed patterns → hypotheses → one controlled experiment, with an experiment log |
| Career Health Review | A monthly, explainable review across **5 transparent dimensions** — direction, proof, opportunity activity, preparation, wellbeing — each with trend, confidence, evidence, and your smallest next action. No opaque "employability score." |

### 📡 Opportunity Radar

| Feature | What it does |
|---|---|
| Auto-Refreshing Board | **80 opportunities** refreshed automatically **every 2 days** — hackathons from the Devpost API, internships from SimplifyJobs — with a freshness indicator |
| Smart Merging | Curated entries are never touched; expired auto-entries are pruned, duplicates removed |
| Filters & Bookmarks | Filter by type (hackathon / internship / competition), bookmark what matters |

### ⚡ Ultimate Lab

| Feature | What it does |
|---|---|
| 91 Power Tools | Every feature's deep "ultimate" enhancements (streak freeze, squad challenges, peer mocks, rejection-pattern alerts, mentor prep packets, monthly health review…) runnable from one dashboard at `/ultimate/lab` |
| Tool API | `GET /api/ultimate/tools` lists all tools; `POST /api/ultimate/run/<tool_id>` runs one with a JSON body |

### 🔑 Sign-in & Extras

| Feature | What it does |
|---|---|
| Google Sign-in | One-click OAuth login alongside email/password (email verified via Google) |
| India Salary Explorer | Explore salary ranges by role, experience, and city, grounded in the curated salary dataset |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Flask 3.x, Flask-SQLAlchemy, Flask-Login |
| Database | SQLite (dev) / PostgreSQL (prod via `DATABASE_URL`) |
| AI | Google Gemini API with Groq/OpenRouter fallback; TF-IDF/BM25 retrieval (sentence-transformers optional — keyword fallback in production) |
| Frontend | Jinja2 templates, custom Bento CSS design system, vanilla JS |
| Server | Gunicorn |
| Testing | pytest (8720 tests) |
| Deployment | Render (free tier) |

---

## 📁 Project Structure

```
acra/
├── unified_app.py          # Flask app: models, routes, app factory (~7000 lines)
├── studybuddy/             # Feature modules (pure-logic, no Flask/network/LLM)
│   ├── momentum.py         # XP / streaks / leagues / quests engine
│   ├── community.py        # Peer mocks + mentor office hours
│   ├── health_review.py    # Monthly career health aggregation
│   ├── flashcards.py       # Flashcard generation (TF-IDF, cloze, MCQ)
│   ├── gap_finder.py       # Research-gap analysis
│   ├── lit_review.py       # Literature review generator
│   ├── arxiv_import.py     # arXiv / DOI import + citation graph
│   ├── citation_fmt.py     # IEEE / APA / MLA / Vancouver / Chicago / BibTeX
│   ├── pdf_qa.py           # Source-grounded PDF question answering
│   ├── opportunity_sources.py  # Devpost + SimplifyJobs auto-ingest
│   ├── learning_roadmaps.py    # Skill roadmaps + resources
│   ├── skill_quizzes.py    # Quiz engine
│   ├── mock_interview.py   # Interview question bank + rubric scoring
│   ├── dsa_practice.py     # DSA problems + hints
│   ├── ai_gateway.py       # Gemini → Groq → OpenRouter fallback chain
│   ├── ultimate_reg_*.py   # Ultimate Lab tool registry (91 tools)
│   ├── ultimate_routes.py  # /ultimate/lab dashboard + /api/ultimate API
│   └── ...                 # 15+ more feature modules
├── templates/              # Jinja2 templates (Bento UI)
├── static/
│   ├── css/bento.css       # Design system
│   └── img/                # STUDY-BUDDY owl logo + favicons
├── tests/                  # pytest suite (8720 tests)
└── data/                   # JSON content banks (questions, resources)
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.12+
- A [Gemini API key](https://aistudio.google.com/) (optional — core features work without it; AI-enhanced paths need it)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Vivek492005/AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform.git
cd AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env   # then edit .env
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Flask session secret — set a long random value in production |
| `DATABASE_URL` | ⚠️ prod | PostgreSQL URL (Render provides this); falls back to local SQLite |
| `GEMINI_API_KEY` | optional | Enables Gemini-powered feedback, rewriting, and Q&A enhancements |

### Run

```bash
# Development
python unified_app.py

# Production (as deployed)
gunicorn unified_app:app
```

Open **http://localhost:5000** and create an account to get started.

---

## 🧪 Testing

```bash
pytest tests/ -q
```

- **8720 tests**, covering every feature module: happy paths, validation, auth isolation, CSRF, rate limits, and error/edge cases
- Run the suite twice before any release; the project standard is **100% green, 0 failures**

---

## ☁️ Deployment

The live site runs on **Render's free tier**:

1. Connect the GitHub repo to Render as a **Web Service**
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn unified_app:app`
4. Set `SECRET_KEY`, `DATABASE_URL` (Render Postgres), and `GEMINI_API_KEY` in the dashboard
5. Every push to `main` auto-deploys

---

## 🗺 Roadmap

- [x] Career core (resume, JD match, tracker)
- [x] Placement prep (interviews, DSA, aptitude, STAR)
- [x] Learning hub (roadmaps, quizzes, certifications)
- [x] Research intelligence (PDF Q&A, citations, lit review, gaps, flashcards)
- [x] Engagement (XP, streaks, leagues, quests)
- [x] Community (peer mocks, mentor office hours)
- [x] Review & analytics (retrospectives, health review)
- [x] Opportunity radar auto-refresh
- [ ] Mobile PWA polish & offline packs
- [ ] Vernacular (Hindi + regional) language support

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

Quick version:
1. Fork the repo and create a feature branch (`git checkout -b feat/my-feature`)
2. Add tests — the suite must stay 100% green
3. Run `ruff check --no-cache` — must be clean
4. Open a PR using the template

### Benchmarks

We measure, we don't guess. See [docs/benchmarks.md](docs/benchmarks.md):

| Benchmark | Metric | Score |
|-----------|--------|-------|
| Resume parsing | Field accuracy (name/email/phone) | 1.00* |
| Resume parsing | Skill F1 | 1.00* |
| RAG retrieval | Recall@1 / MRR | 1.00* |
| RAG answers | Citation validity / Abstention | 1.00* |

\* *On synthetic gold sets. Real-world documents score lower — help us expand
the gold sets with challenging examples!*

Run them yourself:
```bash
python benchmarks/run.py --quick
python benchmarks/rag_eval.py --quick
python scripts/validate_data.py
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Vivek Bartwal** — [GitHub @Vivek492005](https://github.com/Vivek492005)

Built for students, by a student. 🦉
