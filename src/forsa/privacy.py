# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""`forsa privacy-check`: find personal data before you publish or share a folder.

Looks for e-mail addresses (except example domains), absolute home paths, secret-looking tokens and any extra
terms you give it (your name, handle, company...). Terms are only compared in memory, never written anywhere.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".html", ".txt", ".cfg", ".ini", ".service", ".timer",
                 ".cmd", ".sh", ".example", ".tpl", ""}
OK_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "users.noreply.github.com"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
HOME_PATH = re.compile(r"(?<![\w.])/(?:home|Users)/[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\[A-Za-z0-9_.-]+")
TOKENS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"), re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), re.compile(r"\bxox[abp]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(app[_-]?password|api[_-]?key|secret|token)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_-]{16,}"),
)


@dataclass
class Finding:
    path: str
    line: int
    kind: str
    sample: str  # masked


def _mask(s: str) -> str:
    return s[:2] + "****" if len(s) > 4 else "****"


def tracked_files(root: Path) -> list[Path]:
    """Files git would commit (respects .gitignore); falls back to a directory walk when not a git repo."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
        return [root / p for p in out if (root / p).is_file()]
    except (OSError, subprocess.SubprocessError):
        return [p for p in root.rglob("*") if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS)]


def scan(root: Path, terms: list[str] | None = None) -> list[Finding]:
    terms = [t.lower() for t in (terms or []) if t.strip()]
    found: list[Finding] = []
    for p in tracked_files(root):
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {"LICENSE", "NOTICE", "Dockerfile"}:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(p.relative_to(root))
        for n, line in enumerate(text.splitlines(), 1):
            for m in EMAIL.finditer(line):
                if m.group(1).lower() not in OK_EMAIL_DOMAINS:
                    found.append(Finding(rel, n, "email", _mask(m.group(0))))
            for m in HOME_PATH.finditer(line):
                found.append(Finding(rel, n, "absolute home path", _mask(m.group(0))))
            for pat in TOKENS:
                m = pat.search(line)
                if m:
                    found.append(Finding(rel, n, "secret-looking token", _mask(m.group(0))))
            low = line.lower()
            for t in terms:
                if t in low:
                    found.append(Finding(rel, n, "your term", _mask(t)))
    return found


def format_report(findings: list[Finding]) -> str:
    if not findings:
        return "privacy-check: nothing found."
    lines = [f"privacy-check: {len(findings)} finding(s) (values are masked)"]
    lines += [f"  {f.path}:{f.line}  {f.kind}  {f.sample}" for f in findings[:200]]
    return "\n".join(lines)
