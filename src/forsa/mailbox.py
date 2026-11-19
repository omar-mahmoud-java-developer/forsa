# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Read-only mailbox access: job-alert emails and application-status updates.

Security rules (the reasons this is safe to offer):
  * opt-in (`mailbox.enabled`), credentials only from the environment, never written anywhere;
  * the folder is opened READ-ONLY and messages are fetched with BODY.PEEK (nothing is marked read or changed);
  * only messages from the allow-listed sender domains are looked at, and (by default) only when the message passed
    SPF/DKIM according to the receiving server (Authentication-Results), so forged mails are ignored;
  * email text is untrusted: it is parsed with regular expressions only. No LLM reads it, no email can trigger any
    action, no command is ever taken from an email;
  * only company, job title, status and date are stored; bodies are never stored.
"""

from __future__ import annotations

import datetime as dt
import email
import email.policy
import html
import imaplib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message
from email.utils import parseaddr

MAX_MESSAGE_BYTES = 300_000

_VIEWED = re.compile(r"your application was viewed by (?P<company>.+?)\s*$", re.I)
_SENT = re.compile(r"your application was sent to (?P<company>.+?)\s*$", re.I)
_APPLIED_TO = re.compile(r"your application to (?P<title>.+?) at (?P<company>.+?)\s*$", re.I)
_UPDATE_FROM = re.compile(r"(?:your update from|an update on your application (?:from|to|at)) (?P<company>.+?)\s*$", re.I)
_REJECTED = re.compile(
    r"unfortunately|not (?:to )?(?:move|moving) forward|decided to (?:pursue|move forward with) other|"
    r"position has been filled|no longer under consideration", re.I)
_INTERVIEW = re.compile(r"interview|invite you to|schedule a (?:call|chat|meeting)|assessment", re.I)
_OFFER = re.compile(r"\b(?:job )?offer\b", re.I)
_JOB_LINK = re.compile(
    r"""href=["'][^"']*linkedin\.com/(?:comm/)?jobs/view/(\d{6,})[^"']*["'][^>]*>(.*?)</a>""", re.I | re.S)
_GENERIC = re.compile(r"^(view|apply|see|more|details|open|show|job details|apply now|view job|view details)\b", re.I)
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Update:
    company: str
    title: str
    status: str  # applied | viewed | interview | offer | rejected
    msgid: str = ""


@dataclass
class AlertJob:
    id: str
    title: str


@dataclass
class MailResult:
    updates: list[Update] = field(default_factory=list)
    alert_jobs: list[AlertJob] = field(default_factory=list)
    scanned: int = 0
    ignored_unauthenticated: int = 0


def _clean(s: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", s or "")).split())


def sender_allowed(from_header: str, senders: list[str]) -> bool:
    """True when the From domain equals or is a subdomain of an allow-listed domain."""
    addr = parseaddr(from_header)[1].lower()
    domain = addr.rsplit("@", 1)[-1] if "@" in addr else ""
    return any(domain == s.lower() or domain.endswith("." + s.lower()) for s in senders)


def authenticated(msg: Message) -> bool:
    """The receiving server vouched for the sender (SPF or DKIM pass). Missing header = not authenticated."""
    results = " ".join(str(v) for v in msg.get_all("Authentication-Results", []))
    return bool(re.search(r"\b(?:dkim|spf)=pass\b", results, re.I))


def classify(subject: str, body_text: str) -> Update | None:
    """Application update from a subject (+ body for the tone); None when the mail is not about an application."""
    subject = _clean(subject)
    m = _APPLIED_TO.search(subject)
    if m:
        status, company, title = "applied", m.group("company"), m.group("title")
    elif (m := _SENT.search(subject)):
        status, company, title = "applied", m.group("company"), ""
    elif (m := _VIEWED.search(subject)):
        status, company, title = "viewed", m.group("company"), ""
    elif (m := _UPDATE_FROM.search(subject)):
        status, company, title = "viewed", m.group("company"), ""
    else:
        return None
    text = _clean(body_text)[:3000]
    if _REJECTED.search(text) or _REJECTED.search(subject):
        status = "rejected"
    elif _INTERVIEW.search(subject) or (status != "applied" and _INTERVIEW.search(text[:600])):
        status = "interview"
    elif _OFFER.search(subject):
        status = "offer"
    return Update(company.strip(" .:-"), title.strip(), status)


def alert_jobs(html_body: str) -> list[AlertJob]:
    """LinkedIn job links in an alert email (id + link text). Plain regex; nothing is executed or fetched."""
    out, seen = [], set()
    for m in _JOB_LINK.finditer(html_body or ""):
        title = _clean(m.group(2))
        if m.group(1) in seen or not title or _GENERIC.match(title):
            continue
        seen.add(m.group(1))
        out.append(AlertJob(m.group(1), title[:120]))
    return out


def _body(msg: Message) -> tuple[str, str]:
    """(html, text) parts, capped."""
    html_part = text_part = ""
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        try:
            content = part.get_content()
        except Exception:  # noqa: BLE001 - odd encodings
            continue
        if part.get_content_subtype() == "html":
            html_part += str(content)[:MAX_MESSAGE_BYTES]
        else:
            text_part += str(content)[:MAX_MESSAGE_BYTES]
    return html_part, text_part or _clean(html_part)


def read_mailbox(cfg: dict, user: str, password: str, seen: Callable[[str], bool] = lambda _id: False,
                 imap_factory=imaplib.IMAP4_SSL, now: dt.datetime | None = None) -> MailResult:
    """Fetch recent messages read-only and turn them into updates and alert jobs."""
    mb = cfg["mailbox"]
    since = ((now or dt.datetime.now()) - dt.timedelta(days=int(mb["max_days"]))).strftime("%d-%b-%Y")
    result = MailResult()
    imap = imap_factory(mb["imap_host"], int(mb["imap_port"]))
    try:
        imap.login(user, password)
        for folder in mb["folders"]:
            typ, _ = imap.select(f'"{folder}"', readonly=True)  # READ-ONLY: nothing can be changed
            if typ != "OK":
                continue
            for sender in mb["senders"]:
                typ, data = imap.search(None, "SINCE", since, "FROM", f'"{sender}"')
                ids = (data[0] or b"").split()[-int(mb["max_messages"]):] if typ == "OK" else []
                for mid in ids:
                    typ, parts = imap.fetch(mid, "(BODY.PEEK[])")
                    raw = next((p[1] for p in parts if isinstance(p, tuple)), b"") if typ == "OK" else b""
                    if not raw or len(raw) > MAX_MESSAGE_BYTES * 3:
                        continue
                    msg = email.message_from_bytes(raw, policy=email.policy.default)
                    result.scanned += 1
                    msgid = str(msg.get("Message-ID", "")).strip()
                    if msgid and seen(msgid):
                        continue
                    if not sender_allowed(str(msg.get("From", "")), mb["senders"]):
                        continue
                    if mb["require_auth"] and not authenticated(msg):
                        result.ignored_unauthenticated += 1
                        continue
                    html_body, text_body = _body(msg)
                    upd = classify(str(msg.get("Subject", "")), text_body)
                    if upd:
                        upd.msgid = msgid
                        result.updates.append(upd)
                    else:
                        result.alert_jobs += alert_jobs(html_body)
                        if msgid:
                            result.updates.append(Update("", "", "seen", msgid))  # bookkeeping only
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
    return result
