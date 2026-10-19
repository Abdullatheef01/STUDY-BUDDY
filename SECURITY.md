# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| main    | ✅        |

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

Instead, email the maintainer privately or use GitHub's private
vulnerability reporting (Security → Report a vulnerability).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

We aim to acknowledge reports within 48 hours and ship a fix as soon as
possible. We follow coordinated disclosure: we will not publish details
until a fix is available.

## Scope

In scope: authentication bypass, injection (XSS/SQL/command), SSRF,
insecure file handling, secret exposure, privilege escalation.

Out of scope: spam, social engineering, physical attacks, issues in
third-party dependencies without a demonstrated exploit path in this app
(report those upstream).

## Security practices in this repo

- Dependencies are hash-pinned (`requirements.txt`) and audited in CI
  (`pip-audit`, `bandit`).
- Secrets are never committed; see `.env.example` for required variables.
- See `docs/privacy/breach-runbook.md` for incident response.
