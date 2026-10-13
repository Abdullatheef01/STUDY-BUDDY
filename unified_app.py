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
import sys
import uuid
import json
import hashlib
from datetime import datetime, date, timezone

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables (.env for local dev, platform env vars in prod)
load_dotenv()

# google-generativeai is optional: the app must boot and serve everything
# except live Gemini calls even if the package / API key is missing.
try:
    import google.generativeai as genai
    _GENAI_IMPORTED = True
except Exception:  # pragma: no cover - defensive
    genai = None
    _GENAI_IMPORTED = False

if _GENAI_IMPORTED and os.getenv("GEMINI_API_KEY"):
    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        GENAI_AVAILABLE = True
    except Exception:
        GENAI_AVAILABLE = False
else:
    GENAI_AVAILABLE = False

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
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=datetime.utcnow, nullable=False)

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


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ========================================================
# --- HELPERS ---
# ========================================================

# Server-side results storage for anonymous Resume Analyzer sessions
# (logged-in users get their results persisted in the DB instead).
RESULTS_CACHE = {}

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
    app.secret_key = os.getenv("SECRET_KEY", "unified-ai-platform-secret-2026")

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

    register_routes(app)

    with app.app_context():
        db.create_all()

    return app


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

    @app.route('/logout')
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    # ---------- RESUME ANALYZER ----------
    @app.route('/resume')
    def resume_home():
        """Resume Analyzer upload page."""
        return render_template('resume_index.html')

    @app.route('/analyze', methods=['POST'])
    def analyze():
        """Handle resume upload and analysis. Works anonymously; when logged in
        the result is also persisted as a ResumeAnalysis row."""
        if 'resume' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF or DOCX.'}), 400

        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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

            # Clean up
            try:
                os.remove(filepath)
            except OSError:
                pass

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

            # Persist for logged-in users; anonymous users use the memory cache.
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
                return jsonify({'success': True,
                                'redirect': url_for('view_result', analysis_id='db-{}'.format(row.id))})

            analysis_id = str(uuid.uuid4())
            RESULTS_CACHE[analysis_id] = result
            session['last_analysis_id'] = analysis_id
            return jsonify({'success': True,
                            'redirect': url_for('view_result', analysis_id=analysis_id)})

        except Exception as e:
            return jsonify({'error': 'Analysis failed: {}'.format(str(e))}), 500

    @app.route('/results/<analysis_id>')
    def view_result(analysis_id):
        """Render a single analysis result (anonymous cache or saved DB row)."""
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
        result = RESULTS_CACHE.get(analysis_id)
        if not result:
            return redirect(url_for('resume_home'))
        return render_template('dashboard.html', result=result)

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
    def api_chat_research():
        """Gemini-powered Document Intelligence Chat with Resilience.

        When the caller is logged in, the conversation is appended to a
        per-user ResearchSession (returned as research_session_id)."""
        try:
            data = request.get_json(silent=True) or {}
            user_msg = data.get('message')
            doc_text = data.get('document_text', '') or ''
            client_session_id = data.get('research_session_id')

            if not GENAI_AVAILABLE or not os.getenv("GEMINI_API_KEY") \
                    or os.getenv("GEMINI_API_KEY") == "your_actual_api_key_here":
                return jsonify({'response': "<strong>API Key Missing</strong><br><br>Please add your Gemini API Key to the .env file."}), 200

            prompt = """
            You are a PhD-level Research Assistant. You are grounded 100% in the following document text.

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
            """.format(doc=doc_text[:15000], q=user_msg)

            response_text = call_gemini_ai(prompt)

            # Persist the exchange for logged-in users.
            saved_session_id = None
            if current_user.is_authenticated and user_msg:
                saved_session_id = _save_research_exchange(
                    current_user.id, client_session_id, user_msg, response_text, doc_text)

            payload = {'response': response_text}
            if saved_session_id:
                payload['research_session_id'] = saved_session_id
            return jsonify(payload)

        except Exception as e:
            print("DEBUG: Global AI Error: {}".format(e))
            return jsonify({'error': str(e)}), 500

    @app.route('/api/constructor_generate', methods=['POST'])
    def api_constructor_generate():
        """Real AI-powered IEEE Research Paper Generation."""
        try:
            data = request.get_json(silent=True) or {}
            repo_url = data.get('repo_url')
            author = data.get('author')
            institution = data.get('institution')

            print("DEBUG: Generating AI Paper for: {}".format(repo_url))

            if not GENAI_AVAILABLE or not os.getenv("GEMINI_API_KEY") \
                    or os.getenv("GEMINI_API_KEY") == "your_actual_api_key_here":
                return jsonify({'error': 'API Key Missing'}), 400

            prompt = """
            Generate a strictly professional IEEE Research Paper draft based on the repository: {repo}
            Author: {author}
            Institution: {inst}

            You are a PhD-level architect. Provide an EXTREMELY IN-DEPTH technical response in JSON format.

            REQUIRED JSON KEYS (Must be exactly these):
            - title: Academic Title
            - abstract: 200 word technical summary
            - introduction: 250+ word technical introduction
            - lit_review: 200+ word literature review
            - architecture: 300+ word architecture breakdown
            - implementation: 250+ word technical implementation details
            - results: 200+ word results/analysis
            - conclusion: Formal conclusion
            - stats: {{ "files": number, "complexity": "Extreme/High/Moderate", "confidence": "percentage" }}

            STRICTION: Return ONLY raw JSON. No conversational filler. Use exactly the keys listed above.
            """.format(repo=repo_url, author=author, inst=institution)

            response_text = call_gemini_ai(prompt)
            # Clean potential markdown from AI response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(response_text)
            return jsonify({'success': True, 'analysis': analysis})

        except Exception as e:
            print("DEBUG: Constructor Error: {}".format(e))
            return jsonify({'error': str(e)}), 500


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


# --- AI Resiliency Helper ---
def call_gemini_ai(prompt):
    """Dynamically discover and call the best available Gemini model."""
    if not GENAI_AVAILABLE:
        raise Exception("google-generativeai is not installed or no GEMINI_API_KEY is set. "
                        "Add it to use AI features.")
    try:
        models_info = genai.list_models()

        # Collect candidates that explicitly support generateContent
        candidates = []
        for m in models_info:
            methods = getattr(m, "supported_generation_methods", None) or []
            methods_lower = [str(x).lower() for x in methods]

            # Accept both possible spellings that may show up in SDKs
            supports_generate_content = (
                "generatecontent" in methods_lower or
                "generate_content" in methods_lower
            )

            if supports_generate_content:
                candidates.append((m.name, methods))

        # If none matched, fail with a helpful diagnostic showing what is available
        if not candidates:
            available = [(m.name, getattr(m, "supported_generation_methods", None) or []) for m in models_info]
            debug_list = "\n".join(["- {}: {}".format(name, methods) for name, methods in available[:50]])
            raise Exception(
                "No available Gemini models support generateContent/generate_content for this SDK.\n"
                "Available models (sample):\n{}".format(debug_list)
            )

        # Prioritize flash/pro by name, then keep the rest
        priority = []
        for keyword in ["flash", "pro"]:
            for name, methods in candidates:
                if keyword in name.lower() and (name, methods) not in priority:
                    priority.append((name, methods))
        for item in candidates:
            if item not in priority:
                priority.append(item)

        models_to_try = [name for name, _ in priority]

        print("DEBUG: Found {} eligible AI models. Trying best match...".format(len(models_to_try)))
        last_error = None

        for model_name in models_to_try:
            try:
                print("DEBUG: Attempting AI call with discovered model: {}".format(model_name))
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)  # python SDK uses snake_case
                print("DEBUG: Success with model: {}".format(model_name))
                return response.text
            except Exception as e:
                print("DEBUG: Model {} failed: {}".format(model_name, e))
                last_error = str(e)
                continue

        raise Exception("All {} eligible Gemini models failed. Last error: {}".format(
            len(models_to_try), last_error))

    except Exception as e:
        print("DEBUG: Discovery/Call failure: {}".format(e))
        raise e


app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  Unified AI Excellence Platform")
    print("  Starting server at http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
