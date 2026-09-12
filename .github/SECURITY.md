# Security Policy

## Supported Versions

This project is continuously deployed, not version-pinned for end users —
there is no separate LTS/maintenance branch. Only the code currently on
`master` (and what's running in production) is supported. If you're running a
fork or an older checkout, please update to `master` before reporting an issue.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

This app handles user authentication (NextAuth JWTs, guest tokens), stores
scraped/analyzed content and LLM provider credentials, and proxies requests to
several third-party LLM APIs — a public issue could expose an exploitable gap
before it's fixed.

Instead, report it privately by emailing **s091648@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce it (a minimal repro is very helpful)
- Any relevant logs, request/response samples, or affected endpoint(s)/file(s)

You can expect an acknowledgment within a few days. This is a solo-maintained
side project, so response and fix times are best-effort, not SLA-backed — but
security reports get priority over regular issues/PRs.

If the report is confirmed, a fix will be prepared and deployed before any
public disclosure or write-up. Credit is given in the fix's release notes if
you'd like it (just say so in your report) — anonymous reports are equally
welcome.

## Scope

Roughly, "in scope" means anything that could compromise:

- User accounts, auth tokens (JWT/guest-token), or admin access
  (`backend/auth/guards.py`, `require_admin`/`require_user`/`require_any_token`)
- The production database or its credentials
- Other users' data (e.g. one account reading/modifying another's)
- The LLM provider API keys or the ability to make the app spend LLM budget
  on an attacker's behalf
- The CI/CD pipeline or infrastructure config (`infra/terraform/github/`,
  `.railway/`)

Low-severity issues (e.g. best-practice suggestions with no demonstrated
impact, or findings that only apply to a local dev setup with default/example
credentials) are welcome as a regular GitHub issue instead — see
[CONTRIBUTING.md](./CONTRIBUTING.md).
