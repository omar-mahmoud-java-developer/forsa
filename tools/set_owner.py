# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Maintainer helper: fill in the copyright holder and GitHub handle before publishing.

    python tools/set_owner.py --name "Jane Doe" --handle jane-doe [--year 2026] [--dry-run]

Replaces the placeholders "[YOUR NAME OR GITHUB HANDLE]" (copyright) and "[GITHUB_HANDLE]" (URLs) in every
text file of this repository. Run it once, review `git diff`, then commit.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

COPYRIGHT = "[YOUR NAME OR GITHUB HANDLE]"
HANDLE = "[GITHUB_HANDLE]"
ROOT = Path(__file__).resolve().parent.parent


def files() -> list[Path]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
        return [ROOT / p for p in out]
    except (OSError, subprocess.SubprocessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="copyright holder: your name or GitHub handle")
    ap.add_argument("--handle", required=True, help="GitHub user or organisation for repository URLs")
    ap.add_argument("--year", default="2026")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    changed = 0
    for p in files():
        if not p.is_file() or p.name == "set_owner.py":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = text.replace(COPYRIGHT, a.name).replace(HANDLE, a.handle)
        new = new.replace("Copyright (c) 2026", f"Copyright (c) {a.year}")
        if new != text:
            changed += 1
            print(("would change " if a.dry_run else "updated ") + str(p.relative_to(ROOT)))
            if not a.dry_run:
                p.write_text(new, encoding="utf-8")
    print(f"{changed} file(s). Review with: git diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
