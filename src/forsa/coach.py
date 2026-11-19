# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Coach: reviews results and SUGGESTS changes. It can never change safety settings and never commits anything."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .config import SAFETY_KEYS, get_path

ALLOWED_PREFIXES = ("search.titles", "search.keywords", "search.excluded_keywords", "search.excluded_companies",
                    "search.locations", "scoring.skills")
_WORD = re.compile(r"\b[A-Z][A-Za-z0-9+#.]{2,}\b")
_COMMON = {"The", "And", "You", "Our", "For", "With", "We", "This", "That", "Remote", "Hybrid", "Berlin"}


class Refused(ValueError):
    pass


def suggest(store, cfg: dict, limit: int = 5) -> list[dict]:
    """Rule-based suggestions from the store: skills that recur in good jobs but are not scored yet."""
    known = {k.lower() for k in cfg["scoring"]["skills"]} | {k.lower() for k in cfg["search"]["keywords"]}
    counts: Counter[str] = Counter()
    for j in store.jobs(min_score=cfg["scoring"]["thresholds"]["stretch"]):
        words = {w for w in _WORD.findall(f"{j['title']} {j['description']}") if w not in _COMMON}
        counts.update(w for w in words if w.lower() not in known)
    out = [{"id": f"skill-{w.lower()}", "path": "scoring.skills", "op": "set_key", "key": w.lower(), "value": 3,
            "why": f"'{w}' appears in {n} good-fit jobs but is not scored"}
           for w, n in counts.most_common(limit) if n >= 2]
    flags = store.flags()
    if flags:
        out.append({"id": "profile-answers", "path": None, "op": "note", "value": None,
                    "why": f"{len(flags)} job(s) need answers: add them to profile.md (forsa answer)"})
    return out


def check_allowed(s: dict) -> None:
    path = s.get("path")
    if path is None:
        raise Refused("this suggestion is advice only")
    if any(path == k or path.startswith(k + ".") for k in SAFETY_KEYS) or path.startswith("safety"):
        raise Refused(f"the Coach can never change safety settings ({path})")
    if not any(path == p or path.startswith(p + ".") for p in ALLOWED_PREFIXES):
        raise Refused(f"the Coach may not change '{path}'")


def apply_suggestion(config_path: Path, s: dict) -> str:
    """Write one approved suggestion into config.json. No git commit, no other keys touched."""
    check_allowed(s)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    cur = cfg
    parts = s["path"].split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    leaf = parts[-1]
    if s["op"] == "set_key":
        cur.setdefault(leaf, {})[s["key"]] = s["value"]
    elif s["op"] == "append":
        lst = cur.setdefault(leaf, [])
        if s["value"] not in lst:
            lst.append(s["value"])
    else:
        raise Refused(f"unknown operation {s['op']}")
    config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return f"applied {s['id']} to {config_path.name} (not committed)"


def save(path: Path, suggestions: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(suggestions, indent=2), encoding="utf-8")


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


__all__ = ["suggest", "apply_suggestion", "check_allowed", "Refused", "save", "load", "get_path"]
