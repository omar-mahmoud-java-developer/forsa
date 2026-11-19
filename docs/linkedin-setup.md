# LinkedIn setup

> Automating LinkedIn may violate its Terms of Service. Read the [disclaimer](../DISCLAIMER.md). Prefer a secondary
> account, `dry_run: true` and low limits.

1. `pip install "forsa[linkedin] @ git+https://github.com/omar-mahmoud-java-developer/forsa.git"` (Python 3.12.4+; or `pip install "forsa[linkedin]"` from PyPI after release). This installs the MCP client and the pinned
   `mcp-server-linkedin==4.29.0`.
2. `forsa login`: a browser opens; **you** sign in. The session is stored in `sessions/` (git-ignored).
3. `forsa login --status` and `forsa doctor` should be green.
4. Add `"linkedin"` to `sources.enabled`.
5. Reset anytime: `forsa reset-session`, then log in again.

If the server cannot start, `doctor` falls back to read-only public pages (Jina) and prints the fix.

Easy Apply (experimental): `pip install "forsa[apply] @ git+https://github.com/omar-mahmoud-java-developer/forsa.git"`, `patchright install chromium`,
`forsa login --apply-browser`, then set `auto_apply` and `dry_run` yourself. It uses its own browser profile and
never reads cookies from other tools.
