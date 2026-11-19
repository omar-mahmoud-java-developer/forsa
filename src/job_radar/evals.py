# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Eval suite: synthetic labeled cases. Fails (exit 1) when a case that should pass does not."""

from __future__ import annotations

import json
from pathlib import Path

from . import config as cfgmod
from . import profile as profmod
from .apply.answers import answer
from .models import Job
from .scoring import score_job

CASES = Path(__file__).parent / "eval_cases"


def main(root: Path, cases_dir: str | None = None) -> int:
    d = Path(cases_dir) if cases_dir else CASES
    ex = Path(__file__).parent / "examples"
    cfg = cfgmod.merge(__import__("copy").deepcopy(cfgmod.DEFAULTS), json.loads((ex / "config.example.json").read_text()))
    prof = profmod.parse((ex / "profile.example.md").read_text())
    failed = total = 0
    for c in json.loads((d / "jobs.json").read_text()):
        total += 1
        j = score_job(Job(**c["job"]), cfg)
        ok = j.tier == c["expect_tier"]
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} job {c['job']['id']}: tier {j.tier} (want {c['expect_tier']}) score {j.score}")
    for c in json.loads((d / "questions.json").read_text()):
        total += 1
        a = answer(c["label"], c.get("kind", "text"), c.get("options", []), prof)
        got = a.value if a else None
        ok = got == c["expect"]
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} question '{c['label'][:50]}': {got!r} (want {c['expect']!r})")
    print(f"\n{total - failed}/{total} cases passed")
    return 1 if failed else 0
