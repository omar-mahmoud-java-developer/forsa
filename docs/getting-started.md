# Getting started

You need Python 3.11+ (3.12.4+ for the LinkedIn source). Windows, macOS and Linux are supported.

## 1. Install
```bash
pipx install "job-radar-agent[linkedin]"        # or: pip install "job-radar-agent[linkedin]"
```
From a clone: `pip install -e ".[dev]"`. Extras: `[linkedin]` (MCP client + pinned server), `[llm]` (Anthropic API),
`[apply]` (experimental Easy Apply browser).

## 2. Create your folder and answer the setup questions
```bash
mkdir my-job-search && cd my-job-search
job-radar init
```
It asks for your target titles, skills, locations, work modes and seniority, then writes **`config.json`**,
**`profile.md`** and **`.env`** (all git-ignored) and runs `doctor`. `job-radar init --yes` keeps the fake example
values so you can try everything without any account.

## 3. Tell it who you are (`profile.md`)
Edit `profile.md`: contact details, `years_experience`, skills with years, and ready answers. It is the **only**
source for application answers; anything it does not say is skipped and flagged.
See [configuration](configuration.md#profilemd).

## 4. Try a dry run
```bash
job-radar run --dry-run
```
Open `output/digest.html`. Nothing was sent, applied or connected. Drafts are in `output/drafts/`.

## 5. Use real sources
- **RSS/Atom feeds** (any board that offers one):
  `"sources": {"enabled": ["rss"], "rss": {"feeds": [{"name": "Board", "url": "https://..."}]}}`
- **LinkedIn**: add `"linkedin"` to `sources.enabled`, run `job-radar login`, sign in in the browser window yourself,
  then `job-radar doctor`. See [LinkedIn setup](linkedin-setup.md) and read the [disclaimer](../DISCLAIMER.md).
- **Your own source**: `job-radar new-provider myboard` ([adding sources](adding-sources.md)).

## 6. Review, then (optionally) go live
Read several dry-run digests first. Only when you trust them, change the safety switches **by hand** in
`config.json` (`dry_run`, `auto_apply`, `auto_connect`, `send_emails`) and keep the limits low.
`job-radar answer "question" "answer"` teaches the profile new answers. `job-radar coach` suggests improvements.

## 7. Schedule it
`job-radar schedule cron|systemd|windows` prints ready snippets with your paths and times.

## Daily commands
`run --dry-run` · `status` · `digest` · `answer` · `coach` · `doctor` · `eval` · `providers` · `templates` ·
`privacy-check`
