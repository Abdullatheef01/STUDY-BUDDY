# Project Summary: AI Resume Analyzer & Job Recommendation System

## 🌟 Overview
The **AI Resume Analyzer & Job Recommendation System** is a comprehensive full-stack platform designed to automate and enhance the job application process for candidates. It leverages cutting-edge Natural Language Processing (NLP) and Machine Learning (ML) to provide deep insights into resume quality, ATS compatibility, and career alignment.

## 🏗️ System Architecture
The application follows a modular architecture, separating the core intelligence logic from the web interface.

### 1. Data Layer
The system uses a set of curated CSV datasets for high-performance retrieval without the overhead of a database:
- `jobs.csv`: Contains 50+ detailed job roles, categories, and required skill profiles.
- `skills_db.csv`: A comprehensive dictionary of 250+ skills mapped to categories and aliases for robust extraction.
- `company_questions.csv` & `coding_questions.csv`: Datasets for interview and coding specific practice.

### 2. Backend Modules (The Intelligence Core)
The backend is built in **Python 3.10+** and organized into specialized packages:

- **`parser/`**: 
    - Text extraction from PDF (`PyPDF2`) and DOCX (`python-docx`).
    - Sophisticated text cleaning and normalization.
    - Section extraction (identifying Education, Experience, Skills, etc.) using pattern matching.
- **`models/`**:
    - **Skill Extractor**: A rule-based engine that identifies skills using the alias-mapped skills database.
    - **BERT Matcher**: The "brain" of the recommender. It uses **`sentence-transformers` (all-MiniLM-L6-v2)** to compute semantic similarity between the resume text and job descriptions.
    - **ATS Scorer**: Evaluates resumes across 5 dimensions: Skill Match, Section Completeness, Content Quality, Contact Info, and formatting.
    - **Resume Feedback**: An AI-driven suggestions engine that provides actionable steps for improvement.
- **`recommendation/`**:
    - **Job Recommender**: Ranks roles based on a weighted blend of BERT semantic scores and keyword matching.
    - **Skill Gap Analysis**: Identifies missing skills for top-matched jobs and prioritizes them.
    - **Learning Roadmap**: Generates time-estimated learning paths with resource suggestions.
- **`preparation/`**:
    - Generates role-based interview questions and maps them to top tech companies.

## ⚙️ Backend Stability & Performance
The system includes two critical architectural optimizations for Windows environments:
- **Server-Side Result Caching**: To bypass the 4KB limit of browser cookies, analysis results are cached on the server in a `RESULTS_CACHE` dict, indexed by a unique `analysis_id`.
- **Reloader-Free Execution**: Disables the aggressive Flask reloader to prevent infinite loops when handling large ML libraries like `torch` and `transformers`.

## 📦 Core Technologies
- **Framework**: Flask (Web App)
- **Deep Learning**: Sentence-Transformers (BERT)
- **NLP Utilities**: NLTK (Tokenization, Stopwords)
- **Data Science**: Pandas, Scikit-Learn, Numpy
- **File Processing**: PyPDF2, python-docx
