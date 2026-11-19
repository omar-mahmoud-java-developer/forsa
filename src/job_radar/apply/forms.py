# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Application-form field detection.

A field is REQUIRED only when the page says so through attributes (`required`, `aria-required`) and it is
still empty. Label text such as "Please enter your notice period" is never inspected, so it can never be
mistaken for an error message (the bug of the original project).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FormField:
    kind: str  # text | textarea | select | radio | checkbox | file
    label: str
    required: bool = False  # from the html `required` / aria-required attribute
    value: str = ""
    checked: bool = False
    options: list[str] = field(default_factory=list)
    invalid: bool = False  # aria-invalid="true"
    handle: object = None  # driver-specific element handle


def is_filled(f: FormField) -> bool:
    if f.kind == "checkbox":
        return f.checked
    if f.kind == "file":
        return True  # resume upload is handled separately by the driver
    v = (f.value or "").strip()
    return bool(v) and v.lower() not in {"select an option", "select", "-"}


def missing_required(fields: list[FormField]) -> list[FormField]:
    """Required fields that are still empty."""
    return [f for f in fields if f.required and not is_filled(f)]


def validation_errors(fields: list[FormField]) -> list[FormField]:
    """Fields the page itself marked invalid after an attempt to continue."""
    return [f for f in fields if f.invalid]
