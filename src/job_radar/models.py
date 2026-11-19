# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Plain data types shared by providers and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    id: str
    source: str
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    posted: str = ""
    work_mode: str = ""  # remote | hybrid | onsite | ""
    easy_apply: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
    # filled by scoring
    score: int = 0
    tier: str = "skip"
    why: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id, "source": self.source, "title": self.title, "company": self.company,
            "location": self.location, "url": self.url, "description": self.description[:4000],
            "score": self.score, "tier": self.tier, "why": self.why, "easy_apply": self.easy_apply,
            "extra": self.extra,
        }
