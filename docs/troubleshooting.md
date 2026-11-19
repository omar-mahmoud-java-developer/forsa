# Troubleshooting

Start with `job-radar doctor`: every problem comes with a fix line.

| Symptom | Fix |
|---|---|
| `config file not found` | run `job-radar init` in your project folder (or set `JOB_RADAR_HOME`) |
| `unknown config key` | a typo in `config.json`; the message names the key |
| `linkedin [jina]` warning | install `[linkedin]`, Python 3.12.4+, then `job-radar login` |
| Jobs found but nothing scores | lower `scoring.thresholds.best` / add your words to `scoring.skills` |
| A job keeps being skipped | the digest lists the missing answer; add it with `job-radar answer` |
| Digest email not arriving | set `notify.mode: email`, `notify.email_to`, and `JOB_RADAR_SMTP_USER` / `JOB_RADAR_SMTP_PASSWORD` in `.env` (works in dry-run too; it only ever goes to `notify.email_to`) |
| Mailbox step skipped/failed | set `mailbox.enabled: true` and `JOB_RADAR_IMAP_USER` / `JOB_RADAR_IMAP_PASSWORD` (or the SMTP ones); run `job-radar doctor` |
| Session expired | `job-radar reset-session`, then `job-radar login` |
