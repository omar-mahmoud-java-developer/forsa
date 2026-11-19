# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Tiny {placeholder} templating for cover letters, outreach notes and the digest. Missing values fail loudly."""

from __future__ import annotations

import re
from pathlib import Path

_PH = re.compile(r"\{([a-z_]+)\}")


class TemplateError(ValueError):
    pass


def render(template: str, values: dict[str, str]) -> str:
    missing = sorted({m for m in _PH.findall(template) if not str(values.get(m, "")).strip()})
    if missing:
        raise TemplateError(f"no value for: {', '.join(missing)}")
    return _PH.sub(lambda m: str(values[m.group(1)]), template)


def load(root: Path, name: str) -> str:
    """User copy in ./templates first, then the packaged default."""
    user = root / "templates" / name
    if user.exists():
        return user.read_text(encoding="utf-8")
    return (Path(__file__).parent / "default_templates" / name).read_text(encoding="utf-8")
