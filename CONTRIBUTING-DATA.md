# Contributing Data to STUDY-BUDDY

You don't need to know Python to contribute data. Data contributions are
the easiest way to join this project — fixing a question, adding a skill
alias, or adding an opportunity helps thousands of students.

## What you can contribute (no code needed)

### 1. Fix a question
Found a wrong answer, typo, or unclear explanation in a quiz?

- **Aptitude questions:** `data/aptitude_questions.json` (312 questions)
- **Interview questions:** `data/interview_questions.json` (339 questions)
- **Skill quizzes:** `data/skill_quizzes.json` (320 questions)

Each question looks like this:
```json
{
  "id": "apt-0001",
  "category": "quantitative",
  "difficulty": "Easy",
  "statement": "What is 50% of 360?",
  "options": ["162", "216", "180", "198"],
  "answer": 2,
  "explanation": "50% of 360 = 180."
}
```
Rules:
- `answer` is the **index** into `options` (0-based). Double-check it.
- Keep explanations short and show the working.
- Don't copy questions verbatim from copyrighted sources — write original phrasings.
- Don't claim "asked at Google" unless you have a citable source. Use "commonly reported" instead.

### 2. Add a skill alias
`data/taxonomy/skills_taxonomy.json` maps skill names to aliases:
```json
{
  "React": {
    "aliases": ["reactjs", "react.js", "react js"],
    "category": "frontend"
  }
}
```
Add missing aliases you know (e.g. "K8s" for Kubernetes).

### 3. Add an opportunity
`data/opportunities.json` lists internships/jobs. Include:
- title, company, link (must be a real, working URL)
- `retrieved_at` date and `source_url` (provenance is required — see `scripts/validate_data.py`)

### 4. Fix salary data
`data/salary_ranges.json` — only update with a citable source (link required).

## Validation (run before you submit)

```bash
# Question banks: duplicates, missing fields, answer ranges
python scripts/validate_questions.py

# All data files: provenance fields, freshness
python scripts/validate_data.py
```

Both must report **0 errors** before your PR is merged. CI runs them automatically.

## How to submit

1. Fork the repo, create a branch: `data/fix-aptitude-typo`
2. Edit the JSON/CSV file directly (any text editor works)
3. Run the validation scripts above
4. Open a PR using the **Data contribution** template
5. A maintainer reviews for correctness and licensing

## Review checklist (for maintainers)

- [ ] Validation scripts pass (`validate_questions.py`, `validate_data.py`)
- [ ] No verbatim copies from copyrighted assessments
- [ ] No unverifiable "asked at <Company>" claims
- [ ] Answer indices correct (spot-check 3-5)
- [ ] Provenance fields present for new data (`source_url`, `retrieved_at`)
- [ ] Explanations are clear and correct

## Questions?

Open a [data issue](https://github.com/Vivek492005/AI-Career-Research-Assistant-Resume-Analysis-Job-Recommendation-Research-Paper-Intelligence-Platform/issues/new?template=data.yml)
or ask in Discussions. Data PRs are reviewed within a week.
