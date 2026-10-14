"""
Unified AI-Powered Excellence Platform
Main Entry Point

Phase 1 (Foundation): Flask-SQLAlchemy + Flask-Login persistence.
- Users can register / log in (email + password, Werkzeug hashing).
- Resume analyses are saved per-user when logged in; /analyze still works anonymously.
- /dashboard (login required) shows analysis history + career goals.
- Research chat sessions are saved per-user when logged in.
"""
import os
import re
import sys
import time
import uuid
import json
import random
import hashlib
import secrets
import logging

from datetime import datetime, date, timedelta, timezone

import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from authlib.integrations.flask_client import OAuth
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from github_integration import (analyze_github_profile, GithubAPIError,
                                validate_github_username)
from leetcode_integration import (fetch_leetcode_stats, get_card_stats,
                                  render_leetcode_card_svg, render_error_svg,
                                  LeetCodeAPIError, validate_leetcode_username)

log = logging.getLogger("acra")

# Load environment variables (.env for local dev, platform env vars in prod)
load_dotenv()

# google-genai (new SDK) is optional: the app must boot and serve everything
# except live Gemini calls even if the package / API key is missing.
try:
    from google import genai as genai_client
    from google.genai import types as genai_types
    _GENAI_IMPORTED = True
except Exception:  # pragma: no cover - defensive
    genai_client = None
    genai_types = None
    _GENAI_IMPORTED = False

# Sentinel API-key values that mean "not configured" (must stay in sync with
# .env.example so a fresh setup always shows the friendly missing-key message).
_GEMINI_KEY_SENTINELS = frozenset({
    "", "your_actual_api_key_here", "<redacted>", "change-me",
    "YOUR_GEMINI_API_KEY", "paste-your-key-here",
})


def _gemini_api_key():
    """Return the configured Gemini key, or None when missing/placeholder."""
    key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    return key if key and key not in _GEMINI_KEY_SENTINELS else None


def _ai_ready():
    return _GENAI_IMPORTED and _gemini_api_key() is not None


class GeminiError(Exception):
    """A Gemini failure with a user-safe message (safe to return to clients)."""


class GithubRepoError(Exception):
    """A GitHub repository fetch failure with a user-safe message."""


# --- Gemini model discovery cache (module level, refreshed hourly) ---
_MODEL_CACHE = {"names": [], "fetched_at": 0.0}
_MODEL_CACHE_TTL = 3600


def _make_gemini_client():
    """Build a genai client with a 30s HTTP timeout, or None when unusable.

    The HTTP client is constructed explicitly (proxy + CA bundle from env)
    because httpx's env parsing chokes on bracketed IPv6 entries that some
    sandboxes put in no_proxy (e.g. "[::1]" -> "Invalid port" crash).
    """
    key = _gemini_api_key()
    if not _GENAI_IMPORTED or not key:
        return None
    import httpx
    proxy = (os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
             or os.getenv("HTTP_PROXY") or os.getenv("http_proxy"))
    verify = os.getenv("SSL_CERT_FILE") or True
    # NB: both sync AND async clients must be supplied - the SDK builds an
    # async client unconditionally, which would hit the same env bug.
    http_client = httpx.Client(proxy=proxy, timeout=30.0,
                               trust_env=False, verify=verify)
    async_client = httpx.AsyncClient(proxy=proxy, timeout=30.0,
                                     trust_env=False, verify=verify)
    return genai_client.Client(
        api_key=key,
        http_options=genai_types.HttpOptions(
            timeout=30_000,  # ms
            httpx_client=http_client,
            httpx_async_client=async_client),
    )


def _discover_model_names(client):
    """Return cached generateContent-capable model names (hourly refresh)."""
    now = time.monotonic()
    if _MODEL_CACHE["names"] and now - _MODEL_CACHE["fetched_at"] < _MODEL_CACHE_TTL:
        return list(_MODEL_CACHE["names"])
    names = []
    for m in client.models.list():
        actions = [str(a).lower() for a in (getattr(m, "supported_actions", None) or [])]
        if "generatecontent" in actions or "generate_content" in actions:
            names.append(m.name)
    # Prefer flash/pro variants first, keep the rest as fallbacks.
    priority = [n for kw in ("flash", "pro") for n in names if kw in n.lower()]
    ordered = priority + [n for n in names if n not in priority]
    _MODEL_CACHE.update({"names": ordered, "fetched_at": now})
    return list(ordered)


def _github_get(path):
    """GET a GitHub REST API path with timeout; raises GithubRepoError."""
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "acra-student-platform"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer {}".format(token.strip())
    try:
        resp = requests.get("https://api.github.com" + path, headers=headers, timeout=10)
    except requests.RequestException as e:
        raise GithubRepoError(
            "Could not reach GitHub right now. Check your connection and try again."
        ) from e
    if resp.status_code == 404:
        raise GithubRepoError("Repository not found on GitHub. Check the URL and try again.")
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise GithubRepoError("GitHub's API rate limit was hit. Please try again in a few minutes.")
    if not resp.ok:
        raise GithubRepoError("GitHub returned an unexpected response ({}).".format(resp.status_code))
    return resp.json()


def _fetch_repo_data(owner, repo):
    """Fetch real repository facts from the GitHub API for the constructor."""
    meta = _github_get("/repos/{}/{}".format(owner, repo))
    languages = _github_get("/repos/{}/{}/languages".format(owner, repo)) or {}
    readme_text = ""
    try:
        readme = _github_get("/repos/{}/{}/readme".format(owner, repo))
        import base64
        readme_text = base64.b64decode(readme.get("content", "") or "").decode(
            "utf-8", "ignore")[:4000]
    except GithubRepoError:
        readme_text = ""
    files, dirs = [], set()
    try:
        tree = _github_get("/repos/{}/{}/git/trees/HEAD?recursive=1".format(owner, repo))
        for entry in (tree.get("tree") or [])[:3000]:
            if entry.get("type") == "blob":
                files.append(entry.get("path", ""))
                if "/" in entry.get("path", ""):
                    dirs.add(entry["path"].split("/")[0])
    except GithubRepoError:
        pass
    total_lang_bytes = sum(languages.values()) or 1
    top_languages = sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:5]
    file_count = len(files)
    complexity = ("High" if file_count > 200 or len(languages) > 6
                  else "Moderate" if file_count > 50 else "Focused")
    return {
        "full_name": meta.get("full_name", "{}/{}".format(owner, repo)),
        "description": (meta.get("description") or "No description provided.")[:500],
        "stars": meta.get("stargazers_count", 0),
        "forks": meta.get("forks_count", 0),
        "primary_language": meta.get("language") or "Unknown",
        "topics": (meta.get("topics") or [])[:10],
        "top_languages": [(lang, round(100.0 * n / total_lang_bytes, 1))
                          for lang, n in top_languages],
        "file_count": file_count,
        "top_dirs": sorted(dirs)[:12],
        "sample_files": files[:40],
        "has_tests": any("test" in f.lower() for f in files),
        "has_docker": any(f.lower().endswith("dockerfile") or "docker-compose" in f.lower()
                          for f in files),
        "has_ci": any(".github/workflows" in f for f in files),
        "readme": readme_text,
        "complexity": complexity,
    }


def _parse_json_safely(text):
    """Strip code fences and parse JSON; raises ValueError on failure."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)
    return json.loads(t.strip())

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import logic from Resume Analyzer components
from parser.pdf_reader import extract_text_from_pdf
from parser.docx_reader import extract_text_from_docx
from parser.text_cleaning import clean_text, extract_email, extract_phone, extract_links
from parser.section_extractor import extract_sections, extract_education_details, extract_experience_years
from models.skill_extractor import extract_skills, get_skills_by_category, get_skill_names
from models.ats_scorer import calculate_ats_score
from models.resume_feedback import generate_feedback, get_overall_summary
from jd_matcher import (score_jd_match, generate_rule_based_suggestions,
                        JD_MIN_CHARS, JD_MAX_CHARS)
from bullet_rewriter import (improve_bullet, BULLET_MIN_CHARS, BULLET_MAX_CHARS)
from cover_generator import (rule_based_cover_letter, rule_based_outreach,
                             validate_cover_inputs, TONES)
from linkedin_grader import (grade_linkedin_profile, generate_rule_based_summary,
                             validate_linkedin_inputs)
from career_assessment import (score_assessment, rule_based_why,
                               validate_assessment_inputs, public_questions,
                               QUESTIONS, TOP_N_CLUSTERS)
from salary_data import (get_options as salary_options, query as salary_query,
                          SalaryDataError)
from opportunities import (list_opportunities, get_meta as opp_meta,
                           opp_exists, TYPES as OPP_TYPES, OpportunityDataError)
from portfolio import validate_portfolio_payload, unique_slug
from mock_interview import (interview_options, pick_questions, score_answer,
                            generate_rule_based_feedback, validate_interview_setup)
from communication_coach import analyze_transcript, validate_coach_inputs
from dsa_practice import (all_problems, get_problem, topics as dsa_topics,
                          difficulties as dsa_difficulties,
                          filter_problems, public_problem, reveal_hint,
                          reveal_approach, validate_status_payload,
                          weak_topic_diagnosis, VALID_STATUSES)
from aptitude_test import (categories as aptitude_categories,
                           pick_questions as aptitude_pick,
                           validate_test_setup, score_attempt,
                           SUBMIT_GRACE_SEC, all_questions as aptitude_all)
from star_builder import (COMPETENCIES, COMPETENCY_IDS, SECTIONS,
                          SECTION_GUIDE, all_examples, examples_for,
                          get_example, validate_draft, score_draft,
                          generate_rule_based_rewrite_tip)
from learning_roadmaps import (list_skills as roadmap_skills,
                               list_domains as roadmap_domains,
                               get_skill as get_roadmap_skill,
                               list_roles as roadmap_roles,
                               analyze_gap, build_personal_roadmap,
                               validate_progress_payload, validate_gap_payload,
                               progress_summary as roadmap_progress_summary)
from recommendation.job_recommender import get_recommendations
from recommendation.skill_gap_analysis import analyze_skill_gaps
from recommendation.learning_roadmap import generate_roadmap, estimate_total_time
from recommendation.career_guidance import suggest_career_paths
from preparation.interview_questions import generate_interview_questions
from preparation.company_questions import get_company_questions, get_available_companies as get_interview_companies, get_company_stats
from preparation.coding_practice import (
    get_coding_questions, get_available_companies as get_coding_companies,
    get_available_topics, get_company_coding_stats, get_recommended_problems
)

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
oauth = OAuth()  # social login clients (registered per-app in create_app)


# ========================================================
# --- DATABASE MODELS ---
# ========================================================

class User(UserMixin, db.Model):
    """Registered student user."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # --- Social login + profile integrations (added post-Phase-1) ---
    # google_sub is unique but enforced via a manual unique index (see
    # _ensure_schema) so pre-Phase-2 databases can adopt it without a rebuild.
    google_sub = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    github_username = db.Column(db.String(39), nullable=True)
    leetcode_username = db.Column(db.String(39), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ResumeAnalysis(db.Model):
    """A saved resume analysis belonging to a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    filename = db.Column(db.String(255))
    ats_score = db.Column(db.Float)
    result_json = db.Column(db.JSON)  # full analysis payload (dashboard rendering)
    # Cleaned resume text (truncated) so Wave-1 JD matching can reuse the
    # latest saved analysis without a re-upload. Backfilled via _ensure_schema.
    resume_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("analyses", lazy="dynamic",
                                                     cascade="all, delete-orphan"))


class JDMatchReport(db.Model):
    """A JD-matched ATS scoring report belonging to a user (Wave 1 #1)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    job_title = db.Column(db.String(255))
    score = db.Column(db.Float)
    report_json = db.Column(db.JSON)  # full match report payload
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("jd_match_reports", lazy="dynamic",
                                                     cascade="all, delete-orphan"))


class BulletRewrite(db.Model):
    """A saved bullet-rewrite result belonging to a user (Wave 1 #2)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    original = db.Column(db.Text, nullable=False)
    rewrites = db.Column(db.JSON)  # [{"label","text","tip"}...] + optional AI variant
    ai_powered = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("bullet_rewrites", lazy="dynamic",
                                                     cascade="all, delete-orphan"))


class ResumeVersion(db.Model):
    """A named, saved resume version belonging to a user (Wave 1 #3)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)  # e.g. "Backend v1"
    resume_text = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("resume_versions", lazy="dynamic",
                                                     cascade="all, delete-orphan"))


class CoverDoc(db.Model):
    """A generated cover letter / outreach message belonging to a user (Wave 1 #4)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    doc_type = db.Column(db.String(20), nullable=False)  # cover_letter | outreach
    title = db.Column(db.String(255))
    tone = db.Column(db.String(20), default="professional", nullable=False)
    content = db.Column(db.Text, nullable=False)
    ai_powered = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("cover_docs", lazy="dynamic",
                                                     cascade="all, delete-orphan"))


class LinkedInReport(db.Model):
    """A LinkedIn profile grading report belonging to a user (Wave 1 #5)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    score = db.Column(db.Float)
    report_json = db.Column(db.JSON)  # full grading report payload
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("linkedin_reports", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


# Kanban stages for the application tracker (Wave 1 #6).
TRACKER_STAGES = (
    ("wishlist", "Wishlist"),
    ("applied", "Applied"),
    ("oa", "OA / Assignment"),
    ("interview", "Interview"),
    ("offer", "Offer"),
    ("rejected", "Rejected"),
)
TRACKER_STAGE_IDS = {s[0] for s in TRACKER_STAGES}


class JobApplication(db.Model):
    """A tracked job application belonging to a user (Wave 1 #6)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    company = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), nullable=False)
    stage = db.Column(db.String(20), nullable=False, default="wishlist", index=True)
    jd_url = db.Column(db.String(500))
    notes = db.Column(db.Text)
    applied_date = db.Column(db.Date)
    stage_updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                                 nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("job_applications", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class CareerAssessment(db.Model):
    """A career-discovery assessment result belonging to a user (Wave 1 #7)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    top_clusters = db.Column(db.JSON)  # ranked cluster results
    answers_json = db.Column(db.JSON)  # {question_id: option_index}
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("career_assessments", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class InterviewSession(db.Model):
    """A company-specific mock interview session belonging to a user (Wave 2 #13)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    company = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    questions_json = db.Column(db.JSON)  # selected question dicts
    answers_json = db.Column(db.JSON)    # [{question_id, answer, scoring, feedback}]
    total_score = db.Column(db.Float)
    ai_powered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("interview_sessions", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class CommunicationAnalysis(db.Model):
    """A communication-coach analysis belonging to a user (Wave 2 #14)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    clarity_score = db.Column(db.Float)
    analysis_json = db.Column(db.JSON)  # full analysis payload
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("communication_analyses", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class DSAProgress(db.Model):
    """Per-user DSA practice progress (Wave 2 #15). One row per user+problem."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    problem_id = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), default="attempted", nullable=False)  # attempted|solved|stuck
    hints_used = db.Column(db.Integer, default=0, nullable=False)
    code = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "problem_id", name="uq_dsa_user_problem"),)

    user = db.relationship("User", backref=db.backref("dsa_progress", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class AptitudeAttempt(db.Model):
    """A timed aptitude test attempt belonging to a user (Wave 2 #16)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False)  # quantitative|logical|verbal|mixed
    num_questions = db.Column(db.Integer, nullable=False)
    time_limit_sec = db.Column(db.Integer, nullable=False)
    question_ids = db.Column(db.JSON)   # ordered question ids (server-picked)
    answers_json = db.Column(db.JSON)   # {qid: chosen_index}
    results_json = db.Column(db.JSON)   # per-question review payload
    summary_json = db.Column(db.JSON)   # score + analytics
    expired = db.Column(db.Boolean, default=False, nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)  # server timestamp
    submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("aptitude_attempts", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class STARDraft(db.Model):
    """A STAR answer draft belonging to a user (Wave 2 #17)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    competency = db.Column(db.String(50), nullable=False)
    situation = db.Column(db.Text, default="")
    task = db.Column(db.Text, default="")
    action = db.Column(db.Text, default="")
    result = db.Column(db.Text, default="")
    scores_json = db.Column(db.JSON)       # per-section + overall scores
    suggestions_json = db.Column(db.JSON)  # rewrite suggestions
    ai_powered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("star_drafts", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class RoadmapProgress(db.Model):
    """Per-user learning-roadmap progress (Wave 3 #18). One row per user+skill+stage."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    skill_id = db.Column(db.String(50), nullable=False, index=True)
    stage = db.Column(db.String(20), nullable=False)  # beginner|intermediate|advanced
    status = db.Column(db.String(20), default="not_started", nullable=False)  # not_started|in_progress|completed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "skill_id", "stage",
                                          name="uq_roadmap_user_skill_stage"),)

    user = db.relationship("User", backref=db.backref("roadmap_progress", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class ResearchSession(db.Model):
    """A saved research-chat conversation belonging to a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(255))
    data = db.Column(db.JSON)  # {"messages": [{"role":..., "content":...}], "doc_hash": ...}
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("research_sessions", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class Goal(db.Model):
    """A career goal tracked by a user on their dashboard."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    target_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)  # active | done
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("goals", lazy="dynamic",
                                                     cascade="all, delete-orphan"))


class OpportunityBookmark(db.Model):
    """A user's bookmarked opportunity from the radar board (Wave 1 #9)."""
    __tablename__ = "opportunity_bookmark"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    opp_id = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "opp_id",
                                         name="uq_bookmark_user_opp"),)

    user = db.relationship("User", backref=db.backref("opportunity_bookmarks", lazy="dynamic",
                                                      cascade="all, delete-orphan"))


class Portfolio(db.Model):
    """A user's one-page portfolio (Wave 1 #12). One row per user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False,
                       unique=True, index=True)
    slug = db.Column(db.String(60), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(80), nullable=False)
    headline = db.Column(db.String(140))
    bio = db.Column(db.Text)
    skills = db.Column(db.JSON)
    projects = db.Column(db.JSON)
    links = db.Column(db.JSON)
    show_github = db.Column(db.Boolean, default=False, nullable=False)
    show_leetcode = db.Column(db.Boolean, default=False, nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("portfolio", uselist=False,
                                                      cascade="all, delete-orphan"))


class AnonymousAnalysis(db.Model):
    """A resume analysis for an anonymous visitor.

    Replaces the old per-process RESULTS_CACHE dict so results survive
    restarts and work across multiple gunicorn workers. Rows expire after
    24h and are cleaned up opportunistically on each new analysis.
    """
    id = db.Column(db.String(36), primary_key=True)  # uuid4 hex
    filename = db.Column(db.String(255))
    result_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)


_ANON_TTL_SECONDS = 24 * 3600


class ProfileSnapshot(db.Model):
    """Cached third-party profile snapshot (GitHub / LeetCode).

    One row per (user, provider); refreshed on demand with 24h freshness so
    we stay kind to the upstream APIs. The payload in `data` is whatever the
    integration module returned (analyzer result or stats dict)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    provider = db.Column(db.String(20), nullable=False)  # "github" | "leetcode"
    username = db.Column(db.String(80), nullable=False)
    data = db.Column(db.JSON)
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("profile_snapshots", lazy="dynamic",
                                                      cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("user_id", "provider",
                                          name="uq_snapshot_user_provider"),)


_SNAPSHOT_TTL_SECONDS = 24 * 3600


def _utcnow_naive():
    """UTC now without tzinfo (SQLite returns naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _purge_expired_anonymous():
    """Delete expired anonymous analyses (best-effort, never raises)."""
    try:
        AnonymousAnalysis.query.filter(
            AnonymousAnalysis.expires_at < _utcnow_naive()).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("Failed to purge expired anonymous analyses")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ========================================================
# --- HELPERS ---
# ========================================================

# Anonymous results now live in the AnonymousAnalysis table (P1#8).
# (The old per-process RESULTS_CACHE dict was removed: it lost data on
# every restart and broke under multiple gunicorn workers.)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def json_safe(obj):
    """Round-trip through JSON so DB-stored payloads are always serializable
    (numpy types from the ML pipeline become plain python types)."""
    return json.loads(json.dumps(obj, default=str))


def get_db_url():
    db_url = os.getenv("DATABASE_URL", "sqlite:///acra.db")
    # Heroku/Render style postgres:// -> SQLAlchemy postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def is_safe_next(target):
    """Only allow relative redirects after login."""
    return target and target.startswith("/") and not target.startswith("//")


def _ensure_schema():
    """Backfill social/integration columns on pre-existing databases.

    Phase 1 used db.create_all() with no migrations, and create_all() never
    adds columns to an existing table. This inspects the `user` table and
    ALTERs in any missing columns (SQLite + Postgres compatible), plus a
    unique index on google_sub (NULLs stay non-conflicting on both dialects).
    Safe to run on every boot; a no-op when the schema is current.
    """
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    if "user" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("user")}
    wanted = {
        "google_sub": "VARCHAR(255)",
        "avatar_url": "VARCHAR(512)",
        "github_username": "VARCHAR(39)",
        "leetcode_username": "VARCHAR(39)",
    }
    have_index = any(i["name"] == "ix_user_google_sub"
                     for i in insp.get_indexes("user"))
    missing = [(col, ddl) for col, ddl in wanted.items() if col not in existing]
    if missing or not have_index:
        with db.engine.begin() as conn:
            for col, ddl in missing:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN {} {}'.format(col, ddl)))
                log.info("Schema evolution: added user.%s", col)
            conn.execute(text(
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_user_google_sub ON "user" (google_sub)'))
    # Wave-1: resume_text on resume_analysis (TEXT works on SQLite + Postgres).
    # Independent of the user-table backfill above (no shared early return).
    if "resume_analysis" in insp.get_table_names():
        ra_existing = {c["name"] for c in insp.get_columns("resume_analysis")}
        if "resume_text" not in ra_existing:
            with db.engine.begin() as conn:
                conn.execute(text('ALTER TABLE "resume_analysis" ADD COLUMN resume_text TEXT'))
            log.info("Schema evolution: added resume_analysis.resume_text")


# ========================================================
# --- GOOGLE OAUTH (Authlib) ---
# ========================================================

def _google_configured():
    """True when Google OAuth credentials are present in the environment."""
    return bool((os.getenv("GOOGLE_CLIENT_ID") or "").strip()
                and (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip())


def _register_google_oauth(app):
    """Register the Google OpenID client (identity scopes only)."""
    oauth.register(
        "google",
        client_id=os.getenv("GOOGLE_CLIENT_ID").strip(),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET").strip(),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        # Identity only: we never read Drive, Gmail, Calendar, etc.
        client_kwargs={"scope": "openid email profile"},
    )


def _process_google_login(userinfo):
    """Find-or-create the user for a verified Google identity.

    Never creates a duplicate account for the same email: an existing
    password user with the same email gets their Google identity linked.
    Returns (user, is_new). Raises ValueError on unverifiable identity.
    """
    sub = (userinfo.get("sub") or "").strip()
    email = (userinfo.get("email") or "").strip().lower()
    if not sub or not email or "@" not in email:
        raise ValueError("Google did not return a verifiable identity. Please try again.")
    if userinfo.get("email_verified") is False:
        raise ValueError("Your Google email is not verified. Please verify it and try again.")

    user = User.query.filter_by(google_sub=sub).first()
    if user:
        return user, False
    user = User.query.filter_by(email=email).first()
    if user:
        user.google_sub = sub
        if not user.avatar_url:
            user.avatar_url = (userinfo.get("picture") or "")[:512] or None
        db.session.commit()
        log.info("Linked Google identity to existing account %s", email)
        return user, False
    # Brand-new account. The password hash is a random secret that can never
    # validate, so this account is Google-sign-in-only (password_hash stays
    # NOT NULL, no schema change needed).
    user = User(
        name=(userinfo.get("name") or email.split("@")[0])[:120],
        email=email,
        google_sub=sub,
        avatar_url=(userinfo.get("picture") or "")[:512] or None,
    )
    user.set_password(secrets.token_hex(32))
    db.session.add(user)
    db.session.commit()
    log.info("Created account via Google sign-in: %s", email)
    return user, True


# ========================================================
# --- PROFILE SNAPSHOT CACHE ---
# ========================================================

def _fresh_snapshot(user_id, provider, max_age_seconds=_SNAPSHOT_TTL_SECONDS):
    """Return the user's cached snapshot for a provider, or None if stale."""
    row = ProfileSnapshot.query.filter_by(user_id=user_id, provider=provider).first()
    if not row or not row.fetched_at:
        return None
    age = (datetime.now(timezone.utc).replace(tzinfo=None)
           - row.fetched_at.replace(tzinfo=None)).total_seconds()
    return row if age < max_age_seconds else None


def _store_snapshot(user_id, provider, username, data):
    """Upsert the cached snapshot for a (user, provider)."""
    row = ProfileSnapshot.query.filter_by(user_id=user_id, provider=provider).first()
    payload = json_safe(data)
    if row:
        row.username = username
        row.data = payload
        row.fetched_at = datetime.now(timezone.utc)
    else:
        row = ProfileSnapshot(user_id=user_id, provider=provider,
                              username=username, data=payload)
        db.session.add(row)
    db.session.commit()
    return row


# ========================================================
# --- APP FACTORY ---
# ========================================================

def create_app(config_overrides=None):
    app = Flask(__name__)

    # --- SECRET_KEY policy (P1#7) ---
    # Refuse to boot in production without a real secret; in local dev use
    # an ephemeral key with a loud warning (sessions won't survive restarts).
    secret = os.getenv("SECRET_KEY")
    _insecure = {None, "", "change-me-to-a-long-random-secret",
                 "unified-ai-platform-secret-2026"}
    if secret in _insecure:
        is_prod = (os.getenv("FLASK_ENV") == "production"
                   or os.getenv("RENDER") or os.getenv("DYNO"))
        if is_prod:
            raise RuntimeError(
                "SECRET_KEY is not set (or is still the placeholder). "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set it as an environment variable.")
        secret = secrets.token_hex(32)
        print("WARNING: SECRET_KEY is not set - using an ephemeral key for this "
              "local dev run. Set SECRET_KEY in .env for real use.")
    app.secret_key = secret

    app.config["SQLALCHEMY_DATABASE_URI"] = get_db_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max

    if config_overrides:
        app.config.update(config_overrides)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "info"
    csrf.init_app(app)
    limiter.init_app(app)
    oauth.init_app(app)
    if _google_configured():
        _register_google_oauth(app)
    if app.config.get("TESTING"):
        limiter.enabled = False

    register_routes(app)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()
        _ensure_schema()

    return app


def _error_payload(code, message):
    """JSON for API routes, styled page otherwise (P2#10)."""
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), code
    return render_template("error.html", code=code, message=message), code


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return _error_payload(400, getattr(e, "description", None)
                              or "That request wasn't quite right. Please try again.")

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        log.warning("CSRF validation failed: %s", e.description)
        return _error_payload(400, "Security check failed (expired form). "
                                   "Please reload the page and try again.")

    @app.errorhandler(404)
    def not_found(e):
        return _error_payload(404, "The page you asked for doesn't exist.")

    @app.errorhandler(405)
    def method_not_allowed(e):
        return _error_payload(405, getattr(e, "description", None)
                              or "That action isn't allowed with this method.")

    @app.errorhandler(429)
    def rate_limited(e):
        return _error_payload(429, "You're moving a bit fast. "
                                   "Please wait a moment and try again.")

    @app.errorhandler(500)
    def server_error(e):
        log.exception("Unhandled 500 error")
        return _error_payload(500, "Something went wrong on our side. "
                                   "Please try again in a moment.")


# ========================================================
# --- ROUTES ---
# ========================================================

def _jd_match_suggestions(report, jd_text):
    """Qualitative fix suggestions via Gemini, with a rule-based fallback.

    Returns (suggestions, ai_powered). The numeric score never depends on
    the LLM, so a Gemini outage degrades suggestions only - never the
    report itself.
    """
    fallback = generate_rule_based_suggestions(report)
    prompt = (
        "You are a senior career coach. A resume was scored against the "
        "job description below. Resume experience: ~{} years. "
        "Match score: {}/100. Missing skills/keywords (most important "
        "first): {}. Matched skills: {}.\n\n"
        "JOB DESCRIPTION (truncated):\n{}\n\n"
        'Return ONLY a JSON object like {{"suggestions": [{{"section": "...", '
        '"issue": "...", "fix": "..."}}]}} with at most 6 concrete, '
        "section-by-section fixes (Summary, Experience, Skills, Education, "
        "Formatting). Each fix must reference the actual JD above - no "
        "generic advice."
    ).format(
        report.get("resume_experience_years") or 0,
        report.get("score"),
        ", ".join((report.get("missing_keywords") or [])[:12]) or "none",
        ", ".join((report.get("matched_skills") or [])[:8]) or "none",
        (jd_text or "")[:4000],
    )
    # Robust JSON parsing: strip fences, retry once (constructor pattern).
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("JD-match suggestions: Gemini unavailable: %s", e)
            return fallback, False
        try:
            parsed = _parse_json_safely(raw)
            items = parsed.get("suggestions") if isinstance(parsed, dict) else None
            cleaned = []
            for it in (items or [])[:6]:
                if not isinstance(it, dict):
                    continue
                section = str(it.get("section") or "Overall")[:60]
                issue = str(it.get("issue") or "").strip()[:300]
                fix = str(it.get("fix") or "").strip()[:600]
                if issue and fix:
                    cleaned.append({"section": section, "issue": issue, "fix": fix})
            if cleaned:
                return cleaned, True
            log.warning("JD-match suggestions: model returned no usable items")
        except (ValueError, json.JSONDecodeError):
            log.warning("JD-match suggestions: non-JSON model output, retrying")
    return fallback, False


def _linkedin_suggestions(report, fields):
    """Polished LinkedIn fixes via Gemini, with a rule-based fallback.

    Returns (suggestions, ai_powered). The numeric score never depends on
    the LLM, so a Gemini outage degrades suggestions only - never the
    report itself.
    """
    fallback = [{"section": s["section"], "fix": s["fix"]}
                for s in (report.get("suggestions") or [])]
    weakest = sorted((report.get("breakdown") or {}).items(),
                     key=lambda kv: kv[1])[:3]
    prompt = (
        "You are a LinkedIn profile coach. A profile scored {}/100 with the "
        "weakest areas: {}. Profile sections (truncated):\n"
        "HEADLINE: {}\nABOUT: {}\nEXPERIENCE: {}\nSKILLS: {}\n\n"
        'Return ONLY a JSON object like {{"suggestions": [{{"section": "...", '
        '"fix": "..."}}]}} with at most 8 concrete, prioritized fixes. Each '
        "fix must reference the actual profile text above - no generic advice."
    ).format(
        report.get("score"),
        ", ".join("{} ({})".format(k, v) for k, v in weakest) or "none",
        (fields.get("headline") or "")[:600],
        (fields.get("about") or "")[:1500],
        (fields.get("experience") or "")[:2000],
        (fields.get("skills") or "")[:800],
    )
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("LinkedIn suggestions: Gemini unavailable: %s", e)
            return fallback, False
        try:
            parsed = _parse_json_safely(raw)
            items = parsed.get("suggestions") if isinstance(parsed, dict) else None
            cleaned = []
            for it in (items or [])[:8]:
                if not isinstance(it, dict):
                    continue
                section = str(it.get("section") or "Profile")[:60]
                fix = str(it.get("fix") or "").strip()[:600]
                if fix:
                    cleaned.append({"section": section, "fix": fix})
            if cleaned:
                return cleaned, True
            log.warning("LinkedIn suggestions: model returned no usable items")
        except (ValueError, json.JSONDecodeError):
            log.warning("LinkedIn suggestions: non-JSON model output, retrying")
    return fallback, False


def _interview_feedback(scored_answers, questions):
    """Polish per-answer strengths/improvements via Gemini, rule-based fallback.

    Returns (feedback_list, ai_powered). Numeric scores never depend on the
    LLM; a Gemini outage degrades the wording only.
    """
    fallback = [generate_rule_based_feedback(s, q)
                for s, q in zip(scored_answers, questions)]
    compact = []
    for s, q in zip(scored_answers, questions):
        compact.append({
            "q": (q.get("question") or "")[:300],
            "key_points": (q.get("key_points") or [])[:4],
            "scores": s["scores"],
            "answer": (s.get("answer_text") or "")[:1200],
        })
    prompt = (
        "You are an expert interview coach. Below are a candidate's answers "
        "with rubric scores (correctness/40, communication/25, depth/20, "
        "edge_cases/15). For EACH answer return one strengths item and up to "
        "3 improvements, referencing the actual answer text - no generic advice.\n"
        'Return ONLY JSON like {"feedback": [{"strengths": ["..."], '
        '"improvements": ["..."]}]} with one entry per answer, in order.\n'
        "ANSWERS:\n" + json.dumps(compact)[:12000]
    )
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("Interview feedback: Gemini unavailable: %s", e)
            return fallback, False
        try:
            parsed = _parse_json_safely(raw)
            items = parsed.get("feedback") if isinstance(parsed, dict) else None
            if isinstance(items, list) and len(items) == len(compact):
                cleaned = []
                for it in items:
                    if not isinstance(it, dict):
                        cleaned.append({"strengths": [], "improvements": []})
                        continue
                    cleaned.append({
                        "strengths": [str(x)[:400] for x in (it.get("strengths") or [])[:3]],
                        "improvements": [str(x)[:400] for x in (it.get("improvements") or [])[:4]],
                    })
                return cleaned, True
            log.warning("Interview feedback: model returned unusable shape")
        except (ValueError, json.JSONDecodeError):
            log.warning("Interview feedback: non-JSON model output, retrying")
    return fallback, False


def _coach_polish(report, text):
    """Polish the cleaned rewrite + drills via Gemini, rule-based fallback.

    Returns (cleaned_version, drills, ai_powered). Scores never depend on
    the LLM.
    """
    fallback_cleaned = report.get("cleaned_version") or ""
    fallback_drills = report.get("drills") or []
    prompt = (
        "You are a communication coach for job interviews. A candidate wrote "
        "this answer (clarity score {}/100; top issues: {}):\n{}\n\n"
        "1) Rewrite it cleanly: same meaning, confident active voice, no filler, "
        "tight sentences. 2) Give 5 rewrite drills as short 'before' sentences "
        "with the issue named.\n"
        'Return ONLY JSON like {{"cleaned": "...", "drills": '
        '[{{"sentence": "...", "issues": ["..."]}}]}}.'
    ).format(
        report.get("clarity_score"),
        ", ".join(h["word"] for h in (report.get("filler_hits") or [])[:6]) or "none",
        (text or "")[:4000],
    )
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("Coach polish: Gemini unavailable: %s", e)
            return fallback_cleaned, fallback_drills, False
        try:
            parsed = _parse_json_safely(raw)
            if isinstance(parsed, dict) and parsed.get("cleaned"):
                drills = []
                for d in (parsed.get("drills") or [])[:5]:
                    if isinstance(d, dict) and d.get("sentence"):
                        drills.append({
                            "sentence": str(d["sentence"])[:500],
                            "issues": [str(x)[:60] for x in (d.get("issues") or [])[:4]],
                        })
                return (str(parsed["cleaned"])[:8000],
                        drills or fallback_drills, True)
            log.warning("Coach polish: model returned unusable shape")
        except (ValueError, json.JSONDecodeError):
            log.warning("Coach polish: non-JSON model output, retrying")
    return fallback_cleaned, fallback_drills, False


def _assessment_explanations(clusters):
    """Personalized 'why you fit' blurbs via Gemini, with rule-based fallback.

    Returns (clusters_with_why, ai_powered). Scoring never depends on the
    LLM - only the explanatory text does.
    """
    for c in clusters:
        c["why"] = rule_based_why(c)
    summaries = "; ".join(
        "{} ({}% match, signals: {})".format(
            c["name"], c["match"], ", ".join(c.get("top_signals") or [])[:2] or "general pattern")
        for c in clusters
    )
    prompt = (
        "You are a career counselor. A student took a career-discovery quiz. "
        "Top matches: {}. For EACH career, write a 2-sentence 'why you fit' "
        "blurb grounded in the signals shown, plus one concrete first step. "
        'Return ONLY JSON like {{"blurbs": [{{"id": "<career-id>", '
        '"why": "...", "first_step": "..."}}]}} using these ids: {}.'
    ).format(summaries, ", ".join(c["id"] for c in clusters))
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("Assessment explanations: Gemini unavailable: %s", e)
            return clusters, False
        try:
            parsed = _parse_json_safely(raw)
            items = parsed.get("blurbs") if isinstance(parsed, dict) else None
            by_id = {c["id"]: c for c in clusters}
            applied = 0
            for it in (items or [])[:len(clusters)]:
                if not isinstance(it, dict):
                    continue
                c = by_id.get(str(it.get("id") or ""))
                if not c:
                    continue
                why = str(it.get("why") or "").strip()[:500]
                step = str(it.get("first_step") or "").strip()[:300]
                if why:
                    c["why"] = why + (" First step: " + step if step else "")
                    applied += 1
            if applied:
                return clusters, True
            log.warning("Assessment explanations: model returned no usable items")
        except (ValueError, json.JSONDecodeError):
            log.warning("Assessment explanations: non-JSON model output, retrying")
    return clusters, False


def _rewrite_bullet_ai(bullet):
    """AI-polished bullet rewrites via Gemini, with rule-based fallback.

    Returns (rewrites, ai_powered). The rule-based variants from
    bullet_rewriter.improve_bullet always work; Gemini adds an AI-polished
    alternative when available.
    """
    fallback = improve_bullet(bullet)
    prompt = (
        "You are a senior career coach rewriting resume bullets. Rewrite "
        "this resume bullet into 2 stronger versions: one emphasizing "
        "quantified impact, one emphasizing leadership/scope. Use strong "
        "action verbs. Keep each under 25 words. If the bullet has no "
        "numbers, insert a bracketed placeholder like [X%] for the metric.\n\n"
        f"BULLET: {bullet[:800]}\n\n"
        'Return ONLY a JSON object like {"rewrites": [{"label": "...", '
        '"text": "...", "tip": "..."}]} with exactly 2 items.'
    )
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("Bullet rewrite: Gemini unavailable: %s", e)
            return fallback, False
        try:
            parsed = _parse_json_safely(raw)
            items = parsed.get("rewrites") if isinstance(parsed, dict) else None
            cleaned = []
            for it in (items or [])[:2]:
                if not isinstance(it, dict):
                    continue
                text = str(it.get("text") or "").strip()[:400]
                if text and text != bullet.strip():
                    cleaned.append({
                        "label": str(it.get("label") or "AI-polished")[:60],
                        "text": text,
                        "tip": str(it.get("tip") or "AI-polished alternative.")[:200],
                    })
            if cleaned:
                return fallback + cleaned, True
            log.warning("Bullet rewrite: model returned no usable items")
        except (ValueError, json.JSONDecodeError):
            log.warning("Bullet rewrite: non-JSON model output, retrying")
    return fallback, False


def _generate_cover_ai(resume_text, jd_text, tone):
    """Tailored cover letter + outreach via Gemini, with rule-based fallback.

    Returns ((cover_letter, outreach), ai_powered). Follows the constructor
    pattern: fenced-JSON-tolerant parsing, retry once.
    """
    fallback = (rule_based_cover_letter(resume_text, jd_text, tone),
                rule_based_outreach(resume_text, jd_text, tone))
    prompt = (
        "You are a senior career coach. Write a tailored cover letter and a "
        "short cold-outreach message (LinkedIn/email style, under 80 words) "
        f"for the candidate below. Tone: {tone}. The cover letter must "
        "reference specific requirements from the job description — no "
        "generic filler. Keep the letter under 220 words.\n\n"
        f"CANDIDATE RESUME (truncated):\n{(resume_text or '')[:4000]}\n\n"
        f"JOB DESCRIPTION (truncated):\n{(jd_text or '')[:4000]}\n\n"
        'Return ONLY a JSON object like {"cover_letter": "...", "outreach": "..."}.'
    )
    for _attempt in range(2):
        try:
            raw = call_gemini_ai(prompt)
        except GeminiError as e:
            log.warning("Cover generator: Gemini unavailable: %s", e)
            return fallback, False
        try:
            parsed = _parse_json_safely(raw)
            if not isinstance(parsed, dict):
                raise ValueError("non-dict output")
            letter = str(parsed.get("cover_letter") or "").strip()
            outreach = str(parsed.get("outreach") or "").strip()
            if letter and outreach and len(letter) > 100:
                return (letter[:6000], outreach[:1500]), True
            log.warning("Cover generator: model returned unusable items")
        except (ValueError, json.JSONDecodeError):
            log.warning("Cover generator: non-JSON model output, retrying")
    return fallback, False


def register_routes(app):

    # ---------- MAIN HUB ----------
    @app.route('/')
    def index():
        """Unified Platform Landing Page (The Hub)."""
        return render_template('index.html')

    @app.route('/privacy')
    def privacy():
        """Privacy Policy page."""
        return render_template('privacy.html')

    @app.route('/terms')
    def terms():
        """Terms of Service page."""
        return render_template('terms.html')

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    # ---------- AUTH ----------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        error = None
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            email = (request.form.get('email') or '').strip().lower()
            password = request.form.get('password') or ''
            if not name or not email or not password:
                error = 'Please fill in name, email and password.'
            elif len(password) < 8:
                error = 'Password must be at least 8 characters.'
            elif '@' not in email or '.' not in email:
                error = 'Please enter a valid email address.'
            elif User.query.filter_by(email=email).first():
                error = 'An account with this email already exists. Please log in.'
            else:
                user = User(name=name, email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash('Welcome, {}! Your account is ready.'.format(user.name), 'success')
                return redirect(url_for('dashboard'))
        return render_template('register.html', error=error,
                               google_configured=_google_configured())

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        error = None
        if request.method == 'POST':
            email = (request.form.get('email') or '').strip().lower()
            password = request.form.get('password') or ''
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user, remember=bool(request.form.get('remember')))
                flash('Welcome back, {}!'.format(user.name), 'success')
                nxt = request.args.get('next') or request.form.get('next')
                return redirect(nxt if is_safe_next(nxt) else url_for('dashboard'))
            error = 'Invalid email or password.'
        return render_template('login.html', error=error,
                               next=request.args.get('next', ''),
                               google_configured=_google_configured())

    @app.route('/logout', methods=['GET', 'POST'])
    def logout():
        # Sign-out must be a POST (CSRF-protected form) so a stray GET —
        # e.g. a prefetched link — can never log the user out (P2#11).
        if request.method == 'GET':
            abort(405, description="Please use the Log out button to sign out.")
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    # ---------- GOOGLE SIGN-IN (OAuth 2.0, only when configured) ----------
    if _google_configured():
        @app.route('/auth/google/login')
        def google_login():
            if current_user.is_authenticated:
                return redirect(url_for('dashboard'))
            nxt = request.args.get('next', '')
            if is_safe_next(nxt):
                session['google_next'] = nxt
            redirect_uri = url_for('google_callback', _external=True)
            return oauth.google.authorize_redirect(redirect_uri)

        @app.route('/auth/google/callback')
        def google_callback():
            # Authlib validates the `state` parameter by default, which
            # defeats CSRF/login-CSRF on the OAuth flow.
            try:
                oauth.google.authorize_access_token()
            except Exception as e:
                log.warning("Google OAuth token exchange failed: %r", e)
                flash('Google sign-in failed. Please try again.', 'error')
                return redirect(url_for('login'))
            try:
                userinfo = oauth.google.userinfo()
            except Exception:
                try:
                    userinfo = oauth.google.parse_id_token()
                except Exception as e:
                    log.warning("Google userinfo fetch failed: %r", e)
                    flash('Could not read your Google profile. Please try again.', 'error')
                    return redirect(url_for('login'))
            try:
                user, is_new = _process_google_login(userinfo or {})
            except ValueError as e:
                flash(str(e), 'error')
                return redirect(url_for('login'))
            login_user(user, remember=True)
            flash('Welcome{}!'.format(
                ', {}'.format(user.name) if is_new else ' back, {}'.format(user.name)),
                'success')
            nxt = session.pop('google_next', None)
            return redirect(nxt if is_safe_next(nxt) else url_for('dashboard'))

    # ---------- CONNECTED PROFILE (/profile) ----------
    @app.route('/profile')
    @login_required
    def profile():
        """Connected accounts: Google sign-in, GitHub, LeetCode."""
        github_snap = ProfileSnapshot.query.filter_by(
            user_id=current_user.id, provider='github').first()
        leetcode_snap = ProfileSnapshot.query.filter_by(
            user_id=current_user.id, provider='leetcode').first()
        return render_template(
            'profile.html',
            google_configured=_google_configured(),
            google_connected=bool(current_user.google_sub),
            github_username=current_user.github_username,
            github_snapshot=(github_snap.data if github_snap else None),
            leetcode_username=current_user.leetcode_username,
            leetcode_snapshot=(leetcode_snap.data if leetcode_snap else None))

    @app.route('/profile/connect/github', methods=['POST'])
    @login_required
    @limiter.limit("10 per hour")
    def profile_connect_github():
        username = (request.form.get('username') or '').strip()
        try:
            validate_github_username(username)
        except GithubAPIError as e:
            flash(str(e), 'error')
            return redirect(url_for('profile'))
        fresh = _fresh_snapshot(current_user.id, 'github')
        if fresh and (fresh.username or '').lower() == username.lower():
            current_user.github_username = fresh.username
            db.session.commit()
            flash('GitHub reconnected: @{}'.format(fresh.username), 'success')
            return redirect(url_for('profile'))
        try:
            result = analyze_github_profile(username)
        except GithubAPIError as e:
            flash(str(e), 'error')
            return redirect(url_for('profile'))
        current_user.github_username = result['username']
        _store_snapshot(current_user.id, 'github', result['username'], result)
        db.session.commit()
        flash('GitHub connected: @{} — profile score {}/100'.format(
            result['username'], result['score']), 'success')
        return redirect(url_for('profile'))

    @app.route('/profile/unlink/github', methods=['POST'])
    @login_required
    def profile_unlink_github():
        current_user.github_username = None
        ProfileSnapshot.query.filter_by(
            user_id=current_user.id, provider='github').delete()
        db.session.commit()
        flash('GitHub disconnected.', 'info')
        return redirect(url_for('profile'))

    @app.route('/profile/connect/leetcode', methods=['POST'])
    @login_required
    @limiter.limit("10 per hour")
    def profile_connect_leetcode():
        username = (request.form.get('username') or '').strip()
        try:
            validate_leetcode_username(username)
        except LeetCodeAPIError as e:
            flash(str(e), 'error')
            return redirect(url_for('profile'))
        fresh = _fresh_snapshot(current_user.id, 'leetcode')
        if fresh and (fresh.username or '').lower() == username.lower():
            current_user.leetcode_username = fresh.username
            db.session.commit()
            flash('LeetCode reconnected: {}'.format(fresh.username), 'success')
            return redirect(url_for('profile'))
        try:
            stats = fetch_leetcode_stats(username)
        except LeetCodeAPIError as e:
            flash(str(e), 'error')
            return redirect(url_for('profile'))
        current_user.leetcode_username = stats['username']
        _store_snapshot(current_user.id, 'leetcode', stats['username'], stats)
        db.session.commit()
        flash('LeetCode connected: {} ({} solved)'.format(
            stats['username'], stats['solved']['total']), 'success')
        return redirect(url_for('profile'))

    @app.route('/profile/unlink/leetcode', methods=['POST'])
    @login_required
    def profile_unlink_leetcode():
        current_user.leetcode_username = None
        ProfileSnapshot.query.filter_by(
            user_id=current_user.id, provider='leetcode').delete()
        db.session.commit()
        flash('LeetCode disconnected.', 'info')
        return redirect(url_for('profile'))

    # ---------- PUBLIC LEETCODE STAT CARD ----------
    @app.route('/cards/leetcode/<username>.svg')
    @limiter.limit("60 per hour")
    def leetcode_card(username):
        """Embeddable SVG stat card (github-readme-stats style). Public, since
        cards are meant to be embedded in READMEs and portfolio pages."""
        try:
            stats = get_card_stats(username)
        except LeetCodeAPIError as e:
            return Response(render_error_svg(str(e)), mimetype='image/svg+xml')
        return Response(render_leetcode_card_svg(stats), mimetype='image/svg+xml')

    # ---------- RESUME ANALYZER ----------
    @app.route('/resume')
    def resume_home():
        """Resume Analyzer upload page."""
        has_saved_resume = False
        if current_user.is_authenticated:
            has_saved_resume = db.session.query(
                ResumeAnalysis.query
                .filter_by(user_id=current_user.id)
                .filter(ResumeAnalysis.resume_text.isnot(None))
                .exists()).scalar()
        return render_template('resume_index.html',
                               has_saved_resume=has_saved_resume)

    @app.route('/analyze', methods=['POST'])
    @limiter.limit("20 per hour")
    def analyze():
        """Handle resume upload and analysis. Works anonymously; when logged in
        the result is also persisted as a ResumeAnalysis row.

        Note: fetch-based upload (resume_script.js); CSRF-exempt like the
        other JSON APIs. Login/register/goals forms carry CSRF tokens."""
        if 'resume' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF or DOCX.'}), 400

        # P2#13: uuid prefix prevents filename collisions between uploads.
        filename = "{}_{}".format(uuid.uuid4().hex[:8], secure_filename(file.filename))
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(filepath)

            # Step 1: Extract text
            ext = filename.rsplit('.', 1)[1].lower()
            if ext == 'pdf':
                raw_text = extract_text_from_pdf(file_path=filepath)
            elif ext in ('docx', 'doc'):
                raw_text = extract_text_from_docx(file_path=filepath)
            else:
                return jsonify({'error': 'Unsupported file format'}), 400

            if not raw_text or len(raw_text.strip()) < 50:
                return jsonify({'error': 'Could not extract enough text from the resume.'}), 400

            # Analysis pipeline (identical to original)
            cleaned_text = clean_text(raw_text)
            sections = extract_sections(cleaned_text)
            email = extract_email(raw_text)
            phone = extract_phone(raw_text)
            links = extract_links(raw_text)
            skills = extract_skills(cleaned_text)
            skill_names = get_skill_names(skills)
            skills_by_category = get_skills_by_category(skills)
            education = extract_education_details(sections.get('education', ''))
            experience_years = extract_experience_years(cleaned_text)
            ats_result = calculate_ats_score(cleaned_text, sections, skills, experience_years)
            feedback = generate_feedback(ats_result, sections, skills, experience_years)
            summary = get_overall_summary(ats_result, skills, sections)
            recommendations = get_recommendations(cleaned_text, skill_names, top_k=8)
            skill_gaps = analyze_skill_gaps(skill_names, recommendations)
            roadmap = generate_roadmap(skill_gaps, skill_names)
            total_learning_time = estimate_total_time(roadmap)
            career_paths = suggest_career_paths(skill_names, experience_years)

            top_role = recommendations[0]['title'] if recommendations else 'Software Engineer'
            interview_qs = generate_interview_questions(top_role, skill_names[:5])

            result = {
                'contact': {'email': email, 'phone': phone, 'links': links},
                'sections_found': list(sections.keys()),
                'skills': skills,
                'skill_names': skill_names,
                'skills_by_category': skills_by_category,
                'education': education,
                'experience_years': experience_years,
                'ats': ats_result,
                'feedback': feedback,
                'summary': summary,
                'recommendations': recommendations,
                'skill_gaps': skill_gaps,
                'roadmap': roadmap,
                'total_learning_time': total_learning_time,
                'career_paths': career_paths,
                'interview_questions': interview_qs,
                'filename': filename
            }

            # Persist for logged-in users; anonymous users get a DB row with
            # a 24h TTL (survives restarts, works across workers).
            if current_user.is_authenticated:
                row = ResumeAnalysis(
                    user_id=current_user.id,
                    filename=filename,
                    ats_score=(ats_result.get('total_score')
                               if isinstance(ats_result, dict) else None),
                    result_json=json_safe(result),
                    resume_text=cleaned_text[:20000],
                )
                db.session.add(row)
                db.session.commit()
                _purge_expired_anonymous()
                return jsonify({'success': True,
                                'redirect': url_for('view_result', analysis_id='db-{}'.format(row.id))})

            analysis_id = uuid.uuid4().hex
            anon = AnonymousAnalysis(
                id=analysis_id,
                filename=filename,
                result_json=json_safe(result),
                expires_at=_utcnow_naive() + timedelta(seconds=_ANON_TTL_SECONDS),
            )
            db.session.add(anon)
            db.session.commit()
            _purge_expired_anonymous()
            return jsonify({'success': True,
                            'redirect': url_for('view_result', analysis_id=analysis_id)})

        except Exception:
            log.exception("Resume analysis failed")
            return jsonify({'error': 'Analysis failed. Please try again with a different file.'}), 500
        finally:
            # P2#14: failed analyses must not leak uploaded files.
            try:
                os.remove(filepath)
            except OSError:
                pass

    csrf.exempt(analyze)

    # ---------- JD-MATCHED ATS SCORING (Wave 1 #1) ----------
    @app.route('/jd-match', methods=['POST'])
    @limiter.limit("10 per hour")
    def jd_match():
        """Score the user's resume against a pasted job description.

        Login required (reports are persisted per user). Accepts JSON or
        multipart form: jd_text + resume_source ("upload"|"latest"), with an
        optional "resume" file for the upload path. The page sends the CSRF
        token in the X-CSRFToken header, so this route is NOT CSRF-exempt.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to match your resume against a job description.'}), 401

        if request.is_json:
            payload = request.get_json(silent=True) or {}
            jd_text = (payload.get('jd_text') or '').strip()
            resume_source = (payload.get('resume_source') or 'upload').strip()
        else:
            jd_text = (request.form.get('jd_text') or '').strip()
            resume_source = (request.form.get('resume_source') or 'upload').strip()

        # --- Server-side JD validation ---
        if not jd_text:
            return jsonify({'error': 'Please paste a job description first.'}), 400
        if len(jd_text) < JD_MIN_CHARS:
            return jsonify({'error': 'The job description looks too short '
                                     '(minimum {} characters). Please paste the full posting.'
                                     .format(JD_MIN_CHARS)}), 400
        if len(jd_text) > JD_MAX_CHARS:
            return jsonify({'error': 'The job description is too long '
                                     '(maximum {:,} characters). Please trim it and try again.'
                                     .format(JD_MAX_CHARS)}), 400

        # --- Resolve resume text ---
        resume_text = None
        filename = None
        uploaded_path = None
        try:
            if resume_source == 'latest':
                row = (ResumeAnalysis.query
                       .filter_by(user_id=current_user.id)
                       .filter(ResumeAnalysis.resume_text.isnot(None))
                       .order_by(ResumeAnalysis.created_at.desc()).first())
                if not row:
                    return jsonify({'error': 'No saved resume with extractable text found. '
                                             'Please upload your resume instead.'}), 400
                resume_text = row.resume_text
                filename = row.filename
            elif resume_source == 'version':
                if request.is_json:
                    version_id = (payload.get('version_id') or 0)
                else:
                    version_id = request.form.get('version_id', type=int) or 0
                try:
                    version_id = int(version_id)
                except (TypeError, ValueError):
                    version_id = 0
                version = ResumeVersion.query.filter_by(id=version_id,
                                                        user_id=current_user.id).first()
                if not version:
                    return jsonify({'error': 'Please choose one of your saved resume versions.'}), 400
                resume_text = version.resume_text
                filename = version.name
            else:
                if 'resume' not in request.files:
                    return jsonify({'error': 'No file uploaded.'}), 400
                file = request.files['resume']
                if not file or file.filename == '':
                    return jsonify({'error': 'No file selected.'}), 400
                if not allowed_file(file.filename):
                    return jsonify({'error': 'Invalid file type. Please upload PDF or DOCX.'}), 400
                filename = "{}_{}".format(uuid.uuid4().hex[:8], secure_filename(file.filename))
                uploaded_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(uploaded_path)
                ext = filename.rsplit('.', 1)[1].lower()
                if ext == 'pdf':
                    raw_text = extract_text_from_pdf(file_path=uploaded_path)
                elif ext in ('docx', 'doc'):
                    raw_text = extract_text_from_docx(file_path=uploaded_path)
                else:
                    return jsonify({'error': 'Unsupported file format.'}), 400
                if not raw_text or len(raw_text.strip()) < 50:
                    return jsonify({'error': 'Could not extract enough text from the resume.'}), 400
                resume_text = clean_text(raw_text)
        finally:
            if uploaded_path:
                try:
                    os.remove(uploaded_path)
                except OSError:
                    pass

        # --- Deterministic server-side scoring ---
        cleaned = resume_text or ''
        sections = extract_sections(cleaned)
        skills = extract_skills(cleaned)
        skill_names = get_skill_names(skills)
        experience_years = extract_experience_years(cleaned)
        contact = {'email': extract_email(cleaned), 'phone': extract_phone(cleaned)}
        report = score_jd_match(cleaned, skill_names, experience_years,
                                sections, contact, jd_text)
        suggestions, ai_powered = _jd_match_suggestions(report, jd_text)
        report['suggestions'] = suggestions
        report['ai_powered'] = ai_powered
        report['filename'] = filename

        # --- Persist per user ---
        try:
            match_row = JDMatchReport(
                user_id=current_user.id,
                job_title=(report.get('job_title') or '')[:255],
                score=report.get('score'),
                report_json=json_safe(report),
            )
            db.session.add(match_row)
            db.session.commit()
        except Exception:
            log.exception("JD-match report persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your report. Please try again.'}), 500

        return jsonify({
            'success': True,
            'report_id': match_row.id,
            'report': json_safe(report),
            'saved_url': url_for('view_jd_match', report_id=match_row.id),
        })

    @app.route('/jd-match/<int:report_id>')
    @login_required
    def view_jd_match(report_id):
        """Render a saved JD-match report (owner only)."""
        row = JDMatchReport.query.filter_by(id=report_id,
                                            user_id=current_user.id).first_or_404()
        return render_template('jd_match_report.html', report=row.report_json,
                               report_id=row.id, created_at=row.created_at)

    # ---------- AI BULLET REWRITER (Wave 1 #2) ----------
    @app.route('/rewrite-bullet', methods=['POST'])
    @limiter.limit("10 per hour")
    def rewrite_bullet():
        """Rewrite a resume bullet into stronger variants.

        Login required (rewrites are persisted per user). Accepts JSON:
        {bullet_text}. The page sends the CSRF token in the X-CSRFToken
        header, so this route is NOT CSRF-exempt.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to rewrite bullets.'}), 401

        payload = request.get_json(silent=True) or {}
        bullet_text = (payload.get('bullet_text') or '').strip()

        # --- Server-side validation ---
        if not bullet_text:
            return jsonify({'error': 'Please enter a bullet to rewrite.'}), 400
        if len(bullet_text) < BULLET_MIN_CHARS:
            return jsonify({'error': f'That bullet looks too short '
                                     f'(minimum {BULLET_MIN_CHARS} characters).'}), 400
        if len(bullet_text) > BULLET_MAX_CHARS:
            return jsonify({'error': f'That bullet is too long '
                                     f'(maximum {BULLET_MAX_CHARS} characters).'}), 400

        try:
            rewrites, ai_powered = _rewrite_bullet_ai(bullet_text)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        try:
            row = BulletRewrite(
                user_id=current_user.id,
                original=bullet_text,
                rewrites=json_safe(rewrites),
                ai_powered=ai_powered,
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("Bullet rewrite persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your rewrite. Please try again.'}), 500

        return jsonify({
            'success': True,
            'rewrite_id': row.id,
            'original': bullet_text,
            'rewrites': json_safe(rewrites),
            'ai_powered': ai_powered,
        })

    # ---------- RESUME VERSIONS (Wave 1 #3) ----------
    @app.route('/resume-versions', methods=['GET'])
    def list_resume_versions():
        """List the user's saved resume versions (newest first)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to manage resume versions.'}), 401
        versions = (ResumeVersion.query
                    .filter_by(user_id=current_user.id)
                    .order_by(ResumeVersion.created_at.desc()).all())
        return jsonify({
            'success': True,
            'versions': [{
                'id': v.id,
                'name': v.name,
                'is_default': v.is_default,
                'created_at': v.created_at.isoformat(),
                'preview': (v.resume_text or '')[:200],
            } for v in versions],
        })

    @app.route('/resume-versions', methods=['POST'])
    @limiter.limit("20 per hour")
    def create_resume_version():
        """Save a named resume version. JSON: {name, resume_text} or
        {name, source: "latest"} to snapshot the latest saved analysis.
        CSRF token via X-CSRFToken header (not exempt)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to save resume versions.'}), 401
        payload = request.get_json(silent=True) or {}
        name = (payload.get('name') or '').strip()
        source = (payload.get('source') or 'text').strip()
        resume_text = (payload.get('resume_text') or '').strip()

        if not name:
            return jsonify({'error': 'Please give this version a name.'}), 400
        if len(name) > 120:
            return jsonify({'error': 'Version name is too long (max 120 characters).'}), 400
        if source == 'latest':
            row = (ResumeAnalysis.query
                   .filter_by(user_id=current_user.id)
                   .filter(ResumeAnalysis.resume_text.isnot(None))
                   .order_by(ResumeAnalysis.created_at.desc()).first())
            if not row or not (row.resume_text or '').strip():
                return jsonify({'error': 'No saved resume with extractable text found.'}), 400
            resume_text = row.resume_text.strip()
        if len(resume_text) < 50:
            return jsonify({'error': 'Resume text looks too short to save as a version.'}), 400
        if len(resume_text) > 50000:
            return jsonify({'error': 'Resume text is too long (max 50,000 characters).'}), 400

        existing = ResumeVersion.query.filter_by(user_id=current_user.id).count()
        try:
            version = ResumeVersion(
                user_id=current_user.id,
                name=name,
                resume_text=resume_text,
                is_default=(existing == 0),  # first version becomes the default
            )
            db.session.add(version)
            db.session.commit()
        except Exception:
            log.exception("Resume version save failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save this version. Please try again.'}), 500
        return jsonify({'success': True, 'version': {
            'id': version.id, 'name': version.name,
            'is_default': version.is_default,
            'created_at': version.created_at.isoformat(),
        }})

    @app.route('/resume-versions/<int:version_id>', methods=['GET'])
    def get_resume_version(version_id):
        """Fetch one version with its full text (owner only)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        version = ResumeVersion.query.filter_by(id=version_id,
                                                user_id=current_user.id).first()
        if not version:
            return jsonify({'error': 'Version not found.'}), 404
        return jsonify({'success': True, 'version': {
            'id': version.id,
            'name': version.name,
            'is_default': version.is_default,
            'resume_text': version.resume_text,
            'created_at': version.created_at.isoformat(),
        }})

    @app.route('/resume-versions/<int:version_id>/set-default', methods=['POST'])
    @limiter.limit("20 per hour")
    def set_default_resume_version(version_id):
        """Mark one version as the default (used by JD-match "version" source)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        version = ResumeVersion.query.filter_by(id=version_id,
                                                user_id=current_user.id).first()
        if not version:
            return jsonify({'error': 'Version not found.'}), 404
        try:
            (ResumeVersion.query.filter_by(user_id=current_user.id)
             .update({'is_default': False}))
            version.is_default = True
            db.session.commit()
        except Exception:
            log.exception("Set-default version failed")
            db.session.rollback()
            return jsonify({'error': 'Could not update the default version.'}), 500
        return jsonify({'success': True, 'version_id': version.id})

    @app.route('/resume-versions/<int:version_id>/delete', methods=['POST'])
    @limiter.limit("20 per hour")
    def delete_resume_version(version_id):
        """Delete a saved version (POST-only, CSRF-protected)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        version = ResumeVersion.query.filter_by(id=version_id,
                                                user_id=current_user.id).first()
        if not version:
            return jsonify({'error': 'Version not found.'}), 404
        try:
            was_default = version.is_default
            db.session.delete(version)
            db.session.commit()
            if was_default:
                # Promote the newest remaining version to default.
                nxt = (ResumeVersion.query.filter_by(user_id=current_user.id)
                       .order_by(ResumeVersion.created_at.desc()).first())
                if nxt:
                    nxt.is_default = True
                    db.session.commit()
        except Exception:
            log.exception("Delete version failed")
            db.session.rollback()
            return jsonify({'error': 'Could not delete this version.'}), 500
        return jsonify({'success': True})

    @app.route('/resume-versions/<int:version_id>/diff', methods=['GET'])
    def diff_resume_version(version_id):
        """Line diff of a version against another (?against=<id>, default:
        the next-older version). Returns structured lines for safe rendering."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        version = ResumeVersion.query.filter_by(id=version_id,
                                                user_id=current_user.id).first()
        if not version:
            return jsonify({'error': 'Version not found.'}), 404
        against_id = request.args.get('against', type=int)
        if against_id:
            other = ResumeVersion.query.filter_by(id=against_id,
                                                  user_id=current_user.id).first()
            if not other:
                return jsonify({'error': 'Comparison version not found.'}), 404
        else:
            other = (ResumeVersion.query
                     .filter(ResumeVersion.user_id == current_user.id,
                             ResumeVersion.id != version.id,
                             ResumeVersion.created_at <= version.created_at)
                     .order_by(ResumeVersion.created_at.desc()).first())
            if not other:
                return jsonify({'error': 'No earlier version to compare against.'}), 400
        import difflib
        old_lines = (other.resume_text or '').splitlines()
        new_lines = (version.resume_text or '').splitlines()
        out_lines = []
        added = removed = 0
        for line in difflib.unified_diff(old_lines, new_lines, lineterm='', n=2):
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line.startswith('@@'):
                out_lines.append({'type': 'hunk', 'text': line})
            elif line.startswith('+'):
                out_lines.append({'type': 'add', 'text': line[1:]})
                added += 1
            elif line.startswith('-'):
                out_lines.append({'type': 'del', 'text': line[1:]})
                removed += 1
            else:
                out_lines.append({'type': 'ctx', 'text': line[1:] if line.startswith(' ') else line})
        return jsonify({
            'success': True,
            'version': {'id': version.id, 'name': version.name},
            'against': {'id': other.id, 'name': other.name},
            'summary': {'added': added, 'removed': removed},
            'lines': out_lines[:500],
        })

    # ---------- COVER LETTER + OUTREACH GENERATOR (Wave 1 #4) ----------
    @app.route('/generate-cover', methods=['POST'])
    @limiter.limit("10 per hour")
    def generate_cover():
        """Generate a tailored cover letter + cold-outreach message.

        Login required. JSON: {jd_text, tone, resume_text?, version_id?}.
        Resume resolves from version_id (owner-checked) -> resume_text ->
        latest saved analysis. CSRF via X-CSRFToken header (not exempt).
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to generate cover letters.'}), 401
        payload = request.get_json(silent=True) or {}
        data, error = validate_cover_inputs(payload)
        if error:
            return jsonify({'error': error}), 400

        # --- Resolve resume text ---
        resume_text = data["resume_text"]
        if data["version_id"]:
            try:
                vid = int(data["version_id"])
            except (TypeError, ValueError):
                vid = 0
            version = ResumeVersion.query.filter_by(id=vid,
                                                    user_id=current_user.id).first()
            if not version:
                return jsonify({'error': 'Please choose one of your saved resume versions.'}), 400
            resume_text = version.resume_text
        if not resume_text:
            row = (ResumeAnalysis.query
                   .filter_by(user_id=current_user.id)
                   .filter(ResumeAnalysis.resume_text.isnot(None))
                   .order_by(ResumeAnalysis.created_at.desc()).first())
            if not row or not (row.resume_text or '').strip():
                return jsonify({'error': 'No resume found. Upload or save a resume version first.'}), 400
            resume_text = row.resume_text.strip()

        (cover_letter, outreach), ai_powered = _generate_cover_ai(
            resume_text, data["jd_text"], data["tone"])
        title = (data["jd_text"].strip().splitlines() or ["Role"])[0][:120]

        try:
            docs = []
            for doc_type, content in (("cover_letter", cover_letter),
                                      ("outreach", outreach)):
                doc = CoverDoc(
                    user_id=current_user.id,
                    doc_type=doc_type,
                    title=title,
                    tone=data["tone"],
                    content=content,
                    ai_powered=ai_powered,
                )
                db.session.add(doc)
                docs.append(doc)
            db.session.commit()
        except Exception:
            log.exception("Cover doc persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your documents. Please try again.'}), 500

        return jsonify({
            'success': True,
            'cover_letter': cover_letter,
            'outreach': outreach,
            'ai_powered': ai_powered,
            'tone': data["tone"],
            'doc_ids': [d.id for d in docs],
        })

    @app.route('/cover-docs', methods=['GET'])
    def list_cover_docs():
        """List the user's generated cover letters / outreach messages."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        docs = (CoverDoc.query
                .filter_by(user_id=current_user.id)
                .order_by(CoverDoc.created_at.desc())
                .limit(50).all())
        return jsonify({'success': True, 'docs': [{
            'id': d.id, 'doc_type': d.doc_type, 'title': d.title,
            'tone': d.tone, 'ai_powered': d.ai_powered,
            'created_at': d.created_at.isoformat(),
            'preview': (d.content or '')[:200],
        } for d in docs]})

    # ---------- LINKEDIN PROFILE GRADER (Wave 1 #5) ----------
    @app.route('/linkedin-grade', methods=['POST'])
    @limiter.limit("10 per hour")
    def linkedin_grade():
        """Grade pasted LinkedIn profile text (TEXT ONLY - we never scrape LinkedIn).

        Login required (reports are persisted per user). Accepts JSON or form
        data: headline, about, experience, skills. The page sends the CSRF
        token in the X-CSRFToken header, so this route is NOT CSRF-exempt.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to grade your LinkedIn profile.'}), 401

        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict()
        fields, error = validate_linkedin_inputs(payload)
        if error:
            return jsonify({'error': error}), 400

        # --- Deterministic server-side grading ---
        report = grade_linkedin_profile(**fields)
        suggestions, ai_powered = _linkedin_suggestions(report, fields)
        report['suggestions'] = suggestions
        report['ai_powered'] = ai_powered
        report['summary'] = generate_rule_based_summary(report)

        # --- Persist per user ---
        try:
            row = LinkedInReport(
                user_id=current_user.id,
                score=report.get('score'),
                report_json=json_safe(report),
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("LinkedIn report persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your report. Please try again.'}), 500

        return jsonify({
            'success': True,
            'report_id': row.id,
            'report': json_safe(report),
            'saved_url': url_for('view_linkedin_report', report_id=row.id),
        })

    @app.route('/linkedin/<int:report_id>')
    @login_required
    def view_linkedin_report(report_id):
        """Render a saved LinkedIn grading report (owner only)."""
        row = LinkedInReport.query.filter_by(id=report_id,
                                             user_id=current_user.id).first_or_404()
        return render_template('linkedin_report.html', report=row.report_json,
                               report_id=row.id, created_at=row.created_at)

    # ---------- APPLICATION TRACKER KANBAN (Wave 1 #6) ----------
    def _tracker_app_to_dict(a):
        return {
            'id': a.id, 'company': a.company, 'role': a.role, 'stage': a.stage,
            'jd_url': a.jd_url, 'notes': a.notes,
            'applied_date': a.applied_date.isoformat() if a.applied_date else None,
            'stage_updated_at': a.stage_updated_at.isoformat() if a.stage_updated_at else None,
            'created_at': a.created_at.isoformat() if a.created_at else None,
        }

    def _validate_tracker_payload(payload, require_company_role=True):
        """Validate tracker add/edit fields. Returns (data, error)."""
        data = {}
        company = (payload.get('company') or '').strip()
        role = (payload.get('role') or '').strip()
        if require_company_role:
            if not company:
                return None, 'Company name is required.'
            if not role:
                return None, 'Role / position is required.'
        if company and len(company) > 200:
            return None, 'Company name is too long (max 200 characters).'
        if role and len(role) > 200:
            return None, 'Role is too long (max 200 characters).'
        data['company'] = company[:200]
        data['role'] = role[:200]
        jd_url = (payload.get('jd_url') or '').strip()
        if jd_url:
            if len(jd_url) > 500:
                return None, 'Link is too long (max 500 characters).'
            if not re.match(r'^https?://', jd_url, re.I):
                return None, 'Link must start with http:// or https://.'
        data['jd_url'] = jd_url[:500] or None
        notes = (payload.get('notes') or '').strip()
        if len(notes) > 5000:
            return None, 'Notes are too long (max 5,000 characters).'
        data['notes'] = notes or None
        raw_date = (payload.get('applied_date') or '').strip()
        if raw_date:
            try:
                data['applied_date'] = date.fromisoformat(raw_date)
            except ValueError:
                return None, 'Applied date must be YYYY-MM-DD.'
        else:
            data['applied_date'] = None
        return data, None

    def _tracker_stats(user_id):
        """Stage counts, response rate, and avg current dwell per stage."""
        apps = JobApplication.query.filter_by(user_id=user_id).all()
        counts = {sid: 0 for sid, _ in TRACKER_STAGES}
        for a in apps:
            counts[a.stage] = counts.get(a.stage, 0) + 1
        in_pipeline = counts['applied'] + counts['oa'] + counts['interview'] + counts['offer'] + counts['rejected']
        responded = counts['oa'] + counts['interview'] + counts['offer']
        response_rate = round(100.0 * responded / in_pipeline, 1) if in_pipeline else 0.0
        now = datetime.now(timezone.utc)
        dwell = {}
        for sid, _ in TRACKER_STAGES:
            days = []
            for a in apps:
                if a.stage != sid or not a.stage_updated_at:
                    continue
                ts = a.stage_updated_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                days.append(max(0.0, (now - ts).total_seconds() / 86400.0))
            dwell[sid] = round(sum(days) / len(days), 1) if days else 0.0
        return {'counts': counts, 'total': len(apps),
                'response_rate': response_rate, 'avg_days_in_stage': dwell}

    @app.route('/tracker')
    @login_required
    def tracker_board():
        """Kanban board of the user's job applications."""
        apps = (JobApplication.query.filter_by(user_id=current_user.id)
                .order_by(JobApplication.created_at.desc()).all())
        by_stage = {sid: [] for sid, _ in TRACKER_STAGES}
        for a in apps:
            by_stage.setdefault(a.stage, []).append(a)
        return render_template('tracker.html', stages=TRACKER_STAGES,
                               by_stage=by_stage, stats=_tracker_stats(current_user.id))

    @app.route('/tracker/add', methods=['POST'])
    @limiter.limit("60 per hour")
    def tracker_add():
        """Add a job application. CSRF via X-CSRFToken header (not exempt)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to track applications.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        payload = payload or {}
        stage = (payload.get('stage') or 'wishlist').strip()
        if stage not in TRACKER_STAGE_IDS:
            return jsonify({'error': 'Invalid stage.'}), 400
        data, error = _validate_tracker_payload(payload)
        if error:
            return jsonify({'error': error}), 400
        app_row = JobApplication(user_id=current_user.id, stage=stage, **data)
        db.session.add(app_row)
        db.session.commit()
        return jsonify({'success': True, 'application': _tracker_app_to_dict(app_row)}), 201

    @app.route('/tracker/<int:app_id>/move', methods=['POST'])
    def tracker_move(app_id):
        """Move an application to another stage. CSRF via X-CSRFToken header."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        app_row = JobApplication.query.filter_by(id=app_id,
                                                 user_id=current_user.id).first()
        if not app_row:
            return jsonify({'error': 'Application not found.'}), 404
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        stage = ((payload or {}).get('stage') or '').strip()
        if stage not in TRACKER_STAGE_IDS:
            return jsonify({'error': 'Invalid stage.'}), 400
        if app_row.stage != stage:
            app_row.stage = stage
            app_row.stage_updated_at = datetime.now(timezone.utc)
            db.session.commit()
        return jsonify({'success': True, 'application': _tracker_app_to_dict(app_row)})

    @app.route('/tracker/<int:app_id>/edit', methods=['POST'])
    def tracker_edit(app_id):
        """Edit an application's fields. CSRF via X-CSRFToken header."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        app_row = JobApplication.query.filter_by(id=app_id,
                                                 user_id=current_user.id).first()
        if not app_row:
            return jsonify({'error': 'Application not found.'}), 404
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        data, error = _validate_tracker_payload(payload or {}, require_company_role=False)
        if error:
            return jsonify({'error': error}), 400
        if data['company']:
            app_row.company = data['company']
        if data['role']:
            app_row.role = data['role']
        app_row.jd_url = data['jd_url']
        app_row.notes = data['notes']
        app_row.applied_date = data['applied_date']
        db.session.commit()
        return jsonify({'success': True, 'application': _tracker_app_to_dict(app_row)})

    @app.route('/tracker/<int:app_id>/delete', methods=['POST'])
    def tracker_delete(app_id):
        """Delete an application. CSRF via X-CSRFToken header."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        app_row = JobApplication.query.filter_by(id=app_id,
                                                 user_id=current_user.id).first()
        if not app_row:
            return jsonify({'error': 'Application not found.'}), 404
        db.session.delete(app_row)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/tracker/stats')
    @login_required
    def tracker_stats():
        """JSON stats for the user's tracker."""
        return jsonify({'success': True, 'stats': _tracker_stats(current_user.id)})

    # ---------- CAREER-DISCOVERY ASSESSMENT (Wave 1 #7) ----------
    @app.route('/assessment')
    @login_required
    def assessment_quiz():
        """Guided career-discovery quiz (16 questions, stepper UI)."""
        return render_template('assessment.html', questions=public_questions())

    @app.route('/assessment/submit', methods=['POST'])
    @limiter.limit("10 per hour")
    def assessment_submit():
        """Score the assessment answers and persist the result.

        Login required. Accepts JSON {answers: {question_id: option_index}}.
        CSRF via X-CSRFToken header (not exempt).
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to take the assessment.'}), 401
        payload = request.get_json(silent=True) if request.is_json else {}
        answers, error = validate_assessment_inputs(payload or {})
        if error:
            return jsonify({'error': error}), 400

        # --- Deterministic server-side scoring ---
        clusters = score_assessment(answers)
        clusters, ai_powered = _assessment_explanations(clusters)
        for c in clusters:
            c["ai_powered"] = ai_powered
        result = {
            'clusters': clusters,
            'ai_powered': ai_powered,
            'total_questions': len(QUESTIONS),
        }

        # --- Persist per user (retakes create new rows) ---
        try:
            row = CareerAssessment(
                user_id=current_user.id,
                top_clusters=json_safe(clusters),
                answers_json=json_safe(answers),
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("Assessment persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your result. Please try again.'}), 500

        return jsonify({
            'success': True,
            'assessment_id': row.id,
            'result': json_safe(result),
            'saved_url': url_for('view_assessment', assessment_id=row.id),
        })

    @app.route('/assessment/<int:assessment_id>')
    @login_required
    def view_assessment(assessment_id):
        """Render a saved assessment result (owner only)."""
        row = CareerAssessment.query.filter_by(id=assessment_id,
                                               user_id=current_user.id).first_or_404()
        return render_template('assessment_result.html',
                               clusters=row.top_clusters,
                               assessment_id=row.id, created_at=row.created_at)

    # ---------- COMPANY-SPECIFIC MOCK INTERVIEWS (Wave 2 #13) ----------
    @app.route('/interview')
    def interview_home():
        """Mock interview setup: pick company, role, category."""
        from mock_interview import _load_bank
        return render_template('interview.html', options=interview_options(),
                               total_questions=len(_load_bank()),
                               is_authed=current_user.is_authenticated)

    @app.route('/interview/start', methods=['POST'])
    @limiter.limit("10 per hour")
    def interview_start():
        """Start a mock interview session. Login required (sessions are per-user).

        Accepts JSON or form data: company, role, category, num_questions.
        CSRF token comes via the X-CSRFToken header, so this route is NOT
        CSRF-exempt.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to start a mock interview.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        cleaned, error = validate_interview_setup(payload or {})
        if error:
            return jsonify({'error': error}), 400
        questions = pick_questions(cleaned["company"], cleaned["role"],
                                   cleaned["category"], n=cleaned["n"])
        if not questions:
            return jsonify({'error': 'No questions available for that selection.'}), 400
        try:
            row = InterviewSession(
                user_id=current_user.id,
                company=cleaned["company"], role=cleaned["role"],
                category=cleaned["category"],
                questions_json=json_safe(questions),
                answers_json=[],
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("Interview session creation failed")
            db.session.rollback()
            return jsonify({'error': 'Could not start the interview. Please try again.'}), 500
        return jsonify({'success': True, 'session_id': row.id,
                        'questions': json_safe(questions)})

    @app.route('/interview/<int:session_id>/submit', methods=['POST'])
    @limiter.limit("10 per hour")
    def interview_submit(session_id):
        """Score all answers for a session against the rubric.

        Body: {"answers": [{"question_id": "...", "answer": "..."}]}.
        Scoring is deterministic and server-side; Gemini only polishes the
        feedback wording (rule-based fallback always works).
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to submit answers.'}), 401
        row = InterviewSession.query.filter_by(id=session_id,
                                               user_id=current_user.id).first()
        if not row:
            return jsonify({'error': 'Interview session not found.'}), 404
        payload = request.get_json(silent=True) or {}
        raw_answers = payload.get("answers")
        if not isinstance(raw_answers, list) or not raw_answers:
            return jsonify({'error': 'Provide a non-empty answers list.'}), 400
        questions = row.questions_json or []
        qmap = {q.get("id"): q for q in questions}
        scored = []
        for item in raw_answers[:10]:
            if not isinstance(item, dict):
                continue
            qid = str(item.get("question_id") or "")
            question = qmap.get(qid)
            if not question:
                continue
            answer = str(item.get("answer") or "")[:8000]
            s = score_answer(question, answer)
            s["answer_text"] = answer
            scored.append(s)
        if not scored:
            return jsonify({'error': 'No answers matched this session\u2019s questions.'}), 400
        feedback, ai_powered = _interview_feedback(scored, [qmap[s["question_id"]] for s in scored])
        for s, fb in zip(scored, feedback):
            s["feedback"] = fb
        total = round(sum(s["total"] for s in scored) / len(scored), 1)
        try:
            row.answers_json = json_safe(scored)
            row.total_score = total
            row.ai_powered = ai_powered
            db.session.commit()
        except Exception:
            log.exception("Interview result persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your results. Please try again.'}), 500
        return jsonify({'success': True, 'total_score': total,
                        'ai_powered': ai_powered,
                        'results': json_safe(scored),
                        'report_url': url_for('view_interview', session_id=row.id)})

    @app.route('/interview/<int:session_id>')
    @login_required
    def view_interview(session_id):
        """Render a saved interview report (owner only)."""
        row = InterviewSession.query.filter_by(id=session_id,
                                               user_id=current_user.id).first_or_404()
        return render_template('interview_report.html', session=row,
                               questions=row.questions_json or [],
                               answers=row.answers_json or [])

    # ---------- COMMUNICATION COACH (Wave 2 #14) ----------
    @app.route('/coach')
    def coach_home():
        """Communication coach: paste an answer, get filler/pacing/clarity analysis."""
        return render_template('coach.html',
                               is_authed=current_user.is_authenticated)

    @app.route('/coach/analyze', methods=['POST'])
    @limiter.limit("10 per hour")
    def coach_analyze():
        """Analyze a pasted answer. Login required (analyses are persisted).

        Accepts JSON or form data: text. CSRF token via X-CSRFToken header,
        so this route is NOT CSRF-exempt.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to use the communication coach.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        text, error = validate_coach_inputs(payload or {})
        if error:
            return jsonify({'error': error}), 400

        report = analyze_transcript(text)
        cleaned, drills, ai_powered = _coach_polish(report, text)
        report['cleaned_version'] = cleaned
        report['drills'] = drills
        report['ai_powered'] = ai_powered
        report['original_text'] = text  # needed to render highlights on the saved report

        try:
            row = CommunicationAnalysis(
                user_id=current_user.id,
                clarity_score=report.get('clarity_score'),
                analysis_json=json_safe(report),
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("Coach analysis persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your analysis. Please try again.'}), 500
        return jsonify({'success': True, 'analysis_id': row.id,
                        'report': json_safe(report),
                        'report_url': url_for('view_coach_report', analysis_id=row.id)})

    @app.route('/coach/<int:analysis_id>')
    @login_required
    def view_coach_report(analysis_id):
        """Render a saved coach analysis (owner only)."""
        row = CommunicationAnalysis.query.filter_by(id=analysis_id,
                                                   user_id=current_user.id).first_or_404()
        return render_template('coach_report.html', report=row.analysis_json,
                               analysis_id=row.id, created_at=row.created_at)

    # ---------- DSA PRACTICE (Wave 2 #15) ----------
    @app.route('/dsa')
    def dsa_home():
        """DSA practice: filter problems by topic/difficulty."""
        return render_template('dsa.html', topics=dsa_topics(),
                               difficulties=dsa_difficulties(),
                               total=len(all_problems()),
                               is_authed=current_user.is_authenticated)

    @app.route('/api/dsa/problems')
    def dsa_problem_list():
        """JSON problem list with optional topic/difficulty filters."""
        topic = (request.args.get('topic') or '').strip()[:60]
        difficulty = (request.args.get('difficulty') or '').strip()[:10]
        problems = filter_problems(topic or None, difficulty or None)
        out = []
        if current_user.is_authenticated:
            progress = {r.problem_id: r.status for r in
                        DSAProgress.query.filter_by(user_id=current_user.id).all()}
            for p in problems:
                p = dict(p)
                p['my_status'] = progress.get(p['id'])
                out.append(p)
        else:
            out = problems
        return jsonify({'problems': out, 'count': len(out)})

    @app.route('/dsa/diagnosis')
    @login_required
    def dsa_diagnosis():
        """Weak-topic diagnosis dashboard (owner only)."""
        rows = DSAProgress.query.filter_by(user_id=current_user.id).all()
        progress = [{"problem_id": r.problem_id, "status": r.status,
                     "hints_used": r.hints_used} for r in rows]
        report = weak_topic_diagnosis(progress)
        return render_template('dsa_diagnosis.html', report=report)

    @app.route('/dsa/<problem_id>')
    def dsa_problem_page(problem_id):
        """Problem workspace: statement, progressive hints, code area."""
        problem_id = (problem_id or '').strip()[:50]
        p = get_problem(problem_id)
        if not p:
            abort(404)
        hints_revealed = 0
        my_status = None
        saved_code = ""
        if current_user.is_authenticated:
            row = DSAProgress.query.filter_by(user_id=current_user.id,
                                              problem_id=problem_id).first()
            if row:
                hints_revealed = row.hints_used
                my_status = row.status
                saved_code = row.code or ""
        payload = public_problem(problem_id, hints_revealed)
        return render_template('dsa_problem.html', problem=payload,
                               my_status=my_status, saved_code=saved_code,
                               is_authed=current_user.is_authenticated)

    def _dsa_progress_row(problem_id):
        row = DSAProgress.query.filter_by(user_id=current_user.id,
                                          problem_id=problem_id).first()
        if not row:
            row = DSAProgress(user_id=current_user.id, problem_id=problem_id)
            db.session.add(row)
        return row

    @app.route('/dsa/<problem_id>/hint', methods=['POST'])
    @limiter.limit("30 per hour")
    def dsa_hint(problem_id):
        """Reveal the next progressive hint. Login required; persisted."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to use hints.'}), 401
        problem_id = (problem_id or '').strip()[:50]
        if not get_problem(problem_id):
            return jsonify({'error': 'Unknown problem.'}), 404
        try:
            row = _dsa_progress_row(problem_id)
            hint, new_count = reveal_hint(problem_id, row.hints_used or 0)
            row.hints_used = new_count
            if row.status == 'attempted':
                pass
            db.session.commit()
        except Exception:
            log.exception("DSA hint persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not reveal hint. Please try again.'}), 500
        return jsonify({'success': True, 'hint': hint, 'hints_used': new_count,
                        'exhausted': hint is None})

    @app.route('/dsa/<problem_id>/approach', methods=['POST'])
    @limiter.limit("30 per hour")
    def dsa_approach(problem_id):
        """Reveal the approach outline — only on explicit request."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to view the approach.'}), 401
        problem_id = (problem_id or '').strip()[:50]
        approach = reveal_approach(problem_id)
        if approach is None:
            return jsonify({'error': 'Unknown problem.'}), 404
        return jsonify({'success': True, 'approach': approach})

    @app.route('/dsa/<problem_id>/status', methods=['POST'])
    @limiter.limit("30 per hour")
    def dsa_status(problem_id):
        """Save code + mark solved/stuck/attempted. Login required."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to save progress.'}), 401
        problem_id = (problem_id or '').strip()[:50]
        if not get_problem(problem_id):
            return jsonify({'error': 'Unknown problem.'}), 404
        payload = request.get_json(silent=True) or {}
        data, error = validate_status_payload(payload)
        if error:
            return jsonify({'error': error}), 400
        try:
            row = _dsa_progress_row(problem_id)
            row.status = data['status']
            row.code = data['code']
            db.session.commit()
        except Exception:
            log.exception("DSA status persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save progress. Please try again.'}), 500
        return jsonify({'success': True, 'status': row.status})

    # ---------- TIMED APTITUDE TESTS (Wave 2 #16) ----------
    @app.route('/aptitude')
    def aptitude_home():
        """Aptitude test setup: category, question count, time limit."""
        return render_template('aptitude.html',
                               categories=aptitude_categories(),
                               total=len(aptitude_all()),
                               is_authed=current_user.is_authenticated)

    @app.route('/aptitude/start', methods=['POST'])
    @limiter.limit("10 per hour")
    def aptitude_start():
        """Start a timed attempt. Login required. Server stamps the start
        time; the client countdown is display-only.

        CSRF token comes via the X-CSRFToken header, so this route is NOT
        CSRF-exempt.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to take a test.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        cleaned, error = validate_test_setup(payload or {})
        if error:
            return jsonify({'error': error}), 400
        seed = random.randint(0, 2 ** 31 - 1)
        questions = aptitude_pick(cleaned["category"], n=cleaned["n"], seed=seed)
        if not questions:
            return jsonify({'error': 'No questions available for that selection.'}), 400
        try:
            row = AptitudeAttempt(
                user_id=current_user.id,
                category=cleaned["category"],
                num_questions=len(questions),
                time_limit_sec=cleaned["time_limit"],
                question_ids=[q["id"] for q in questions],
                started_at=datetime.now(timezone.utc),
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("Aptitude attempt creation failed")
            db.session.rollback()
            return jsonify({'error': 'Could not start the test. Please try again.'}), 500
        return jsonify({'success': True, 'attempt_id': row.id,
                        'questions': json_safe(questions),
                        'time_limit_sec': row.time_limit_sec})

    @app.route('/aptitude/<int:attempt_id>/submit', methods=['POST'])
    @limiter.limit("20 per hour")
    def aptitude_submit(attempt_id):
        """Submit answers. Scoring is fully server-side: the question set
        and correct answers come from the bank, never the client. The time
        window is validated against the server start timestamp.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to submit.'}), 401
        row = db.session.get(AptitudeAttempt, attempt_id)
        if not row or row.user_id != current_user.id:
            return jsonify({'error': 'Attempt not found.'}), 404
        if row.submitted_at is not None:
            return jsonify({'error': 'This attempt was already submitted.'}), 400
        payload = request.get_json(silent=True) or {}
        raw_answers = payload.get("answers") or {}
        if not isinstance(raw_answers, dict):
            return jsonify({'error': 'Invalid answers format.'}), 400
        answers = {}
        for qid in (row.question_ids or []):
            if qid in raw_answers:
                try:
                    idx = int(raw_answers[qid])
                except (TypeError, ValueError):
                    continue
                if 0 <= idx <= 3:
                    answers[qid] = idx
        now = datetime.now(timezone.utc)
        started = row.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = (now - started).total_seconds()
        expired = elapsed > (row.time_limit_sec + SUBMIT_GRACE_SEC)
        results, summary = score_attempt(row.question_ids or [], answers)
        summary["time_used_sec"] = int(min(elapsed, row.time_limit_sec + SUBMIT_GRACE_SEC))
        summary["expired"] = expired
        try:
            row.answers_json = json_safe(answers)
            row.results_json = json_safe(results)
            row.summary_json = json_safe(summary)
            row.expired = expired
            row.submitted_at = now
            db.session.commit()
        except Exception:
            log.exception("Aptitude submit persistence failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your attempt. Please try again.'}), 500
        return jsonify({'success': True, 'expired': expired,
                        'summary': json_safe(summary),
                        'results': json_safe(results)})

    @app.route('/aptitude/<int:attempt_id>')
    @login_required
    def aptitude_report(attempt_id):
        """Saved attempt report (owner only)."""
        row = db.session.get(AptitudeAttempt, attempt_id)
        if not row or row.user_id != current_user.id:
            abort(404)
        if row.submitted_at is None:
            flash("This attempt has not been submitted yet.", "warning")
            return redirect(url_for('aptitude_home'))
        return render_template('aptitude_result.html', attempt=row,
                               results=row.results_json or [],
                               summary=row.summary_json or {})

    # ---------- STAR ANSWER BUILDER (Wave 2 #17) ----------
    def _star_suggestions(scored, sections, competency):
        """Polish per-section rewrite suggestions via Gemini, rule-based
        fallback. Returns (suggestions, ai_powered). Scores never depend on
        the LLM."""
        fallback = {}
        for s in SECTIONS:
            tip = generate_rule_based_rewrite_tip(s, sections.get(s) or "")
            existing = scored["sections"][s]["suggestions"]
            fallback[s] = ([tip] + existing)[:4]
        comp_label = dict((c[0], c[1]) for c in COMPETENCIES).get(competency,
                                                                 competency)
        compact = {
            "competency": comp_label,
            "sections": {s: (sections.get(s) or "")[:800] for s in SECTIONS},
            "scores": {s: scored["sections"][s]["score"] for s in SECTIONS},
        }
        prompt = (
            "You are an interview coach. A candidate drafted a STAR answer "
            f"for the competency '{comp_label}'. Section scores are out of 25. "
            "For EACH of situation/task/action/result, give up to 2 specific "
            "rewrite suggestions referencing their actual text - no generic "
            "advice. Return ONLY JSON like "
            '{"suggestions": {"situation": ["..."], "task": ["..."], '
            '"action": ["..."], "result": ["..."]}}.\n'
            "DRAFT:\n" + json.dumps(compact)[:6000]
        )
        for _attempt in range(2):
            try:
                raw = call_gemini_ai(prompt)
            except GeminiError as e:
                log.warning("STAR suggestions: Gemini unavailable: %s", e)
                return fallback, False
            try:
                parsed = _parse_json_safely(raw)
                items = parsed.get("suggestions") if isinstance(parsed, dict) else None
                if isinstance(items, dict) and all(
                        isinstance(items.get(s), list) for s in SECTIONS):
                    cleaned = {s: [str(x)[:400] for x in items[s][:3]]
                               for s in SECTIONS}
                    return cleaned, True
                log.warning("STAR suggestions: model returned unusable shape")
            except (ValueError, json.JSONDecodeError):
                log.warning("STAR suggestions: non-JSON model output, retrying")
        return fallback, False

    @app.route('/star')
    def star_home():
        """STAR builder: competency picker, examples, guided editor."""
        return render_template('star.html', competencies=COMPETENCIES,
                               guide=SECTION_GUIDE,
                               is_authed=current_user.is_authenticated)

    @app.route('/api/star/examples')
    def star_examples_api():
        """Annotated STAR examples, optionally filtered by competency."""
        comp = (request.args.get('competency') or '').strip().lower()[:40]
        if comp and comp not in COMPETENCY_IDS:
            return jsonify({'error': 'Unknown competency.'}), 400
        examples = examples_for(comp) if comp else all_examples()
        return jsonify({'examples': json_safe(examples),
                        'count': len(examples)})

    @app.route('/star/score', methods=['POST'])
    @limiter.limit("10 per hour")
    def star_score():
        """Score a STAR draft per section + rewrite suggestions.

        Login required. CSRF token via X-CSRFToken header.
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to score your answer.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        cleaned, error = validate_draft(payload or {})
        if error:
            return jsonify({'error': error}), 400
        scored = score_draft(cleaned["sections"])
        suggestions, ai_powered = _star_suggestions(
            scored, cleaned["sections"], cleaned["competency"])
        return jsonify({'success': True, 'scores': json_safe(scored),
                        'suggestions': json_safe(suggestions),
                        'ai_powered': ai_powered,
                        'competency': cleaned["competency"]})

    @app.route('/star/save', methods=['POST'])
    @limiter.limit("30 per hour")
    def star_save():
        """Persist a STAR draft (with its latest scores, if scored)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to save drafts.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        cleaned, error = validate_draft(payload or {})
        if error:
            return jsonify({'error': error}), 400
        scores = payload.get("scores") if isinstance(payload, dict) else None
        suggestions = payload.get("suggestions") if isinstance(payload, dict) else None
        try:
            row = STARDraft(
                user_id=current_user.id,
                competency=cleaned["competency"],
                situation=cleaned["sections"]["situation"],
                task=cleaned["sections"]["task"],
                action=cleaned["sections"]["action"],
                result=cleaned["sections"]["result"],
                scores_json=json_safe(scores) if isinstance(scores, dict) else None,
                suggestions_json=json_safe(suggestions) if isinstance(suggestions, dict) else None,
                ai_powered=bool(payload.get("ai_powered")) if isinstance(payload, dict) else False,
            )
            db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("STAR draft save failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save your draft. Please try again.'}), 500
        return jsonify({'success': True, 'draft_id': row.id})

    @app.route('/star/drafts')
    @login_required
    def star_drafts():
        """List the user's saved STAR drafts."""
        rows = (STARDraft.query.filter_by(user_id=current_user.id)
                .order_by(STARDraft.updated_at.desc()).all())
        out = [{
            "id": r.id,
            "competency": r.competency,
            "overall": (r.scores_json or {}).get("overall"),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "preview": (r.situation or "")[:120],
        } for r in rows]
        if request.args.get("format") == "json":
            return jsonify({"drafts": out})
        return render_template('star_drafts.html', drafts=out,
                               competencies=dict((c[0], c[1]) for c in COMPETENCIES))

    @app.route('/star/drafts/<int:draft_id>/delete', methods=['POST'])
    @limiter.limit("30 per hour")
    def star_draft_delete(draft_id):
        """Delete one of the user's STAR drafts (owner only)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        row = db.session.get(STARDraft, draft_id)
        if not row or row.user_id != current_user.id:
            return jsonify({'error': 'Draft not found.'}), 404
        try:
            db.session.delete(row)
            db.session.commit()
        except Exception:
            log.exception("STAR draft delete failed")
            db.session.rollback()
            return jsonify({'error': 'Could not delete the draft.'}), 500
        return jsonify({'success': True})

    def _learn_ai_tip(prompt, fallback):
        """Optional Gemini polish for learning tips. Returns (tip, ai_powered).

        Deterministic fallback always works; the tip never affects scores.
        """
        if not _ai_ready():
            return fallback, False
        try:
            raw = call_gemini_ai(
                "You are a concise study coach. In 2-3 sentences, give one "
                "actionable study tip. No preamble, no bullet list.\n" + prompt[:1500])
            tip = (raw or "").strip()
            if len(tip) >= 20:
                return tip[:600], True
        except GeminiError as e:
            log.warning("Learn AI tip unavailable: %s", e)
        except Exception:
            log.exception("Learn AI tip failed")
        return fallback, False

    # ----- Feature #18: skill-gap learning roadmaps -----
    @app.route('/learn/roadmaps')
    def roadmaps_home():
        """Browse skills + run the skill-gap analyzer."""
        return render_template('roadmaps.html',
                               skills=roadmap_skills(),
                               domains=roadmap_domains(),
                               roles=roadmap_roles(),
                               is_authed=current_user.is_authenticated)

    @app.route('/learn/roadmaps/<skill_id>')
    def roadmap_detail(skill_id):
        """Full 3-stage roadmap for one skill, with progress toggles."""
        skill = get_roadmap_skill(skill_id)
        if not skill:
            abort(404)
        progress = {}
        if current_user.is_authenticated:
            rows = RoadmapProgress.query.filter_by(
                user_id=current_user.id, skill_id=skill_id).all()
            progress = {r.stage: r.status for r in rows}
        return render_template('roadmap_detail.html', skill=skill,
                               progress=progress,
                               is_authed=current_user.is_authenticated)

    @app.route('/learn/roadmaps/gap', methods=['POST'])
    @limiter.limit("30 per hour")
    def roadmaps_gap():
        """Skill-gap analysis: current skills + target role -> ranked gaps.

        JSON body: {"target_role": "...", "current_skills": [{"skill_id","stage"}]}.
        CSRF token via X-CSRFToken header (not exempt). Anonymous allowed.
        """
        payload = request.get_json(silent=True) or {}
        cleaned, error = validate_gap_payload(payload)
        if error:
            return jsonify({'error': error}), 400
        gaps, role = analyze_gap(cleaned["current_skills"], cleaned["target_role"])
        if role is None:
            return jsonify({'error': 'Unknown target role.'}), 400
        plan = build_personal_roadmap(gaps)
        gap_desc = "; ".join(
            f"{g['skill_name']} to {g['min_stage']} (priority {g['priority']})"
            for g in gaps[:6])
        fallback_tip = (
            f"Start with your highest-priority gap and finish one stage "
            f"before moving on. Consistency beats intensity — 1 focused hour "
            f"daily compounds fast.")
        tip, ai_powered = _learn_ai_tip(
            f"A student targeting '{role['name']}' has these skill gaps: "
            f"{gap_desc}. Give one actionable study tip.",
            fallback_tip)
        return jsonify({'success': True,
                        'role': {'id': role['id'], 'name': role['name']},
                        'gaps': json_safe(gaps),
                        'total_weeks': plan['total_weeks'],
                        'num_skills': plan['num_skills'],
                        'study_tip': tip, 'ai_powered': ai_powered})

    @app.route('/learn/roadmaps/progress', methods=['POST'])
    @limiter.limit("60 per hour")
    def roadmaps_progress():
        """Save per-stage progress. Login required.

        JSON body: {"skill_id": "...", "stage": "beginner", "status": "completed"}.
        CSRF token via X-CSRFToken header (not exempt).
        """
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to track progress.'}), 401
        payload = request.get_json(silent=True) or {}
        cleaned, error = validate_progress_payload(payload)
        if error:
            return jsonify({'error': error}), 400
        try:
            row = RoadmapProgress.query.filter_by(
                user_id=current_user.id, skill_id=cleaned["skill_id"],
                stage=cleaned["stage"]).first()
            if row:
                row.status = cleaned["status"]
            else:
                row = RoadmapProgress(
                    user_id=current_user.id, skill_id=cleaned["skill_id"],
                    stage=cleaned["stage"], status=cleaned["status"])
                db.session.add(row)
            db.session.commit()
        except Exception:
            log.exception("Roadmap progress save failed")
            db.session.rollback()
            return jsonify({'error': 'Could not save progress. Please try again.'}), 500
        return jsonify({'success': True, 'status': cleaned["status"]})

    @app.route('/learn/roadmaps/dashboard')
    @login_required
    def roadmaps_dashboard():
        """The user's roadmap progress across skills."""
        rows = RoadmapProgress.query.filter_by(user_id=current_user.id).all()
        return render_template('roadmaps_dashboard.html',
                               summary=roadmap_progress_summary(rows),
                               skills={s["id"]: s for s in roadmap_skills()})

    @app.route('/results/<analysis_id>')
    def view_result(analysis_id):
        """Render a single analysis result (anonymous DB row or saved DB row)."""
        if analysis_id.startswith('db-'):
            if not current_user.is_authenticated:
                return redirect(url_for('login', next=request.path))
            try:
                row_id = int(analysis_id[3:])
            except ValueError:
                abort(404)
            row = db.session.get(ResumeAnalysis, row_id)
            if not row or row.user_id != current_user.id:
                abort(404)
            return render_template('dashboard.html', result=row.result_json)
        anon = db.session.get(AnonymousAnalysis, analysis_id)
        if not anon or anon.expires_at < _utcnow_naive():
            return redirect(url_for('resume_home'))
        return render_template('dashboard.html', result=anon.result_json)

    @app.route('/dashboard')
    @login_required
    def dashboard():
        """User home: analysis history + career goals."""
        analyses = (ResumeAnalysis.query
                    .filter_by(user_id=current_user.id)
                    .order_by(ResumeAnalysis.created_at.desc()).all())
        jd_matches = (JDMatchReport.query
                      .filter_by(user_id=current_user.id)
                      .order_by(JDMatchReport.created_at.desc()).all())
        rewrites = (BulletRewrite.query
                    .filter_by(user_id=current_user.id)
                    .order_by(BulletRewrite.created_at.desc()).all())
        cover_docs = (CoverDoc.query
                      .filter_by(user_id=current_user.id)
                      .order_by(CoverDoc.created_at.desc()).all())
        linkedin_reports = (LinkedInReport.query
                            .filter_by(user_id=current_user.id)
                            .order_by(LinkedInReport.created_at.desc()).all())
        tracker_stats = _tracker_stats(current_user.id)
        assessments = (CareerAssessment.query
                       .filter_by(user_id=current_user.id)
                       .order_by(CareerAssessment.created_at.desc()).all())
        interviews = (InterviewSession.query
                      .filter_by(user_id=current_user.id)
                      .order_by(InterviewSession.created_at.desc()).all())
        coach_reports = (CommunicationAnalysis.query
                         .filter_by(user_id=current_user.id)
                         .order_by(CommunicationAnalysis.created_at.desc()).all())
        aptitude_attempts = (AptitudeAttempt.query
                             .filter(AptitudeAttempt.user_id == current_user.id,
                                     AptitudeAttempt.submitted_at.isnot(None))
                             .order_by(AptitudeAttempt.created_at.desc()).all())
        star_drafts = (STARDraft.query
                       .filter_by(user_id=current_user.id)
                       .order_by(STARDraft.updated_at.desc())
                       .limit(12).all())
        goals = (Goal.query.filter_by(user_id=current_user.id)
                 .order_by(Goal.status.asc(), Goal.created_at.desc()).all())
        return render_template('history.html', analyses=analyses, goals=goals,
                               jd_matches=jd_matches, rewrites=rewrites,
                               cover_docs=cover_docs, linkedin_reports=linkedin_reports,
                               tracker_stats=tracker_stats, assessments=assessments,
                               interviews=interviews, coach_reports=coach_reports,
                               aptitude_attempts=aptitude_attempts,
                               star_drafts=star_drafts,
                               star_competencies=dict((c[0], c[1]) for c in COMPETENCIES))

    # ---------- INDIA SALARY EXPLORER (Wave 1 #8) ----------
    @app.route('/salary')
    def salary_explorer():
        """Role x city-tier x experience salary explorer (curated indicative ranges)."""
        try:
            options = salary_options()
        except SalaryDataError:
            return render_template('error.html',
                                   message="Salary data is temporarily unavailable. Please try again later."), 503
        return render_template('salary.html', options=options,
                               is_authed=current_user.is_authenticated)

    @app.route('/salary/data')
    @limiter.limit("60 per hour")
    def salary_data_api():
        """JSON feed of salary ranges. Unknown filter values yield empty results."""
        try:
            entries = salary_query(role=request.args.get('role') or None,
                                   tier=request.args.get('tier') or None,
                                   band=request.args.get('band') or None)
        except SalaryDataError:
            return jsonify({'success': False,
                            'error': 'Salary data is temporarily unavailable.'}), 503
        return jsonify({'success': True, 'entries': entries})

    # ---------- OPPORTUNITY RADAR (Wave 1 #9) ----------
    def _opp_labels(o):
        """(deadline_label, countdown_label) for a board card."""
        if not o["deadline"]:
            return "", ""
        y, m, d = (int(p) for p in o["deadline"].split("-"))
        label = date(y, m, d).strftime("%d %b %Y")
        n = o["days_left"]
        countdown = "closes today" if n == 0 else ("1 day left" if n == 1 else f"{n} days left")
        return label, countdown

    @app.route('/opportunities')
    def opportunity_board():
        """Curated board of internships, scholarships and exams, sorted by deadline."""
        opp_type = (request.args.get('type') or '').strip()
        if opp_type not in OPP_TYPES:
            opp_type = ""
        try:
            opps = list_opportunities(opp_type=opp_type or None)
            meta = opp_meta()
        except OpportunityDataError:
            return render_template('error.html', message=(
                "Opportunity data is temporarily unavailable. Please try again later.")), 503
        bookmarked = set()
        saved_only = False
        if current_user.is_authenticated:
            bookmarked = {b.opp_id for b in
                          OpportunityBookmark.query.filter_by(user_id=current_user.id).all()}
            saved_only = request.args.get('saved') == '1'
            if saved_only:
                opps = [o for o in opps if o["id"] in bookmarked]
        for o in opps:
            o["deadline_label"], o["countdown_label"] = _opp_labels(o)
        return render_template('opportunities.html', opps=opps, meta=meta,
                               types=OPP_TYPES, active_type=opp_type,
                               saved_only=saved_only, bookmarked=bookmarked,
                               is_authed=current_user.is_authenticated)

    @app.route('/opportunities/bookmark', methods=['POST'])
    @limiter.limit("60 per hour")
    def opportunity_bookmark_add():
        """Bookmark an opportunity. CSRF via X-CSRFToken header (not exempt)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to save opportunities.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        opp_id = ((payload or {}).get('opp_id') or '').strip()
        if not opp_id or not opp_exists(opp_id):
            return jsonify({'error': 'Opportunity not found.'}), 404
        existing = OpportunityBookmark.query.filter_by(
            user_id=current_user.id, opp_id=opp_id).first()
        if not existing:
            db.session.add(OpportunityBookmark(user_id=current_user.id, opp_id=opp_id))
            db.session.commit()
        return jsonify({'success': True, 'opp_id': opp_id}), 201

    @app.route('/opportunities/bookmark/remove', methods=['POST'])
    @limiter.limit("60 per hour")
    def opportunity_bookmark_remove():
        """Remove a bookmark. CSRF via X-CSRFToken header (not exempt)."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in.'}), 401
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        opp_id = ((payload or {}).get('opp_id') or '').strip()
        row = OpportunityBookmark.query.filter_by(
            user_id=current_user.id, opp_id=opp_id).first()
        if not row:
            return jsonify({'error': 'Bookmark not found.'}), 404
        db.session.delete(row)
        db.session.commit()
        return jsonify({'success': True, 'opp_id': opp_id})

    # ---------- PORTFOLIO BUILDER (Wave 1 #12) ----------
    def _portfolio_prefill(user):
        """Prefill data for the builder: name + connected coding profiles."""
        prefill = {"name": user.name or "",
                   "github": {"linked": False}, "leetcode": {"linked": False}}
        if user.github_username:
            snap = ProfileSnapshot.query.filter_by(
                user_id=user.id, provider="github").first()
            score = None
            if snap and snap.data:
                try:
                    score = round(float(snap.data.get("score") or 0))
                except (TypeError, ValueError):
                    score = None
            prefill["github"] = {"linked": True, "username": user.github_username,
                                 "score": score}
        if user.leetcode_username:
            snap = ProfileSnapshot.query.filter_by(
                user_id=user.id, provider="leetcode").first()
            solved = rating = None
            if snap and snap.data:
                solved = ((snap.data.get("solved") or {}).get("total"))
                rating = snap.data.get("rating")
            prefill["leetcode"] = {"linked": True, "username": user.leetcode_username,
                                   "solved": solved, "rating": rating}
        return prefill

    def _portfolio_to_dict(row):
        return {
            "display_name": row.display_name, "headline": row.headline or "",
            "bio": row.bio or "", "skills": row.skills or [],
            "projects": row.projects or [], "links": row.links or [],
            "show_github": row.show_github, "show_leetcode": row.show_leetcode,
            "is_published": row.is_published, "slug": row.slug,
        }

    def _portfolio_public_context(row):
        """Build the render context for the public page / download."""
        github = leetcode = None
        if row.show_github and row.user.github_username:
            snap = ProfileSnapshot.query.filter_by(
                user_id=row.user_id, provider="github").first()
            if snap and snap.data:
                try:
                    score = round(float(snap.data.get("score") or 0))
                except (TypeError, ValueError):
                    score = None
                github = {"username": row.user.github_username, "score": score}
        if row.show_leetcode and row.user.leetcode_username:
            snap = ProfileSnapshot.query.filter_by(
                user_id=row.user_id, provider="leetcode").first()
            if snap and snap.data:
                solved = (snap.data.get("solved") or {}).get("total")
                leetcode = {"username": row.user.leetcode_username,
                            "solved_total": solved,
                            "rating": snap.data.get("rating")}
        return {"portfolio": _portfolio_to_dict(row),
                "github": github, "leetcode": leetcode}

    @app.route('/portfolio')
    @login_required
    def portfolio_builder():
        """Portfolio builder page (login required)."""
        row = Portfolio.query.filter_by(user_id=current_user.id).first()
        return render_template('portfolio_builder.html',
                               portfolio=row,
                               portfolio_payload=_portfolio_to_dict(row) if row else None,
                               prefill=_portfolio_prefill(current_user))

    @app.route('/portfolio/save', methods=['POST'])
    @limiter.limit("20 per hour")
    def portfolio_save():
        """Create/update the user's portfolio. CSRF via X-CSRFToken header."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Please log in to build your portfolio.'}), 401
        payload = request.get_json(silent=True)
        data, error = validate_portfolio_payload(payload or {})
        if error:
            return jsonify({'error': error}), 400
        # Only feature coding profiles the user actually connected.
        if data["show_github"] and not current_user.github_username:
            data["show_github"] = False
        if data["show_leetcode"] and not current_user.leetcode_username:
            data["show_leetcode"] = False
        row = Portfolio.query.filter_by(user_id=current_user.id).first()
        if row is None:
            taken = {p.slug for p in Portfolio.query.with_entities(Portfolio.slug).all()}
            row = Portfolio(user_id=current_user.id,
                            slug=unique_slug(data["display_name"], taken))
            db.session.add(row)
        row.display_name = data["display_name"]
        row.headline = data["headline"]
        row.bio = data["bio"]
        row.skills = data["skills"]
        row.projects = data["projects"]
        row.links = data["links"]
        row.show_github = data["show_github"]
        row.show_leetcode = data["show_leetcode"]
        row.is_published = data["is_published"]
        row.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True, 'slug': row.slug,
                        'is_published': row.is_published,
                        'public_url': url_for('public_portfolio', slug=row.slug,
                                              _external=True)})

    @app.route('/p/<slug>')
    def public_portfolio(slug):
        """Public portfolio page — only what the user chose to publish."""
        row = Portfolio.query.filter_by(slug=slug).first()
        if not row or not row.is_published:
            abort(404)
        return render_template('portfolio_public.html',
                               **_portfolio_public_context(row))

    @app.route('/portfolio/download')
    @login_required
    def portfolio_download():
        """Download the portfolio as a standalone HTML file."""
        row = Portfolio.query.filter_by(user_id=current_user.id).first_or_404()
        html = render_template('portfolio_public.html',
                               **_portfolio_public_context(row))
        return Response(html, mimetype='text/html', headers={
            'Content-Disposition':
                f'attachment; filename="portfolio-{row.slug}.html"'})

    # ---------- GOALS ----------
    @app.route('/goals/add', methods=['POST'])
    @login_required
    def goal_add():
        title = (request.form.get('title') or '').strip()
        target_raw = (request.form.get('target_date') or '').strip()
        if not title:
            flash('Goal title cannot be empty.', 'error')
            return redirect(url_for('dashboard'))
        target_date = None
        if target_raw:
            try:
                target_date = date.fromisoformat(target_raw)
            except ValueError:
                flash('Invalid target date.', 'error')
                return redirect(url_for('dashboard'))
        goal = Goal(user_id=current_user.id, title=title, target_date=target_date)
        db.session.add(goal)
        db.session.commit()
        flash('Goal added.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/goals/<int:goal_id>/toggle', methods=['POST'])
    @login_required
    def goal_toggle(goal_id):
        goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
        goal.status = 'done' if goal.status == 'active' else 'active'
        db.session.commit()
        return redirect(url_for('dashboard'))

    @app.route('/goals/<int:goal_id>/delete', methods=['POST'])
    @login_required
    def goal_delete(goal_id):
        goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
        db.session.delete(goal)
        db.session.commit()
        flash('Goal removed.', 'info')
        return redirect(url_for('dashboard'))

    @app.route('/practice')
    def practice():
        """Interview and coding practice page."""
        return render_template('practice.html',
                               companies_interview=get_interview_companies(),
                               companies_coding=get_coding_companies(),
                               topics=get_available_topics(),
                               company_stats=get_company_stats(),
                               coding_stats=get_company_coding_stats())

    # ---------- RESEARCH ASSISTANT ----------
    @app.route('/research')
    def research_home():
        """Research Paper Assistant Page."""
        return render_template('research.html')

    # ---------- API ENDPOINTS (Shared) ----------
    @app.route('/api/interview-questions/<company>')
    def api_interview_questions(company):
        questions = get_company_questions(company=company,
                                          category=request.args.get('category'),
                                          difficulty=request.args.get('difficulty'))
        return jsonify(questions)

    @app.route('/api/coding-practice')
    @app.route('/api/coding-practice/<company>')
    def api_coding_practice(company=None):
        questions = get_coding_questions(company=company,
                                         topic=request.args.get('topic'),
                                         difficulty=request.args.get('difficulty'))
        return jsonify(questions)

    @app.route('/api/companies')
    def api_companies():
        return jsonify({'interview': get_interview_companies(), 'coding': get_coding_companies()})

    @app.route('/api/topics')
    def api_topics():
        return jsonify(get_available_topics())

    @app.route('/api/chat_research', methods=['POST'])
    @limiter.limit("30 per hour")
    def api_chat_research():
        """Gemini-powered Document Intelligence Chat with Resilience.

        Accepts the frontend's `history` (last exchanges) and merges it with
        the server-side ResearchSession when logged in, so follow-up
        questions keep context. When the caller is logged in, the
        conversation is appended to a per-user ResearchSession (returned as
        research_session_id)."""
        try:
            data = request.get_json(silent=True) or {}
            # P2#17: never send the literal string "None" to the model.
            user_msg = (data.get('message') or '').strip()
            if not user_msg:
                return jsonify({'error': 'Please type a question first.'}), 400
            doc_text = data.get('document_text', '') or ''

            if not _ai_ready():
                return jsonify({'response': "<strong>API Key Missing</strong><br><br>Please add your Gemini API Key to the .env file."}), 200

            # --- Conversation history (P1#4) ---
            # Prefer the server-side session (authoritative, tamper-proof);
            # fall back to the client-supplied history for anonymous users.
            history_lines = []
            server_session = None
            client_session_id = data.get('research_session_id')
            if current_user.is_authenticated and client_session_id:
                try:
                    server_session = ResearchSession.query.filter_by(
                        id=int(client_session_id),
                        user_id=current_user.id).first()
                except (ValueError, TypeError):
                    server_session = None
            if server_session and (server_session.data or {}).get("messages"):
                for m in (server_session.data["messages"])[-12:]:
                    role = "User" if m.get("role") == "user" else "Assistant"
                    history_lines.append("{}: {}".format(
                        role, str(m.get("content", ""))[:1500]))
            else:
                client_history = data.get('history') or []
                if isinstance(client_history, list):
                    for h in client_history[-12:]:
                        if isinstance(h, dict) and str(h.get('content') or '').strip():
                            role = "User" if h.get('role') == 'user' else "Assistant"
                            history_lines.append("{}: {}".format(
                                role, str(h['content'])[:1500]))
            history_block = ("\nCONVERSATION SO FAR (for context):\n" + "\n".join(history_lines)
                             if history_lines else "")

            prompt = """
            You are a PhD-level Research Assistant. You are grounded 100% in the following document text.
            {history}
            DOCUMENT TEXT:
            {doc}

            USER QUESTION:
            {q}

            INSTRUCTIONS:
            1. Answer with professional depth and technical precision.
            2. Use a formal, academic tone. Avoid all emojis.
            3. Structure your response with Markdown (use bolding for key terms, bullet points for lists, and headers if appropriate).
            4. If the answer is directly in the text, cite the context professionally.
            5. If the answer is not present, state so clearly in a formal manner.
            6. Use the conversation history above to resolve follow-up references like "it", "that section", or "the second point".
            """.format(history=history_block, doc=doc_text[:15000], q=user_msg)

            try:
                response_text = call_gemini_ai(prompt)
            except GeminiError as e:
                return jsonify({'error': str(e)}), 502

            # Persist the exchange for logged-in users.
            saved_session_id = None
            if current_user.is_authenticated:
                saved_session_id = _save_research_exchange(
                    current_user.id, client_session_id, user_msg, response_text, doc_text)

            payload = {'response': response_text}
            if saved_session_id:
                payload['research_session_id'] = saved_session_id
            return jsonify(payload)

        except Exception:
            log.exception("Research chat failed")
            return jsonify({'error': 'The research assistant hit an unexpected error. Please try again.'}), 500

    csrf.exempt(api_chat_research)

    @app.route('/api/constructor_generate', methods=['POST'])
    @limiter.limit("10 per hour")
    def api_constructor_generate():
        """AI-powered IEEE Research Paper Generation from a REAL repository.

        Fetches live repository facts from the GitHub API and grounds the
        prompt in them, so statistics reflect the actual repo (P1#3)."""
        try:
            data = request.get_json(silent=True) or {}
            # P2#20: reject empty input server-side (never generate about "None").
            repo_url = (data.get('repo_url') or '').strip()
            if not repo_url:
                return jsonify({'error': 'Please paste a GitHub repository URL first.'}), 400
            author = (data.get('author') or 'Anonymous').strip() or 'Anonymous'
            institution = (data.get('institution') or 'Independent Research').strip() \
                or 'Independent Research'

            if not _ai_ready():
                return jsonify({'error': 'API Key Missing. Add GEMINI_API_KEY to use the constructor.'}), 400

            match = re.match(
                r'https?://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$', repo_url, re.IGNORECASE)
            if not match:
                return jsonify({'error': 'That doesn\u2019t look like a GitHub repository URL '
                                         '(expected https://github.com/owner/repo).'}), 400
            owner, repo = match.group(1), match.group(2)

            try:
                repo_data = _fetch_repo_data(owner, repo)
            except GithubRepoError as e:
                return jsonify({'error': str(e)}), 502

            lang_lines = "\n".join(
                "- {}: {}%".format(lang, pct)
                for lang, pct in repo_data["top_languages"]) or "- Unknown"
            prompt = (
                "Generate a strictly professional IEEE Research Paper draft based on the REAL "
                "repository data below. Author: {author}. Institution: {inst}.\n\n"
                "REPOSITORY FACTS (from the live GitHub API - base EVERY statistic on these, "
                "never invent numbers):\n"
                "- Repository: {full_name}\n"
                "- Description: {desc}\n"
                "- Stars: {stars} | Forks: {forks}\n"
                "- Primary language: {primary_lang}\n"
                "- Language breakdown:\n{langs}\n"
                "- Files indexed: {files}\n"
                "- Top-level directories: {dirs}\n"
                "- Representative files: {sample}\n"
                "- Has automated tests: {tests}\n"
                "- Has Docker: {docker}\n"
                "- Has CI workflows: {ci}\n"
                "- README excerpt: {readme}\n\n"
                "You are a PhD-level architect. Provide an EXTREMELY IN-DEPTH technical response "
                "in JSON format.\n\n"
                "REQUIRED JSON KEYS (Must be exactly these):\n"
                "- title: Academic Title\n"
                "- abstract: 200 word technical summary\n"
                "- introduction: 250+ word technical introduction\n"
                "- lit_review: 200+ word literature review\n"
                "- architecture: 300+ word architecture breakdown\n"
                "- implementation: 250+ word technical implementation details\n"
                "- results: 200+ word results/analysis\n"
                "- conclusion: Formal conclusion\n"
                "- stats: {{\"files\": {files}, \"complexity\": \"{complexity}\", "
                "\"confidence\": \"High - grounded in live repository data\"}}\n\n"
                "STRICTION: Return ONLY raw JSON. No conversational filler. Use exactly the keys "
                "listed above."
            ).format(
                author=author, inst=institution,
                full_name=repo_data["full_name"], desc=repo_data["description"],
                stars=repo_data["stars"], forks=repo_data["forks"],
                primary_lang=repo_data["primary_language"], langs=lang_lines,
                files=repo_data["file_count"],
                dirs=", ".join(repo_data["top_dirs"]) or "flat layout",
                sample=", ".join(repo_data["sample_files"][:15]) or "n/a",
                tests=repo_data["has_tests"], docker=repo_data["has_docker"],
                ci=repo_data["has_ci"],
                readme=repo_data["readme"] or "No README found.",
                complexity=repo_data["complexity"],
            )

            # P1#5: robust JSON parsing - strip fences, retry once, then fail
            # gracefully with 502 (never 500 on model deviation).
            analysis = None
            attempts = 0
            while attempts < 2 and analysis is None:
                attempts += 1
                try:
                    response_text = call_gemini_ai(prompt)
                except GeminiError as e:
                    return jsonify({'error': str(e)}), 502
                try:
                    analysis = _parse_json_safely(response_text)
                except (ValueError, json.JSONDecodeError):
                    log.warning("Constructor: model returned non-JSON (attempt %d)", attempts)
                    analysis = None
            if analysis is None:
                return jsonify({'error': 'The AI returned an unreadable draft. '
                                         'Please try again in a moment.'}), 502
            return jsonify({'success': True, 'analysis': analysis})

        except Exception:
            log.exception("Constructor failed")
            return jsonify({'error': 'Paper generation hit an unexpected error. Please try again.'}), 500

    csrf.exempt(api_constructor_generate)


def _save_research_exchange(user_id, client_session_id, user_msg, ai_response, doc_text):
    """Append a chat exchange to the user's ResearchSession. Returns session id.

    Reuses the client-provided session when it belongs to the user AND the
    document hasn't changed (doc_hash); otherwise starts a new session so
    conversations about different papers never mix."""
    doc_hash = hashlib.sha256(doc_text[:4000].encode("utf-8", "ignore")).hexdigest()

    sess = None
    if client_session_id:
        try:
            sess = ResearchSession.query.filter_by(id=int(client_session_id),
                                                   user_id=user_id).first()
        except (ValueError, TypeError):
            sess = None
        if sess and (sess.data or {}).get("doc_hash") != doc_hash:
            sess = None  # different document -> new session

    if sess is None:
        title = user_msg if len(user_msg) <= 60 else user_msg[:57] + "..."
        sess = ResearchSession(user_id=user_id, title=title,
                               data={"messages": [], "doc_hash": doc_hash})
        db.session.add(sess)
        db.session.flush()  # assign id

    messages = list((sess.data or {}).get("messages", []))
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "assistant", "content": ai_response})
    # Bound session size: keep the most recent 40 messages.
    messages = messages[-40:]
    sess.data = {"messages": messages, "doc_hash": doc_hash}
    db.session.commit()
    return sess.id


# --- AI Resiliency Helper (google-genai SDK, P1#9) ---
def call_gemini_ai(prompt, max_attempts=4):
    """Call the best available Gemini model with fail-fast semantics (P0#2).

    - Model discovery hits the API at most once per hour (module-level cache).
    - The HTTP client carries a 30s timeout: no more 30-60s hangs.
    - Any failure raises GeminiError with a user-safe message (never leaks
      SDK/proxy internals); endpoints translate it to HTTP 502.
    """
    client = _make_gemini_client()
    if client is None:
        raise GeminiError(
            "AI features need a Gemini API key. Add GEMINI_API_KEY to your "
            ".env file (free at Google AI Studio) and restart.")

    try:
        model_names = _discover_model_names(client)
    except Exception as e:
        log.warning("Gemini model discovery failed: %r", e)
        msg = str(e)
        if ("API_KEY_INVALID" in msg or "API key not valid" in msg
                or "API_KEY_EXPIRED" in msg):
            raise GeminiError(
                "Your Gemini API key was rejected. Check GEMINI_API_KEY "
                "in your .env file and try again.")
        raise GeminiError(
            "Could not reach the AI service. Please try again in a moment.")
    if not model_names:
        raise GeminiError(
            "No usable AI models are available for this API key right now.")

    log.info("Gemini: %d eligible models, trying up to %d",
             len(model_names), max_attempts)
    for model_name in model_names[:max_attempts]:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt)
            text = (getattr(response, "text", "") or "").strip()
            if text:
                return text
            log.warning("Gemini model %s returned empty text", model_name)
        except Exception as e:
            log.warning("Gemini model %s failed: %r", model_name, e)
            continue

    raise GeminiError(
        "The AI service is temporarily unavailable. Please try again shortly.")


app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  Unified AI Excellence Platform")
    print("  Starting server at http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
