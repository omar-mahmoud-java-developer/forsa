# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""One run: fetch -> score -> advise -> drafts -> connect -> apply -> digest.

Reading and acting are separate steps. LLM steps only see untrusted text to write drafts/advice and have no
tools; every action (connect, apply, send) is decided by plain code from config, profile and the store.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import dashboard, mailbox, notify, recruiters
from . import llm as llmmod
from .apply.runner import FormDriver, run_application
from .config import env
from .models import Job
from .profile import Profile
from .providers.base import Provider
from .retry import CircuitOpen, RateLimiter
from .scoring import score_job
from .store import Store
from .templating import TemplateError, load, render

log = logging.getLogger("job_radar.pipeline")


@dataclass
class RunResult:
    dry_run: bool
    new_jobs: int = 0
    scored: int = 0
    drafts: int = 0
    connects: list[dict] = field(default_factory=list)
    applications: list[dict] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    digest_path: str = ""
    digest_status: str = ""


def candidates_for_apply(store: Store, cfg: dict) -> list[dict]:
    """Jobs to apply to: above the threshold, Easy Apply, not done, under the attempt cap; best first."""
    s = cfg["safety"]
    thr = cfg["scoring"]["thresholds"]["apply_min"]
    out, seen_companies = [], set()
    for j in store.jobs(min_score=thr):
        if not j["easy_apply"] or store.succeeded(j["id"], "apply"):
            continue
        if store.attempts(j["id"], "apply") >= s["max_attempts_per_job"]:
            continue
        key = (j["company"] or "").lower()
        if key and key in seen_companies:
            continue
        seen_companies.add(key)
        out.append(j)
    return out


def run(root: Path, cfg: dict, profile: Profile, store: Store, providers: list[Provider],
        dry_run: bool | None = None, driver_factory: Callable[[], FormDriver] | None = None,
        sleep: Callable[[float], None] | None = None, llm: llmmod.LLM | None = None,
        mail_reader: Callable[..., mailbox.MailResult] | None = None) -> RunResult:
    s = cfg["safety"]
    dry = s["dry_run"] if dry_run is None else dry_run
    if dry_run is False and s["dry_run"]:
        dry = True  # a CLI flag can never switch dry_run off; only the config file can
    res = RunResult(dry_run=dry)
    llm = llm or llmmod.LLM(cfg["llm"]["provider"], cfg["llm"]["model"], cfg["llm"]["max_calls_per_run"])
    limiter = RateLimiter(s["min_delay_seconds"], s["max_delay_seconds"], sleep=sleep or time.sleep)

    # 1) fetch (read-only) ------------------------------------------------------------------
    found: list[Job] = []
    for p in providers:
        try:
            jobs = p.search(cfg["search"])
        except CircuitOpen as ex:
            res.steps.append(f"{p.name}: stopped early ({ex})")
            continue
        except Exception as ex:  # noqa: BLE001 - one failing source must not stop the run
            res.steps.append(f"{p.name}: FAILED ({str(ex)[:100]})")
            log.warning("source %s failed: %s", p.name, ex)
            continue
        for j in jobs:
            known = store.get_job(j.id)
            if known is None or not known["description"]:
                try:
                    j = p.details(j)
                except Exception as ex:  # noqa: BLE001
                    log.warning("details failed for %s: %s", j.id, ex)
            elif known:
                j.description = j.description or known["description"]
            found.append(j)
        res.steps.append(f"{p.name}: {len(jobs)} jobs")
        res.backends += getattr(getattr(p, "channel", None), "used", []) or [p.name]

    # 1b) mailbox (read-only, opt-in): application updates + job-alert links ------------------------
    found += _read_mailbox(cfg, store, res, mail_reader)

    # 1c) recruiters (read-only search, opt-in) -----------------------------------------------------
    _find_recruiters(cfg, store, providers, limiter, res)

    # 2) score + persist --------------------------------------------------------------------
    for j in found:
        score_job(j, cfg)
        res.new_jobs += store.upsert_job(j.to_row())
        res.scored += 1

    # 3) advice + drafts (LLM, no tools; skipped when no provider) --------------------------------
    if llm.enabled:
        res.drafts += _drafts(root, cfg, profile, store, llm, res)
    res.drafts += _template_drafts(root, cfg, profile, store, llm.enabled)

    # 4) connect (only hiring contacts the provider found; off by default) -------------------------
    if s["auto_connect"]:
        _connect(root, cfg, profile, store, providers, dry, limiter, res)
    else:
        res.steps.append("connect: off (safety.auto_connect is false)")

    # 5) apply (off by default) -----------------------------------------------------------------
    if s["auto_apply"]:
        _apply(cfg, profile, store, dry, limiter, driver_factory, res)
    else:
        res.steps.append("apply: off (safety.auto_apply is false)")

    # 6) digest (written always; emailed only when allowed) ---------------------------------------
    html_text = notify.build_digest(root, store, profile, cfg, dry, res.backends, res.applications)
    res.digest_path = str(notify.write_digest(root, cfg, html_text))
    dashboard.write(root, cfg, store, profile.name)
    res.digest_status = notify.send_digest(cfg, html_text, dry)
    store.add_run(dry, {"new_jobs": res.new_jobs, "scored": res.scored, "steps": res.steps,
                        "applications": res.applications, "connects": res.connects, "backends": res.backends})
    return res


def _read_mailbox(cfg, store, res, mail_reader) -> list[Job]:
    """Read-only mailbox step. A failure is one line in the digest, never a crash."""
    mb = cfg["mailbox"]
    if not mb["enabled"]:
        return []
    user = env("JOB_RADAR_IMAP_USER") or env("JOB_RADAR_SMTP_USER")
    pw = env("JOB_RADAR_IMAP_PASSWORD") or env("JOB_RADAR_SMTP_PASSWORD")
    if not (user and pw):
        res.steps.append("mailbox: skipped (JOB_RADAR_IMAP_USER / PASSWORD not set)")
        return []
    try:
        out = (mail_reader or mailbox.read_mailbox)(cfg, user, pw, seen=store.mail_seen)
    except Exception as ex:  # noqa: BLE001 - IMAP down, login refused, odd mail
        res.steps.append(f"mailbox: FAILED ({str(ex)[:100]})")
        return []
    n = 0
    for u in out.updates:
        if u.msgid:
            store.mark_mail_seen(u.msgid)
        if u.status != "seen" and u.company:
            store.upsert_application(u.company, u.title or "(role not in email)", u.status, "email")
            n += 1
    jobs = [Job(a.id, "email-alert", a.title, url=f"https://www.linkedin.com/jobs/view/{a.id}/") for a in out.alert_jobs]
    extra = f", {out.ignored_unauthenticated} ignored (sender not authenticated)" if out.ignored_unauthenticated else ""
    res.steps.append(f"mailbox: {out.scanned} messages read-only, {n} application update(s), "
                     f"{len(jobs)} alert job(s){extra}")
    return jobs


def _find_recruiters(cfg, store, providers, limiter, res) -> None:
    rc = cfg["search"]["recruiters"]
    if not rc["enabled"]:
        return
    store.purge_people(int(rc["keep_days"]))
    queries = [(k, loc) for k in rc["keywords"] for loc in (rc["locations"] or [""])]
    added = 0
    for p in providers:
        if not hasattr(p, "search_people"):
            continue
        for kw, loc in queries[: max(1, int(rc["max_per_run"]))]:
            try:
                limiter.wait()
                cards = p.search_people(kw, loc)
            except Exception as ex:  # noqa: BLE001
                res.steps.append(f"recruiters ({p.name}): FAILED ({str(ex)[:80]})")
                break
            for c in cards:
                if recruiters.worth_keeping(c):
                    added += store.upsert_person(c)
    res.steps.append(f"recruiters: {added} new contact(s) (read-only search)")


def _profile_block(profile: Profile) -> str:
    skills = ", ".join(f"{k} ({v:g}y)" for k, v in profile.skills.items())
    return llmmod.fence(f"name: {profile.name}\nyears: {profile.get('years_experience')}\nskills: {skills}\n"
                        f"summary: {profile.summary}", "profile")


def _job_block(row: dict) -> str:
    return llmmod.fence(f"title: {row['title']}\ncompany: {row['company']}\nlocation: {row['location']}\n\n"
                        f"{(row['description'] or '')[:1500]}", "job")


def _drafts(root, cfg, profile, store, llm, res) -> int:
    n = 0
    tpl = load(root, "prompts/cover.md")
    for j in store.jobs(tier="best")[:3]:
        if (root / cfg["paths"]["output_dir"] / "drafts" / f"cover-{j['id']}.md").exists():
            continue
        prompt = tpl.replace("{profile}", _profile_block(profile)).replace("{job}", _job_block(j))
        try:
            text = llm.complete(prompt)
        except llmmod.LLMError as ex:
            res.steps.append(f"cover letters: FAILED ({ex})")
            return n
        why = llmmod.validate_text(text, 260)
        if why:
            res.steps.append(f"cover letter for {j['id']} rejected: {why}")
            continue
        notify.save_draft(root, cfg, "cover", j["id"], text or "")
        n += 1
    return n


def _template_drafts(root, cfg, profile, store, llm_enabled) -> int:
    """Rules-only drafts from templates/cover_letter.md (used when no LLM is configured)."""
    if llm_enabled:
        return 0
    n = 0
    tpl = load(root, "cover_letter.md")
    for j in store.jobs(tier="best")[:3]:
        values = {"company": j["company"], "role": j["title"], "name": profile.name, "email": profile.get("email"),
                  "summary": profile.summary.split("\n")[0] if profile.summary else "",
                  "skills": ", ".join(list(profile.skills)[:6])}
        try:
            text = render(tpl, values)
        except TemplateError as ex:
            store.flag(j["id"], f"cover letter template needs: {ex}")
            continue
        notify.save_draft(root, cfg, "cover", j["id"], text)
        n += 1
    return n


def _connect(root, cfg, profile, store, providers, dry, limiter, res) -> None:
    s = cfg["safety"]
    tpl = None
    for j in store.jobs(tier="best"):
        extra = json.loads(j.get("data") or "{}")
        contact = extra.get("hiring_contact")
        if not contact or store.succeeded(contact, "connect") or store.attempts(contact, "connect") >= 1:
            continue
        done = store.count_today("connect") + limiter.counts.get("connect", 0)
        if done >= s["max_connects_per_day"]:
            res.steps.append("connect: daily cap reached")
            break
        tpl = tpl or load(root, "outreach.md")
        note = render(tpl, {"first_name": (contact.split("-")[0] or "there"), "role": j["title"],
                            "company": j["company"], "headline": profile.get("headline", profile.name)})[:200]
        ok = True
        if not dry:
            limiter.wait()
            provider = next((p for p in providers if p.name == j["source"]), None)
            try:
                ok = bool(provider and provider.connect(contact, note))
            except Exception as ex:  # noqa: BLE001
                ok = False
                log.warning("connect failed: %s", ex)
        store.record_attempt(contact, "connect", ok, dry, note[:80])
        limiter.record("connect")
        res.connects.append({"to": contact, "ok": ok, "dry_run": dry})
    _connect_recruiters(root, cfg, profile, store, providers, dry, limiter, res)


def _connect_recruiters(root, cfg, profile, store, providers, dry, limiter, res) -> None:
    """Connection requests to discovered recruiters: only with auto_connect, capped, noted from the outreach template."""
    s = cfg["safety"]
    tpl = load(root, "outreach.md")
    provider = next((p for p in providers if hasattr(p, "connect") and p.name == "linkedin"), None)
    for person in store.people(status="new"):
        if store.count_today("connect") + limiter.counts.get("connect", 0) >= s["max_connects_per_day"]:
            res.steps.append("connect: daily cap reached")
            return
        first = (person["name"] or "").split()[0] if person["name"] else "there"
        job_title = (cfg["search"]["titles"] or ["roles like mine"])[0]
        try:
            note = render(tpl, {"first_name": first, "role": job_title, "company": "your team",
                                "headline": profile.get("headline", profile.name)})[:200]
        except TemplateError as ex:
            res.steps.append(f"connect (recruiters): template needs {ex}")
            return
        ok = True
        if not dry:
            limiter.wait()
            try:
                ok = bool(provider and provider.connect(person["username"], note))
            except Exception as ex:  # noqa: BLE001
                ok = False
                log.warning("connect failed: %s", ex)
            store.set_person_status(person["username"], "sent" if ok else "failed")
        store.record_attempt(person["username"], "connect", ok, dry, "recruiter")
        limiter.record("connect")
        res.connects.append({"to": person["username"], "ok": ok, "dry_run": dry})


def _apply(cfg, profile, store, dry, limiter, driver_factory, res) -> None:
    s = cfg["safety"]
    for j in candidates_for_apply(store, cfg):
        done_today = store.count_today("apply") + limiter.counts.get("apply", 0)
        if done_today >= s["max_applications_per_day"]:
            res.steps.append("apply: daily cap reached")
            break
        rec = {"title": j["title"], "company": j["company"], "status": ""}
        if driver_factory is None:
            rec["status"] = "would apply (dry run, no browser driver)" if dry else "skipped: no browser driver configured"
            if dry:
                store.record_attempt(j["id"], "apply", False, True, "simulated")
            res.applications.append(rec)
            continue
        limiter.wait()
        driver = driver_factory()
        from .models import Job as _Job  # noqa: PLC0415
        job = _Job(j["id"], j["source"], j["title"], j["company"], j["location"], j["url"], j["description"])
        try:
            r = run_application(driver, job, profile, dry)
        except Exception as ex:  # noqa: BLE001
            r_ok, why, q = False, f"error: {str(ex)[:80]}", ""
        else:
            r_ok, why, q = r.ok, r.reason, r.question
        store.record_attempt(j["id"], "apply", bool(r_ok), dry, why[:120])
        if r_ok and not dry:
            store.upsert_application(j["company"], j["title"], "applied", "apply", j["id"])
        if q:
            store.flag(j["id"], f"needs your answer: {q} (add it with: job-radar answer)")
        limiter.record("apply")
        rec["status"] = "applied" if r_ok else why or ("dry run" if r_ok is None else "failed")
        res.applications.append(rec)
