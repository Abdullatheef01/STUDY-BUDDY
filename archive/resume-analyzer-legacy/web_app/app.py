"""
AI Resume Analyzer & Job Recommendation System
Flask Web Application - Main Entry Point
"""
import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename

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
from models.bert_matcher import _get_model as prewarm_bert

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))

app.secret_key = 'resume-analyzer-secret-key-2025'

# Server-side results storage (fixes cookie size limit issue)
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


@app.route('/')
def index():
    """Landing page with resume upload."""
    return render_template('index.html')


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
            return jsonify({'error': 'Could not extract enough text from the resume. Please ensure the file contains readable text.'}), 400

        # Step 2: Clean text
        cleaned_text = clean_text(raw_text)

        # Step 3: Extract sections
        sections = extract_sections(cleaned_text)

        # Step 4: Extract contact info
        email = extract_email(raw_text)
        phone = extract_phone(raw_text)
        links = extract_links(raw_text)

        # Step 5: Extract skills
        skills = extract_skills(cleaned_text)
        skill_names = get_skill_names(skills)
        skills_by_category = get_skills_by_category(skills)

        # Step 6: Extract education & experience
        education = extract_education_details(sections.get('education', ''))
        experience_years = extract_experience_years(cleaned_text)

        # Step 7: Calculate ATS score
        ats_result = calculate_ats_score(cleaned_text, sections, skills, experience_years)

        # Step 8: Generate feedback
        feedback = generate_feedback(ats_result, sections, skills, experience_years)
        summary = get_overall_summary(ats_result)

        # Step 9: Job recommendations
        recommendations = get_recommendations(cleaned_text, skill_names, top_k=8)

        # Step 10: Skill gap analysis
        skill_gaps = analyze_skill_gaps(skill_names, recommendations)

        # Step 11: Learning roadmap
        roadmap = generate_roadmap(skill_gaps, skill_names)
        total_learning_time = estimate_total_time(roadmap)

        # Step 12: Career paths
        career_paths = suggest_career_paths(skill_names, experience_years)

        # Step 13: Interview prep for top role
        top_role = recommendations[0]['title'] if recommendations else 'Software Engineer'
        interview_qs = generate_interview_questions(top_role, skill_names[:5])

        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass

        # Build result
        result = {
            'contact': {
                'email': email,
                'phone': phone,
                'links': links
            },
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

        # Use a unique ID for the analysis results to bypass cookie limits
        import uuid
        analysis_id = str(uuid.uuid4())
        RESULTS_CACHE[analysis_id] = result
        session['last_analysis_id'] = analysis_id

        return jsonify({'success': True, 'redirect': '/dashboard'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@app.route('/dashboard')
def dashboard():
    """Results dashboard page."""
    analysis_id = session.get('last_analysis_id')
    if not analysis_id or analysis_id not in RESULTS_CACHE:
        return redirect(url_for('index'))

    result = RESULTS_CACHE[analysis_id]
    return render_template('dashboard.html', result=result)


@app.route('/practice')
def practice():
    """Interview and coding practice page."""
    companies_interview = get_interview_companies()
    companies_coding = get_coding_companies()
    topics = get_available_topics()
    company_stats = get_company_stats()
    coding_stats = get_company_coding_stats()

    return render_template('practice.html',
                           companies_interview=companies_interview,
                           companies_coding=companies_coding,
                           topics=topics,
                           company_stats=company_stats,
                           coding_stats=coding_stats)


# ----- API Endpoints -----

@app.route('/api/interview-questions/<company>')
def api_interview_questions(company):
    """Get interview questions for a company."""
    category = request.args.get('category')
    difficulty = request.args.get('difficulty')
    questions = get_company_questions(company=company, category=category, difficulty=difficulty)
    return jsonify(questions)


@app.route('/api/coding-practice/<company>')
def api_coding_practice(company):
    """Get coding questions for a company."""
    topic = request.args.get('topic')
    difficulty = request.args.get('difficulty')
    questions = get_coding_questions(company=company, topic=topic, difficulty=difficulty)
    return jsonify(questions)


@app.route('/api/coding-practice')
def api_coding_practice_all():
    """Get all coding questions with optional filters."""
    company = request.args.get('company')
    topic = request.args.get('topic')
    difficulty = request.args.get('difficulty')
    questions = get_coding_questions(company=company, topic=topic, difficulty=difficulty)
    return jsonify(questions)


@app.route('/api/companies')
def api_companies():
    """Get available companies."""
    return jsonify({
        'interview': get_interview_companies(),
        'coding': get_coding_companies()
    })


@app.route('/api/topics')
def api_topics():
    """Get available coding topics."""
    return jsonify(get_available_topics())


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  AI Resume Analyzer & Job Recommendation System")
    print("  Pre-warming BERT model... (One-time setup)")
    try:
        prewarm_bert()
    except Exception as e:
        print(f"  Warning: BERT pre-warm failed: {e}")
    
    print("  Starting server at http://localhost:5000")
    print("="*60 + "\n")
    # Disable reloader to prevent infinite loops on Windows with large ML libraries
    app.run(debug=True, port=5000, use_reloader=False)
