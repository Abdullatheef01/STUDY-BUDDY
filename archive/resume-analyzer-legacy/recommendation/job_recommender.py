"""
Job Recommender - Combines BERT semantic matching with keyword analysis.
"""
from models.bert_matcher import match_jobs


def get_recommendations(resume_text, resume_skills, top_k=10):
    """
    Get job recommendations for a resume.
    
    Args:
        resume_text: Full cleaned resume text
        resume_skills: List of skill names
        top_k: Number of recommendations to return
    
    Returns:
        list: Top matching jobs with detailed scores
    """
    matches = match_jobs(resume_text, resume_skills, top_k=top_k)
    
    # Enhance with additional metadata
    for i, match in enumerate(matches):
        match['rank'] = i + 1
        
        # Calculate skill match percentage
        total_required = len(match['required_skills'])
        total_matched = len(match['matched_skills'])
        match['skill_match_percent'] = round((total_matched / total_required * 100) if total_required > 0 else 0, 1)
        
        # Fit level assessment
        score = match['match_score']
        if score >= 75:
            match['fit_level'] = 'Excellent Fit'
            match['fit_color'] = '#00d4aa'
        elif score >= 55:
            match['fit_level'] = 'Good Fit'
            match['fit_color'] = '#7c5cfc'
        elif score >= 35:
            match['fit_level'] = 'Moderate Fit'
            match['fit_color'] = '#ffb347'
        else:
            match['fit_level'] = 'Stretch Role'
            match['fit_color'] = '#ff6b6b'
    
    return matches


def get_job_categories(recommendations):
    """
    Get unique job categories from recommendations.
    
    Returns:
        list: Unique categories
    """
    categories = list(set(r['category'] for r in recommendations))
    categories.sort()
    return categories
