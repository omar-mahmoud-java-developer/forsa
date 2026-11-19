# Security policy

## Reporting a vulnerability
Please report privately through GitHub "Report a vulnerability" (Security tab) on this repository
instead of opening a public issue. Include steps to reproduce. You will get an answer within a week.

## Never commit credentials or sessions
- Secrets live only in `.env` (git-ignored). `.env.example` has placeholders only.
- LinkedIn sessions live only in `sessions/` (git-ignored). Reset them with `job-radar reset-session`.
- Never paste cookies, app passwords, API keys or your `profile.md` in an issue. If you committed one by
  mistake, revoke it first, then rewrite history.
- CI runs gitleaks on every push and pull request.

## Design rules that protect you
- No LinkedIn password is stored or typed into this tool; you sign in through the MCP server's own flow.
- LLM steps have no tools; untrusted text (job descriptions, pages) is fenced and never reaches an action.
- Mailbox access is opt-in, read-only, limited to authenticated allow-listed senders and parsed without an LLM; recruiter
  data is minimal, local and auto-expiring.
- The Coach can only suggest changes, never to safety settings, and never commits.
