# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Agent Eyes
# Derived from Agent Reach v1.5.0 (https://github.com/Panniantong/Agent-Reach),
# upstream commit f65526cbaaad3879473acc1ba6dbefd195caf2be, file agent_reach/channels/web.py.
# Modifications Copyright (c) 2026 Omar Qenawy: translated to English, added a public-URL
# check, a response size cap and an anti-bot page check; read-only by design.
"""Jina Reader: read-only fallback for PUBLIC pages (no login, no actions)."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import urllib.request
from urllib.parse import urlsplit

from .base import Channel

_UA = "forsa (+read-only public page fetch)"
MAX_BYTES = 2 * 1024 * 1024


def tls_context() -> ssl.SSLContext:
    """A TLS context that VERIFIES certificates and host names (the stdlib default for imaplib/smtplib does not)."""
    return ssl.create_default_context()


def _resolve(host: str) -> list[str]:
    return [ai[4][0] for ai in socket.getaddrinfo(host, None)]


def public_url(url: str, resolve: bool = True) -> str:
    """Normalize to https and refuse anything that is not clearly a public http(s) host.

    With resolve=True the host name is also resolved and EVERY address must be public, so names such as
    127.0.0.1.nip.io or an internal DNS name cannot be used to reach local or cloud-metadata services."""
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
        if resolve:
            try:
                addrs = _resolve(host)
            except OSError:
                raise ValueError("host name does not resolve") from None
            if not addrs or any(not ipaddress.ip_address(a.split("%")[0]).is_global for a in addrs):
                raise ValueError("only public HTTP(S) URLs are allowed (host resolves to a non-public address)") from None
    return u


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Every redirect target is validated again: a feed or page can not bounce us to an internal address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_public(req, timeout: float = 30):
    """urllib opener with verified TLS and validated redirects."""
    opener = urllib.request.build_opener(_SafeRedirect, urllib.request.HTTPSHandler(context=tls_context()))
    return opener.open(req, timeout=timeout)


def looks_blocked(body: bytes) -> bool:
    sample = body[:4096].decode("utf-8", "replace").lower()
    return ("requiring captcha" in sample and "warning:" in sample) or ("just a moment" in sample and "cloudflare" in sample)


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

    def read(self, url: str, opener=None) -> str:
        """Markdown text of a public page."""
        jina_url = f"https://r.jina.ai/{public_url(url)}"
        req = urllib.request.Request(jina_url, headers={"User-Agent": _UA, "Accept": "text/plain"})
        with (opener or open_public)(req, timeout=30) as resp:
            body = resp.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Jina Reader response is too large")
        if looks_blocked(body):
            raise RuntimeError("Jina Reader returned an anti-bot page; no content was fetched")
        return body.decode("utf-8", "replace")
