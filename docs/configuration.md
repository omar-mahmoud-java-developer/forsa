# Configuration

Unknown keys are errors (typos never pass silently). Secrets never go in `config.json`.

## config.json
See `config.example.json`. Sections: `safety`, `search`, `scoring`, `schedule`, `language`, `sources`, `llm`,
`notify`, `paths`. The full reference table is in the README.

Recipes:
- **Any role:** set `search.titles`, `search.keywords`, and put your own words in `scoring.skills`
  (`{"icu": 10, "patient care": 6}`). A skill starting with `re:` is a regex.
- **Any country:** list places in `search.locations`; add `remote` in `work_modes` for remote roles.
- **Seniority:** `search.seniority.max_years` is the most years of experience a job may ask for before it is penalised.
- **Strictness:** raise `scoring.thresholds.best`; lower `apply_min` only if you accept more automatic applications.

## Email digest, mailbox, recruiters, dashboard
- **Digest to yourself:** `"notify": {"mode": "email", "email_to": "you@yourdomain"}` + `JOB_RADAR_SMTP_*` in `.env`.
- **Track applications from email:** `"mailbox": {"enabled": true}` + `JOB_RADAR_IMAP_*` in `.env`. Reads job alerts and
  "application viewed / not moving forward" emails (read-only) into the tracker. `job-radar applications`, `job-radar track`.
- **Recruiters:** `"search": {"recruiters": {"enabled": true, "keywords": ["technical recruiter"]}}` (LinkedIn source).
  `job-radar people` lists them; they are only contacted if you also enable `auto_connect` and go live.
- **Dashboard:** rebuilt every run: open `output/dashboard.html` (or `job-radar dashboard`).

## .env
`JOB_RADAR_SMTP_USER`, `JOB_RADAR_SMTP_PASSWORD` (digest to yourself), `ANTHROPIC_API_KEY` (LLM). Real environment
variables win over `.env`.

## profile.md
```
name: ...                       # header lines: key: value
email: ...   phone: ...   location: ...   linkedin_url: ...
years_experience: 5   notice_period: 30 days   salary_expectation: ...
work_authorization: Yes   requires_sponsorship: No   open_to_relocation: No
## Summary                      # free text used in cover-letter drafts
## Skills                       # - skill: years
## Answers                      # - part of a question: answer
```
Answers match when the key appears inside the question text (longest key wins). Years questions use `## Skills`.
Missing information is never guessed: the job is skipped and flagged in the digest.

## Templates
`job-radar templates` copies the defaults (cover letter, outreach, digest, prompts) into `./templates/`; your copies
win. Placeholders look like `{name}`, `{role}`, `{company}`. A template with a missing value fails loudly.
