"""
Company Questions - Serves company-specific interview questions from dataset.
"""
import os
import csv


_questions_data = None


def _load_questions():
    """Load company questions from CSV."""
    global _questions_data
    if _questions_data is not None:
        return _questions_data
    
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'company_questions.csv')
    _questions_data = []
    
    if not os.path.exists(csv_path):
        print(f"Warning: Company questions CSV not found at {csv_path}")
        return _questions_data
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            _questions_data.append(row)
    
    return _questions_data


def get_company_questions(company=None, category=None, difficulty=None):
    """
    Get interview questions filtered by company, category, and/or difficulty.
    
    Args:
        company: Company name filter (optional)
        category: Question category filter (optional)
        difficulty: Difficulty filter (optional)
    
    Returns:
        list: Filtered interview questions
    """
    questions = _load_questions()
    
    filtered = questions
    
    if company:
        filtered = [q for q in filtered if q['company'].lower() == company.lower()]
    
    if category:
        filtered = [q for q in filtered if q['category'].lower() == category.lower()]
    
    if difficulty:
        filtered = [q for q in filtered if q['difficulty'].lower() == difficulty.lower()]
    
    return filtered


def get_available_companies():
    """Get list of companies with available questions."""
    questions = _load_questions()
    companies = list(set(q['company'] for q in questions))
    companies.sort()
    return companies


def get_company_stats():
    """Get question count statistics per company."""
    questions = _load_questions()
    stats = {}
    
    for q in questions:
        company = q['company']
        if company not in stats:
            stats[company] = {'total': 0, 'categories': {}}
        stats[company]['total'] += 1
        
        cat = q['category']
        if cat not in stats[company]['categories']:
            stats[company]['categories'][cat] = 0
        stats[company]['categories'][cat] += 1
    
    return stats
