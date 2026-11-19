# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
import json

import pytest

from forsa import coach
from forsa.config import SAFETY_KEYS

from .test_store import row


@pytest.mark.parametrize(
    "path", [*SAFETY_KEYS, "safety", "safety.anything", "llm.provider", "notify.mode", "paths.data_dir"])
def test_coach_cannot_touch_safety_or_other_settings(path):
    with pytest.raises(coach.Refused):
        coach.check_allowed({"path": path, "op": "set_key", "key": "x", "value": 1})


def test_apply_writes_config_only(root):
    cfgp = root / "config.json"
    before = json.loads(cfgp.read_text())
    msg = coach.apply_suggestion(cfgp, {"id": "s", "path": "scoring.skills", "op": "set_key", "key": "rust", "value": 3})
    after = json.loads(cfgp.read_text())
    assert after["scoring"]["skills"]["rust"] == 3 and "not committed" in msg
    assert after["safety"] == before["safety"]


def test_refused_suggestion_leaves_file_untouched(root):
    cfgp = root / "config.json"
    before = cfgp.read_text()
    with pytest.raises(coach.Refused):
        coach.apply_suggestion(cfgp, {"id": "s", "path": "safety.dry_run", "op": "set_key", "key": "x", "value": False})
    assert cfgp.read_text() == before


def test_suggest_from_store(store, cfg):
    for i in range(3):
        store.upsert_job(row(f"g{i}", title="Backend", description="We use Terraform and Python daily", score=80))
    ids = [s["id"] for s in coach.suggest(store, cfg)]
    assert "skill-terraform" in ids
