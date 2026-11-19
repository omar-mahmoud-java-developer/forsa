# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Runs the real browser driver against a LOCAL synthetic page (skipped when no browser is installed)."""
from pathlib import Path

import pytest

pw = pytest.importorskip("patchright.sync_api")

from forsa.apply.browser import PatchrightDriver  # noqa: E402
from forsa.apply.runner import run_application  # noqa: E402
from forsa.models import Job  # noqa: E402

PAGE = (Path(__file__).parent / "site" / "job.html").resolve().as_uri()


@pytest.fixture
def driver(tmp_path):
    try:
        d = PatchrightDriver(tmp_path, headless=True)
    except Exception as ex:  # noqa: BLE001 - browser binary not installed
        pytest.skip(f"no browser available: {str(ex)[:80]}")
    yield d
    d.close()


JOB = Job("1", "t", "Backend Engineer", "Acme", url=PAGE)


def test_dry_run_fills_but_does_not_submit(driver, profile):
    r = run_application(driver, JOB, profile, dry_run=True)
    assert r.ok is None
    assert not driver.page.locator("#done").is_visible()


def test_live_application_end_to_end(driver, profile):
    r = run_application(driver, JOB, profile, dry_run=False)
    assert r.ok is True, r
    assert driver.page.locator("#done").is_visible()


def test_unknown_required_field_stops(driver, profile):
    profile.skills.pop("python")
    profile.fields["years_experience"] = ""
    r = run_application(driver, JOB, profile, dry_run=False)
    assert r.ok is False and "Python" in r.question
