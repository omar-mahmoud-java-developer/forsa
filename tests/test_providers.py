# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
import pytest

from forsa.models import Job
from forsa.providers import base as pb
from forsa.providers import demo  # noqa: F401
from forsa.providers.linkedin import LinkedInProvider, parse_detail, parse_search
from forsa.retry import CircuitBreaker, CircuitOpen

SEARCH = {"references": {"r": [
    {"kind": "job", "url": "/jobs/view/111/", "text": "Backend Engineer with verification"},
    {"kind": "job", "url": "/jobs/view/222/", "text": "Platform Engineer"},
    {"kind": "company", "url": "/company/x/", "text": "X"},
    {"kind": "job", "url": "/jobs/view/111/", "text": "dup"}]}}
DETAIL = {"sections": {"main": "Acme Co\nBackend Engineer\nBerlin, Germany · 1 day ago · 20 applicants\nHybrid\n"
                               "Easy Apply\nAbout the job\nPython services. 3 years of experience."}}


class FakeSession:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def call(self, tool, **kw):
        self.calls.append((tool, kw))
        return {"search_jobs": SEARCH, "get_job_details": DETAIL}.get(tool, {"ok": True})


def test_registry_and_demo():
    assert "demo" in pb.known() and "linkedin" in pb.known()
    assert len(pb.create("demo").search({})) == 5
    with pytest.raises(KeyError):
        pb.create("nope")


def test_new_provider_needs_no_core_changes(cfg):
    @pb.register("fake-board")
    class Fake(pb.Provider):
        name = "fake-board"

        def search(self, search_cfg):
            return [Job("f1", "fake-board", "Backend Engineer")]

    assert pb.create("fake-board").search(cfg["search"])[0].id == "f1"


def test_parse_search_dedupes_and_filters():
    jobs = parse_search(SEARCH)
    assert [j.id for j in jobs] == ["111", "222"] and jobs[0].title == "Backend Engineer"


def test_parse_detail():
    j = parse_detail(DETAIL, Job("111", "linkedin", ""))
    assert j.company == "Acme Co" and j.easy_apply and j.work_mode == "hybrid" and "Python" in j.description


def test_provider_with_mocked_mcp_server(cfg):
    fs = FakeSession()
    p = LinkedInProvider(session_factory=lambda: fs)
    jobs = p.search(cfg["search"])
    assert {j.id for j in jobs} == {"111", "222"}
    p.details(jobs[0])
    tools = {t for t, _ in fs.calls}
    assert tools == {"search_jobs", "get_job_details"}
    assert p.channel.used and set(p.channel.used) == {"mcp"}
    assert fs.calls[0][1]["date_posted"] == "r259200"
    p.close()
    assert fs.calls[-1][0] == "close_session"


def test_connect_uses_tool(cfg):
    fs = FakeSession()
    p = LinkedInProvider(session_factory=lambda: fs)
    assert p.connect("jane-doe", "hi") is True
    assert fs.calls[-1] == ("connect_with_person", {"linkedin_username": "jane-doe", "note": "hi"})


def test_circuit_breaker_opens():
    b = CircuitBreaker(3)
    b.fail()
    b.fail()
    with pytest.raises(CircuitOpen):
        b.fail()
    b2 = CircuitBreaker(3)
    b2.fail()
    b2.ok()
    b2.fail()
