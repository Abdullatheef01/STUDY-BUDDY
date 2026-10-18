"""
Resume Feedback - Generates AI-based improvement suggestions.
"""


def generate_feedback(ats_result, sections, skills, experience_years):
    """
    Generate resume improvement suggestions based on ATS analysis.
    
    Args:
        ats_result: ATS score result dict
        sections: Extracted resume sections
        skills: Extracted skills list
        experience_years: Estimated years of experience
    
    Returns:
        list: List of feedback items with priority, category, and suggestion
    """
    feedback = []
    breakdown = ats_result['breakdown']

    # --- Section Feedback ---
    if breakdown['sections']['score'] < 15:
        missing_essential = []
        for section in ['summary', 'education', 'experience', 'skills']:
            if section not in sections:
                missing_essential.append(section.title())

        if missing_essential:
            feedback.append({
                'priority': 'high',
                'category': 'Structure',
                'icon': '📋',
                'title': 'Add Missing Sections',
                'suggestion': f"Your resume is missing these important sections: {', '.join(missing_essential)}. ATS systems expect standard sections to properly parse your resume.",
                'impact': 'High Impact'
            })

    if 'summary' not in sections:
        feedback.append({
            'priority': 'high',
            'category': 'Structure',
            'icon': '📝',
            'title': 'Add a Professional Summary',
            'suggestion': 'Start your resume with a 2-3 sentence professional summary highlighting your key expertise, years of experience, and career goals. This helps ATS systems and recruiters quickly understand your profile.',
            'impact': 'High Impact'
        })

    # --- Skills Feedback ---
    num_skills = len(skills)
    if num_skills < 7:
        feedback.append({
            'priority': 'high',
            'category': 'Skills',
            'icon': '🎯',
            'title': 'Add More Technical Skills',
            'suggestion': f"Only {num_skills} skills were detected. Aim for 10-15+ relevant skills. Include programming languages, frameworks, tools, and methodologies you're proficient in.",
            'impact': 'High Impact'
        })

    categories = set(s['category'] for s in skills)
    if len(categories) < 3 and num_skills > 0:
        feedback.append({
            'priority': 'medium',
            'category': 'Skills',
            'icon': '🧩',
            'title': 'Diversify Your Skill Set',
            'suggestion': 'Your skills are concentrated in few categories. Consider adding skills from other areas like soft skills, tools, frameworks, or methodologies to show well-roundedness.',
            'impact': 'Medium Impact'
        })

    # --- Content Feedback ---
    if breakdown['content']['score'] < 12:
        feedback.append({
            'priority': 'high',
            'category': 'Content',
            'icon': '✨',
            'title': 'Use Action Verbs',
            'suggestion': 'Start your bullet points with strong action verbs like "Developed," "Implemented," "Led," "Optimized," "Designed," or "Achieved." This makes your achievements more impactful and ATS-friendly.',
            'impact': 'High Impact'
        })

        feedback.append({
            'priority': 'high',
            'category': 'Content',
            'icon': '📊',
            'title': 'Quantify Your Achievements',
            'suggestion': 'Add numbers and metrics to your achievements. Instead of "Improved performance," write "Improved system performance by 40%, reducing load time from 5s to 3s." Quantified results are 2x more likely to catch recruiter attention.',
            'impact': 'High Impact'
        })

    # --- Contact Feedback ---
    if breakdown['contact']['score'] < 8:
        feedback.append({
            'priority': 'medium',
            'category': 'Contact',
            'icon': '🔗',
            'title': 'Enhance Contact Information',
            'suggestion': 'Include all relevant contact details: professional email, phone number, LinkedIn profile URL, and GitHub/portfolio links. This increases your visibility and makes it easy for recruiters to reach you.',
            'impact': 'Medium Impact'
        })

    # --- Experience Feedback ---
    if breakdown['experience']['score'] < 8 and experience_years < 2:
        feedback.append({
            'priority': 'medium',
            'category': 'Experience',
            'icon': '💼',
            'title': 'Highlight Projects & Internships',
            'suggestion': 'If you have limited work experience, emphasize personal projects, academic projects, internships, and open-source contributions. Describe them with the same detail as work experience.',
            'impact': 'Medium Impact'
        })

    # --- Formatting Feedback ---
    if breakdown['formatting']['score'] < 6:
        feedback.append({
            'priority': 'low',
            'category': 'Formatting',
            'icon': '📐',
            'title': 'Improve Resume Structure',
            'suggestion': 'Use clear section headings, consistent formatting, and bullet points. Keep your resume to 1-2 pages. Use a clean, professional font and adequate white space.',
            'impact': 'Low Impact'
        })

    # --- General Best Practices ---
    if ats_result['percentage'] < 70:
        feedback.append({
            'priority': 'medium',
            'category': 'Strategy',
            'icon': '🎯',
            'title': 'Tailor for Target Role',
            'suggestion': 'Customize your resume for each job application. Mirror keywords from the job description. Use the exact terms mentioned in the posting (e.g., "React.js" instead of just "React").',
            'impact': 'High Impact'
        })

    if 'projects' not in sections:
        feedback.append({
            'priority': 'medium',
            'category': 'Structure',
            'icon': '🚀',
            'title': 'Add a Projects Section',
            'suggestion': 'Include 2-4 notable projects with brief descriptions, technologies used, and outcomes. Projects demonstrate practical skills and initiative.',
            'impact': 'Medium Impact'
        })

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    feedback.sort(key=lambda x: priority_order.get(x['priority'], 3))

    return feedback


def get_overall_summary(ats_result, skills, sections):
    """
    Generate a dynamic narrative summary based on ATS score and specific resume content.
    """
    percentage = ats_result['percentage']
    num_skills = len(skills)
    top_skills = [s['name'] for s in skills[:3]]

    # Identify primary strength
    main_strength = ""
    if 'experience' in sections:
        main_strength = "professional experience"
    elif 'projects' in sections:
        main_strength = "project portfolio"
    elif num_skills > 10:
        main_strength = "diverse technical skill set"
    else:
        main_strength = "educational background"

    # Narrative construction
    if percentage >= 85:
        summary = f"Your resume is exceptional! Your deep expertise in {', '.join(top_skills)} and strong {main_strength} make you a top-tier candidate for competitive roles. "
        summary += "It is highly optimized for modern ATS algorithms."
    elif percentage >= 70:
        summary = f"Great work! You have a solid professional profile with clear strengths in {', '.join(top_skills) if top_skills else 'your core domain'}. "
        summary += f"While your {main_strength} is well-presented, adding more quantified achievements could push you into the top 10% of applicants."
    elif percentage >= 55:
        summary = f"Your resume shows good potential, particularly in {top_skills[0] if top_skills else 'your field'}. "
        summary += f"However, to better compete for high-demand roles, we recommend strengthening your {main_strength} section and focusing on missing keywords."
    elif percentage >= 40:
        summary = "Your resume covers the basics but lacks the keyword density required by top-tier ATS systems. "
        summary += f"Focus on highlighting your {', '.join(top_skills) if top_skills else 'technical skills'} more prominently and improving the bullet point impact."
    else:
        summary = "Your resume requires significant optimization to be effectively parsed by modern hiring systems. "
        summary += "Focus on the high-priority suggestions below to restructure your profile for better visibility."

    return summary
