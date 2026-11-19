# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Recruiter / hiring-manager discovery (read-only search; opt-in).

Privacy: only public profile basics are kept (username, name, headline, location, connection degree), stored locally
in the SQLite file, deleted automatically after `search.recruiters.keep_days`, and purgeable any time with
`forsa people purge`. Nothing is sent to anyone from here; connecting stays behind `safety.auto_connect`.
"""

from __future__ import annotations

import re

RECRUITER = re.compile(
    r"recruit|talent|\bhr\b|human resources?|acquisition|head ?hunt|sourc(?:er|ing)|staffing|people (?:partner|operations)|"
    r"hiring manager|engineering manager|head of", re.I)
_DEGREE = re.compile(r"^•?\s*(1st|2nd|3rd\+?)$")
_ACTIONS = ("Connect", "Pending", "Message", "Follow")
_NAME_TOKEN = re.compile(r"[^a-z]+")


def _tokens(s: str) -> set[str]:
    return {t for t in _NAME_TOKEN.split(s.lower()) if len(t) > 2}


def parse_people(result) -> list[dict]:
    """People cards from a search_people result: name, degree, headline, location, action, username."""
    if not isinstance(result, dict):
        return []
    text = "\n".join(str(v) for v in result.get("sections", {}).values())
    lines: list[str] = []
    for raw in (ln.strip() for ln in text.split("\n")):
        if not raw:
            continue
        m = re.match(r"^(.*\S)\s+(•\s*(?:1st|2nd|3rd\+?))$", raw)  # "Name • 2nd" on one line
        lines += [m.group(1), m.group(2)] if m else [raw]
    cards = []
    for i in range(len(lines) - 1):
        d = _DEGREE.match(lines[i + 1])
        if not d:
            continue
        rest = lines[i + 2:i + 6]
        action = next((x for x in rest if x in _ACTIONS), "")
        info = [x for x in (rest[:rest.index(action)] if action else rest[:2]) if x]
        cards.append({"name": lines[i], "degree": d.group(1), "headline": info[0] if info else "",
                      "location": info[1] if len(info) > 1 else "", "action": action, "username": ""})
    links = [r for group in result.get("references", {}).values() for r in group
             if str(r.get("url", "")).startswith("/in/")]
    pos = 0
    for c in cards:
        toks = _tokens(c["name"])
        need = min(2, len(toks)) or 1
        for k in range(pos, len(links)):
            slug = links[k]["url"].strip("/").split("/")[-1]
            if (links[k].get("text") or "").strip() == c["name"] or len(toks & _tokens(slug)) >= need:
                c["username"], pos = slug, k + 1
                break
    return [c for c in cards if re.fullmatch(r"[A-Za-z0-9%_-]{3,100}", c["username"])]


def worth_keeping(card: dict) -> bool:
    """A recruiter/hiring contact we have not connected with yet."""
    return card["degree"] != "1st" and card["action"] in ("Connect", "") and bool(RECRUITER.search(card["headline"]))
