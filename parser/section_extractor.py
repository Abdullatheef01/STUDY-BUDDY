"""
Section Extractor - Identifies and extracts resume sections.
"""
import re
from datetime import datetime

# Common section headers in resumes
SECTION_PATTERNS = {
    'summary': r'(?i)(?:summary|objective|about\s*me|profile|professional\s*summary|career\s*objective|personal\s*statement|executive\s*profile|career\s*summary|professional\s*profile)',
    'education': r'(?i)(?:education|academic|qualification|degree|university|college|school|certification|certifications)',
    'experience': r'(?i)(?:experience|work\s*experience|employment|work\s*history|professional\s*experience|career\s*history|internship|work\s*history)',
    'skills': r'(?i)(?:skills|technical\s*skills|core\s*competencies|competencies|technologies|tech\s*stack|proficiencies|areas\s*of\s*expertise)',
    'projects': r'(?i)(?:projects|personal\s*projects|academic\s*projects|key\s*projects|portfolio|project\s*experience|selected\s*projects|technical\s*projects)',
    'awards': r'(?i)(?:awards|achievements|honors|accomplishments|recognition)',
    'languages': r'(?i)(?:languages|language\s*proficiency)',
    'interests': r'(?i)(?:interests|hobbies|extracurricular|activities)',
    'references': r'(?i)(?:references|referees)',
    'publications': r'(?i)(?:publications|papers|research)',
    'volunteer': r'(?i)(?:volunteer|volunteering|community\s*service)',
}


def extract_sections(text):
    """
    Extract different sections from resume text.
    
    Args:
        text: Cleaned resume text
    
    Returns:
        dict: Dictionary with section names as keys and content as values
    """
    if not text:
        return {}

    sections = {}
    lines = text.split('\n')
    current_section = 'header'
    current_content = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check if this line is a section header (case-insensitive)
        found_section = None
        # Remove numbers/icons for better matching
        clean_line = re.sub(r'^[^\w\s]+|^\d+[\.\)\s-]*', '', line_stripped).strip()

        for section_name, pattern in SECTION_PATTERNS.items():
            if re.search(pattern, clean_line):
                # Ensure the line is relatively short (headers aren't usually long sentences)
                if len(clean_line) < 50:
                    found_section = section_name
                    break

        if found_section:
            # Save previous section
            if current_content:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = found_section
            current_content = []
        else:
            current_content.append(line_stripped)

    # Save last section
    if current_content:
        sections[current_section] = '\n'.join(current_content).strip()

    # --- Heuristic Fallback for Summary ---
    # If no formal summary section was found, check if the "header" section
    # contains a large block of text starting with professional keywords
    if 'summary' not in sections and 'header' in sections:
        header_lines = sections['header'].split('\n')
        for i, line in enumerate(header_lines):
            # If we find a line that looks like the start of a summary
            # (long sentence, professional keywords, but no explicit header)
            if len(line) > 100 or re.search(r'(?i)(?:professional|experience|seeking|passionate|specializing)', line):
                # The rest of the header might be the summary
                sections['summary'] = '\n'.join(header_lines[i:]).strip()
                break

    return sections


def extract_education_details(education_text):
    """
    Extract education details from education section.
    
    Returns:
        list: List of education entries with degree, institution, year
    """
    if not education_text:
        return []

    entries = []

    # Common degree patterns
    degree_patterns = [
        r'(?i)(B\.?(?:Tech|E|Sc|A|Com|S)|Bachelor(?:\'s)?)',
        r'(?i)(M\.?(?:Tech|E|Sc|A|Com|S|BA)|Master(?:\'s)?)',
        r'(?i)(Ph\.?D\.?|Doctorate)',
        r'(?i)(Diploma|Associate)',
        r'(?i)(B\.?C\.?A|M\.?C\.?A)',
        r'(?i)(B\.?B\.?A|M\.?B\.?A)',
        r'(?i)(12th|10th|HSC|SSC|High School)',
    ]

    # Year pattern
    year_pattern = r'((?:19|20)\d{2})'

    lines = education_text.split('\n')
    for line in lines:
        entry = {'raw': line}

        # Find degree
        for dp in degree_patterns:
            match = re.search(dp, line)
            if match:
                entry['degree'] = match.group(1)
                break

        # Find year
        years = re.findall(year_pattern, line)
        if years:
            entry['year'] = years[-1]  # Take the last year (graduation year)

        if 'degree' in entry or 'year' in entry:
            entries.append(entry)

    return entries


def extract_experience_years(text):
    """
    Estimate total years of experience from resume text.
    
    Returns:
        float: Estimated years of experience
    """
    if not text:
        return 0

    # Direct mention of experience
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
        r'(?:experience|exp)\s*(?:of\s*)?(\d+)\+?\s*(?:years?|yrs?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))

    # Count date ranges
    date_ranges = re.findall(
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4})\s*[-–to]+\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}|Present|Current)',
        text, re.IGNORECASE
    )

    if date_ranges:
        return max(1, len(date_ranges))  # Rough estimate

    # Year ranges
    year_ranges = re.findall(r'(\d{4})\s*[-–to]+\s*(\d{4}|Present|Current)', text, re.IGNORECASE)
    if year_ranges:
        total = 0
        for start, end in year_ranges:
            start_yr = int(start)
            end_yr = datetime.now().year if end.lower() in ('present', 'current') else int(end)
            total += max(0, end_yr - start_yr)
        return total if total > 0 else 1

    return 0
