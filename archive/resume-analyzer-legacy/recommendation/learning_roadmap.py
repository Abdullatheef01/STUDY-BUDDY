"""
Learning Roadmap - Generates learning paths for missing skills.
"""

# Curated learning resources for common skills
LEARNING_RESOURCES = {
    'Python': {
        'beginner': ['Python.org Official Tutorial', 'Automate the Boring Stuff (free online)', 'Codecademy Python Course'],
        'intermediate': ['Real Python Tutorials', 'Python Cookbook', 'LeetCode Python Track'],
        'estimated_time': '2-4 weeks'
    },
    'Java': {
        'beginner': ['Oracle Java Tutorials', 'Codecademy Java', 'Head First Java (Book)'],
        'intermediate': ['Effective Java (Book)', 'Spring Framework Docs', 'HackerRank Java'],
        'estimated_time': '4-6 weeks'
    },
    'JavaScript': {
        'beginner': ['MDN Web Docs', 'freeCodeCamp JavaScript', 'Eloquent JavaScript (free)'],
        'intermediate': ['JavaScript.info', 'You Don\'t Know JS (free)', 'Frontend Masters'],
        'estimated_time': '3-5 weeks'
    },
    'React': {
        'beginner': ['React Official Docs', 'freeCodeCamp React', 'Scrimba React Course'],
        'intermediate': ['React Patterns', 'Kent C. Dodds Courses', 'Build a project'],
        'estimated_time': '3-4 weeks'
    },
    'SQL': {
        'beginner': ['SQLBolt (Interactive)', 'W3Schools SQL', 'Khan Academy SQL'],
        'intermediate': ['LeetCode SQL Problems', 'Mode Analytics SQL Tutorial', 'PostgreSQL Docs'],
        'estimated_time': '2-3 weeks'
    },
    'Docker': {
        'beginner': ['Docker Official Getting Started', 'Docker Curriculum', 'Play with Docker'],
        'intermediate': ['Docker Compose Docs', 'Kubernetes Basics', 'Docker Deep Dive (Book)'],
        'estimated_time': '1-2 weeks'
    },
    'AWS': {
        'beginner': ['AWS Free Tier + Tutorials', 'AWS Cloud Practitioner Course', 'A Cloud Guru'],
        'intermediate': ['AWS Solutions Architect Prep', 'Hands-on Labs', 'AWS Well-Architected'],
        'estimated_time': '4-8 weeks'
    },
    'Machine Learning': {
        'beginner': ['Andrew Ng ML Course (Coursera)', 'Google ML Crash Course', 'Kaggle Learn'],
        'intermediate': ['Fast.ai Course', 'Hands-On ML Book', 'Kaggle Competitions'],
        'estimated_time': '6-10 weeks'
    },
    'Git': {
        'beginner': ['Git Official Docs', 'Learn Git Branching (Interactive)', 'GitHub Skills'],
        'intermediate': ['Pro Git Book (free)', 'Advanced Git Workflows', 'Open Source Contributions'],
        'estimated_time': '1 week'
    },
    'Data Structures': {
        'beginner': ['GeeksforGeeks DSA', 'Visualgo.net', 'MIT OpenCourseWare'],
        'intermediate': ['LeetCode Practice', 'Competitive Programming', 'CLRS Book'],
        'estimated_time': '4-8 weeks'
    },
    'Algorithms': {
        'beginner': ['Khan Academy Algorithms', 'Visualgo.net', 'GeeksforGeeks'],
        'intermediate': ['LeetCode Medium Problems', 'Codeforces', 'Algorithm Design Manual'],
        'estimated_time': '4-8 weeks'
    },
    'TensorFlow': {
        'beginner': ['TensorFlow Official Tutorials', 'DeepLearning.AI TF Course', 'Google Colab Notebooks'],
        'intermediate': ['TF Model Garden', 'TensorFlow Extended', 'Research Papers'],
        'estimated_time': '3-5 weeks'
    },
    'Kubernetes': {
        'beginner': ['Kubernetes Official Tutorial', 'Katacoda K8s', 'Kubernetes the Hard Way'],
        'intermediate': ['CKA Certification Prep', 'Helm Charts', 'K8s Patterns Book'],
        'estimated_time': '3-5 weeks'
    },
    'Node.js': {
        'beginner': ['Node.js Official Docs', 'The Odin Project', 'freeCodeCamp Node'],
        'intermediate': ['Express.js Guide', 'Node.js Design Patterns', 'Build REST APIs'],
        'estimated_time': '2-4 weeks'
    },
}

# Generic resources for skills not in the curated list
DEFAULT_RESOURCES = {
    'beginner': ['Official Documentation', 'YouTube Tutorials', 'Udemy/Coursera Courses'],
    'intermediate': ['Hands-on Projects', 'Open Source Contributions', 'Community Forums'],
    'estimated_time': '2-4 weeks'
}


def generate_roadmap(skill_gaps, resume_skills):
    """
    Generate a learning roadmap based on skill gaps.
    
    Args:
        skill_gaps: Skill gap analysis result
        resume_skills: Current skills list
    
    Returns:
        list: Ordered learning path with resources and timing
    """
    roadmap = []
    order = 1
    
    # Process critical gaps first
    for gap in skill_gaps.get('critical', []):
        skill = gap['skill']
        resources = LEARNING_RESOURCES.get(skill, DEFAULT_RESOURCES)
        
        roadmap.append({
            'order': order,
            'skill': skill,
            'priority': 'Critical',
            'why': f"Required by {gap['demanded_by']} of your top matching roles",
            'resources': resources.get('beginner', DEFAULT_RESOURCES['beginner']),
            'advanced_resources': resources.get('intermediate', DEFAULT_RESOURCES['intermediate']),
            'estimated_time': resources.get('estimated_time', '2-4 weeks'),
            'related_jobs': gap['related_jobs']
        })
        order += 1
    
    # Then important gaps
    for gap in skill_gaps.get('important', []):
        skill = gap['skill']
        resources = LEARNING_RESOURCES.get(skill, DEFAULT_RESOURCES)
        
        roadmap.append({
            'order': order,
            'skill': skill,
            'priority': 'Important',
            'why': f"Will strengthen your candidacy for roles like {', '.join(gap['related_jobs'][:2])}",
            'resources': resources.get('beginner', DEFAULT_RESOURCES['beginner']),
            'advanced_resources': resources.get('intermediate', DEFAULT_RESOURCES['intermediate']),
            'estimated_time': resources.get('estimated_time', '2-4 weeks'),
            'related_jobs': gap['related_jobs']
        })
        order += 1
    
    # Nice to have (limit to top 3)
    for gap in skill_gaps.get('nice_to_have', [])[:3]:
        skill = gap['skill']
        resources = LEARNING_RESOURCES.get(skill, DEFAULT_RESOURCES)
        
        roadmap.append({
            'order': order,
            'skill': skill,
            'priority': 'Nice to Have',
            'why': f"Could open doors to {', '.join(gap['related_jobs'][:2])} roles",
            'resources': resources.get('beginner', DEFAULT_RESOURCES['beginner']),
            'advanced_resources': resources.get('intermediate', DEFAULT_RESOURCES['intermediate']),
            'estimated_time': resources.get('estimated_time', '2-4 weeks'),
            'related_jobs': gap['related_jobs']
        })
        order += 1
    
    return roadmap


def estimate_total_time(roadmap):
    """Estimate total learning time for the roadmap."""
    if not roadmap:
        return "0 weeks"
    
    total_weeks = 0
    for item in roadmap:
        time_str = item.get('estimated_time', '2-4 weeks')
        # Parse the range and take the average
        import re
        nums = re.findall(r'\d+', time_str)
        if nums:
            avg = sum(int(n) for n in nums) / len(nums)
            total_weeks += avg
    
    if total_weeks <= 4:
        return f"~{int(total_weeks)} weeks"
    else:
        months = total_weeks / 4
        return f"~{months:.1f} months"
