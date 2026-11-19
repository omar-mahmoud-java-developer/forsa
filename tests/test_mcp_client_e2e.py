# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")  # provided by the [linkedin] extra

from job_radar.providers.linkedin import LinkedInProvider  # noqa: E402
from job_radar.reach.mcp_client import McpSession, McpUnavailable  # noqa: E402
from job_radar.retry import CircuitBreaker, CircuitOpen, RetryPolicy  # noqa: E402

SERVER = str(Path(__file__).with_name("fake_mcp_server.py"))


def session(**kw):
    return McpSession(sys.executable, [SERVER], timeout=60, policy=RetryPolicy(1, 0), **kw)


def test_real_client_against_local_server():
    with session() as s:
        assert {"search_jobs", "get_job_details"} <= set(s.list_tools())
        res = s.call("search_jobs", keywords="Backend", location="")
        assert res["references"]["r"][0]["url"] == "/jobs/view/900/"


def test_provider_over_real_client(cfg):
    p = LinkedInProvider(session_factory=session)
    jobs = p.search(cfg["search"])
    assert jobs and jobs[0].id == "900"
    assert p.details(jobs[0]).company == "Fake Co"
    p.close()


def test_tool_error_opens_circuit_breaker():
    with session(breaker=CircuitBreaker(2)) as s:
        with pytest.raises(RuntimeError):
            s.call("boom")
        with pytest.raises(CircuitOpen):
            s.call("boom")


def test_missing_server_is_reported():
    with pytest.raises(McpUnavailable):
        with McpSession("definitely-not-a-binary", [], timeout=10):
            pass
