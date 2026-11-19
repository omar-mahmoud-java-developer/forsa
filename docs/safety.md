# Safety model

- Defaults: `dry_run: true`, `auto_apply` / `auto_connect` / `send_emails`: false. A CLI flag can never turn dry-run off.
- Per-day caps, per-job attempt cap (stored permanently), random delays between actions, circuit breaker.
- Application answers come only from `profile.md`; unknown required answers skip the job and flag it.
- Nothing is sent to employers: only drafts. The digest goes only to your own address and only if enabled.
- LLM calls have no tools. Untrusted text is fenced and only used to write drafts/advice; output is validated.
- The Coach only suggests; it refuses `safety.*` and any key outside the search/scoring lists; it never commits.
- Secrets only in `.env`; sessions only in `sessions/`; both are git-ignored. `job-radar privacy-check` scans your
  folder for personal data before you share it.
