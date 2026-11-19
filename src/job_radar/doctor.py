# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""One `doctor` command: checks everything and prints how to fix each problem."""

from __future__ import annotations

import os
import shutil
import smtplib
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config as cfgmod
from . import profile as profmod
from .reach.mcp_client import SERVER_PIN, python_ok

OK, WARN, ERROR, OFF = "ok", "warn", "error", "off"


@dataclass
class Check:
    name: str
    status: str
    message: str
    fix: str = ""


def check_python() -> Check:
    v = sys.version_info
    if v < (3, 11):
        return Check("python", ERROR, f"Python {v.major}.{v.minor} is too old", "Install Python 3.11 or newer.")
    if not python_ok():
        return Check("python", WARN, f"Python {v.major}.{v.minor}.{v.micro}: fine for the agent, too old for the "
                     "LinkedIn MCP server", "Install Python 3.12.4+ to use the LinkedIn backend.")
    return Check("python", OK, f"Python {v.major}.{v.minor}.{v.micro}")


def check_config(root: Path) -> tuple[Check, dict | None]:
    p = root / "config.json"
    try:
        cfg = cfgmod.load(p)
    except cfgmod.ConfigError as ex:
        return Check("config", ERROR, str(ex), "Run `job-radar init` or copy config.example.json to config.json."), None
    s = cfg["safety"]
    msg = f"valid (dry_run={s['dry_run']}, auto_apply={s['auto_apply']}, auto_connect={s['auto_connect']})"
    if not s["dry_run"]:
        return Check("config", WARN, msg + " - LIVE mode: real actions are allowed",
                     "Set safety.dry_run to true until you trust the results."), cfg
    return Check("config", OK, msg), cfg


def check_profile(root: Path) -> Check:
    try:
        prof = profmod.load(root / "profile.md")
    except profmod.ProfileError as ex:
        return Check("profile", ERROR, str(ex), "Run `job-radar init` or copy profile.example.md to profile.md.")
    missing = [k for k in ("name", "email", "location") if not prof.get(k)]
    if missing:
        return Check("profile", WARN, f"missing fields: {', '.join(missing)}", "Fill them in profile.md.")
    return Check("profile", OK, f"{len(prof.skills)} skills, {len(prof.answers)} saved answers")


def check_env(cfg: dict | None) -> list[Check]:
    out = []
    if cfg and cfg["notify"]["mode"] == "email":
        user, pw = os.environ.get("JOB_RADAR_SMTP_USER"), os.environ.get("JOB_RADAR_SMTP_PASSWORD")
        if not (user and pw):
            out.append(Check("email", ERROR, "notify.mode is 'email' but JOB_RADAR_SMTP_USER / PASSWORD are not set",
                             "Add them to .env (use an app password of a dedicated mailbox)."))
        else:
            out.append(_check_smtp(cfg, user, pw))
    else:
        out.append(Check("email", OFF, "notifications are off (notify.mode = none)"))
    if cfg and cfg["llm"]["provider"] == "anthropic":
        ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
        out.append(Check("llm", OK if ok else ERROR, "anthropic key set" if ok else "ANTHROPIC_API_KEY is not set",
                         "" if ok else "Add ANTHROPIC_API_KEY to .env, or set llm.provider to 'none'."))
    elif cfg and cfg["llm"]["provider"] == "claude-cli":
        ok = shutil.which("claude") is not None
        out.append(Check("llm", OK if ok else ERROR, "claude CLI found" if ok else "claude CLI not found",
                         "" if ok else "Install Claude Code or set llm.provider to 'none'."))
    else:
        out.append(Check("llm", OFF, "no LLM configured: rules-only mode (cover letters and judge are skipped)"))
    return out


def _check_smtp(cfg: dict, user: str, pw: str) -> Check:
    try:
        with smtplib.SMTP_SSL(cfg["notify"]["smtp_host"], int(cfg["notify"]["smtp_port"]), timeout=20) as s:
            s.login(user, pw)
        return Check("email", OK, "SMTP login works")
    except (smtplib.SMTPException, OSError) as ex:
        return Check("email", ERROR, f"SMTP login failed: {str(ex)[:100]}",
                     "Check host/port and that the app password is valid.")


def check_paths(root: Path, cfg: dict | None) -> Check:
    if not cfg:
        return Check("paths", OFF, "skipped (no valid config)")
    try:
        for k in ("data_dir", "output_dir", "sessions_dir"):
            from .paths import resolve  # noqa: PLC0415
            resolve(root, cfg["paths"][k])
    except ValueError as ex:
        return Check("paths", ERROR, str(ex), "Use paths inside the project folder.")
    return Check("paths", OK, "all paths stay inside the project")


def check_gitignore(root: Path) -> Check:
    gi = root / ".gitignore"
    if not (root / ".git").exists():
        return Check("git", OFF, "not a git repository")
    text = gi.read_text() if gi.exists() else ""
    need = [x for x in (".env", "data/", "sessions/", "profile.md") if x not in text]
    if need:
        return Check("git", WARN, f".gitignore does not cover: {', '.join(need)}", "Add them before committing.")
    return Check("git", OK, "secrets and local data are git-ignored")


def run_all(root: Path, linkedin: bool | None = None, probe_linkedin: bool = True) -> list[Check]:
    checks = [check_python()]
    c, cfg = check_config(root)
    checks += [c, check_profile(root), check_paths(root, cfg)]
    checks += check_env(cfg)
    checks.append(check_gitignore(root))
    enabled = cfg["sources"]["enabled"] if cfg else []
    if cfg:
        from .providers import base as pbase  # noqa: PLC0415
        from .providers import demo as _d  # noqa: F401, PLC0415
        from .providers import linkedin as _l  # noqa: F401, PLC0415
        from .providers import loader  # noqa: PLC0415
        from .providers import rss as _r  # noqa: F401, PLC0415

        problems = loader.load_plugins(root)
        checks.append(Check("plugins", ERROR if problems else OK, "; ".join(problems) or "no plugin problems",
                            "Fix or delete the plugin file named above." if problems else ""))
        unknown = [n for n in enabled if n not in pbase.known()]
        if unknown:
            checks.append(Check("sources", ERROR, f"unknown source(s): {', '.join(unknown)}",
                                "Use `job-radar providers` to list names, or `job-radar new-provider NAME`."))
        else:
            checks.append(Check("sources", OK, f"enabled: {', '.join(enabled) or 'none'}"))
        if "rss" in enabled and not cfg["sources"]["rss"]["feeds"]:
            checks.append(Check("rss", WARN, "rss is enabled but sources.rss.feeds is empty",
                                'Add {"name": "...", "url": "https://..."} entries to sources.rss.feeds.'))
    want_li = linkedin if linkedin is not None else "linkedin" in enabled
    if want_li:
        from .reach.linkedin import LinkedInChannel  # noqa: PLC0415
        sessions = root / (cfg["paths"]["sessions_dir"] if cfg else "sessions")
        ch = LinkedInChannel(sessions, cfg["sources"]["linkedin"]["backend_order"] if cfg else None)
        if probe_linkedin:
            status, msg = ch.check()
        else:
            status, msg = WARN, "not probed"
        fix = ""
        if status != OK:
            fix = (f"pip install 'job-radar-agent[linkedin]' (pins {SERVER_PIN}), then run `job-radar login`")
        checks.append(Check(f"linkedin [{ch.active_backend or 'none'}]", status, msg, fix))
    else:
        checks.append(Check("linkedin", OFF, "source not enabled (sources.enabled)"))
    return checks


ICON = {OK: "[ OK ]", WARN: "[WARN]", ERROR: "[FAIL]", OFF: "[ -- ]"}


def format_report(checks: list[Check]) -> str:
    lines = ["job-radar doctor", "=" * 16]
    for c in checks:
        lines.append(f"{ICON[c.status]} {c.name}: {c.message}")
        if c.fix and c.status in (WARN, ERROR):
            lines.append(f"         fix: {c.fix}")
    bad = sum(c.status == ERROR for c in checks)
    lines.append("")
    lines.append("All required checks passed." if not bad else f"{bad} problem(s) to fix.")
    return "\n".join(lines)


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.status == ERROR for c in checks) else 0
