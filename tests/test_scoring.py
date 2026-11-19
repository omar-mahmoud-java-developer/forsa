# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
from job_radar.models import Job
from job_radar.scoring import required_years, score_job


def J(**kw):
    base = dict(id="x", source="t", title="Backend Engineer", company="Acme", location="Berlin, Germany",
                description="Python and PostgreSQL. 3 years of experience.", work_mode="hybrid")
    return Job(**{**base, **kw})


def test_good_job_is_best(cfg):
    assert score_job(J(), cfg).tier == "best"


def test_excluded_company_zero(cfg):
    j = score_job(J(company="Example Staffing Ltd"), cfg)
    assert j.score == 0 and "excluded company" in j.why


def test_excluded_keyword_zero(cfg):
    assert score_job(J(description="unpaid trial. python"), cfg).score == 0


def test_too_senior_penalty(cfg):
    low = score_job(J(description="Python. 15+ years of experience."), cfg).score
    ok = score_job(J(description="Python. 3 years of experience."), cfg).score
    assert low < ok


def test_unwanted_work_mode_penalised(cfg):
    assert score_job(J(work_mode="onsite"), cfg).score < score_job(J(work_mode="hybrid"), cfg).score


def test_remote_bonus(cfg):
    a = score_job(J(location="Remote", work_mode="remote"), cfg)
    assert "remote" in a.why


def test_thresholds_come_from_config(cfg):
    cfg["scoring"]["thresholds"] = {"best": 99, "stretch": 98, "apply_min": 99}
    assert score_job(J(), cfg).tier == "skip"


def test_works_for_any_stack(cfg):
    cfg["search"]["titles"] = ["Nurse"]
    cfg["scoring"]["skills"] = {"icu": 10}
    j = score_job(J(title="ICU Nurse", description="ICU ward. 2 years of experience.", location="Berlin, Germany"), cfg)
    assert j.tier in ("best", "stretch") and "icu" in j.why


def test_required_years():
    assert required_years("5+ years of experience") == 5
    assert required_years("no numbers here") is None
