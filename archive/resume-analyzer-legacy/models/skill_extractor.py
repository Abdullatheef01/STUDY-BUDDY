"""
Skill Extractor - Rule-based skill extraction using comprehensive skills database.
"""
import os
import re
import csv


# Load skills database
SKILLS_DB = {}
SKILL_ALIASES = {}

def _load_skills_db():
    """Load skills database from CSV file."""
    global SKILLS_DB, SKILL_ALIASES
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'skills_db.csv')
    
    if not os.path.exists(db_path):
        print(f"Warning: Skills DB not found at {db_path}")
        return
    
    with open(db_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            skill_name = row['skill'].strip()
            category = row['category'].strip()
            aliases = row.get('aliases', '').strip()
            
            SKILLS_DB[skill_name.lower()] = {
                'name': skill_name,
                'category': category
            }
            
            # Build alias mapping
            if aliases:
                for alias in aliases.split('|'):
                    alias = alias.strip().lower()
                    if alias:
                        SKILL_ALIASES[alias] = skill_name

# Load on module import
_load_skills_db()


def extract_skills(text):
    """
    Extract skills from resume text using pattern matching against skills database.
    
    Args:
        text: Resume text (cleaned)
    
    Returns:
        list: List of dicts with skill name and category
    """
    if not text:
        return []
    
    text_lower = text.lower()
    found_skills = {}
    
    # Method 1: Direct skill name matching
    for skill_lower, info in SKILLS_DB.items():
        # Use word boundary matching to avoid partial matches
        pattern = r'(?<![a-zA-Z])' + re.escape(skill_lower) + r'(?![a-zA-Z])'
        if re.search(pattern, text_lower):
            found_skills[info['name']] = info['category']
    
    # Method 2: Alias matching
    for alias, skill_name in SKILL_ALIASES.items():
        pattern = r'(?<![a-zA-Z])' + re.escape(alias) + r'(?![a-zA-Z])'
        if re.search(pattern, text_lower):
            if skill_name in SKILLS_DB.get(skill_name.lower(), {}):
                category = SKILLS_DB[skill_name.lower()]['category']
            else:
                category = 'Other'
            found_skills[skill_name] = category
    
    # Convert to list of dicts
    result = []
    for name, category in found_skills.items():
        result.append({
            'name': name,
            'category': category
        })
    
    # Sort by category then name
    result.sort(key=lambda x: (x['category'], x['name']))
    
    return result


def get_skills_by_category(skills):
    """
    Group extracted skills by category.
    
    Args:
        skills: List of skill dicts from extract_skills()
    
    Returns:
        dict: Category -> list of skill names
    """
    categorized = {}
    for skill in skills:
        cat = skill['category']
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(skill['name'])
    return categorized


def get_skill_names(skills):
    """Get just the skill names as a list."""
    return [s['name'] for s in skills]
