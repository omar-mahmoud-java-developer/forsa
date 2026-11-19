# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Scheduling snippets for cron, systemd user timers and Windows Task Scheduler. Paths are filled in at print time."""

from __future__ import annotations

import sys
from pathlib import Path


def _cmd(root: Path) -> list[str]:
    return [sys.executable, "-m", "job_radar", "run"]


def cron(root: Path, times: list[str]) -> str:
    lines = ["# Job Radar (paste into: crontab -e)"]
    for t in times:
        h, m = t.split(":")
        lines.append(f"{int(m)} {int(h)} * * * cd '{root}' && '{sys.executable}' -m job_radar run >> logs/cron.log 2>&1")
    return "\n".join(lines) + "\n"


def systemd(root: Path, times: list[str]) -> dict[str, str]:
    service = f"""[Unit]
Description=Job Radar run

[Service]
Type=oneshot
WorkingDirectory={root}
ExecStart={sys.executable} -m job_radar run
"""
    cal = "\n".join(f"OnCalendar=*-*-* {t}:00" for t in times)
    timer = f"""[Unit]
Description=Job Radar schedule

[Timer]
{cal}
Persistent=true

[Install]
WantedBy=timers.target
"""
    return {"job-radar.service": service, "job-radar.timer": timer}


def windows(root: Path, times: list[str]) -> str:
    lines = ["REM Job Radar: run these once in a Command Prompt"]
    for i, t in enumerate(times, 1):
        lines.append(f'schtasks /Create /SC DAILY /ST {t} /TN "JobRadar{i}" /TR "cmd /c cd /d {root} && '
                     f'{sys.executable} -m job_radar run" /F')
    return "\n".join(lines) + "\n"
