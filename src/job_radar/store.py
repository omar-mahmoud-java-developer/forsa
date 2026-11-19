# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""SQLite state store. One file, schema-versioned, persists between runs (nothing is wiped on a new run)."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT, company TEXT, location TEXT, url TEXT,
  description TEXT, score INTEGER, tier TEXT, why TEXT, easy_apply INTEGER DEFAULT 0,
  first_seen TEXT, last_seen TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, kind TEXT NOT NULL, at TEXT NOT NULL,
  ok INTEGER NOT NULL, dry_run INTEGER NOT NULL, note TEXT
);
CREATE INDEX IF NOT EXISTS attempts_job ON attempts(job_id, kind);
CREATE TABLE IF NOT EXISTS flags (
  job_id TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (job_id, reason)
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, dry_run INTEGER NOT NULL, summary TEXT
);
"""


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        row = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            self.db.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        elif int(row["value"]) > SCHEMA_VERSION:
            raise RuntimeError("the database was created by a newer job-radar version")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # ---- jobs
    def upsert_job(self, job: dict[str, Any]) -> bool:
        """Insert or update a job. Returns True if it is new. Attempts/flags are never touched."""
        t = now()
        old = self.db.execute("SELECT first_seen FROM jobs WHERE id=?", (job["id"],)).fetchone()
        self.db.execute(
            """INSERT INTO jobs (id, source, title, company, location, url, description, score, tier, why,
                                 easy_apply, first_seen, last_seen, data)
               VALUES (:id,:source,:title,:company,:location,:url,:description,:score,:tier,:why,:easy_apply,:t,:t,:data)
               ON CONFLICT(id) DO UPDATE SET title=:title, company=:company, location=:location, url=:url,
                 description=:description, score=:score, tier=:tier, why=:why, easy_apply=:easy_apply,
                 last_seen=:t, data=:data""",
            {"id": job["id"], "source": job.get("source", ""), "title": job.get("title", ""),
             "company": job.get("company", ""), "location": job.get("location", ""), "url": job.get("url", ""),
             "description": job.get("description", ""), "score": job.get("score", 0), "tier": job.get("tier", "skip"),
             "why": job.get("why", ""), "easy_apply": int(bool(job.get("easy_apply"))), "t": t,
             "data": json.dumps(job.get("extra", {}))})
        self.db.commit()
        return old is None

    def get_job(self, job_id: str) -> dict | None:
        r = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(r) if r else None

    def jobs(self, min_score: int = 0, tier: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM jobs WHERE score>=?", [min_score]
        if tier:
            q += " AND tier=?"
            args.append(tier)
        return [dict(r) for r in self.db.execute(q + " ORDER BY score DESC, first_seen DESC", args)]

    # ---- attempts (the attempt limit lives here and is never pruned)
    def record_attempt(self, job_id: str, kind: str, ok: bool, dry_run: bool, note: str = "") -> None:
        self.db.execute("INSERT INTO attempts (job_id, kind, at, ok, dry_run, note) VALUES (?,?,?,?,?,?)",
                        (job_id, kind, now(), int(ok), int(dry_run), note))
        self.db.commit()

    def attempts(self, job_id: str, kind: str, real_only: bool = True) -> int:
        q = "SELECT COUNT(*) FROM attempts WHERE job_id=? AND kind=?"
        if real_only:
            q += " AND dry_run=0"
        return self.db.execute(q, (job_id, kind)).fetchone()[0]

    def succeeded(self, job_id: str, kind: str) -> bool:
        return self.db.execute("SELECT 1 FROM attempts WHERE job_id=? AND kind=? AND ok=1 AND dry_run=0",
                               (job_id, kind)).fetchone() is not None

    def count_today(self, kind: str) -> int:
        today = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
        return self.db.execute("SELECT COUNT(*) FROM attempts WHERE kind=? AND dry_run=0 AND at>=?",
                               (kind, today)).fetchone()[0]

    # ---- flags (shown in the digest: needs the user)
    def flag(self, job_id: str, reason: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO flags VALUES (?,?,?)", (job_id, reason, now()))
        self.db.commit()

    def flags(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT f.job_id, f.reason, f.at, j.title, j.company FROM flags f LEFT JOIN jobs j ON j.id=f.job_id "
            "ORDER BY f.at DESC")]

    def clear_flag(self, job_id: str, reason: str) -> None:
        self.db.execute("DELETE FROM flags WHERE job_id=? AND reason=?", (job_id, reason))
        self.db.commit()

    # ---- runs
    def add_run(self, dry_run: bool, summary: dict) -> int:
        cur = self.db.execute("INSERT INTO runs (at, dry_run, summary) VALUES (?,?,?)",
                              (now(), int(dry_run), json.dumps(summary)))
        self.db.commit()
        return int(cur.lastrowid or 0)

    def last_run(self) -> dict | None:
        r = self.db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        return None if r is None else {**dict(r), "summary": json.loads(r["summary"] or "{}")}
