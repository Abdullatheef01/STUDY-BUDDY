"""
Career Guidance - Suggests career paths based on skills and experience.
"""

# Career path definitions
CAREER_PATHS = {
    'Full Stack Web Development': {
        'core_skills': ['JavaScript', 'HTML', 'CSS', 'React', 'Node.js', 'SQL'],
        'progression': ['Junior Developer', 'Mid-Level Developer', 'Senior Developer', 'Tech Lead', 'Engineering Manager'],
        'related_roles': ['Frontend Developer', 'Backend Developer', 'Full Stack Developer'],
        'growth_areas': ['Cloud Computing', 'DevOps', 'System Design', 'Team Leadership'],
        'industry_demand': 'Very High',
        'icon': '🌐'
    },
    'Data Science & Analytics': {
        'core_skills': ['Python', 'SQL', 'Statistics', 'Machine Learning', 'Pandas', 'Data Visualization'],
        'progression': ['Data Analyst', 'Data Scientist', 'Senior Data Scientist', 'Lead DS', 'Head of Data'],
        'related_roles': ['Data Analyst', 'Data Scientist', 'Data Engineer'],
        'growth_areas': ['Deep Learning', 'MLOps', 'Big Data', 'Cloud Platforms'],
        'industry_demand': 'Very High',
        'icon': '📊'
    },
    'Machine Learning & AI': {
        'core_skills': ['Python', 'TensorFlow', 'PyTorch', 'Machine Learning', 'Deep Learning', 'NLP'],
        'progression': ['ML Engineer', 'Senior ML Engineer', 'ML Architect', 'AI Research Scientist', 'VP of AI'],
        'related_roles': ['Machine Learning Engineer', 'AI Research Scientist', 'NLP Engineer', 'Computer Vision Engineer'],
        'growth_areas': ['Generative AI', 'Reinforcement Learning', 'MLOps', 'Research'],
        'industry_demand': 'Extremely High',
        'icon': '🤖'
    },
    'Cloud & DevOps': {
        'core_skills': ['AWS', 'Docker', 'Kubernetes', 'Linux', 'CI/CD', 'Terraform'],
        'progression': ['DevOps Engineer', 'Senior DevOps', 'Cloud Architect', 'Platform Lead', 'VP Infrastructure'],
        'related_roles': ['DevOps Engineer', 'Cloud Architect', 'Site Reliability Engineer', 'Cloud Engineer'],
        'growth_areas': ['Security', 'Multi-Cloud', 'Infrastructure as Code', 'Observability'],
        'industry_demand': 'Very High',
        'icon': '☁️'
    },
    'Cybersecurity': {
        'core_skills': ['Network Security', 'Linux', 'Python', 'Penetration Testing', 'Firewalls', 'Cryptography'],
        'progression': ['Security Analyst', 'Senior Security Engineer', 'Security Architect', 'CISO'],
        'related_roles': ['Cybersecurity Analyst', 'Penetration Tester', 'Security Engineer'],
        'growth_areas': ['Cloud Security', 'Application Security', 'Threat Intelligence', 'Compliance'],
        'industry_demand': 'Very High',
        'icon': '🔒'
    },
    'Mobile Development': {
        'core_skills': ['Swift', 'Kotlin', 'React Native', 'Flutter', 'Mobile Development'],
        'progression': ['Junior Mobile Dev', 'Mobile Developer', 'Senior Mobile Dev', 'Mobile Lead', 'Mobile Architect'],
        'related_roles': ['Mobile App Developer', 'iOS Developer', 'Android Developer'],
        'growth_areas': ['Cross-Platform', 'AR/VR', 'Performance Optimization', 'App Architecture'],
        'industry_demand': 'High',
        'icon': '📱'
    },
    'Product & Project Management': {
        'core_skills': ['Agile', 'Scrum', 'JIRA', 'Communication', 'Leadership', 'Product Strategy'],
        'progression': ['Associate PM', 'Product Manager', 'Senior PM', 'Director of Product', 'VP Product'],
        'related_roles': ['Product Manager', 'Project Manager', 'Scrum Master'],
        'growth_areas': ['Data-Driven Decisions', 'User Research', 'Technical Depth', 'Strategy'],
        'industry_demand': 'High',
        'icon': '📋'
    },
    'UI/UX Design': {
        'core_skills': ['Figma', 'User Research', 'Wireframing', 'Prototyping', 'UI/UX', 'Design Thinking'],
        'progression': ['Junior Designer', 'UI/UX Designer', 'Senior Designer', 'Design Lead', 'Head of Design'],
        'related_roles': ['UI/UX Designer', 'UX Researcher', 'Graphic Designer'],
        'growth_areas': ['Design Systems', 'Motion Design', 'Accessibility', 'Frontend Development'],
        'industry_demand': 'High',
        'icon': '🎨'
    },
    'Embedded Systems & IoT': {
        'core_skills': ['C', 'C++', 'Embedded Systems', 'Microcontrollers', 'RTOS', 'Arduino'],
        'progression': ['Junior Firmware Eng', 'Embedded Engineer', 'Senior Embedded Eng', 'Hardware Lead', 'CTO'],
        'related_roles': ['Embedded Systems Engineer', 'Firmware Engineer', 'Robotics Engineer'],
        'growth_areas': ['IoT Platforms', 'Edge Computing', 'ML at Edge', 'System Integration'],
        'industry_demand': 'High',
        'icon': '🔧'
    },
    'Blockchain & Web3': {
        'core_skills': ['Solidity', 'Ethereum', 'Smart Contracts', 'Web3', 'Blockchain', 'JavaScript'],
        'progression': ['Blockchain Developer', 'Senior Blockchain Dev', 'Protocol Engineer', 'Blockchain Architect'],
        'related_roles': ['Blockchain Developer'],
        'growth_areas': ['DeFi', 'Layer 2 Solutions', 'Cross-chain', 'Security Auditing'],
        'industry_demand': 'Moderate',
        'icon': '⛓️'
    }
}


def suggest_career_paths(resume_skills, experience_years):
    """
    Suggest career paths based on current skills and experience.
    
    Args:
        resume_skills: List of skill names
        experience_years: Estimated years of experience
    
    Returns:
        list: Ranked career path suggestions
    """
    resume_skills_lower = {s.lower() for s in resume_skills}
    suggestions = []
    
    for path_name, path_info in CAREER_PATHS.items():
        core_skills_lower = {s.lower() for s in path_info['core_skills']}
        matched = resume_skills_lower.intersection(core_skills_lower)
        match_pct = (len(matched) / len(core_skills_lower)) * 100 if core_skills_lower else 0
        
        if match_pct > 0:  # Only suggest if at least some skills match
            # Determine current level based on experience
            progression = path_info['progression']
            if experience_years >= 8:
                current_level = min(3, len(progression) - 1)
            elif experience_years >= 5:
                current_level = min(2, len(progression) - 1)
            elif experience_years >= 2:
                current_level = min(1, len(progression) - 1)
            else:
                current_level = 0
            
            missing_core = [s for s in path_info['core_skills'] if s.lower() not in resume_skills_lower]
            
            suggestions.append({
                'path': path_name,
                'icon': path_info['icon'],
                'match_percentage': round(match_pct, 1),
                'matched_skills': [s for s in path_info['core_skills'] if s.lower() in resume_skills_lower],
                'missing_skills': missing_core,
                'current_level': progression[current_level],
                'next_level': progression[min(current_level + 1, len(progression) - 1)],
                'progression': progression,
                'growth_areas': path_info['growth_areas'],
                'industry_demand': path_info['industry_demand'],
                'related_roles': path_info['related_roles']
            })
    
    # Sort by match percentage
    suggestions.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    return suggestions[:5]  # Return top 5 career paths
