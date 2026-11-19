# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
import pytest

from forsa.reach import linkedin as li
from forsa.reach.base import Channel
from forsa.reach.probe import probe_command
from forsa.reach.web import WebChannel, looks_blocked, public_url


def test_probe_missing_and_ok():
    assert probe_command("definitely-not-a-command-xyz").status == "missing"
    import sys
    assert probe_command(sys.executable, ["--version"]).ok


def test_channel_backend_override():
    class C(Channel):
        name = "x"
        backends = ["a", "b"]

        def can_handle(self, url):
            return True

    assert C().ordered_backends({"x_backend": "b"}) == ["b", "a"]
    assert C().ordered_backends({"x_backend": "zzz"}) == ["a", "b"]


def test_linkedin_order_and_url():
    ch = li.LinkedInChannel(backend_order=["jina", "mcp"])
    assert ch.ordered_backends() == ["jina", "mcp"]
    assert ch.can_handle("https://www.linkedin.com/jobs/view/1/") and not ch.can_handle("https://example.com")


def test_check_falls_back_to_jina_when_server_missing(monkeypatch, tmp_path):
    def boom(_):
        raise li.McpUnavailable("no server")

    monkeypatch.setattr(li, "server_command", boom)
    monkeypatch.setattr(li, "python_ok", lambda: True)
    ch = li.LinkedInChannel(tmp_path)
    status, msg = ch.check()
    assert status == "warn" and ch.active_backend == "jina" and "Jina" in msg


def test_check_old_python_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(li, "python_ok", lambda: False)
    ch = li.LinkedInChannel(tmp_path)
    assert ch.check()[0] == "warn" and ch.active_backend == "jina"


def test_check_ok_with_fake_session(monkeypatch, tmp_path):
    class S:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def list_tools(self):
            return ["search_jobs", "get_job_details"]

    monkeypatch.setattr(li, "python_ok", lambda: True)
    monkeypatch.setattr(li, "server_command", lambda d: ("srv", []))
    monkeypatch.setattr(li, "McpSession", S)
    ch = li.LinkedInChannel(tmp_path)
    assert ch.check()[0] == "ok" and ch.active_backend == "mcp"


def test_jina_fallback_is_logged_and_read_only(caplog):
    class R:
        def read(self, n):
            return b"# Public job page"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    ch = li.LinkedInChannel()
    ch.web.read = lambda url, opener=None: "text"  # no network
    with caplog.at_level("INFO", logger="forsa.reach"):
        assert ch.public_page("https://www.linkedin.com/jobs/view/1/") == "text"
    assert ch.used == ["jina"] and "backend=jina" in caplog.text


@pytest.mark.parametrize("bad", ["http://localhost/x", "http://127.0.0.1", "ftp://example.com", "https://user:pw@example.com",
                                 "http://intranet/", "", "https://a b.com"])
def test_public_url_rejects_private_targets(bad):
    with pytest.raises(ValueError):
        public_url(bad)


def test_public_url_normalizes():
    assert public_url("example.com/a") == "https://example.com/a"


def test_jina_read_with_fake_opener():
    class Resp:
        def __init__(self, body):
            self.body = body

        def read(self, n):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    w = WebChannel()
    assert w.read("example.com", opener=lambda req, timeout: Resp(b"hello")) == "hello"
    with pytest.raises(RuntimeError):
        w.read("example.com", opener=lambda req, timeout: Resp(b"warning: requiring captcha"))
    assert looks_blocked(b"Just a moment... Cloudflare")
