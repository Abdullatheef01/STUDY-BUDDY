"""
BERT Matcher - Semantic job matching using sentence-transformers.
Uses all-MiniLM-L6-v2 model for fast, accurate semantic similarity.
"""
import os
import csv
import numpy as np

# Lazy load to avoid slow startup
_model = None
_jobs_data = None
_job_embeddings = None


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading BERT model (all-MiniLM-L6-v2)... This may take a moment on first run.")
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            print("BERT model loaded successfully!")
        except ImportError:
            print("Warning: sentence-transformers not installed. Using fallback keyword matching.")
            _model = "FALLBACK"
        except Exception as e:
            print(f"Warning: Could not load BERT model: {e}. Using fallback.")
            _model = "FALLBACK"
    return _model


def _load_jobs():
    """Load jobs data from CSV."""
    global _jobs_data
    if _jobs_data is not None:
        return _jobs_data
    
    jobs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'jobs.csv')
    _jobs_data = []
    
    if not os.path.exists(jobs_path):
        print(f"Warning: Jobs CSV not found at {jobs_path}")
        return _jobs_data
    
    with open(jobs_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            _jobs_data.append(row)
    
    return _jobs_data


def _get_job_embeddings():
    """Get or compute job description embeddings."""
    global _job_embeddings
    
    model = _get_model()
    if model == "FALLBACK":
        return None
    
    if _job_embeddings is not None:
        return _job_embeddings
    
    jobs = _load_jobs()
    if not jobs:
        return None
    
    # Create rich text for each job combining title, description, and skills
    job_texts = []
    for job in jobs:
        text = f"{job['title']}. {job['description']}. Skills: {job['required_skills']}"
        job_texts.append(text)
    
    _job_embeddings = model.encode(job_texts, show_progress_bar=False)
    return _job_embeddings


def _keyword_match_score(resume_skills, job_skills_str):
    """Fallback keyword-based matching when BERT is unavailable."""
    resume_skills_lower = {s.lower() for s in resume_skills}
    job_skills = {s.strip().lower() for s in job_skills_str.split(',')}
    
    if not job_skills:
        return 0.0
    
    matches = resume_skills_lower.intersection(job_skills)
    return len(matches) / len(job_skills)


def match_jobs(resume_text, resume_skills, top_k=10):
    """
    Match resume against job descriptions using semantic similarity.
    
    Args:
        resume_text: Full resume text
        resume_skills: List of skill names extracted from resume
        top_k: Number of top matches to return
    
    Returns:
        list: Top matching jobs with scores
    """
    jobs = _load_jobs()
    if not jobs:
        return []
    
    model = _get_model()
    
    if model != "FALLBACK":
        # BERT-based semantic matching
        job_embeddings = _get_job_embeddings()
        if job_embeddings is None:
            model = "FALLBACK"
        else:
            # Create resume embedding
            resume_embedding = model.encode([resume_text], show_progress_bar=False)
            
            # Compute cosine similarities
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(resume_embedding, job_embeddings)[0]
            
            # Combine semantic score with keyword overlap
            results = []
            for i, job in enumerate(jobs):
                semantic_score = float(similarities[i])
                keyword_score = _keyword_match_score(resume_skills, job['required_skills'])
                
                # Weighted combination: 60% semantic, 40% keyword
                combined_score = (0.6 * semantic_score) + (0.4 * keyword_score)
                
                # Calculate matched skills
                job_skill_list = [s.strip() for s in job['required_skills'].split(',')]
                matched = [s for s in job_skill_list if s.lower() in {rs.lower() for rs in resume_skills}]
                missing = [s for s in job_skill_list if s.lower() not in {rs.lower() for rs in resume_skills}]
                
                results.append({
                    'title': job['title'],
                    'description': job['description'],
                    'category': job['category'],
                    'experience_level': job['experience_level'],
                    'salary_range': job['salary_range'],
                    'required_skills': job_skill_list,
                    'matched_skills': matched,
                    'missing_skills': missing,
                    'semantic_score': round(semantic_score * 100, 1),
                    'keyword_score': round(keyword_score * 100, 1),
                    'match_score': round(combined_score * 100, 1),
                })
            
            results.sort(key=lambda x: x['match_score'], reverse=True)
            return results[:top_k]
    
    # Fallback: keyword-only matching
    results = []
    for job in jobs:
        keyword_score = _keyword_match_score(resume_skills, job['required_skills'])
        
        job_skill_list = [s.strip() for s in job['required_skills'].split(',')]
        matched = [s for s in job_skill_list if s.lower() in {rs.lower() for rs in resume_skills}]
        missing = [s for s in job_skill_list if s.lower() not in {rs.lower() for rs in resume_skills}]
        
        results.append({
            'title': job['title'],
            'description': job['description'],
            'category': job['category'],
            'experience_level': job['experience_level'],
            'salary_range': job['salary_range'],
            'required_skills': job_skill_list,
            'matched_skills': matched,
            'missing_skills': missing,
            'semantic_score': 0,
            'keyword_score': round(keyword_score * 100, 1),
            'match_score': round(keyword_score * 100, 1),
        })
    
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:top_k]
