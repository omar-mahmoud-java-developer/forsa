---
name: forsa
description: >
  Set up and run Forsa, a self-hosted job-search CLI: find jobs, score them against the user's profile,
  draft cover letters and summarise results. Use when the user wants to search for jobs, tune job filters or schedule a
  job search. Always dry-run first; never changes safety settings or sends anything unless the user explicitly asks;
  never asks for passwords.
---
# Forsa

Install and setup steps: see `docs/install.md`. Core commands: `forsa doctor`, `forsa run --dry-run`,
`forsa status`, `forsa answer "question" "answer"`, `forsa coach`.

Rules for agents: keep `safety.dry_run` true, never enable `auto_apply`, `auto_connect`, `send_emails`, `mailbox`, `search.recruiters` or email notifications on your own,
never invent profile facts, never read or copy `.env`, `sessions/` or `profile.md` into chats or commits.
