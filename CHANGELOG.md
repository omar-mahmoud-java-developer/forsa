# Changelog
All notable changes follow [Keep a Changelog](https://keepachangelog.com) and [SemVer](https://semver.org).

## [0.1.0] - Unreleased
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
### Fixed (compared with the private predecessor)
- Easy Apply required-field detection uses attributes, not label text.
- Job state and attempt counts are never pruned or wiped.
