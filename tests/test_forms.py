# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
from job_radar.apply.forms import FormField, missing_required, validation_errors


def test_label_text_is_never_an_error():
    # The original bug: a label like this was mistaken for an error and stopped the application.
    f = FormField("text", "Please enter your notice period in days", required=True, value="30")
    assert missing_required([f]) == [] and validation_errors([f]) == []


def test_required_empty_is_detected():
    f = FormField("text", "Notice period", required=True, value="")
    assert missing_required([f]) == [f]


def test_optional_empty_is_fine():
    assert missing_required([FormField("text", "Cover note", required=False)]) == []


def test_placeholder_select_counts_as_empty():
    assert missing_required([FormField("select", "Country", required=True, value="Select an option")])


def test_checkbox_and_file():
    assert missing_required([FormField("checkbox", "I agree", required=True, checked=False)])
    assert not missing_required([FormField("checkbox", "I agree", required=True, checked=True)])
    assert not missing_required([FormField("file", "Resume", required=True)])


def test_invalid_attribute_is_the_error_signal():
    f = FormField("text", "Years", required=True, value="x", invalid=True)
    assert validation_errors([f]) == [f]
