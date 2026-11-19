# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Digest and drafts. Digest to YOURSELF is the only thing that can be sent, and only when enabled."""

from __future__ import annotations

import datetime as dt
import html
import smtplib
from email.message import EmailMessage
from pathlib import Path

from . import config as cfgmod
from .templating import load, render


def _rows(jobs: list[dict]) -> str:
    if not jobs:
        return "<p>none</p>"
    items = "".join(
        f"<li><b>{html.escape(j['title'] or '')}</b> at {html.escape(j['company'] or '')} "
        f"({html.escape(j['location'] or '')}) score {j['score']} "
        f"<a href='{html.escape(j['url'] or '')}'>link</a><br><small>{html.escape(j['why'] or '')}</small></li>"
        for j in jobs)
    return f"<ul>{items}</ul>"


def build_digest(root: Path, store, profile, cfg: dict, dry_run: bool, backends: list[str], applications: list[dict]) -> str:
    best = store.jobs(tier="best")[:15]
    stretch = store.jobs(tier="stretch")[:10]
    flags = store.flags()
    flag_html = ("<ul>" + "".join(
        f"<li>{html.escape(f['title'] or f['job_id'])} at {html.escape(f['company'] or '')}: "
        f"{html.escape(f['reason'])}</li>" for f in flags) + "</ul>") if flags else "<p>nothing</p>"
    app_html = ("<ul>" + "".join(
        f"<li>{html.escape(a['title'])} at {html.escape(a['company'])}: {html.escape(a['status'])}</li>"
        for a in applications) + "</ul>") if applications else "<p>none this run</p>"
    mode = ("DRY RUN: nothing was sent, applied or connected." if dry_run
            else "LIVE run: actions were allowed by your safety settings.")
    return render(load(root, "digest.html"), {
        "name": html.escape(profile.name or "you"), "mode_line": mode, "best": _rows(best),
        "stretch": _rows(stretch), "applications": app_html, "flags": flag_html,
        "backends": ", ".join(sorted(set(backends))) or "none", "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


def write_digest(root: Path, cfg: dict, html_text: str) -> Path:
    out = root / cfg["paths"]["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    p = out / "digest.html"
    p.write_text(html_text, encoding="utf-8")
    return p


def send_digest(cfg: dict, html_text: str, dry_run: bool) -> str:
    """Email the digest to the user. Returns a short status. Never sends in dry-run or when notifications are off."""
    n = cfg["notify"]
    if dry_run:
        return "not sent (dry run)"
    if n["mode"] != "email":
        return "not sent (notify.mode is none)"
    if not cfg["safety"]["send_emails"]:
        return "not sent (safety.send_emails is false)"
    user, pw = cfgmod.env("JOB_RADAR_SMTP_USER"), cfgmod.env("JOB_RADAR_SMTP_PASSWORD")
    if not (user and pw):
        return "not sent (JOB_RADAR_SMTP_USER / PASSWORD not set)"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, n["email_to"], "Job Radar digest"  # always to yourself
    msg.set_content("Open this digest in an HTML-capable mail app.")
    msg.add_alternative(html_text, subtype="html")
    try:
        with smtplib.SMTP_SSL(n["smtp_host"], int(n["smtp_port"]), timeout=60) as s:
            s.login(user, pw)
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as ex:
        return f"FAILED: {str(ex)[:100]}"
    return "sent"


def save_draft(root: Path, cfg: dict, kind: str, job_id: str, text: str) -> Path:
    """Drafts are files for the user to review. Nothing is ever sent to an employer from here."""
    d = root / cfg["paths"]["output_dir"] / "drafts"
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)
    p = d / f"{kind}-{safe}.md"
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return p
