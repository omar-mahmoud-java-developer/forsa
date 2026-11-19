# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Config loading and validation. Safety defaults are strict; unknown keys are errors."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

# Keys that only a human may change (the Coach can never touch them).
SAFETY_KEYS = (
    "safety.dry_run",
    "safety.auto_apply",
    "safety.auto_connect",
    "safety.send_emails",
    "safety.max_applications_per_day",
    "safety.max_connects_per_day",
    "safety.max_attempts_per_job",
    "safety.min_delay_seconds",
    "safety.max_delay_seconds",
)

DEFAULTS: dict[str, Any] = {
    "safety": {
        "dry_run": True,
        "auto_apply": False,
        "auto_connect": False,
        "send_emails": False,
        "max_applications_per_day": 3,
        "max_connects_per_day": 5,
        "max_attempts_per_job": 2,
        "min_delay_seconds": 5,
        "max_delay_seconds": 20,
    },
    "search": {
        "titles": [],
        "keywords": [],
        "excluded_keywords": [],
        "excluded_companies": [],
        "locations": [],
        "work_modes": ["remote", "hybrid", "onsite"],
        "posted_within_days": 3,
        "max_pages": 2,
        "seniority": {"min_years": 0, "max_years": 99},
        # read-only search for recruiters / hiring managers; off by default (stores third-party names locally)
        "recruiters": {"enabled": False, "keywords": ["technical recruiter"], "locations": [], "max_per_run": 10,
                       "keep_days": 30},
    },
    "scoring": {
        "title_match": 30,
        "skills": {},
        "years_fit": 20,
        "years_over_penalty": -20,
        "location_match": 15,
        "remote_bonus": 5,
        "thresholds": {"best": 70, "stretch": 50, "apply_min": 75},
    },
    # read-only mailbox access (IMAP) for job-alert and application-status emails; off by default
    "mailbox": {"enabled": False, "imap_host": "imap.gmail.com", "imap_port": 993,
                "senders": ["linkedin.com"], "max_days": 3, "max_messages": 50, "require_auth": True,
                "folders": ["INBOX"]},
    "schedule": {"times": ["09:00", "17:00"]},
    "language": "en",
    "sources": {"enabled": ["demo"], "linkedin": {"backend_order": ["mcp", "jina"]},
                "rss": {"feeds": []}, "plugin_options": {}},
    "llm": {"provider": "none", "model": "", "max_calls_per_run": 10},
    "notify": {"mode": "none", "email_to": "", "smtp_host": "smtp.gmail.com", "smtp_port": 465},
    "paths": {"data_dir": "data", "output_dir": "output", "sessions_dir": "sessions"},
}

_SCHEMA_TYPES: dict[str, type | tuple[type, ...]] = {
    "safety.dry_run": bool, "safety.auto_apply": bool, "safety.auto_connect": bool,
    "safety.send_emails": bool, "safety.max_applications_per_day": int, "safety.max_connects_per_day": int,
    "safety.max_attempts_per_job": int, "safety.min_delay_seconds": (int, float),
    "safety.max_delay_seconds": (int, float), "search.titles": list, "search.keywords": list,
    "search.excluded_keywords": list, "search.excluded_companies": list, "search.locations": list,
    "search.work_modes": list, "search.posted_within_days": int, "search.max_pages": int,
    "scoring.skills": dict, "schedule.times": list, "language": str, "sources.enabled": list,
    "search.recruiters.enabled": bool, "search.recruiters.keywords": list, "search.recruiters.locations": list,
    "search.recruiters.max_per_run": int, "search.recruiters.keep_days": int,
    "mailbox.enabled": bool, "mailbox.imap_host": str, "mailbox.imap_port": int, "mailbox.senders": list,
    "mailbox.max_days": int, "mailbox.max_messages": int, "mailbox.require_auth": bool, "mailbox.folders": list,
    "llm.provider": str, "llm.max_calls_per_run": int, "notify.mode": str, "notify.email_to": str,
}
LLM_PROVIDERS = ("none", "anthropic", "claude-cli")
NOTIFY_MODES = ("none", "email")


class ConfigError(ValueError):
    """The config file is invalid. The message says which key and why."""


def merge(base: dict, extra: dict, path: str = "") -> dict:
    """Deep-merge `extra` over `base`; unknown keys raise ConfigError (typos must not pass silently)."""
    for k, v in extra.items():
        here = f"{path}.{k}" if path else k
        if k.startswith("_"):  # documentation keys such as "_help"
            continue
        if k not in base:
            raise ConfigError(f"unknown config key: {here}")
        if isinstance(base[k], dict) and isinstance(v, dict) and base[k]:
            merge(base[k], v, here)
        else:
            base[k] = v
    return base


def get_path(cfg: dict, dotted: str) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def validate(cfg: dict) -> list[str]:
    """Return a list of problems (empty = valid)."""
    problems: list[str] = []
    for dotted, typ in _SCHEMA_TYPES.items():
        try:
            val = get_path(cfg, dotted)
        except KeyError:
            problems.append(f"missing key: {dotted}")
            continue
        if isinstance(val, bool) and typ in (int, (int, float)):
            problems.append(f"{dotted} must be a number, not a boolean")
        elif not isinstance(val, typ):
            problems.append(f"{dotted} has the wrong type (expected {typ})")
    s = cfg["safety"]
    if s["min_delay_seconds"] > s["max_delay_seconds"]:
        problems.append("safety.min_delay_seconds must be <= safety.max_delay_seconds")
    for k in ("max_applications_per_day", "max_connects_per_day", "max_attempts_per_job"):
        if isinstance(s[k], int) and s[k] < 0:
            problems.append(f"safety.{k} must be >= 0")
    if cfg["llm"]["provider"] not in LLM_PROVIDERS:
        problems.append(f"llm.provider must be one of {LLM_PROVIDERS}")
    if cfg["notify"]["mode"] not in NOTIFY_MODES:
        problems.append(f"notify.mode must be one of {NOTIFY_MODES}")
    if cfg["notify"]["mode"] == "email" and not cfg["notify"]["email_to"]:
        problems.append("notify.email_to is required when notify.mode is 'email'")
    t = cfg["scoring"]["thresholds"]
    if not (t.get("stretch", 0) <= t.get("best", 0)):
        problems.append("scoring.thresholds: stretch must be <= best")
    if s.get("auto_apply") and s.get("dry_run"):
        pass  # allowed: dry-run simulates auto-apply
    return problems


def load(path: str | Path) -> dict:
    """Load a config file over the defaults and validate it."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config file not found: {p} (run `forsa init`)")
    try:
        user = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise ConfigError(f"{p} is not valid JSON: {ex}") from ex
    if not isinstance(user, dict):
        raise ConfigError(f"{p} must contain a JSON object")
    cfg = merge(copy.deepcopy(DEFAULTS), user)
    problems = validate(cfg)
    if problems:
        raise ConfigError("; ".join(problems))
    return cfg


def env(name: str, default: str = "") -> str:
    """Secrets come only from environment variables (FORSA_* / ANTHROPIC_API_KEY)."""
    return os.environ.get(name, default)


def load_dotenv(path: str | Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; does not override variables already set."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        if v:  # an empty value means "not set"
            os.environ.setdefault(k.strip(), v)
