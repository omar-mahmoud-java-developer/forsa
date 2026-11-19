# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
from job_radar.pipeline import candidates_for_apply

from .test_store import row


def test_attempt_cap_blocks_candidate(store, cfg):
    store.upsert_job(row("j1"))
    assert [c["id"] for c in candidates_for_apply(store, cfg)] == ["j1"]
    for _ in range(cfg["safety"]["max_attempts_per_job"]):
        store.record_attempt("j1", "apply", False, False)
    assert candidates_for_apply(store, cfg) == []


def test_applied_job_is_never_retried(store, cfg):
    store.upsert_job(row("j1"))
    store.record_attempt("j1", "apply", True, False)
    assert candidates_for_apply(store, cfg) == []


def test_one_per_company_and_threshold(store, cfg):
    store.upsert_job(row("a", company="Same", score=90))
    store.upsert_job(row("b", company="Same", score=88))
    store.upsert_job(row("c", company="Other", score=10))
    assert [c["id"] for c in candidates_for_apply(store, cfg)] == ["a"]
