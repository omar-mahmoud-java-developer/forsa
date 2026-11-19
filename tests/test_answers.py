# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
import pytest

from job_radar.apply.answers import answer
from job_radar.profile import Profile, parse


def A(label, profile, kind="text", options=()):
    a = answer(label, kind, list(options), profile)
    return a.value if a else None


def test_skill_years_from_profile(profile):
    assert A("How many years of experience do you have with Python?", profile) == "5"
    assert A("How many years of experience do you have with Docker?", profile) == "4"


@pytest.mark.parametrize("label", [
    "How many years of experience do you have with Kafka?",
    "How many years of experience do you have in the banking domain?",
    "What is your gender?",
    "Are you a veteran?",
])
def test_never_invents(profile, label):
    assert A(label, profile) is None


def test_empty_profile_answers_nothing():
    p = Profile()
    for label in ("What is your phone number?", "Are you willing to relocate?", "How many years of experience?"):
        assert A(label, p) is None


def test_standard_fields(profile):
    assert A("Phone number", profile) == profile.get("phone")
    assert A("Notice period", profile) == "30 days"


def test_radio_picks_matching_option(profile):
    assert A("Are you legally authorized to work here?", profile, "radio", ["Yes", "No"]) == "Yes"
    assert A("Do you require visa sponsorship?", profile, "radio", ["Yes", "No"]) == "No"


def test_option_not_available_means_none(profile):
    assert A("Are you legally authorized to work here?", profile, "select", ["Maybe", "Later"]) is None


def test_explicit_answers_win():
    p = parse("name: X\n\n## Answers\n- security clearance: No\n")
    assert A("Do you hold a security clearance?", p) == "No"
