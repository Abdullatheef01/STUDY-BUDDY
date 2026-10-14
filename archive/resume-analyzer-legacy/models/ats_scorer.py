"""
ATS Scorer - Calculates ATS (Applicant Tracking System) resume score.
Evaluates resume quality based on multiple criteria.
"""
import re


def calculate_ats_score(resume_text, sections, skills, experience_years):
    """
    Calculate ATS score for a resume based on multiple criteria.
    
    Args:
        resume_text: Full cleaned resume text
        sections: Dict of extracted sections
        skills: List of extracted skill dicts
        experience_years: Estimated years of experience
    
    Returns:
        dict: ATS score breakdown with total score and category scores
    """
    scores = {}
    
    # 1. Section Completeness (20 points)
    essential_sections = ['summary', 'education', 'experience', 'skills']
    optional_sections = ['projects', 'awards', 'publications', 'volunteer']
    
    essential_found = sum(1 for s in essential_sections if s in sections)
    optional_found = sum(1 for s in optional_sections if s in sections)
    
    section_score = (essential_found / len(essential_sections)) * 15
    section_score += min(optional_found * 2.5, 5)
    scores['sections'] = {
        'score': round(section_score, 1),
        'max': 20,
        'label': 'Section Completeness',
        'details': f"{essential_found}/{len(essential_sections)} essential sections, {optional_found} bonus sections"
    }
    
    # 2. Skills Density (25 points)
    num_skills = len(skills)
    if num_skills >= 15:
        skill_score = 25
    elif num_skills >= 10:
        skill_score = 20
    elif num_skills >= 7:
        skill_score = 15
    elif num_skills >= 4:
        skill_score = 10
    elif num_skills >= 1:
        skill_score = 5
    else:
        skill_score = 0
    
    # Bonus for diverse skill categories
    categories = set(s['category'] for s in skills)
    if len(categories) >= 4:
        skill_score = min(25, skill_score + 3)
    
    scores['skills'] = {
        'score': round(skill_score, 1),
        'max': 25,
        'label': 'Skills & Keywords',
        'details': f"{num_skills} skills found across {len(categories)} categories"
    }
    
    # 3. Content Quality (20 points)
    word_count = len(resume_text.split())
    content_score = 0
    
    # Word count scoring
    if 300 <= word_count <= 1200:
        content_score += 8
    elif 200 <= word_count <= 1500:
        content_score += 5
    elif word_count > 100:
        content_score += 3
    
    # Action verbs
    action_verbs = [
        'developed', 'designed', 'implemented', 'managed', 'created',
        'built', 'led', 'launched', 'improved', 'optimized', 'reduced',
        'increased', 'achieved', 'delivered', 'coordinated', 'analyzed',
        'established', 'maintained', 'automated', 'integrated', 'resolved',
        'collaborated', 'mentored', 'presented', 'published', 'engineered'
    ]
    verbs_found = sum(1 for v in action_verbs if v in resume_text.lower())
    content_score += min(verbs_found * 1.5, 7)
    
    # Quantifiable achievements (numbers, percentages)
    metrics = re.findall(r'\d+[%+]|\$[\d,]+|\d+\s*(?:users|clients|projects|team|members)', resume_text, re.IGNORECASE)
    content_score += min(len(metrics) * 1.5, 5)
    
    scores['content'] = {
        'score': round(min(content_score, 20), 1),
        'max': 20,
        'label': 'Content Quality',
        'details': f"{word_count} words, {verbs_found} action verbs, {len(metrics)} quantified achievements"
    }
    
    # 4. Contact Information (10 points)
    contact_score = 0
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resume_text))
    has_phone = bool(re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', resume_text))
    has_linkedin = bool(re.search(r'linkedin', resume_text, re.IGNORECASE))
    has_github = bool(re.search(r'github', resume_text, re.IGNORECASE))
    has_portfolio = bool(re.search(r'portfolio|website|blog', resume_text, re.IGNORECASE))
    
    if has_email:
        contact_score += 3
    if has_phone:
        contact_score += 3
    if has_linkedin:
        contact_score += 2
    if has_github or has_portfolio:
        contact_score += 2
    
    scores['contact'] = {
        'score': round(contact_score, 1),
        'max': 10,
        'label': 'Contact Information',
        'details': f"Email: {'✓' if has_email else '✗'}, Phone: {'✓' if has_phone else '✗'}, LinkedIn: {'✓' if has_linkedin else '✗'}, GitHub/Portfolio: {'✓' if has_github or has_portfolio else '✗'}"
    }
    
    # 5. Experience (15 points)
    exp_score = 0
    if experience_years >= 5:
        exp_score = 15
    elif experience_years >= 3:
        exp_score = 12
    elif experience_years >= 1:
        exp_score = 8
    elif 'experience' in sections or 'internship' in resume_text.lower():
        exp_score = 5
    elif 'project' in resume_text.lower() or 'projects' in sections:
        exp_score = 3
    
    scores['experience'] = {
        'score': round(exp_score, 1),
        'max': 15,
        'label': 'Experience',
        'details': f"~{experience_years} years of experience detected"
    }
    
    # 6. Formatting & Readability (10 points)
    format_score = 0
    
    # Check for reasonable line count
    lines = resume_text.split('\n')
    non_empty_lines = [l for l in lines if l.strip()]
    if 20 <= len(non_empty_lines) <= 100:
        format_score += 3
    elif len(non_empty_lines) > 10:
        format_score += 1
    
    # No excessive special characters
    special_chars = len(re.findall(r'[★●◆▪►•]', resume_text))
    if special_chars < 20:
        format_score += 2
    
    # Consistent structure
    if len(sections) >= 3:
        format_score += 3
    elif len(sections) >= 2:
        format_score += 2
    
    # Not too long, not too short
    if 400 <= word_count <= 1000:
        format_score += 2
    elif 200 <= word_count <= 1500:
        format_score += 1
    
    scores['formatting'] = {
        'score': round(min(format_score, 10), 1),
        'max': 10,
        'label': 'Formatting & Readability',
        'details': f"{len(non_empty_lines)} lines, {len(sections)} sections identified"
    }
    
    # Calculate total
    total = sum(s['score'] for s in scores.values())
    max_total = sum(s['max'] for s in scores.values())
    
    # Determine grade
    percentage = (total / max_total) * 100
    if percentage >= 85:
        grade = 'A'
        grade_label = 'Excellent'
    elif percentage >= 70:
        grade = 'B'
        grade_label = 'Good'
    elif percentage >= 55:
        grade = 'C'
        grade_label = 'Average'
    elif percentage >= 40:
        grade = 'D'
        grade_label = 'Below Average'
    else:
        grade = 'F'
        grade_label = 'Needs Improvement'
    
    return {
        'total_score': round(total, 1),
        'max_score': max_total,
        'percentage': round(percentage, 1),
        'grade': grade,
        'grade_label': grade_label,
        'breakdown': scores
    }
