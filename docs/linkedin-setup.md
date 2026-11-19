# LinkedIn setup

> Automating LinkedIn may violate its Terms of Service. Read the [disclaimer](../DISCLAIMER.md). Prefer a secondary
> account, `dry_run: true` and low limits.

1. `pip install "job-radar-agent[linkedin]"` (Python 3.12.4+). This installs the MCP client and the pinned
   `mcp-server-linkedin==4.29.0`.
2. `job-radar login`: a browser opens; **you** sign in. The session is stored in `sessions/` (git-ignored).
3. `job-radar login --status` and `job-radar doctor` should be green.
4. Add `"linkedin"` to `sources.enabled`.
5. Reset anytime: `job-radar reset-session`, then log in again.

If the server cannot start, `doctor` falls back to read-only public pages (Jina) and prints the fix.

Easy Apply (experimental): `pip install "job-radar-agent[apply]"`, `patchright install chromium`,
`job-radar login --apply-browser`, then set `auto_apply` and `dry_run` yourself. It uses its own browser profile and
never reads cookies from other tools.
