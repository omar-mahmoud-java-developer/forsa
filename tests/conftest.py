# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
import copy
import json
import os
from pathlib import Path

import pytest

from job_radar import config as cfgmod
from job_radar import profile as profmod
from job_radar.store import Store

EX = Path(__file__).resolve().parent.parent / "src" / "job_radar" / "examples"


@pytest.fixture
def cfg():
    return cfgmod.merge(copy.deepcopy(cfgmod.DEFAULTS), json.loads((EX / "config.example.json").read_text()))


@pytest.fixture
def profile():
    return profmod.parse((EX / "profile.example.md").read_text())


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.sqlite")
    yield s
    s.close()


@pytest.fixture
def root(tmp_path, cfg):
    (tmp_path / "config.json").write_text((EX / "config.example.json").read_text())
    (tmp_path / "profile.md").write_text((EX / "profile.example.md").read_text())
    return tmp_path


@pytest.fixture(autouse=True)
def _isolated_environment():
    """Tests must never inherit or leak credentials: restore os.environ after every test and drop any secrets."""
    saved = dict(os.environ)
    for k in list(os.environ):
        if k.startswith("JOB_RADAR_") or k == "ANTHROPIC_API_KEY":
            del os.environ[k]
    yield
    os.environ.clear()
    os.environ.update(saved)
