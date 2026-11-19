# Changelog
All notable changes follow [Keep a Changelog](https://keepachangelog.com) and [SemVer](https://semver.org).

## [0.1.0] - 2026-11-19
### Added
- Single CLI: `init`, `doctor`, `run`, `digest`, `coach`, `eval`, `status`, `answer`, `login`, `reset-session`, `schedule`.
- SQLite state store that persists between runs, with a permanent per-job attempt limit.
- Generic scoring from `config.json` and `profile.md` (any role, country or stack).
- Provider interface with `demo` and `linkedin` sources.
- Internal reach layer derived from Agent Reach v1.5.0 (MIT) and a direct MCP client for the pinned
  `mcp-server-linkedin==4.29.0` (no Node, no mcporter). Read-only Jina fallback for public pages.
- Safety defaults: `dry_run`, no auto apply/connect/send, rate limits, caps, profile-only answers.
- Plugin system (`./plugins`, entry points), `rss` provider, `new-provider`, `providers`, `templates`.
- `privacy-check` command and CI step; experimental Easy Apply browser driver (opt-in).
- Docs, agent skill, `llms.txt`, issue/PR templates, DCO check, `tools/set_owner.py`.
- Dashboard (`output/dashboard.html`), application tracker, opt-in read-only mailbox reader, opt-in recruiter search,
  digest e-mail to yourself when configured.
- Judge (LLM second opinion, advice only), hiring-contact extraction from LinkedIn job pages, GHCR image publishing.
### Security
- Pre-release audit: verified TLS for IMAP/SMTP, SSRF-safe fetching, defusedxml, linear-time mail parsing, safe links, path
  confinement, opt-in plugin import, stricter config validation, hardened Docker image and pinned CI actions
  (see docs/security-audit.md).
### Fixed (compared with the private predecessor)
- Easy Apply required-field detection uses attributes, not label text.
- Job state and attempt counts are never pruned or wiped.
