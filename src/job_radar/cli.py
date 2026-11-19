# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Single entry point: job-radar init | doctor | run | digest | coach | eval | status | answer | login | schedule."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, coach, doctor, privacy
from . import config as cfgmod
from . import profile as profmod
from .paths import project_root, resolve
from .providers import base as provbase
from .providers import demo as _demo  # noqa: F401  (registers 'demo')
from .providers import linkedin as _li  # noqa: F401  (registers 'linkedin')
from .providers import loader
from .providers import rss as _rss  # noqa: F401  (registers 'rss')
from .store import Store

EXAMPLES = Path(__file__).parent / "examples"


def _setup(root: Path):
    cfgmod.load_dotenv(root / ".env")
    cfg = cfgmod.load(root / "config.json")
    prof = profmod.load(root / "profile.md")
    store = Store(resolve(root, cfg["paths"]["data_dir"]) / "job_radar.sqlite")
    return cfg, prof, store


def _providers(root: Path, cfg: dict):
    problems = loader.load_plugins(root)
    for p in problems:
        logging.getLogger("job_radar").warning(p)
    return [loader.create_from_config(name, root, cfg) for name in cfg["sources"]["enabled"]]


# ---------------------------------------------------------------- commands

def cmd_init(a, root: Path) -> int:
    ask = (lambda q, d="": d) if a.yes else (lambda q, d="": (input(f"{q} [{d}]: ").strip() or d))
    cfg_path, prof_path = root / "config.json", root / "profile.md"
    if (cfg_path.exists() or prof_path.exists()) and not a.force:
        print("config.json / profile.md already exist (use --force to overwrite).")
        return 1
    cfg = json.loads((EXAMPLES / "config.example.json").read_text(encoding="utf-8"))
    prof_text = (EXAMPLES / "profile.example.md").read_text(encoding="utf-8")
    if not a.yes:
        print("Answer a few questions. Press Enter to keep the example value.\n")
        titles = ask("Target job titles (comma separated)", ", ".join(cfg["search"]["titles"]))
        cfg["search"]["titles"] = [t.strip() for t in titles.split(",") if t.strip()]
        skills = ask("Key skills/keywords (comma separated)", ", ".join(cfg["search"]["keywords"]))
        cfg["search"]["keywords"] = [t.strip() for t in skills.split(",") if t.strip()]
        locs = ask("Locations (comma separated)", ", ".join(x["name"] for x in cfg["search"]["locations"]))
        cfg["search"]["locations"] = [{"name": t.strip()} for t in locs.split(",") if t.strip()]
        modes = ask("Work modes (remote,hybrid,onsite)", ",".join(cfg["search"]["work_modes"]))
        cfg["search"]["work_modes"] = [t.strip() for t in modes.split(",") if t.strip()]
        cfg["search"]["seniority"]["max_years"] = int(ask("Max years of experience jobs may ask for", "6") or 6)
        cfg["llm"]["provider"] = ask("LLM provider (none/anthropic/claude-cli)", "none")
        if ask("Email yourself a digest? (y/n)", "n").lower().startswith("y"):
            cfg["notify"].update(mode="email", email_to=ask("Your email address"))
        if ask("Use LinkedIn as a source? (y/n)", "n").lower().startswith("y"):
            cfg["sources"]["enabled"] = ["linkedin"]
        name = ask("Your full name", "Jane Doe")
        prof_text = prof_text.replace("Jane Doe", name)
        prof_text = prof_text.replace("jane.doe@example.com", ask("Your email", "jane.doe@example.com"))
    cfg["safety"].update(dry_run=True, auto_apply=False, auto_connect=False, send_emails=False)  # always safe
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    prof_path.write_text(prof_text, encoding="utf-8")
    env_p = root / ".env"
    if not env_p.exists():
        shutil.copy(EXAMPLES / ".env.example", env_p)
    print(f"Wrote {cfg_path.name}, {prof_path.name}, .env (all git-ignored). Safety: dry_run=true, auto_apply=false.")
    if "linkedin" in cfg["sources"]["enabled"] and not a.yes:
        if ask("Start the LinkedIn sign-in now? (y/n)", "n").lower().startswith("y"):
            cmd_login(argparse.Namespace(status=False), root)
    print()
    checks = doctor.run_all(root)
    print(doctor.format_report(checks))
    return 0


def cmd_doctor(a, root: Path) -> int:
    cfgmod.load_dotenv(root / ".env")
    checks = doctor.run_all(root, probe_linkedin=not a.no_probe)
    print(doctor.format_report(checks))
    return doctor.exit_code(checks)


def cmd_run(a, root: Path) -> int:
    from . import pipeline  # noqa: PLC0415

    cfg, prof, store = _setup(root)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s",
                        handlers=[logging.StreamHandler(), _file_handler(root, cfg)])
    providers = _providers(root, cfg)
    driver_factory, closer = _apply_driver(root, cfg)
    try:
        res = pipeline.run(root, cfg, prof, store, providers, dry_run=True if a.dry_run else None,
                           driver_factory=driver_factory)
    finally:
        closer()
        for p in providers:
            if hasattr(p, "close"):
                p.close()
    print(f"\n{'DRY RUN' if res.dry_run else 'LIVE RUN'}: {res.new_jobs} new jobs, {res.scored} scored, "
          f"{res.drafts} drafts, {len(res.applications)} application(s), {len(res.connects)} connect(s)")
    for s in res.steps:
        print(f"  - {s}")
    print(f"  digest: {res.digest_path} ({res.digest_status})")
    print(f"  backends used: {', '.join(sorted(set(res.backends))) or 'none'}")
    return 0


def _apply_driver(root: Path, cfg: dict):
    """A browser driver only when auto_apply is on, LinkedIn is a source and the [apply] extra is installed."""
    if not (cfg["safety"]["auto_apply"] and "linkedin" in cfg["sources"]["enabled"]):
        return None, lambda: None
    try:
        from .apply.browser import PatchrightDriver  # noqa: PLC0415

        drv = PatchrightDriver(resolve(root, cfg["paths"]["sessions_dir"]), headless=True)
    except Exception as ex:  # noqa: BLE001
        logging.getLogger("job_radar").warning("no browser driver (%s); applications are skipped", ex)
        return None, lambda: None
    return (lambda: drv), drv.close


def _file_handler(root: Path, cfg: dict) -> logging.Handler:
    d = root / "logs"
    d.mkdir(exist_ok=True)
    return logging.FileHandler(d / "job-radar.log", encoding="utf-8")


def cmd_digest(a, root: Path) -> int:
    from . import notify  # noqa: PLC0415

    cfg, prof, store = _setup(root)
    html_text = notify.build_digest(root, store, prof, cfg, cfg["safety"]["dry_run"], [], [])
    print(f"wrote {notify.write_digest(root, cfg, html_text)}")
    if a.send:
        print(notify.send_digest(cfg, html_text, cfg["safety"]["dry_run"]))
    return 0


def cmd_coach(a, root: Path) -> int:
    cfg, _prof, store = _setup(root)
    path = resolve(root, cfg["paths"]["data_dir"]) / "suggestions.json"
    if a.apply:
        items = {s["id"]: s for s in coach.load(path)}
        if a.apply not in items:
            print(f"no suggestion '{a.apply}'")
            return 1
        try:
            print(coach.apply_suggestion(root / "config.json", items[a.apply]))
        except coach.Refused as ex:
            print(f"refused: {ex}")
            return 1
        return 0
    items = coach.suggest(store, cfg)
    coach.save(path, items)
    if not items:
        print("No suggestions yet.")
    for s in items:
        print(f"- [{s['id']}] {s['why']}")
    print("\nApply one with: job-radar coach --apply <id>   (safety settings can never be changed by the Coach)")
    return 0


def cmd_eval(a, root: Path) -> int:
    from . import evals  # noqa: PLC0415

    return evals.main(root, a.cases)


def cmd_status(a, root: Path) -> int:
    cfg, _prof, store = _setup(root)
    last = store.last_run()
    print(f"job-radar {__version__}  dry_run={cfg['safety']['dry_run']}  jobs={len(store.jobs())}")
    print(f"last run: {last['at'] if last else 'never'}")
    for f in store.flags():
        print(f"  needs you: {f['title'] or f['job_id']}: {f['reason']}")
    return 0


def cmd_answer(a, root: Path) -> int:
    p = root / "profile.md"
    text = p.read_text(encoding="utf-8")
    line = f"- {a.question.strip().lower()}: {a.answer.strip()}\n"
    if "## Answers" not in text:
        text += "\n## Answers\n"
    head, _, tail = text.partition("## Answers\n")
    p.write_text(head + "## Answers\n" + line + tail, encoding="utf-8")
    print("saved to profile.md; jobs that were waiting for this answer will be retried on the next run.")
    return 0


def cmd_login(a, root: Path) -> int:
    from .reach.mcp_client import McpUnavailable, login_command  # noqa: PLC0415

    cfg = cfgmod.load(root / "config.json")
    sessions = resolve(root, cfg["paths"]["sessions_dir"])
    sessions.mkdir(parents=True, exist_ok=True)
    if getattr(a, "apply_browser", False):
        from .apply.browser import sign_in_interactively  # noqa: PLC0415

        sign_in_interactively(sessions)
        return 0
    try:
        cmd = login_command(sessions)
    except McpUnavailable as ex:
        print(f"cannot start the LinkedIn server: {ex}")
        return 1
    if a.status:
        cmd = [c for c in cmd if c != "--login"] + ["--status"]
    print("A browser window opens: sign in to LinkedIn YOURSELF. This tool never sees your password.\n")
    return subprocess.call(cmd)


def cmd_providers(a, root: Path) -> int:
    problems = loader.load_plugins(root)
    cfgmod.load_dotenv(root / ".env")
    try:
        enabled = cfgmod.load(root / "config.json")["sources"]["enabled"]
    except cfgmod.ConfigError:
        enabled = []
    for name in provbase.known():
        print(f"{'*' if name in enabled else ' '} {name}")
    print("\n* = enabled in config.json. Your own sources go in ./plugins/ (job-radar new-provider NAME).")
    for p in problems:
        print(f"problem: {p}")
    return 1 if problems else 0


def cmd_new_provider(a, root: Path) -> int:
    try:
        path = loader.scaffold(root, a.name)
    except FileExistsError as ex:
        print(f"already exists: {ex}")
        return 1
    print(f"created {path.relative_to(root)}. Edit it, then add its name to sources.enabled in config.json.")
    return 0


def cmd_privacy_check(a, root: Path) -> int:
    findings = privacy.scan(root, a.term)
    print(privacy.format_report(findings))
    return 1 if findings else 0


def cmd_templates(a, root: Path) -> int:
    """Copy the default templates to ./templates so you can edit them (your copies win over the defaults)."""
    src = Path(__file__).parent / "default_templates"
    dst = root / "templates"
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            target = dst / f.relative_to(src)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, target)
            n += 1
    print(f"copied {n} template(s) to templates/ (edit them; existing files were kept).")
    return 0


def cmd_reset_session(a, root: Path) -> int:
    cfg = cfgmod.load(root / "config.json")
    d = resolve(root, cfg["paths"]["sessions_dir"])
    if d.exists():
        shutil.rmtree(d)
    print(f"removed {d.relative_to(root)}; run 'job-radar login' to sign in again.")
    return 0


def cmd_schedule(a, root: Path) -> int:
    from . import schedule  # noqa: PLC0415

    cfg = cfgmod.load(root / "config.json")
    times = cfg["schedule"]["times"]
    if a.kind == "cron":
        print(schedule.cron(root, times))
    elif a.kind == "systemd":
        for name, text in schedule.systemd(root, times).items():
            print(f"# ~/.config/systemd/user/{name}\n{text}")
    else:
        print(schedule.windows(root, times))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="job-radar", description="Safe-by-default job-search agent.")
    ap.add_argument("--version", action="version", version=f"job-radar {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init", help="create config.json, profile.md and .env, then run doctor")
    s.add_argument("--yes", action="store_true", help="no questions: use the example values")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("doctor", help="check dependencies, config, profile, session, email")
    s.add_argument("--no-probe", action="store_true", help="do not start the LinkedIn server")
    s = sub.add_parser("run", help="run the pipeline once")
    s.add_argument("--dry-run", action="store_true", help="force dry run (nothing sent, applied or connected)")
    s = sub.add_parser("digest", help="rebuild output/digest.html")
    s.add_argument("--send", action="store_true")
    s = sub.add_parser("coach", help="suggest config changes (never safety settings)")
    s.add_argument("--apply", metavar="ID")
    s = sub.add_parser("eval", help="score synthetic cases and report regressions")
    s.add_argument("--cases", default=None)
    sub.add_parser("status")
    s = sub.add_parser("answer", help="save an answer for application questions into profile.md")
    s.add_argument("question")
    s.add_argument("answer")
    s = sub.add_parser("login", help="sign in to LinkedIn through the MCP server's own login")
    s.add_argument("--status", action="store_true")
    s.add_argument("--apply-browser", action="store_true", help="sign in for the experimental Easy Apply browser")
    sub.add_parser("reset-session", help="delete the local LinkedIn session folder")
    sub.add_parser("templates", help="copy the default templates to ./templates so you can edit them")
    sub.add_parser("providers", help="list available sources (built in and from ./plugins)")
    s = sub.add_parser("new-provider", help="create ./plugins/NAME.py to add your own source")
    s.add_argument("name")
    s = sub.add_parser("privacy-check", help="scan this folder for personal data before you publish it")
    s.add_argument("--term", action="append", default=[], help="extra word to look for (name, handle...); repeatable")
    s = sub.add_parser("schedule", help="print cron / systemd / Windows scheduling snippets")
    s.add_argument("kind", choices=["cron", "systemd", "windows"])
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = project_root()
    handler = {"init": cmd_init, "doctor": cmd_doctor, "run": cmd_run, "digest": cmd_digest, "coach": cmd_coach,
               "eval": cmd_eval, "status": cmd_status, "answer": cmd_answer, "login": cmd_login,
               "reset-session": cmd_reset_session, "schedule": cmd_schedule, "providers": cmd_providers,
               "new-provider": cmd_new_provider, "templates": cmd_templates, "privacy-check": cmd_privacy_check}[args.cmd]
    try:
        return handler(args, root)
    except (cfgmod.ConfigError, profmod.ProfileError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
