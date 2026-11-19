# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Generic job scoring: every weight, keyword and threshold comes from config.json and profile.md."""

from __future__ import annotations

import re

from .models import Job

_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(?:\d{1,2})?\s*\+?\s*(?:years?|yrs)", re.I)


def _contains(text: str, term: str) -> bool:
    term = term.strip()
    if not term:
        return False
    if term.startswith("re:"):
        return re.search(term[3:], text, re.I) is not None
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.I) is not None


def required_years(description: str) -> int | None:
    """Highest plausible "N years" requirement in a description, or None."""
    found = [int(m.group(1)) for m in _YEARS.finditer(description or "") if int(m.group(1)) <= 20]
    return max(found) if found else None


def score_job(job: Job, cfg: dict) -> Job:
    s, sc = cfg["search"], cfg["scoring"]
    title, desc = job.title or "", job.description or ""
    text = f"{title}\n{desc}"
    why: list[str] = []

    for co in s["excluded_companies"]:
        if co and co.lower() in (job.company or "").lower():
            return _done(job, 0, f"excluded company ({co})", cfg)
    for kw in s["excluded_keywords"]:
        if _contains(text, kw):
            return _done(job, 0, f"excluded keyword ({kw})", cfg)

    pts = 0
    if s["titles"]:
        if any(_contains(title, t) for t in s["titles"]):
            pts += sc["title_match"]
            why.append("title match")
    else:
        pts += sc["title_match"] // 2
    for skill, weight in sc["skills"].items():
        if _contains(text, skill):
            pts += int(weight)
            why.append(skill)
    for kw in s["keywords"]:
        if _contains(text, kw):
            pts += 2
            why.append(f"kw:{kw}")

    need = required_years(desc)
    sen = s["seniority"]
    if need is None:
        pts += sc["years_fit"] // 2
    elif need <= sen["max_years"]:
        pts += sc["years_fit"]
        why.append(f"{need}+ yrs fits")
    else:
        pts += sc["years_over_penalty"]
        why.append(f"{need}+ yrs too senior")
    job.extra["years_required"] = need

    loc_terms = [str(loc.get("name", loc)) if isinstance(loc, dict) else str(loc) for loc in s["locations"]]
    loc_hit = any(
        t.strip() and any(part.strip().lower() in (job.location or "").lower() for part in t.split(","))
        for t in loc_terms
    )
    mode = (job.work_mode or ("remote" if re.search(r"\bremote\b", f"{job.location} {title}", re.I) else "")).lower()
    if loc_hit:
        pts += sc["location_match"]
        why.append("location")
    if mode == "remote" and "remote" in s["work_modes"]:
        pts += sc["remote_bonus"]
        why.append("remote")
    if mode and mode not in s["work_modes"]:
        pts -= 30
        why.append(f"work mode {mode} not wanted")
    return _done(job, pts, ", ".join(why), cfg)


def _done(job: Job, pts: int, why: str, cfg: dict) -> Job:
    t = cfg["scoring"]["thresholds"]
    job.score = max(0, min(100, pts))
    job.why = why
    job.tier = "best" if job.score >= t["best"] else "stretch" if job.score >= t["stretch"] else "skip"
    return job
