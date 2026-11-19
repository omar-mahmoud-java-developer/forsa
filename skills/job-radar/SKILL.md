---
name: job-radar
description: >
  Set up and run Job Radar Agent, a self-hosted job-search CLI: find jobs, score them against the user's profile,
  draft cover letters and summarise results. Use when the user wants to search for jobs, tune job filters or schedule a
  job search. Always dry-run first; never changes safety settings or sends anything unless the user explicitly asks;
  never asks for passwords.
---
# Job Radar Agent

Install and setup steps: see `docs/install.md`. Core commands: `job-radar doctor`, `job-radar run --dry-run`,
`job-radar status`, `job-radar answer "question" "answer"`, `job-radar coach`.

Rules for agents: keep `safety.dry_run` true, never enable `auto_apply`, `auto_connect` or `send_emails` on your own,
never invent profile facts, never read or copy `.env`, `sessions/` or `profile.md` into chats or commits.
