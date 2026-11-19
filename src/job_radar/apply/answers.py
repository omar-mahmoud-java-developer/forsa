# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Answers to application questions: ONLY from profile.md. Nothing is ever guessed or defaulted."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..profile import Profile


@dataclass
class Answer:
    value: str
    source: str  # which profile entry it came from


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#. ]", " ", s.lower()).split())


def _pick(options: list[str], wanted: str) -> str | None:
    w = _norm(wanted)
    for o in options:
        if _norm(o) == w:
            return o
    for o in options:
        if _norm(o).startswith(w) or w.startswith(_norm(o)) and _norm(o):
            return o
    return None


_STANDARD = (  # (regex on the label, profile field)
    (r"phone|mobile", "phone"),
    (r"e-?mail", "email"),
    (r"linkedin", "linkedin_url"),
    (r"\b(city|where are you based|current location|location)\b", "location"),
    (r"notice|how soon|available to start|start date|availability", "notice_period"),
    (r"salary|compensation|pay expectation", "salary_expectation"),
    (r"(authori[sz]ed|right to work|work permit|legally)", "work_authorization"),
    (r"sponsor|visa", "requires_sponsorship"),
    (r"relocat", "open_to_relocation"),
)


def answer(label: str, kind: str, options: list[str], profile: Profile) -> Answer | None:
    """Return the profile's answer, or None when the profile does not say (caller must skip the job)."""
    l = _norm(label)
    raw = None
    # 1) explicit answers in profile.md, longest key first
    for key in sorted(profile.answers, key=len, reverse=True):
        if _norm(key) in l:
            raw = Answer(profile.answers[key], f"answers:{key}")
            break
    # 2) years of experience: only for skills the profile lists
    if raw is None and re.search(r"\byears?\b", l) and re.search(r"experience|how many", l):
        hits = [(k, v) for k, v in profile.skills.items()
                if re.search(rf"(?<![a-z0-9]){re.escape(_norm(k))}(?![a-z0-9])", l)]
        if hits:
            k, v = min(hits, key=lambda kv: kv[1])
            raw = Answer(str(int(v)) if float(v).is_integer() else str(v), f"skills:{k}")
        elif profile.years is not None and not _mentions_unknown_skill(l, profile):
            v = profile.years
            raw = Answer(str(int(v)) if float(v).is_integer() else str(v), "years_experience")
    # 3) standard profile fields
    if raw is None:
        for pat, fld in _STANDARD:
            if re.search(pat, l) and profile.get(fld):
                raw = Answer(profile.get(fld), f"field:{fld}")
                break
    if raw is None:
        return None
    if kind in ("select", "radio"):
        opt = _pick(options, raw.value)
        return Answer(opt, raw.source) if opt else None
    return raw


_FILLER = set(
    "how many years year of work experience do does you your have has with in on the a an total professional "
    "relevant overall field are is what please enter number level any as and or for to at least minimum".split()
)


def _mentions_unknown_skill(label: str, profile: Profile) -> bool:
    """True if the question names something (a tool/domain) the profile does not list, e.g. 'Kafka'."""
    words = [w for w in re.findall(r"[a-z][a-z0-9+#.]*", label) if w not in _FILLER and len(w) > 1]
    known = " ".join(_norm(k) for k in profile.skills)
    return any(w not in known for w in words)
