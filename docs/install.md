# Install (for AI agents)

1. Check Python: `python --version` must be 3.11+ (3.12.4+ for LinkedIn).
2. `pipx install "job-radar-agent[linkedin]"` (fallback: `pip install --user ...`).
3. Create a project folder and run `job-radar init --yes`, then `job-radar doctor`.
4. Ask the user for their titles, skills, locations and profile facts, and write them into `config.json` and
   `profile.md`. Never invent profile facts. Never set `dry_run` to false, or `auto_apply`, `auto_connect`,
   `send_emails` to true, or enable `mailbox`, `search.recruiters` or `notify.mode: email`, without the user's explicit
   instruction.
5. Run `job-radar run --dry-run` and show `output/digest.html`.
6. LinkedIn sign-in is done by the user in the browser (`job-radar login`); never ask for or store a password.
