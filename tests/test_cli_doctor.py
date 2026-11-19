# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
from job_radar import cli, doctor
from job_radar.config import load


def test_init_yes_creates_safe_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JOB_RADAR_HOME", str(tmp_path))
    assert cli.main(["init", "--yes"]) == 0
    cfg = load(tmp_path / "config.json")
    assert cfg["safety"]["dry_run"] and not cfg["safety"]["auto_apply"]
    assert (tmp_path / ".env").exists() and "[ OK ] config" in capsys.readouterr().out
    assert cli.main(["init", "--yes"]) == 1  # refuses to overwrite


def test_run_and_status_and_answer(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JOB_RADAR_HOME", str(tmp_path))
    cli.main(["init", "--yes"])
    assert cli.main(["run", "--dry-run"]) == 0
    assert cli.main(["status"]) == 0
    assert cli.main(["answer", "Do you speak Klingon", "No"]) == 0
    assert "do you speak klingon: No" in (tmp_path / "profile.md").read_text()
    assert cli.main(["eval"]) == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_doctor_reports_each_problem_with_fix(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_HOME", str(tmp_path))
    checks = doctor.run_all(tmp_path)
    cfg_check = next(c for c in checks if c.name == "config")
    assert cfg_check.status == "error" and "job-radar init" in cfg_check.fix
    assert doctor.exit_code(checks) == 1
    assert "fix:" in doctor.format_report(checks)


def test_doctor_email_needs_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RADAR_HOME", str(tmp_path))
    monkeypatch.delenv("JOB_RADAR_SMTP_USER", raising=False)
    cli.main(["init", "--yes"])
    p = tmp_path / "config.json"
    import json
    d = json.loads(p.read_text())
    d["notify"].update(mode="email", email_to="me@example.com")
    p.write_text(json.dumps(d))
    c = next(c for c in doctor.run_all(tmp_path) if c.name == "email")
    assert c.status == "error" and ".env" in c.fix


def test_path_escape_rejected(tmp_path):
    import pytest

    from job_radar.paths import resolve
    with pytest.raises(ValueError):
        resolve(tmp_path, "../outside")


def test_schedule_snippets(tmp_path):
    from job_radar import schedule
    assert "OnCalendar=*-*-* 09:00:00" in schedule.systemd(tmp_path, ["09:00"])["job-radar.timer"]
    assert "schtasks" in schedule.windows(tmp_path, ["09:00"])
    assert schedule.cron(tmp_path, ["17:30"]).count("30 17 * * *") == 1
