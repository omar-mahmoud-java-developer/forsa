# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""LinkedIn provider (read + optional connect) on top of the reach layer. Fallback: public pages via Jina."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ..models import Job
from ..reach.linkedin import LinkedInChannel
from ..reach.mcp_client import McpSession, McpUnavailable, server_command
from .base import Provider, register

log = logging.getLogger("forsa.linkedin")


def parse_search(result) -> list[Job]:
    """Jobs (id + title) from a search_jobs result: references of kind 'job' with /jobs/view/<id> links."""
    out, seen = [], set()
    refs = (result or {}).get("references", {}) if isinstance(result, dict) else {}
    for group in refs.values():
        for r in group:
            m = re.search(r"/jobs/view/(\d+)", r.get("url", ""))
            if r.get("kind") == "job" and m and m.group(1) not in seen:
                seen.add(m.group(1))
                title = (r.get("text") or "").replace(" with verification", "").strip()
                out.append(Job(m.group(1), "linkedin", title, url=f"https://www.linkedin.com/jobs/view/{m.group(1)}/"))
    return out


def parse_detail(result, job: Job) -> Job:
    """Fill company/location/description/easy_apply from a get_job_details result."""
    secs = (result or {}).get("sections", {}) if isinstance(result, dict) else {}
    text = "\n".join(str(v) for v in secs.values())
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) > 2:
        job.company = job.company or lines[0]
        job.title = job.title or lines[1]
        meta = [p.strip() for p in lines[2].split("·")]
        job.location = job.location or (meta[0] if meta else "")
        job.posted = meta[1] if len(meta) > 1 else job.posted
    a = text.find("About the job")
    job.description = text[a + 13:].strip() if a >= 0 else text
    job.easy_apply = "Easy Apply" in text[:800]
    for w in ("Remote", "Hybrid", "On-site"):
        if f"\n{w}\n" in text[:800]:
            job.work_mode = {"On-site": "onsite"}.get(w, w.lower())
            break
    contact = hiring_contact(result, text)
    if contact:
        job.extra["hiring_contact"] = contact
    return job


def hiring_contact(result, text: str) -> str:
    """Username of the person in "Meet the hiring team" (the job poster), or "" when there is none."""
    h = text.find("Meet the hiring team")
    if h < 0:
        return ""
    block = [ln.strip() for ln in text[h + 20:h + 400].split("\n") if ln.strip()]
    name = block[0] if block else ""
    refs = [r for group in (result.get("references", {}) if isinstance(result, dict) else {}).values() for r in group
            if r.get("kind") == "person" and r.get("context") == "job posting"]
    for r in refs:
        if (r.get("text") or "").strip() == name:
            user = r["url"].strip("/").split("/")[-1]
            return user if re.fullmatch(r"[A-Za-z0-9%_-]{3,100}", user) else ""
    return ""


@register("linkedin")
class LinkedInProvider(Provider):
    name = "linkedin"
    description = "LinkedIn through the pinned MCP server (sign in with `forsa login`)"

    def __init__(self, sessions_dir: Path = Path("sessions"), backend_order: list[str] | None = None,
                 session_factory=None, max_details: int = 15):
        self.channel = LinkedInChannel(sessions_dir, backend_order)
        self.sessions_dir = sessions_dir
        self._factory = session_factory  # tests inject a fake session
        self._session = None
        self.max_details = max_details

    def _open(self):
        if self._session is None:
            if self._factory:
                self._session = self._factory().__enter__()
            else:
                cmd, args = server_command(self.sessions_dir)
                self._session = McpSession(cmd, args).__enter__()
        return self._session

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.call("close_session")
            except Exception:  # noqa: BLE001
                pass
            self._session.__exit__(None, None, None)
            self._session = None

    def check(self):
        return self.channel.check()

    def search(self, search_cfg: dict) -> list[Job]:
        try:
            s = self._open()
        except McpUnavailable as ex:
            log.warning("backend=mcp unavailable (%s); jobs can not be searched without it", ex)
            return []
        window = f"r{int(search_cfg['posted_within_days']) * 86400}"
        jobs: dict[str, Job] = {}
        for kw in search_cfg["titles"] or search_cfg["keywords"]:
            for loc in search_cfg["locations"] or [{"name": ""}]:
                name = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                res = s.call("search_jobs", keywords=kw, location=name, date_posted=window,
                             max_pages=search_cfg["max_pages"])
                self.channel.used.append("mcp")
                log.info("backend=mcp tool=search_jobs keywords=%s", kw)
                for j in parse_search(res):
                    jobs.setdefault(j.id, j)
        return list(jobs.values())

    def details(self, job: Job) -> Job:
        s = self._open()
        res = s.call("get_job_details", job_id=job.id)
        self.channel.used.append("mcp")
        return parse_detail(res, job)

    def search_people(self, keywords: str, location: str = "") -> list[dict]:
        from ..recruiters import parse_people  # noqa: PLC0415

        res = self._open().call("search_people", keywords=keywords, location=location)
        self.channel.used.append("mcp")
        return parse_people(res)

    def connect(self, username: str, note: str | None = None) -> bool:
        res = self._open().call("connect_with_person", linkedin_username=username, note=note)
        text = str(res)[:300]
        return bool(res) and not re.search(r'"error"|failed|unable', text, re.I)
