# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""profile.md: the ONLY source of truth for application answers.

Format (see profile.example.md):
    key: value                 # header lines before the first "## " section
    ## Skills                  # "- skill: years"
    ## Answers                 # "- question text: answer"
    ## Summary                 # free text, used by templates and the LLM
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class ProfileError(ValueError):
    pass


@dataclass
class Profile:
    fields: dict[str, str] = field(default_factory=dict)
    skills: dict[str, float] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    summary: str = ""

    def get(self, key: str, default: str = "") -> str:
        return self.fields.get(key, default)

    @property
    def name(self) -> str:
        return self.get("name")

    @property
    def years(self) -> float | None:
        raw = self.get("years_experience")
        try:
            return float(raw) if raw != "" else None
        except ValueError:
            return None


def parse(text: str) -> Profile:
    prof = Profile()
    section = ""
    summary: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if line.startswith("# ") or line.strip().startswith("<!--"):
            continue
        if not section:
            if ":" in line and not line.startswith(("-", " ")):
                k, _, v = line.partition(":")
                prof.fields[k.strip().lower()] = v.strip()
            continue
        if section == "summary":
            summary.append(line)
        elif line.startswith("- ") and ":" in line:
            k, _, v = line[2:].partition(":")
            k, v = k.strip().lower(), v.strip()
            if section == "skills":
                try:
                    prof.skills[k] = float(v)
                except ValueError as ex:
                    raise ProfileError(f"skill years must be a number: '{k}: {v}'") from ex
            elif section == "answers":
                prof.answers[k] = v
    prof.summary = "\n".join(summary).strip()
    return prof


def load(path: str | Path) -> Profile:
    p = Path(path)
    if not p.exists():
        raise ProfileError(f"profile not found: {p} (run `job-radar init`)")
    return parse(p.read_text(encoding="utf-8"))


def placeholders(text: str) -> list[str]:
    """Names of {placeholders} left in a rendered text (a rendered letter must have none)."""
    return re.findall(r"\{[a-z_]+\}", text)
