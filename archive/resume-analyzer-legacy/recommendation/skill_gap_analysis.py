"""
Skill Gap Analysis - Identifies missing skills for target roles.
"""


def analyze_skill_gaps(resume_skills, job_recommendations):
    """
    Analyze skill gaps between resume and recommended jobs.
    
    Args:
        resume_skills: List of skill names from resume
        job_recommendations: List of job recommendation dicts
    
    Returns:
        dict: Skill gap analysis results
    """
    resume_skills_lower = {s.lower() for s in resume_skills}
    
    # Aggregate missing skills across top recommendations
    missing_skill_freq = {}
    for job in job_recommendations[:5]:  # Analyze top 5 matches
        for skill in job.get('missing_skills', []):
            skill_lower = skill.lower()
            if skill_lower not in resume_skills_lower:
                if skill not in missing_skill_freq:
                    missing_skill_freq[skill] = {
                        'count': 0,
                        'jobs': []
                    }
                missing_skill_freq[skill]['count'] += 1
                missing_skill_freq[skill]['jobs'].append(job['title'])
    
    # Sort by frequency (most commonly required missing skills first)
    sorted_gaps = sorted(missing_skill_freq.items(), key=lambda x: x[1]['count'], reverse=True)
    
    # Categorize gaps
    critical_gaps = []
    important_gaps = []
    nice_to_have = []
    
    for skill, info in sorted_gaps:
        gap_item = {
            'skill': skill,
            'demanded_by': info['count'],
            'related_jobs': info['jobs'][:3]  # Top 3 jobs needing this skill
        }
        
        if info['count'] >= 3:
            gap_item['priority'] = 'Critical'
            critical_gaps.append(gap_item)
        elif info['count'] >= 2:
            gap_item['priority'] = 'Important'
            important_gaps.append(gap_item)
        else:
            gap_item['priority'] = 'Nice to Have'
            nice_to_have.append(gap_item)
    
    return {
        'critical': critical_gaps,
        'important': important_gaps,
        'nice_to_have': nice_to_have,
        'total_gaps': len(sorted_gaps),
        'summary': _generate_gap_summary(critical_gaps, important_gaps, nice_to_have)
    }


def _generate_gap_summary(critical, important, nice):
    """Generate a text summary of skill gaps."""
    parts = []
    
    if critical:
        skills_list = ', '.join(g['skill'] for g in critical[:3])
        parts.append(f"Critical skills to learn: {skills_list}")
    
    if important:
        skills_list = ', '.join(g['skill'] for g in important[:3])
        parts.append(f"Important additions: {skills_list}")
    
    if not critical and not important:
        return "Your skills align well with your target roles! Consider expanding into complementary areas."
    
    return '. '.join(parts) + '.'
