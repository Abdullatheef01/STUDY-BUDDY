# 🤖 AI Career & Research Assistant Platform

An advanced, full-stack AI-powered platform that integrates **Career Intelligence** and **Research Intelligence** into a unified system. This project leverages **Natural Language Processing (NLP), Machine Learning (ML), and Retrieval-Augmented Generation (RAG)** to assist users in career development and academic research.

---

## 🚀 Live Platform
**Experience the unified platform live here:**  
👉 **[https://ai-career-research-assistant-resume.onrender.com](https://ai-career-research-assistant-resume.onrender.com)**

*(Note: The platform is hosted on a free tier; please allow 50+ seconds for the initial load if the server is sleeping.)*

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Objectives](#-objectives)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Project Workflow](#-project-workflow)
- [Installation & Setup](#-installation--setup)
- [Usage Guide](#-usage-guide)
- [Modules Description](#-modules-description)
- [Dataset Information](#-dataset-information)
- [Testing](#-testing)
- [Project Status](#-project-status)
- [Future Enhancements](#-future-enhancements)
- [Contributors](#-contributors)
- [License](#-license)

---

## 🌟 Overview

The **AI Career & Research Assistant Platform** is designed to simplify two major domains:

1. **Career Development**
2. **Academic Research**

It enables users to analyze resumes, discover job opportunities, identify skill gaps, generate research papers, and extract insights from academic documents — all in one platform.

---

## 🎯 Objectives

- Automate resume evaluation and ATS scoring  
- Provide intelligent job recommendations  
- Identify skill gaps and suggest learning paths  
- Generate structured research papers from codebases  
- Enable intelligent querying of research documents  
- Reduce manual effort in academic and career workflows  

---

## 🚀 Key Features

### 🧑‍💼 Career Intelligence Module

- **Resume Parsing**
  - Supports PDF and DOCX formats
  - Extracts structured sections (Education, Skills, Experience)

- **ATS Score Evaluation**
  - Multi-parameter scoring system
  - Checks formatting, skills, and completeness

- **Skill Extraction**
  - Uses a curated skills database
  - Handles aliases and variations

- **Job Recommendation Engine**
  - Powered by BERT (Sentence Transformers)
  - Semantic similarity matching with job descriptions

- **Skill Gap Analysis**
  - Identifies missing skills for target roles

- **Learning Roadmap Generator**
  - Provides structured and time-based learning plans

---

### 📚 Research Intelligence Module

- **Research Paper Generator**
  - Converts GitHub repositories into IEEE-style papers
  - Generates Abstract, Introduction, Methodology, etc.

- **RAG-based Q&A System**
  - Upload multiple research papers
  - Ask context-aware questions
  - Retrieves accurate answers using vector search

- **Multi-Session Support**
  - Maintains independent research sessions

- **Interactive UI**
  - Real-time processing visualization
  - Smooth and modern user experience

---

## 🏗️ System Architecture

The system follows a **modular architecture**:

---

## 🗄️ Phase 1 — Foundation: Accounts, Database & Persistence

Phase 1 turns the demo into a real product students can keep using: every analysis,
goal and research chat is saved per user.

### What was added
- **User accounts** — `/register`, `/login`, `/logout` (email + password, Werkzeug
  hashing; passwords are never stored in plaintext). Navbar shows login state on
  every page.
- **Database** — Flask-SQLAlchemy. `DATABASE_URL` env var (Postgres-ready;
  `postgres://` auto-converted), SQLite file `acra.db` by default for local dev.
- **Models** — `User`, `ResumeAnalysis` (full result JSON per analysis),
  `ResearchSession` (chat history per user, auto-split when the document changes),
  `Goal` (career goals with target dates + done/active status).
- **Resume flow** — `/analyze` still works **anonymously** (in-memory result).
  When logged in, the analysis is saved and the result opens at `/results/db-<id>`;
  history lives at `/dashboard` (login required), which also hosts the goals tracker.
- **Research chat** — when logged in, each `/api/chat_research` exchange is
  appended to a per-user session; the client keeps the `research_session_id` in
  localStorage so follow-ups stay in the same conversation.

### Setup
```bash
cp .env.example .env        # then fill in GEMINI_API_KEY + SECRET_KEY
pip install -r requirements.txt
python unified_app.py       # dev server on :5000
# production:
gunicorn unified_app:app
```

### Testing
```bash
pytest tests/ -q            # 17 tests: auth flow, persistence, goals,
                            # research sessions, and no-regression GET checks
```

### Deliberately deferred
- **Google OAuth** — needs the user to create OAuth credentials in Google Cloud
  Console (human gate). Email/password auth ships in Phase 1.
- **Alembic migrations** — `db.create_all()` is used for now; migrations arrive
  with the next schema change.
- **Saved research sessions in the sidebar UI** — sessions are persisted
  server-side; rendering history in the research sidebar is Phase 2 UI work.
