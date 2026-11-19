# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Agent Eyes
# Derived from Agent Reach v1.5.0 (https://github.com/Panniantong/Agent-Reach),
# upstream commit f65526cbaaad3879473acc1ba6dbefd195caf2be, file agent_reach/channels/web.py.
# Modifications Copyright (c) 2026 Omar Qenawy: translated to English, added a public-URL
# check, a response size cap and an anti-bot page check; read-only by design.
"""Jina Reader: read-only fallback for PUBLIC pages (no login, no actions)."""

from __future__ import annotations

import ipaddress
import urllib.request
from urllib.parse import urlsplit

from .base import Channel

_UA = "forsa (+read-only public page fetch)"
MAX_BYTES = 2 * 1024 * 1024


def public_url(url: str) -> str:
    """Normalize to https and refuse anything that is not clearly a public http(s) host."""
    u = (url or "").strip()
    if not u or any(c.isspace() for c in u):
        raise ValueError("only public HTTP(S) URLs are allowed")
    if "://" not in u:
        u = "https://" + u
    p = urlsplit(u)
    host = (p.hostname or "").lower().rstrip(".")
    if p.scheme not in ("http", "https") or not host or p.username or p.password:
        raise ValueError("only public HTTP(S) URLs are allowed")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("only public HTTP(S) URLs are allowed")
    except ValueError as ex:
        if "public" in str(ex):
            raise
        if "." not in host or host.endswith((".local", ".internal", ".lan", ".localhost")):
            raise ValueError("only public HTTP(S) URLs are allowed") from None
    return u


def looks_blocked(body: bytes) -> bool:
    sample = body[:4096].decode("utf-8", "replace").lower()
    return ("requiring captcha" in sample and "warning:" in sample) or "just a moment" in sample and "cloudflare" in sample


class WebChannel(Channel):
    name = "web"
    description = "Any public web page"
    backends = ["Jina Reader"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return True  # fallback: handles any URL

    def check(self, config=None):
        self.active_backend = self.backends[0]
        return "ok", "Reads public pages through Jina Reader (https://r.jina.ai/URL). No network probe in doctor."

    def read(self, url: str, opener=urllib.request.urlopen) -> str:
        """Markdown text of a public page."""
        jina_url = f"https://r.jina.ai/{public_url(url)}"
        req = urllib.request.Request(jina_url, headers={"User-Agent": _UA, "Accept": "text/plain"})
        with opener(req, timeout=30) as resp:
            body = resp.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Jina Reader response is too large")
        if looks_blocked(body):
            raise RuntimeError("Jina Reader returned an anti-bot page; no content was fetched")
        return body.decode("utf-8", "replace")
