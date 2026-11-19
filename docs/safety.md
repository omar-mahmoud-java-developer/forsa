# Safety model

- Defaults: `dry_run: true`, `auto_apply` / `auto_connect` / `send_emails`: false. A CLI flag can never turn dry-run off.
- Per-day caps, per-job attempt cap (stored permanently), random delays between actions, circuit breaker.
- Application answers come only from `profile.md`; unknown required answers skip the job and flag it.
- Nothing is sent to employers: only drafts. The digest email goes **only** to `notify.email_to` (yourself) and only when
  `notify.mode` is `email`; it works in dry-run too. `safety.send_emails` is reserved for employer-facing mail and stays false.
- **Mailbox (opt-in, `mailbox.enabled`)**: read-only IMAP (`readonly` select, `BODY.PEEK`), only allow-listed sender domains,
  only messages that passed SPF/DKIM, regex parsing only (no LLM reads email), no email can trigger an action, nothing
  from the body is stored (company, role, status only). Use an app password of a dedicated mailbox.
- **Recruiter search (opt-in, `search.recruiters.enabled`)**: read-only; stores only public basics locally, deleted after
  `keep_days`; `forsa people purge --all` deletes everything; connecting needs `auto_connect`, `dry_run: false` and the daily cap.
- **Dashboard**: a static local file (`output/dashboard.html`): no server, no scripts from outside, strict CSP, all text escaped.
- LLM calls have no tools. Untrusted text is fenced and only used to write drafts/advice; output is validated.
- The Coach only suggests; it refuses `safety.*` and any key outside the search/scoring lists; it never commits.
- Secrets only in `.env`; sessions only in `sessions/`; both are git-ignored. `forsa privacy-check` scans your
  folder for personal data before you share it.
