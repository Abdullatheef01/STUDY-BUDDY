"""
Coding Practice - Recommends coding problems by company, topic, and difficulty.
"""
import os
import csv


_coding_data = None


def _load_coding_questions():
    """Load coding questions from CSV."""
    global _coding_data
    if _coding_data is not None:
        return _coding_data
    
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'coding_questions.csv')
    _coding_data = []
    
    if not os.path.exists(csv_path):
        print(f"Warning: Coding questions CSV not found at {csv_path}")
        return _coding_data
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            _coding_data.append(row)
    
    return _coding_data


def get_coding_questions(company=None, topic=None, difficulty=None):
    """
    Get coding practice questions with optional filters.
    
    Args:
        company: Company name filter
        topic: Topic filter (e.g., 'Arrays', 'Dynamic Programming')
        difficulty: Difficulty filter ('Easy', 'Medium', 'Hard')
    
    Returns:
        list: Filtered coding questions
    """
    questions = _load_coding_questions()
    
    filtered = questions
    
    if company:
        filtered = [q for q in filtered if q['company'].lower() == company.lower()]
    
    if topic:
        filtered = [q for q in filtered if q['topic'].lower() == topic.lower()]
    
    if difficulty:
        filtered = [q for q in filtered if q['difficulty'].lower() == difficulty.lower()]
    
    return filtered


def get_available_companies():
    """Get list of companies with coding questions."""
    questions = _load_coding_questions()
    companies = list(set(q['company'] for q in questions))
    companies.sort()
    return companies


def get_available_topics():
    """Get list of available topics."""
    questions = _load_coding_questions()
    topics = list(set(q['topic'] for q in questions))
    topics.sort()
    return topics


def get_company_coding_stats():
    """Get coding question statistics per company."""
    questions = _load_coding_questions()
    stats = {}
    
    for q in questions:
        company = q['company']
        if company not in stats:
            stats[company] = {'total': 0, 'Easy': 0, 'Medium': 0, 'Hard': 0, 'topics': set()}
        stats[company]['total'] += 1
        diff = q['difficulty']
        if diff in stats[company]:
            stats[company][diff] += 1
        stats[company]['topics'].add(q['topic'])
    
    # Convert sets to lists for JSON serialization
    for company in stats:
        stats[company]['topics'] = sorted(list(stats[company]['topics']))
    
    return stats


def get_recommended_problems(skills, num=10):
    """
    Recommend coding problems based on candidate's skills.
    
    Args:
        skills: List of candidate's skill names
        num: Number of problems to recommend
    
    Returns:
        list: Recommended coding problems
    """
    questions = _load_coding_questions()
    skills_lower = {s.lower() for s in skills}
    
    # Map skills to relevant topics
    skill_to_topic = {
        'arrays': 'Arrays',
        'data structures': 'Arrays',
        'linked list': 'Linked List',
        'trees': 'Trees',
        'graphs': 'Graph',
        'dynamic programming': 'Dynamic Programming',
        'algorithms': 'Dynamic Programming',
        'sorting': 'Sorting',
        'searching': 'Binary Search',
        'hash table': 'Hash Table',
        'stack': 'Stack',
        'heap': 'Heap',
        'strings': 'Strings',
    }
    
    relevant_topics = set()
    for skill in skills_lower:
        if skill in skill_to_topic:
            relevant_topics.add(skill_to_topic[skill])
    
    # If we have relevant topics, prioritize matching questions
    if relevant_topics:
        relevant_qs = [q for q in questions if q['topic'] in relevant_topics]
        other_qs = [q for q in questions if q['topic'] not in relevant_topics]
        
        # Mix: 60% relevant, 40% diverse
        num_relevant = min(int(num * 0.6), len(relevant_qs))
        num_other = min(num - num_relevant, len(other_qs))
        
        selected = relevant_qs[:num_relevant] + other_qs[:num_other]
    else:
        # Return a diverse mix starting with Easy
        easy = [q for q in questions if q['difficulty'] == 'Easy'][:3]
        medium = [q for q in questions if q['difficulty'] == 'Medium'][:5]
        hard = [q for q in questions if q['difficulty'] == 'Hard'][:2]
        selected = easy + medium + hard
    
    return selected[:num]
