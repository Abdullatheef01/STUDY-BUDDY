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
import hashlib
import secrets
import logging

from datetime import datetime, date, timedelta, timezone

import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("analyses", lazy="dynamic",
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
    if app.config.get("TESTING"):
        limiter.enabled = False

    register_routes(app)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()

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

def register_routes(app):

    # ---------- MAIN HUB ----------
    @app.route('/')
    def index():
        """Unified Platform Landing Page (The Hub)."""
        return render_template('index.html')

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
        return render_template('register.html', error=error)

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
                               next=request.args.get('next', ''))

    @app.route('/logout', methods=['GET', 'POST'])
    def logout():
        # Sign-out must be a POST (CSRF-protected form) so a stray GET —
        # e.g. a prefetched link — can never log the user out (P2#11).
        if request.method == 'GET':
            abort(405, description="Please use the Log out button to sign out.")
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    # ---------- RESUME ANALYZER ----------
    @app.route('/resume')
    def resume_home():
        """Resume Analyzer upload page."""
        return render_template('resume_index.html')

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
        goals = (Goal.query.filter_by(user_id=current_user.id)
                 .order_by(Goal.status.asc(), Goal.created_at.desc()).all())
        return render_template('history.html', analyses=analyses, goals=goals)

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
