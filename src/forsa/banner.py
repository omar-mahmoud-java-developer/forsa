# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""The line every user sees before Forsa starts: project name, author and (optionally) a motto.

Printed to stderr so that scripts reading stdout are not affected."""

from __future__ import annotations

import sys

PROJECT = "Forsa"
PROJECT_AR = "فرصة"  # "opportunity"
AUTHOR = "Omar Qenawy"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/omar-qenawy12/"
TAGLINE = ""  # one sentence shown under the name; set by the author


def text() -> str:
    lines = ["", f"  {PROJECT} · {PROJECT_AR}", f"  Created by {AUTHOR} · {AUTHOR_LINKEDIN}"]
    if TAGLINE:
        lines.append(f"  {TAGLINE}")
    lines.append("")
    return "\n".join(lines)


def show(file=None) -> None:
    print(text(), file=file or sys.stderr)
