# Data Inventory (PRIV-01)

Every table/column holding personal data, its purpose, and retention.
Generated 2026-10-18. Retention defaults per roadmap DECISION D-3 recommendation.

## User identity

| Table | Personal columns | Purpose | Retention |
|-------|-----------------|---------|-----------|
| `user` | `email`, `name`, `password_hash`, `github_username`, `leetcode_username`, `linkedin_url` | Account identity + linked profiles | Until account deletion |
| `user` | `created_at`, `last_login` | Security / activity | Until account deletion |

## Resume & career data

| Table | Personal columns | Purpose | Retention |
|-------|-----------------|---------|-----------|
| `resume_analysis` | `resume_text`, `filename`, `analysis_json` | Resume feedback | 90 days inactivity unless saved |
| `resume_version` | `content`, `label` | Version history | Until user deletes |
| `jd_match_report` | `jd_text`, `resume_text`, `report_json` | JD matching | 90 days inactivity |
| `bullet_rewrite` | `original`, `rewritten` | Bullet improvements | 90 days inactivity |
| `cover_doc` | `content` | Cover letters | Until user deletes |
| `linkedin_report` | `profile_text`, `report_json` | LinkedIn optimization | 90 days inactivity |
| `job_application` | All columns | Application tracking | Until user deletes |

## Learning & practice

| Table | Personal columns | Purpose | Retention |
|-------|-----------------|---------|-----------|
| `interview_session` | `transcript`, `feedback` | Mock interviews | 90 days inactivity |
| `communication_analysis` | `text`, `analysis` | Communication coach | 90 days inactivity |
| `dsa_progress` | `code_submissions` | DSA practice | Until user deletes |
| `aptitude_attempt` | `answers_json` | Aptitude tests | 90 days inactivity |
| `quiz_attempt` | `answers_json` | Quizzes | 90 days inactivity |
| `star_draft` | `content` | STAR stories | Until user deletes |
| `roadmap_progress` | `progress_json` | Learning roadmaps | Until user deletes |
| `career_assessment` | `answers_json`, `result_json` | Assessments | 90 days inactivity |
| `retrospective` | `content` | Weekly retros | Until user deletes |
| `cert_plan` | `plan_json` | Certification plans | Until user deletes |
| `study_doc` | `content` | Study documents | Until user deletes |
| `experiment` | `config_json`, `results_json` | Lab experiments | 90 days inactivity |

## Community & social

| Table | Personal columns | Purpose | Retention |
|-------|-----------------|---------|-----------|
| Peer feedback tables | `feedback_text`, `author_id` | Peer mocks | Until user deletes |
| Mentor applications | `application_text` | Mentorship | Until user deletes |

## Uploaded files

Raw uploaded files (PDF/DOCX) are **deleted immediately after parsing**
(SEC-08). Only extracted text is retained per the table above.

## Third parties receiving personal data

| Recipient | Data shared | Purpose |
|-----------|-------------|---------|
| LLM providers (Gemini/Groq/OpenRouter) | Resume text, prompts | AI features (only when user triggers) |
| GitHub API | `github_username` | Profile enrichment (user-opted) |

LLM prompts/responses are **not stored** by default. Logs contain no payloads (ARC-08).

## Deletion

`/account/delete` hard-deletes the user and all cascade-related rows.
`/account/export` returns all of the above as JSON. See PRIV-02.
