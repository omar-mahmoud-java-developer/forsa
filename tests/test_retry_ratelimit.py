# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
import random

import pytest

from forsa.retry import RateLimiter, RetryPolicy, call_with_retry


def test_retry_then_success():
    n, sleeps = {"c": 0}, []

    def f():
        n["c"] += 1
        if n["c"] < 3:
            raise OSError("x")
        return "ok"

    assert call_with_retry(f, RetryPolicy(3, 1, 2), sleeps.append) == "ok"
    assert sleeps == [1, 2]


def test_retry_gives_up():
    with pytest.raises(OSError):
        call_with_retry(lambda: (_ for _ in ()).throw(OSError("x")), RetryPolicy(2, 0), lambda s: None)


def test_rate_limiter_random_delay_and_caps():
    slept = []
    rl = RateLimiter(5, 20, {"apply": 2}, sleep=slept.append, rng=random.Random(1))
    assert rl.wait() == 0.0  # first action is not delayed
    d = rl.wait()
    assert 5 <= d <= 20 and slept == [d]
    assert rl.allowed("apply", 0) and rl.allowed("apply", 1) and not rl.allowed("apply", 2)
    rl.record("apply")
    assert not rl.allowed("apply", 2)
