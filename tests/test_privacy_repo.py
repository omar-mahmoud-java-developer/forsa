# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Guards the public repo: no personal data, absolute home paths or real-looking secrets in tracked sources."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "output", "data", "logs", "node_modules"}
TEXT = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".html", ".txt", ".cfg", ".example", ".service", ".timer"}


def files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and (p.suffix in TEXT or p.name in {
                ".env.example", ".gitignore", "LICENSE", "NOTICE", "Dockerfile", "THIRD_PARTY_LICENSES"}):
            yield p


def test_no_absolute_home_paths():
    pat = re.compile(r"(?<![\w.])/(home|Users)/[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\")
    bad = [str(p.relative_to(ROOT)) for p in files()
           if p.name != "test_privacy_repo.py" and pat.search(p.read_text(errors="ignore"))]
    assert bad == []


def test_only_placeholder_emails():
    pat = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[a-z]{2,})")
    ok = {"example.com", "example.org", "users.noreply.github.com"}
    bad = []
    for p in files():
        for m in pat.finditer(p.read_text(errors="ignore")):
            if m.group(1) not in ok:
                bad.append(f"{p.relative_to(ROOT)}: {m.group(0)}")
    assert bad == []


def test_examples_in_sync_with_packaged_copies():
    pkg = ROOT / "src" / "forsa" / "examples"
    for name in ("config.example.json", "profile.example.md", ".env.example"):
        assert (ROOT / name).read_text() == (pkg / name).read_text(), name


def test_gitignore_covers_secrets():
    gi = (ROOT / ".gitignore").read_text()
    for needed in (".env", "data/", "sessions/", "logs/", "output/", "*report*.html", "job-radar-report/", "cookies"):
        assert needed in gi


def test_every_source_file_has_spdx_header():
    missing = []
    for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").glob("*.py")):
        head = p.read_text(encoding="utf-8")[:300]
        if "SPDX-License-Identifier:" not in head:
            missing.append(str(p.relative_to(ROOT)))
    assert missing == []
