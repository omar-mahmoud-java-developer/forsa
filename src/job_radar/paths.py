# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Project paths. Everything is relative to the project root (or JOB_RADAR_HOME); no absolute paths in code."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """JOB_RADAR_HOME if set, otherwise the current working directory."""
    return Path(os.environ.get("JOB_RADAR_HOME") or Path.cwd()).resolve()


def resolve(root: Path, relative: str) -> Path:
    """Resolve a configured path under the project root; refuse paths that escape it."""
    p = (root / relative).resolve()
    if root != p and root not in p.parents:
        raise ValueError(f"path escapes the project root: {relative}")
    return p
