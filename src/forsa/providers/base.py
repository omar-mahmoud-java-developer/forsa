# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Provider interface: add a new job source by implementing Provider and registering it. No core changes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from ..models import Job


class Provider(ABC):
    """A source of jobs. Providers only READ; they never apply or message anyone."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def search(self, search_cfg: dict) -> list[Job]:
        """Return jobs for the configured search. Raise on hard failure (the pipeline logs it and goes on)."""

    def details(self, job: Job) -> Job:
        """Optionally fill in the full description. Default: unchanged."""
        return job

    def search_people(self, keywords: str, location: str = "") -> list[dict]:
        """Recruiter/hiring-contact cards (read-only). Providers without people search return nothing."""
        return []

    def connect(self, username: str, note: str | None = None) -> bool:
        """Send a connection request. Only called when safety allows it; most providers do not support it."""
        raise NotImplementedError(f"{self.name} does not support connect")

    def check(self) -> tuple[str, str]:
        """(status, message) for `doctor`: status is ok / warn / off / error."""
        return "ok", "built in"


_REGISTRY: dict[str, Callable[..., Provider]] = {}


def register(name: str):
    def deco(factory):
        _REGISTRY[name] = factory
        return factory
    return deco


def create(name: str, **kw) -> Provider:
    if name not in _REGISTRY:
        raise KeyError(f"unknown source '{name}' (known: {', '.join(sorted(_REGISTRY))})")
    return _REGISTRY[name](**kw)


def known() -> list[str]:
    return sorted(_REGISTRY)
