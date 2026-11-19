# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""RSS/Atom job feeds: a source that works for ANY site that publishes a feed (no login, no scraping)."""

from __future__ import annotations

import hashlib
import html
import re
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405 - feeds are small, fetched over https, size-capped

from ..models import Job
from ..reach.web import public_url
from .base import Provider, register

MAX_BYTES = 2 * 1024 * 1024
UA = "job-radar-agent (+read-only feed reader)"
_TAG = re.compile(r"<[^>]+>")


def _text(el, *names):
    for n in names:
        for child in el:
            if child.tag.split("}")[-1] == n and (child.text or "").strip():
                return child.text.strip()
    return ""


def _link(el) -> str:
    for child in el:
        if child.tag.split("}")[-1] == "link":
            return (child.get("href") or child.text or "").strip()
    return ""


def parse_feed(xml_bytes: bytes, source: str = "rss") -> list[Job]:
    root = ET.fromstring(xml_bytes)  # noqa: S314
    items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    jobs = []
    for it in items:
        title = html.unescape(_text(it, "title"))
        link = _link(it)
        if not title:
            continue
        desc = html.unescape(_TAG.sub(" ", _text(it, "description", "summary", "content")))
        desc = " ".join(desc.split())
        company = _text(it, "company", "author", "creator", "name")
        location = _text(it, "location", "region")
        jid = "rss-" + hashlib.sha1((link or title).encode(), usedforsecurity=False).hexdigest()[:12]
        mode = "remote" if re.search(r"\bremote\b", f"{title} {location} {desc[:300]}", re.I) else ""
        posted = _text(it, "pubDate", "updated", "published")
        jobs.append(Job(jid, source, title, company, location, link, desc, posted, mode))
    return jobs


def fetch(url: str, opener=urllib.request.urlopen) -> bytes:
    headers = {"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, */*"}
    req = urllib.request.Request(public_url(url), headers=headers)
    with opener(req, timeout=30) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("feed is too large")
    return data


@register("rss")
class RssProvider(Provider):
    name = "rss"
    description = "RSS/Atom job feeds listed in sources.rss.feeds"

    def __init__(self, feeds: list | None = None, opener=urllib.request.urlopen):
        self.feeds, self._opener = feeds or [], opener

    def search(self, search_cfg: dict) -> list[Job]:
        if not self.feeds:
            raise ValueError("no feeds configured: add {\"name\": ..., \"url\": ...} to sources.rss.feeds")
        out: dict[str, Job] = {}
        for f in self.feeds:
            for j in parse_feed(fetch(f["url"], self._opener), f.get("name", "rss")):
                out.setdefault(j.id, j)
        return list(out.values())

    def check(self):
        return ("ok", f"{len(self.feeds)} feed(s) configured") if self.feeds else ("warn", "no feeds configured")
