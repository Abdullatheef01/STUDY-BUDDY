"""
Unified AI-Powered Excellence Platform
Main Entry Point
"""
import os
import sys
import uuid
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Keys
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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

app = Flask(__name__)
app.secret_key = 'unified-ai-platform-secret-2026'

# Server-side results storage for Resume Analyzer
RESULTS_CACHE = {}

# Configure upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========================================================
# --- MAIN HUB ROUTE ---
# ========================================================

@app.route('/')
def index():
    """Unified Platform Landing Page (The Hub)."""
    return render_template('index.html')

# ========================================================
# --- RESUME ANALYZER ROUTES ---
# ========================================================

@app.route('/resume')
def resume_home():
    """Resume Analyzer upload page."""
    return render_template('resume_index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Handle resume upload and analysis."""
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

        # Analysis pipeline (simplified for brevity, identical to original)
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
        try: os.remove(filepath)
        except: pass

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

        analysis_id = str(uuid.uuid4())
        RESULTS_CACHE[analysis_id] = result
        session['last_analysis_id'] = analysis_id

        return jsonify({'success': True, 'redirect': url_for('dashboard')})

    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/dashboard')
def dashboard():
    """Results dashboard page."""
    analysis_id = session.get('last_analysis_id')
    if not analysis_id or analysis_id not in RESULTS_CACHE:
        return redirect(url_for('resume_home'))
    return render_template('dashboard.html', result=RESULTS_CACHE[analysis_id])

@app.route('/practice')
def practice():
    """Interview and coding practice page."""
    return render_template('practice.html',
                           companies_interview=get_interview_companies(),
                           companies_coding=get_coding_companies(),
                           topics=get_available_topics(),
                           company_stats=get_company_stats(),
                           coding_stats=get_company_coding_stats())

# ========================================================
# --- RESEARCH ASSISTANT ROUTES ---
# ========================================================

@app.route('/research')
def research_home():
    """Research Paper Assistant Page."""
    return render_template('research.html')

# ========================================================
# --- API ENDPOINTS (Shared) ---
# ========================================================

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

# --- AI Resiliency Helper ---
def call_gemini_ai(prompt):
    """Dynamically discover and call the best available Gemini model."""
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
            debug_list = "\n".join([f"- {name}: {methods}" for name, methods in available[:50]])
            raise Exception(
                "No available Gemini models support generateContent/generate_content for this SDK.\n"
                f"Available models (sample):\n{debug_list}"
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

        print(f"DEBUG: Found {len(models_to_try)} eligible AI models. Trying best match...")
        last_error = None

        for model_name in models_to_try:
            try:
                print(f"DEBUG: Attempting AI call with discovered model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)  # python SDK uses snake_case
                print(f"DEBUG: Success with model: {model_name}")
                return response.text
            except Exception as e:
                print(f"DEBUG: Model {model_name} failed: {e}")
                last_error = str(e)
                continue

        raise Exception(f"All {len(models_to_try)} eligible Gemini models failed. Last error: {last_error}")

    except Exception as e:
        print(f"DEBUG: Discovery/Call failure: {e}")
        raise e

@app.route('/api/chat_research', methods=['POST'])
def api_chat_research():
    """Gemini-powered Document Intelligence Chat with Resilience."""
    try:
        data = request.json
        user_msg = data.get('message')
        doc_text = data.get('document_text', '')
        
        print(f"DEBUG: Received AI Chat request: '{user_msg}'")

        if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "your_actual_api_key_here":
            return jsonify({'response': "<strong>API Key Missing</strong><br><br>Please add your Gemini API Key to the .env file."}), 200

        prompt = f"""
        You are a PhD-level Research Assistant. You are grounded 100% in the following document text.
        
        DOCUMENT TEXT: 
        {doc_text[:15000]}
        
        USER QUESTION: 
        {user_msg}
        
        INSTRUCTIONS:
        1. Answer with professional depth and technical precision.
        2. Use a formal, academic tone. Avoid all emojis.
        3. Structure your response with Markdown (use bolding for key terms, bullet points for lists, and headers if appropriate).
        4. If the answer is directly in the text, cite the context professionally.
        5. If the answer is not present, state so clearly in a formal manner.
        """

        response_text = call_gemini_ai(prompt)
        return jsonify({'response': response_text})

    except Exception as e:
        print(f"DEBUG: Global AI Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/constructor_generate', methods=['POST'])
def api_constructor_generate():
    """Real AI-powered IEEE Research Paper Generation."""
    try:
        data = request.json
        repo_url = data.get('repo_url')
        author = data.get('author')
        institution = data.get('institution')

        print(f"DEBUG: Generating AI Paper for: {repo_url}")

        if not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "your_actual_api_key_here":
            return jsonify({'error': 'API Key Missing'}), 400

        prompt = f"""
        Generate a strictly professional IEEE Research Paper draft based on the repository: {repo_url}
        Author: {author}
        Institution: {institution}

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
        """

        response_text = call_gemini_ai(prompt)
        # Clean potential markdown from AI response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(response_text)
        return jsonify({'success': True, 'analysis': analysis})

    except Exception as e:
        print(f"DEBUG: Constructor Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Unified AI Excellence Platform")
    print("  Starting server at http://localhost:5000")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
