# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Application algorithm, independent of any browser. A FormDriver does the clicking; this decides what to do."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import Job
from ..profile import Profile
from .answers import answer
from .forms import FormField, is_filled, missing_required, validation_errors

MAX_STEPS = 12


class FormDriver(Protocol):
    def open(self, job: Job) -> None: ...
    def fields(self) -> list[FormField]: ...
    def fill(self, f: FormField, value: str) -> None: ...
    def advance(self) -> str: ...  # clicks the primary button; returns its name: "next" | "review" | "submit"
    def primary_button(self) -> str: ...
    def discard(self) -> None: ...
    def confirmed(self) -> bool: ...


@dataclass
class ApplyResult:
    ok: bool | None  # True sent, False failed/skipped, None = dry run (stopped before submit)
    reason: str = ""
    question: str = ""  # set when the profile had no answer: the digest asks the user


def run_application(driver: FormDriver, job: Job, profile: Profile, dry_run: bool) -> ApplyResult:
    driver.open(job)
    for _ in range(MAX_STEPS):
        fields = driver.fields()
        for f in fields:
            if f.kind == "file" or (is_filled(f) and f.kind != "checkbox"):
                continue
            if f.kind == "checkbox":
                continue  # consent boxes are never ticked on the user's behalf
            a = answer(f.label, f.kind, f.options, profile)
            if a is None:
                if f.required:
                    driver.discard()
                    return ApplyResult(False, "missing answer in profile", question=f.label[:120])
                continue
            driver.fill(f, a.value)
        fields = driver.fields()
        if any(f.kind == "checkbox" and f.required and not f.checked for f in fields):
            driver.discard()
            return ApplyResult(False, "required checkbox needs the user", question="required checkbox")
        gaps = missing_required(fields)
        if gaps:
            driver.discard()
            return ApplyResult(False, "missing answer in profile", question=gaps[0].label[:120])
        button = driver.primary_button()
        if button == "submit":
            if dry_run:
                driver.discard()
                return ApplyResult(None, "dry run: every step filled, stopped before submit")
            driver.advance()
            return ApplyResult(True, "") if driver.confirmed() else ApplyResult(False, "no confirmation after submit")
        driver.advance()
        errors = validation_errors(driver.fields())
        if errors:
            driver.discard()
            return ApplyResult(False, f"form rejected a field: {errors[0].label[:80]}")
    driver.discard()
    return ApplyResult(False, "too many steps")
