# AI Resume Analyzer and Job Recommendation System

> An AI-powered career support platform for resume analysis, ATS scoring, semantic job matching, skill gap detection, resume improvement, and interview preparation.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-black)
![NLP](https://img.shields.io/badge/NLP-BERT-green)
![Status](https://img.shields.io/badge/Project-Academic%20Project-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📌 Overview

The **AI Resume Analyzer and Job Recommendation System** is an intelligent web application designed to help candidates improve their employability.

The system analyzes an uploaded resume, extracts important information such as skills, education, projects, and experience, calculates the **ATS score**, recommends suitable **job roles**, identifies **missing skills**, and provides **resume improvement suggestions**. It also supports **interview preparation** and **company-specific coding practice**, making it a complete career guidance platform rather than just a resume screening tool.

---

## ❗ Problem Statement

Most existing resume analyzer projects stop at:

- resume parsing
- keyword matching
- basic job recommendations

They do not help the candidate improve further.

Candidates often do not know:

- why their resume is weak
- which skills they are missing
- what jobs best match their profile
- how to improve their resume for ATS
- how to prepare for interviews and coding rounds

This project solves that problem by combining **resume analysis**, **AI-based recommendation**, **skill gap analysis**, and **interview preparation** into one platform.

---

## 🎯 Objectives

- To build a system that parses resumes in PDF or DOC format
- To extract useful information such as skills, education, projects, and work experience
- To calculate ATS score based on resume quality and keyword relevance
- To recommend suitable job roles using semantic similarity
- To identify missing skills for target roles
- To provide AI-based resume improvement suggestions
- To support interview preparation and company-specific coding practice
- To build an interactive dashboard for result visualization

---

## 🚀 Key Features

- 📄 Resume Upload and Parsing
- 🧠 Skill Extraction using NLP
- 🎯 Semantic Job Matching using BERT
- 📊 ATS Resume Score
- 🧩 Missing Skill Detection
- ✨ AI Resume Improvement Suggestions
- 🛤 Career Path Recommendation
- 💬 Intelligent CV Feedback
- 🎤 Interview Question Generation
- 💻 Company-Specific Coding Practice

---

## 🏗️ System Architecture

```text
User
 │
 │ Upload Resume (PDF/DOC)
 ▼
Resume Parser
 │
 │ Extract text from resume
 ▼
Text Preprocessing
 │
 │ Cleaning and normalization
 ▼
Information Extraction
 │
 ├ Skills
 ├ Education
 ├ Experience
 └ Projects
 ▼
AI Matching Engine
 │
 ├ Semantic matching using BERT
 ├ Keyword analysis
 └ ATS scoring
 ▼
Recommendation Engine
 │
 ├ Job role recommendation
 ├ Match score
 ├ Skill gap analysis
 └ Career path suggestion
 ▼
Improvement & Preparation Module
 │
 ├ Resume improvement suggestions
 ├ Interview preparation
 ├ Coding practice
 └ Learning roadmap
 ▼
Dashboard Output


---

## ⚙️ Tech Stack

### Backend
- Python
- Flask

### NLP / AI
- BERT
- spaCy / NLTK
- scikit-learn

### Frontend
- HTML
- CSS
- JavaScript

### Database
- SQLite / MongoDB

### File Processing
- PyPDF2 / pdfplumber
- python-docx


---

## 📂 Project Structure

```text
career-ai/
│
├── data/
│   ├── resumes.csv
│   ├── jobs.csv
│   ├── coding_questions.csv
│   └── company_questions.csv
│
├── models/
│   ├── bert_matcher.py
│   ├── skill_extractor.py
│   ├── ats_scorer.py
│   └── resume_feedback.py
│
├── parser/
│   ├── pdf_reader.py
│   ├── docx_reader.py
│   ├── text_cleaning.py
│   └── section_extractor.py
│
├── recommendation/
│   ├── job_recommender.py
│   ├── skill_gap_analysis.py
│   ├── learning_roadmap.py
│   └── career_guidance.py
│
├── preparation/
│   ├── interview_questions.py
│   ├── company_questions.py
│   └── coding_practice.py
│
├── web_app/
│   ├── app.py
│   ├── templates/
│   │   ├── index.html
│   │   ├── dashboard.html
│   │   └── practice.html
│   └── static/
│       ├── style.css
│       └── script.js
│
├── requirements.txt
└── README.md



---

## 🔄 Workflow

1. User uploads a resume  
2. System extracts text from the file  
3. Resume text is cleaned and processed  
4. Skills and important information are extracted  
5. Resume is matched with job descriptions using semantic similarity  
6. ATS score is calculated  
7. Suitable job roles are recommended  
8. Missing skills are identified  
9. Resume improvement suggestions are generated  
10. Interview and coding practice recommendations are displayed




---

## 📊 Output Dashboard

The dashboard will display:

- Extracted Skills
- Recommended Job Roles
- Match Scores
- ATS Score
- Missing Skills
- Resume Improvement Suggestions
- Career Path Suggestions
- Interview Questions
- Company-Specific Coding Practice



---

## 🌟 Innovation / Unique Selling Points

Unlike traditional resume analyzer projects, this system does not stop at job matching.

### Existing systems usually provide:
- Resume parsing
- Keyword matching
- Basic recommendations

### This project additionally provides:
- Semantic job matching using BERT
- ATS score analysis
- Skill gap detection
- Resume improvement suggestions
- Career path guidance
- Interview preparation
- Company-specific coding practice
- End-to-end candidate improvement support





---

## 📈 Future Scope

- LinkedIn profile analysis
- Real-time job scraping
- Personalized learning roadmap
- Recruiter dashboard
- Mock interview chatbot
- Resume version comparison
- Multilingual resume analysis
- Salary prediction



---

## 🛠️ Installation

```bash
git clone https://github.com/Rohit11danu/career-ai.git
cd career-ai
pip install -r requirements.txt
python app.py


---

## ▶️ Usage

- Launch the web application
- Upload your resume
- View ATS score and job recommendations
- Check missing skills and improvement suggestions
- Explore interview and coding practice recommendations



---

## 📚 Conclusion

The **AI Resume Analyzer and Job Recommendation System** is more than a resume screening tool. It is a complete **career guidance and preparation platform** that helps candidates understand their profile, improve their resume, discover suitable job roles, identify skill gaps, and prepare for interviews and coding rounds.


---

## 👨‍💻 Author

**Rohit danu**

