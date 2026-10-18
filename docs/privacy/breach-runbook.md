# Breach Runbook (PRIV-07)

What to do when personal data may have been exposed. Follow in order.
Time matters — the DPDP Act requires notifying affected users and the
Data Protection Board promptly once the rules are in force.

## 1. Detect (0–1 hour)

**Signals:** unusual access logs, user reports, security scanner alerts,
CSP violation spikes, failed-login surges.

- Confirm: is personal data actually involved? Which tables/columns?
- Scope: how many users? What data types (email, resume text, etc.)?
- Preserve evidence: snapshot logs, do NOT delete anything yet.

## 2. Contain (1–4 hours)

- Revoke compromised credentials immediately (Render dashboard → rotate).
- If an endpoint is leaking data: feature-flag it off (`FEATURE_LABS=0`)
  or take the service to maintenance mode.
- Block attacker IPs at the Render firewall / Cloudflare if applicable.
- Do NOT notify users yet — first understand the scope.

## 3. Assess (4–24 hours)

- Exactly what data left the system? (Use access logs with hashed user ids.)
- Was it encrypted in transit? At rest?
- Could it cause harm? (Resume text + email = phishing risk.)
- Document everything in `docs/privacy/incidents/YYYY-MM-DD.md` (private).

## 4. Notify (within 72 hours)

- **Affected users:** email describing what happened, what data was
  involved, what we're doing, and what they should do.
- **Data Protection Board:** as per DPDP Rule 7 (once in force).
- **Grievance contact:** privacy@studybuddy (set up before launch).

## 5. Recover & learn (1–2 weeks)

- Root-cause fix + regression test (the "1000% quality, 0% error" rule).
- Rotate all potentially exposed secrets.
- Post-mortem: update this runbook with lessons learned.
- If user data was affected: offer free credit-monitoring guidance.

## Contacts

| Role | Contact |
|------|---------|
| Grievance officer | privacy@studybuddy (TODO: assign human) |
| Hosting (Render) | Render dashboard → Support |
| AI providers | Google Cloud / Groq / OpenRouter status pages |

*This is an operational guide, not legal advice. Have a lawyer review
before relying on it for compliance.*
