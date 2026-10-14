"""
Interview Questions - Generates role-specific interview questions.
"""

# Role-specific interview question templates
ROLE_QUESTIONS = {
    'Software Engineer': {
        'technical': [
            'Explain the difference between stack and heap memory.',
            'What is the time complexity of common sorting algorithms?',
            'Describe SOLID principles with examples.',
            'How does garbage collection work?',
            'Explain the difference between concurrency and parallelism.',
            'What are design patterns? Name and explain three.',
            'How would you handle a memory leak in production?',
            'Explain RESTful API design best practices.',
        ],
        'behavioral': [
            'Tell me about a time you debugged a difficult issue.',
            'How do you approach code reviews?',
            'Describe a situation where you had to balance quality with speed.',
            'Tell me about a project you\'re most proud of.',
            'How do you stay updated with new technologies?',
        ],
        'system_design': [
            'Design a URL shortener service.',
            'How would you design a chat application?',
            'Design a rate limiter for an API.',
        ]
    },
    'Frontend Developer': {
        'technical': [
            'Explain the Virtual DOM and how React uses it.',
            'What is the difference between CSS Grid and Flexbox?',
            'How do you optimize web application performance?',
            'Explain event bubbling and event capturing.',
            'What are Web Components?',
            'Describe the critical rendering path.',
            'How does the browser event loop work?',
            'Explain the difference between localStorage and sessionStorage.',
        ],
        'behavioral': [
            'How do you handle browser compatibility issues?',
            'Describe a challenging UI you built.',
            'How do you approach responsive design?',
            'Tell me about a time you improved user experience.',
        ],
        'system_design': [
            'Design a component library.',
            'How would you architect a large SPA?',
        ]
    },
    'Data Scientist': {
        'technical': [
            'Explain the bias-variance tradeoff.',
            'What is regularization and why is it used?',
            'Describe different types of cross-validation.',
            'Explain the difference between bagging and boosting.',
            'How do you handle imbalanced datasets?',
            'What is feature engineering?',
            'Explain gradient descent and its variants.',
            'What is the curse of dimensionality?',
        ],
        'behavioral': [
            'How do you communicate technical findings to non-technical stakeholders?',
            'Describe a project where data quality was an issue.',
            'How do you decide which model to use?',
        ],
        'system_design': [
            'Design an ML pipeline for production.',
            'How would you build a recommendation system?',
        ]
    },
    'DevOps Engineer': {
        'technical': [
            'Explain the difference between containers and virtual machines.',
            'How does Kubernetes orchestration work?',
            'Describe a CI/CD pipeline you\'ve built.',
            'What is Infrastructure as Code?',
            'How do you monitor application health?',
            'Explain blue-green deployment vs canary deployment.',
            'How would you handle a production outage?',
        ],
        'behavioral': [
            'How do you balance automation with manual oversight?',
            'Describe a time you improved deployment reliability.',
            'How do you handle security in the CI/CD pipeline?',
        ],
        'system_design': [
            'Design a scalable logging system.',
            'How would you set up monitoring for microservices?',
        ]
    },
}

# Default questions for roles not in the curated list
DEFAULT_QUESTIONS = {
    'technical': [
        'What technologies are you most experienced with?',
        'Describe your problem-solving approach.',
        'How do you ensure code/work quality?',
        'What\'s your experience with version control?',
        'How do you handle deadlines and priorities?',
    ],
    'behavioral': [
        'Tell me about your biggest professional achievement.',
        'How do you handle conflict in a team?',
        'Describe a time you failed and what you learned.',
        'How do you prioritize multiple tasks?',
        'Why are you interested in this role?',
    ],
    'system_design': [
        'How would you design a scalable web application?',
        'Describe the architecture of a system you\'ve built.',
    ]
}


def generate_interview_questions(role, skills=None):
    """
    Generate interview questions for a specific role.
    
    Args:
        role: Job role title
        skills: Optional list of candidate's skills for contextual questions
    
    Returns:
        dict: Interview questions organized by category
    """
    # Find best matching role template
    questions = None
    for template_role, template_questions in ROLE_QUESTIONS.items():
        if template_role.lower() in role.lower() or role.lower() in template_role.lower():
            questions = template_questions
            break
    
    if not questions:
        # Try partial matching
        role_lower = role.lower()
        for template_role, template_questions in ROLE_QUESTIONS.items():
            template_lower = template_role.lower()
            # Check for keyword overlap
            role_words = set(role_lower.split())
            template_words = set(template_lower.split())
            if role_words.intersection(template_words):
                questions = template_questions
                break
    
    if not questions:
        questions = DEFAULT_QUESTIONS
    
    result = {
        'role': role,
        'technical': questions.get('technical', DEFAULT_QUESTIONS['technical']),
        'behavioral': questions.get('behavioral', DEFAULT_QUESTIONS['behavioral']),
        'system_design': questions.get('system_design', DEFAULT_QUESTIONS['system_design']),
    }
    
    # Add skill-specific questions if skills provided
    if skills:
        skill_questions = []
        for skill in skills[:5]:  # Top 5 skills
            skill_questions.append(f"Describe your experience working with {skill}.")
        result['skill_specific'] = skill_questions
    
    return result
