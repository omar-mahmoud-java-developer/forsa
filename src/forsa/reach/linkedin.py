# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""LinkedIn channel: MCP backend first, read-only Jina Reader fallback for public pages.

Unlike the original Agent Reach check (which only read a config file), `check()` really starts the pinned
server and verifies the session.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .base import Channel
from .mcp_client import McpSession, McpUnavailable, python_ok, server_command
from .web import WebChannel

log = logging.getLogger("forsa.reach")


class LinkedInChannel(Channel):
    name = "linkedin"
    description = "LinkedIn (jobs, people, posts)"
    backends = ["mcp", "jina"]
    tier = 2

    def __init__(self, sessions_dir: Path | None = None, backend_order: list[str] | None = None):
        self.sessions_dir = sessions_dir or Path("sessions")
        self.backend_order = backend_order or list(self.backends)
        self.web = WebChannel()
        self.used: list[str] = []  # backend actually used by each call, for the log/digest

    def can_handle(self, url: str) -> bool:
        return "linkedin.com" in url

    def ordered_backends(self, config=None):
        order = [b for b in self.backend_order if b in self.backends]
        return order + [b for b in self.backends if b not in order]

    # ---- health
    def check(self, config=None):
        self.active_backend = None
        if not python_ok():
            self.active_backend = "jina"
            return "warn", ("The LinkedIn MCP server needs Python >= 3.12.4; only read-only public pages work "
                            "(Jina). Fix: install Python 3.12.4+ and reinstall.")
        try:
            cmd, args = server_command(self.sessions_dir)
        except McpUnavailable as ex:
            self.active_backend = "jina"
            return "warn", f"{ex}. Falling back to read-only public pages (Jina)."
        try:
            with McpSession(cmd, args, timeout=60) as s:
                tools = s.list_tools()
                if "search_jobs" not in tools:
                    return "error", f"server started but has no 'search_jobs' tool (found: {', '.join(tools)[:120]})"
        except Exception as ex:  # noqa: BLE001 - doctor must survive anything
            self.active_backend = "jina"
            return "error", (f"cannot start the LinkedIn MCP server: {str(ex)[:140]}. "
                             f"Fix: run `forsa login`, then `forsa doctor`.")
        self.active_backend = "mcp"
        return "ok", "MCP server starts and lists its tools (sign-in is checked by `forsa login --status`)"

    # ---- reads
    def public_page(self, url: str) -> str:
        self.used.append("jina")
        log.info("backend=jina url=%s", url)
        return self.web.read(url)

    def have_uvx(self) -> bool:
        return shutil.which("uvx") is not None
