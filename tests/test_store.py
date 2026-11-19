# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy

from forsa.store import Store


def row(i="a1", **kw):
    return {"id": i, "source": "t", "title": "T", "company": "C", "location": "L", "url": "u", "description": "d",
            "score": 80, "tier": "best", "why": "w", "easy_apply": True, **kw}


def test_state_persists_between_runs(tmp_path):
    p = tmp_path / "s.sqlite"
    s1 = Store(p)
    assert s1.upsert_job(row()) is True
    s1.record_attempt("a1", "apply", False, False, "x")
    s1.close()
    s2 = Store(p)  # a new run opens the same file: nothing is wiped
    assert s2.get_job("a1")["title"] == "T"
    assert s2.attempts("a1", "apply") == 1
    assert s2.upsert_job(row(title="T2")) is False  # known job: not new
    assert s2.attempts("a1", "apply") == 1  # upsert never resets attempts
    s2.close()


def test_dry_run_attempts_do_not_count(store):
    store.upsert_job(row())
    store.record_attempt("a1", "apply", False, True, "simulated")
    assert store.attempts("a1", "apply") == 0
    assert store.attempts("a1", "apply", real_only=False) == 1


def test_success_and_daily_count(store):
    store.upsert_job(row())
    store.record_attempt("a1", "apply", True, False)
    assert store.succeeded("a1", "apply") and store.count_today("apply") == 1


def test_flags(store):
    store.upsert_job(row())
    store.flag("a1", "needs answer")
    store.flag("a1", "needs answer")
    assert len(store.flags()) == 1
    store.clear_flag("a1", "needs answer")
    assert store.flags() == []


def test_old_jobs_keep_attempts(store):
    store.upsert_job(row())
    for _ in range(2):
        store.record_attempt("a1", "apply", False, False)
    store.db.execute("UPDATE jobs SET last_seen='2000-01-01T00:00:00Z'")
    assert store.attempts("a1", "apply") == 2  # nothing prunes attempts
