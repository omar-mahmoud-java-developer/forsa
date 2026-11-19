# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""A tiny local MCP server (synthetic data) used to test the real MCP client end to end."""
import json

from mcp.server.mcpserver import MCPServer

app = MCPServer("fake-linkedin")


@app.tool()
def search_jobs(keywords: str = "", location: str = "", date_posted: str = "", max_pages: int = 1) -> str:
    return json.dumps({"references": {"r": [{"kind": "job", "url": "/jobs/view/900/", "text": f"{keywords} Engineer"}]}})


@app.tool()
def get_job_details(job_id: str) -> str:
    return json.dumps({"sections": {"m": "Fake Co\nBackend Engineer\nBerlin, Germany · 1 day ago\nEasy Apply\n"
                                         "About the job\nPython. 2 years of experience."}})


@app.tool()
def boom() -> str:
    raise RuntimeError("tool failure")


if __name__ == "__main__":
    app.run("stdio")
