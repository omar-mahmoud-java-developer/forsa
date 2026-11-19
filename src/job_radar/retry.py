# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Shared retries, timeouts and rate limits: the one place every network/LinkedIn action goes through."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class CircuitOpen(RuntimeError):
    """Too many failures in a row: stop calling the backend for this run."""


@dataclass
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 2.0
    factor: float = 2.0
    max_delay: float = 60.0


def call_with_retry(fn: Callable[[], T], policy: RetryPolicy | None = None,
                    sleep: Callable[[float], None] = time.sleep,
                    retry_on: tuple[type[BaseException], ...] = (Exception,)) -> T:
    """Run fn, retrying with exponential backoff. The last exception is re-raised."""
    policy = policy or RetryPolicy()
    delay = policy.base_delay
    for attempt in range(1, policy.attempts + 1):
        try:
            return fn()
        except retry_on:
            if attempt == policy.attempts:
                raise
            sleep(min(delay, policy.max_delay))
            delay *= policy.factor
    raise AssertionError("unreachable")


class RateLimiter:
    """Random delay between actions plus a per-day cap, per action name."""

    def __init__(self, min_delay: float, max_delay: float, caps: dict[str, int] | None = None,
                 sleep: Callable[[float], None] = time.sleep, rng: random.Random | None = None):
        self.min_delay, self.max_delay = min_delay, max_delay
        self.caps = caps or {}
        self.counts: dict[str, int] = {}
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._last = False

    def allowed(self, action: str, already_today: int = 0) -> bool:
        cap = self.caps.get(action)
        return cap is None or already_today + self.counts.get(action, 0) < cap

    def wait(self) -> float:
        """Sleep a random time (skipped before the very first action)."""
        if not self._last:
            self._last = True
            return 0.0
        d = self._rng.uniform(self.min_delay, self.max_delay)
        self._sleep(d)
        return d

    def record(self, action: str) -> None:
        self.counts[action] = self.counts.get(action, 0) + 1


class CircuitBreaker:
    """Opens after `threshold` consecutive failures."""

    def __init__(self, threshold: int = 3):
        self.threshold, self.failures = threshold, 0

    def ok(self) -> None:
        self.failures = 0

    def fail(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            raise CircuitOpen(f"{self.failures} failures in a row")
