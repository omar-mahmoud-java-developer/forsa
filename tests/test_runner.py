# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
from job_radar.apply.forms import FormField
from job_radar.apply.runner import run_application
from job_radar.models import Job


class FakeDriver:
    def __init__(self, steps, confirm=True, reject=False):
        self.steps, self.i, self.confirm, self.reject = steps, 0, confirm, reject
        self.discarded = self.submitted = False
        self.filled = {}

    def open(self, job):
        pass

    def fields(self):
        return self.steps[self.i][0]

    def fill(self, f, value):
        f.value = value
        self.filled[f.label] = value

    def primary_button(self):
        return self.steps[self.i][1]

    def advance(self):
        b = self.primary_button()
        if b == "submit":
            self.submitted = True
        elif self.reject:
            self.steps[self.i][0][0].invalid = True
        else:
            self.i += 1
        return b

    def discard(self):
        self.discarded = True

    def confirmed(self):
        return self.confirm


JOB = Job("1", "t", "Backend Engineer", "Acme")


def test_dry_run_stops_before_submit(profile):
    d = FakeDriver([([FormField("text", "Notice period", True)], "submit")])
    r = run_application(d, JOB, profile, dry_run=True)
    assert r.ok is None and not d.submitted and d.discarded


def test_live_submit_needs_confirmation(profile):
    d = FakeDriver([([FormField("text", "Notice period", True)], "submit")])
    assert run_application(d, JOB, profile, dry_run=False).ok is True
    d = FakeDriver([([FormField("text", "Notice period", True)], "submit")], confirm=False)
    assert run_application(d, JOB, profile, dry_run=False).ok is False


def test_unknown_required_question_skips_job(profile):
    d = FakeDriver([([FormField("text", "How many years of experience with Kafka?", True)], "submit")])
    r = run_application(d, JOB, profile, dry_run=False)
    assert r.ok is False and "Kafka" in r.question and d.discarded and not d.submitted


def test_notice_period_label_does_not_stop_application(profile):
    f = FormField("text", "Please enter your notice period in days", True)
    d = FakeDriver([([f], "next"), ([FormField("text", "Phone", True)], "submit")])
    r = run_application(d, JOB, profile, dry_run=False)
    assert r.ok is True and d.filled["Please enter your notice period in days"] == "30 days"


def test_required_consent_checkbox_needs_user(profile):
    d = FakeDriver([([FormField("checkbox", "I agree to the terms", True)], "submit")])
    r = run_application(d, JOB, profile, dry_run=False)
    assert r.ok is False and not d.submitted


def test_form_rejection_reported(profile):
    d = FakeDriver([([FormField("text", "Notice period", True)], "next")], reject=True)
    r = run_application(d, JOB, profile, dry_run=False)
    assert r.ok is False and "rejected" in r.reason
