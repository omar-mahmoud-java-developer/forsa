# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Talks to the LinkedIn MCP server directly with the official Python MCP client (no Node, no mcporter).

One server process and one session per run. Every call goes through retry, timeout and the circuit breaker.
The server is the pinned `mcp-server-linkedin==4.29.0`; the user signs in through ITS login flow
(`job-radar login`). No password or cookie ever passes through this code.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import shutil
import sys
import threading
from pathlib import Path
from typing import Any

from ..retry import CircuitBreaker, RetryPolicy, call_with_retry

SERVER_PIN = "mcp-server-linkedin==4.29.0"


class McpUnavailable(RuntimeError):
    """The MCP client library or the server is not installed / not startable."""


def server_command(sessions_dir: Path) -> tuple[str, list[str]]:
    """Command that starts the pinned server with sessions stored under our gitignored folder."""
    user_dir = str(sessions_dir / "linkedin")
    exe = shutil.which("mcp-server-linkedin")
    if exe:
        return exe, ["--user-data-dir", user_dir]
    uvx = shutil.which("uvx")
    if uvx:
        return uvx, [SERVER_PIN, "--user-data-dir", user_dir]
    raise McpUnavailable("neither 'mcp-server-linkedin' nor 'uvx' found; install: pip install 'job-radar-agent[linkedin]'")


def login_command(sessions_dir: Path) -> list[str]:
    exe, args = server_command(sessions_dir)
    return [exe, *args, "--login"]


class McpSession:
    """Synchronous wrapper over one stdio MCP session.

    The async MCP client uses anyio cancel scopes, which must be entered and exited in the SAME task. So the
    whole session lives in one long-lived task on a background event loop; calls are sent to it through a queue.
    """

    def __init__(self, command: str, args: list[str], timeout: float = 420.0, policy: RetryPolicy | None = None,
                 breaker: CircuitBreaker | None = None):
        self.command, self.args, self.timeout = command, args, timeout
        self.policy = policy or RetryPolicy(attempts=2, base_delay=3.0)
        self.breaker = breaker or CircuitBreaker(3)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._queue: asyncio.Queue | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def __enter__(self) -> McpSession:
        try:
            import mcp  # noqa: F401, PLC0415
        except ImportError as ex:
            raise McpUnavailable("MCP client missing: pip install 'job-radar-agent[linkedin]'") from ex
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="mcp-session")
        self._thread.start()
        if not self._ready.wait(150):
            raise McpUnavailable("the LinkedIn MCP server did not start within 150 seconds")
        if self._startup_error is not None:
            raise McpUnavailable(f"cannot start the LinkedIn MCP server: {self._startup_error}") from self._startup_error
        return self

    def __exit__(self, *exc) -> None:
        if self._loop and self._queue is not None:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
        if self._thread:
            self._thread.join(timeout=30)

    # ---- background loop
    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._session_task())
        finally:
            self._ready.set()
            self._loop.close()

    async def _session_task(self) -> None:
        from mcp import ClientSession, StdioServerParameters  # noqa: PLC0415
        from mcp.client.stdio import stdio_client  # noqa: PLC0415

        self._queue = asyncio.Queue()
        try:
            params = StdioServerParameters(command=self.command, args=self.args)
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), 120)
                self._ready.set()
                while True:
                    item = await self._queue.get()
                    if item is None:
                        return
                    fn, fut = item
                    try:
                        fut.set_result(await fn(session))
                    except BaseException as ex:  # noqa: BLE001 - delivered to the caller
                        fut.set_exception(ex)
        except BaseException as ex:  # noqa: BLE001
            if not self._ready.is_set():
                self._startup_error = ex
            self._ready.set()

    def _submit(self, fn):
        assert self._loop is not None and self._queue is not None
        done: concurrent.futures.Future = concurrent.futures.Future()
        inner: asyncio.Future = self._loop.create_future()

        def relay(f):
            exc = f.exception()
            done.set_exception(exc) if exc else done.set_result(f.result())

        inner.add_done_callback(relay)
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (fn, inner))
        return done.result(timeout=self.timeout)

    # ---- API
    def list_tools(self) -> list[str]:
        async def go(session):
            return await session.list_tools()
        return [t.name for t in self._submit(go).tools]

    def call(self, tool: str, **arguments: Any) -> Any:
        """Call a tool; returns parsed JSON when the text is JSON, else the text. Raises after retries."""
        args = {k: v for k, v in arguments.items() if v not in (None, "")}

        async def go(session):
            return await session.call_tool(tool, args)

        def once():
            res = self._submit(go)
            text = "".join(getattr(c, "text", "") for c in res.content)
            if getattr(res, "is_error", False) or getattr(res, "isError", False):  # mcp 2.x / 1.x field names
                raise RuntimeError(f"{tool} failed: {text[:200]}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        try:
            out = call_with_retry(once, self.policy)
        except Exception:
            self.breaker.fail()  # raises CircuitOpen after N failures in a row
            raise
        self.breaker.ok()
        return out


def python_ok() -> bool:
    """The pinned server needs Python >= 3.12.4."""
    return sys.version_info >= (3, 12, 4)
