# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
import json

from job_radar import pipeline
from job_radar.apply.forms import FormField
from job_radar.providers import base as pb
from job_radar.providers import demo  # noqa: F401
from job_radar.store import Store

from .test_runner import FakeDriver


def _run(root, cfg, profile, store, **kw):
    return pipeline.run(root, cfg, profile, store, [pb.create("demo")], sleep=lambda s: None, **kw)


def test_dry_run_default_end_to_end(root, cfg, profile, store):
    res = _run(root, cfg, profile, store)
    assert res.dry_run and res.new_jobs == 5 and not res.applications and not res.connects
    assert (root / "output" / "digest.html").exists()
    assert "DRY RUN" in (root / "output" / "digest.html").read_text()
    assert res.digest_status.startswith("not sent")
    assert list((root / "output" / "drafts").glob("cover-*.md"))  # drafts only, nothing sent


def test_second_run_keeps_state_and_new_count(root, cfg, profile, tmp_path):
    p = tmp_path / "s.sqlite"
    assert _run(root, cfg, profile, Store(p)).new_jobs == 5
    assert _run(root, cfg, profile, Store(p)).new_jobs == 0  # same jobs: persisted, not re-created


def test_cli_flag_cannot_turn_dry_run_off(root, cfg, profile, store):
    cfg["safety"]["auto_apply"] = True
    res = _run(root, cfg, profile, store, dry_run=False)
    assert res.dry_run is True


def test_apply_dry_run_records_nothing_real(root, cfg, profile, store):
    cfg["safety"]["auto_apply"] = True
    res = _run(root, cfg, profile, store)
    assert res.applications and all("would apply" in a["status"] for a in res.applications)
    assert store.count_today("apply") == 0


def test_live_apply_respects_daily_cap_and_attempts(root, cfg, profile, store):
    cfg.update()
    cfg["safety"].update(dry_run=False, auto_apply=True, max_applications_per_day=1)
    made = []

    def factory():
        d = FakeDriver([([FormField("text", "Notice period", True)], "submit")])
        made.append(d)
        return d

    r1 = _run(root, cfg, profile, store, driver_factory=factory)
    assert sum(a["status"] == "applied" for a in r1.applications) == 1
    r2 = _run(root, cfg, profile, store, driver_factory=factory)  # cap reached for today
    assert not any(a["status"] == "applied" for a in r2.applications)
    assert len(made) == 1


def test_missing_answer_skips_and_flags(root, cfg, profile, store):
    cfg["safety"].update(dry_run=False, auto_apply=True)
    cfg["scoring"]["thresholds"]["apply_min"] = 10
    factory = lambda: FakeDriver([([FormField("text", "Years with Kafka?", True)], "submit")])  # noqa: E731
    r = _run(root, cfg, profile, store, driver_factory=factory)
    assert not any(a["status"] == "applied" for a in r.applications)
    assert store.flags() and "needs your answer" in store.flags()[0]["reason"]
    assert "needs your answer" in (root / "output" / "digest.html").read_text()


def test_digest_goes_only_to_yourself_and_only_when_configured(cfg, monkeypatch):
    from job_radar import notify

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=0):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def login(self, u, p):
            pass

        def send_message(self, msg):
            sent.append(msg["To"])

    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)
    assert notify.send_digest(cfg, "<p>x</p>", dry_run=True).startswith("not sent (notify.mode")
    cfg["notify"].update(mode="email", email_to="me@example.com")
    assert "not set" in notify.send_digest(cfg, "<p>x</p>", dry_run=True)
    monkeypatch.setenv("JOB_RADAR_SMTP_USER", "u@example.com")
    monkeypatch.setenv("JOB_RADAR_SMTP_PASSWORD", "pw")
    assert notify.send_digest(cfg, "<p>x</p>", dry_run=True) == "sent"  # allowed in dry-run: it is just you
    assert sent == ["me@example.com"]  # the only possible recipient is notify.email_to


def test_failing_source_does_not_stop_run(root, cfg, profile, store):
    class Bad(pb.Provider):
        name = "bad"

        def search(self, c):
            raise RuntimeError("boom")

    res = pipeline.run(root, cfg, profile, store, [Bad(), pb.create("demo")], sleep=lambda s: None)
    assert any("bad: FAILED" in s for s in res.steps) and res.new_jobs == 5


def test_last_run_recorded(root, cfg, profile, store):
    _run(root, cfg, profile, store)
    assert json.loads(json.dumps(store.last_run()["summary"]))["new_jobs"] == 5
