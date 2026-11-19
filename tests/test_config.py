# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
import copy
import json

import pytest

from forsa import config as cfgmod


def test_defaults_are_safe():
    s = cfgmod.DEFAULTS["safety"]
    assert s["dry_run"] is True and s["auto_apply"] is False and s["auto_connect"] is False
    assert s["send_emails"] is False


def test_example_loads(root):
    cfg = cfgmod.load(root / "config.json")
    assert cfg["safety"]["dry_run"] is True


def test_unknown_key_is_error(root):
    p = root / "config.json"
    d = json.loads(p.read_text())
    d["safety"]["dryrun"] = False
    p.write_text(json.dumps(d))
    with pytest.raises(cfgmod.ConfigError, match="unknown config key: safety.dryrun"):
        cfgmod.load(p)


def test_wrong_type_and_ranges(cfg):
    bad = copy.deepcopy(cfg)
    bad["safety"]["max_applications_per_day"] = "many"
    bad["safety"]["min_delay_seconds"] = 50
    bad["llm"]["provider"] = "gpt"
    bad["notify"]["mode"] = "email"
    problems = cfgmod.validate(bad)
    assert any("max_applications_per_day" in p for p in problems)
    assert any("min_delay_seconds" in p for p in problems)
    assert any("llm.provider" in p for p in problems)
    assert any("email_to" in p for p in problems)


def test_missing_file_message(tmp_path):
    with pytest.raises(cfgmod.ConfigError, match="forsa init"):
        cfgmod.load(tmp_path / "nope.json")


def test_dotenv_does_not_override(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("A_KEY=from_file\nB_KEY=2\n# c\n")
    monkeypatch.setenv("A_KEY", "from_env")
    monkeypatch.delenv("B_KEY", raising=False)
    cfgmod.load_dotenv(tmp_path / ".env")
    assert cfgmod.env("A_KEY") == "from_env" and cfgmod.env("B_KEY") == "2"
