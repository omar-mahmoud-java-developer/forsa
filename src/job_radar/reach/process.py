# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Agent Eyes
# Derived from Agent Reach v1.5.0 (https://github.com/Panniantong/Agent-Reach),
# upstream commit f65526cbaaad3879473acc1ba6dbefd195caf2be, file agent_reach/utils/process.py.
# Modifications Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]: none (copied unchanged except this header).
# To sync with upstream: diff this file against the path above at that commit (see NOTICE).
"""Subprocess helpers for consistent cross-platform text handling."""

from __future__ import annotations

import os
from collections.abc import Mapping

UTF8_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}


def utf8_subprocess_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return an environment that forces Python child processes into UTF-8 mode."""
    env = dict(base or os.environ)
    env.update(UTF8_ENV)
    return env


def mcporter_utf8_env_args() -> list[str]:
    """Return mcporter --env arguments for UTF-8 Python stdio servers."""
    args = []
    for key, value in UTF8_ENV.items():
        args.extend(["--env", f"{key}={value}"])
    return args
