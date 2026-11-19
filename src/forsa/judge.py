# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Judge: an LLM second opinion on borderline jobs. ADVICE ONLY.

It never changes a score, a tier or any action. The model has no tools; the job text is untrusted data, fenced, and
the answer is validated (fixed vocabulary, short reason, no placeholders) before it is stored."""

from __future__ import annotations

import json
import re

from . import llm as llmmod
from .templating import load

FITS = ("yes", "maybe", "no")


def parse_verdict(text: str | None) -> tuple[str, str] | None:
    """(fit, reason) from the model's answer, or None when it is not a valid verdict."""
    if not text:
        return None
    m = re.search(r"\{.*?\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    fit = str(d.get("fit", "")).strip().lower()
    reason = " ".join(str(d.get("reason", "")).split())[:200]
    if fit not in FITS or llmmod.validate_text(reason or "ok", 40):
        return None
    return fit, reason


def pick(store, cfg: dict, limit: int) -> list[dict]:
    """Borderline jobs (stretch up to just below the apply threshold) with a description and no verdict yet."""
    lo = cfg["scoring"]["thresholds"]["stretch"]
    hi = cfg["scoring"]["thresholds"]["best"]
    todo = [j for j in store.jobs(min_score=lo) if j["score"] <= hi + 10 and (j["description"] or "").strip()
            and store.judge(j["id"]) is None]
    return todo[:limit]


def run(root, cfg, profile_block: str, job_block, store, llm, limit: int) -> tuple[int, list[str]]:
    """Judge up to `limit` jobs. Returns (judged, problems)."""
    tpl = load(root, "prompts/judge.md")
    judged, problems = 0, []
    for j in pick(store, cfg, limit):
        prompt = tpl.replace("{profile}", profile_block).replace("{job}", job_block(j))
        try:
            text = llm.complete(prompt, max_tokens=200)
        except llmmod.LLMError as ex:
            problems.append(f"judge: FAILED ({ex})")
            break
        if text is None:  # call budget used up
            break
        v = parse_verdict(text)
        if v is None:
            problems.append(f"judge: unusable answer for {j['id']}")
            continue
        store.set_judge(j["id"], *v)
        judged += 1
    return judged, problems
