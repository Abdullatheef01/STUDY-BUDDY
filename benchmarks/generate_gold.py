"""Generate synthetic gold-standard resumes for ENG-09 benchmark."""
import json
import os
import random

random.seed(42)

FIRST = ["Aarav", "Priya", "Rohan", "Sneha", "Arjun", "Kavya", "Vikram", "Ananya"]
LAST = ["Sharma", "Patel", "Singh", "Gupta", "Mehta", "Reddy", "Khan", "Iyer"]
ROLES = ["Software Engineer", "Data Analyst", "Frontend Developer", "Backend Developer"]
SKILLS_POOL = [
    "Python", "JavaScript", "React", "SQL", "Machine Learning",
    "Docker", "AWS", "Git", "Java", "Node.js", "TypeScript", "MongoDB",
]
COMPANIES = ["TechCorp", "DataSystems", "CloudNine", "InnovateLabs"]


def make_resume(i):
    first = random.choice(FIRST)
    last = random.choice(LAST)
    name = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}{i}@example.com"
    phone = f"+91 98{random.randint(10000000, 99999999)}"
    role = random.choice(ROLES)
    skills = random.sample(SKILLS_POOL, k=random.randint(4, 7))
    company = random.choice(COMPANIES)

    text = f"""{name}
{email} | {phone} | linkedin.com/in/{first.lower()}{last.lower()}

PROFESSIONAL SUMMARY
{role} with {random.randint(1, 5)} years of experience building scalable applications.

SKILLS
{', '.join(skills)}

EXPERIENCE
{role} — {company} (2022–Present)
- Built microservices handling 10k req/s
- Reduced latency by 40% through caching

EDUCATION
B.Tech Computer Science, 2021
"""
    return {
        "id": f"syn_{i:03d}",
        "text": text,
        "labels": {
            "name": name,
            "email": email,
            "phone": phone,
            "skills": skills,
            "role": role,
        },
    }


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "resume_gold")
    os.makedirs(out_dir, exist_ok=True)
    for i in range(30):  # Start with 30; expand to 120 per roadmap
        item = make_resume(i)
        with open(os.path.join(out_dir, f"{item['id']}.json"), "w") as f:
            json.dump(item, f, indent=2)
    print(f"Generated 30 synthetic resumes in {out_dir}")


if __name__ == "__main__":
    main()
