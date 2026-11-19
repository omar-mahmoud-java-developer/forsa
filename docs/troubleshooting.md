# Troubleshooting

Start with `forsa doctor`: every problem comes with a fix line.

| Symptom | Fix |
|---|---|
| `config file not found` | run `forsa init` in your project folder (or set `FORSA_HOME`) |
| `unknown config key` | a typo in `config.json`; the message names the key |
| `linkedin [jina]` warning | install `[linkedin]`, Python 3.12.4+, then `forsa login` |
| Jobs found but nothing scores | lower `scoring.thresholds.best` / add your words to `scoring.skills` |
| A job keeps being skipped | the digest lists the missing answer; add it with `forsa answer` |
| Digest email not arriving | set `notify.mode: email`, `notify.email_to`, and `FORSA_SMTP_USER` / `FORSA_SMTP_PASSWORD` in `.env` (works in dry-run too; it only ever goes to `notify.email_to`) |
| Mailbox step skipped/failed | set `mailbox.enabled: true` and `FORSA_IMAP_USER` / `FORSA_IMAP_PASSWORD` (or the SMTP ones); run `forsa doctor` |
| Session expired | `forsa reset-session`, then `forsa login` |
