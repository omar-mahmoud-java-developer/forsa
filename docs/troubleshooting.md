# Troubleshooting

Start with `job-radar doctor`: every problem comes with a fix line.

| Symptom | Fix |
|---|---|
| `config file not found` | run `job-radar init` in your project folder (or set `JOB_RADAR_HOME`) |
| `unknown config key` | a typo in `config.json`; the message names the key |
| `linkedin [jina]` warning | install `[linkedin]`, Python 3.12.4+, then `job-radar login` |
| Jobs found but nothing scores | lower `scoring.thresholds.best` / add your words to `scoring.skills` |
| A job keeps being skipped | the digest lists the missing answer; add it with `job-radar answer` |
| Email not sent | needs `notify.mode: email`, `safety.send_emails: true`, `dry_run: false`, and `.env` credentials |
| Session expired | `job-radar reset-session`, then `job-radar login` |
