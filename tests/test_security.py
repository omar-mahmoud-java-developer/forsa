# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Regression tests for every vulnerability found by the security audit, plus fuzzing of untrusted-input parsers."""

import copy
import os
import random
import stat
import time
from xml.etree.ElementTree import ParseError

import pytest
from defusedxml import DefusedXmlException

from forsa import cli, mailbox, notify, privacy, recruiters
from forsa import config as cfgmod
from forsa.apply.answers import answer
from forsa.paths import resolve
from forsa.profile import Profile, parse
from forsa.providers import loader
from forsa.providers.rss import parse_feed
from forsa.reach import web
from forsa.scoring import required_years
from forsa.store import Store


# ---- XML (XXE / entity bombs)
def test_feed_with_dtd_or_entities_is_rejected():
    for bad in (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/hostname">]><rss/>',
                b"<!DOCTYPE lolz [<!ENTITY a 'aaaa'>]><rss><channel><item><title>&a;</title></item></channel></rss>"):
        with pytest.raises(ValueError, match="DTD"):
            parse_feed(bad)


# ---- SSRF
@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"])
def test_names_resolving_to_private_addresses_are_refused(monkeypatch, ip):
    monkeypatch.setattr(web, "_resolve", lambda host: [ip])
    with pytest.raises(ValueError, match="non-public"):
        web.public_url("https://innocent-looking.example.org/feed")


def test_mixed_resolution_is_refused(monkeypatch):
    monkeypatch.setattr(web, "_resolve", lambda host: ["93.184.216.34", "127.0.0.1"])  # rebinding-style answer
    with pytest.raises(ValueError):
        web.public_url("https://example.org/")


def test_unresolvable_host_is_refused(monkeypatch):
    def boom(host):
        raise OSError("nxdomain")
    monkeypatch.setattr(web, "_resolve", boom)
    with pytest.raises(ValueError, match="resolve"):
        web.public_url("https://nope.example.org/")


def test_redirects_are_revalidated(monkeypatch):
    handler = web._SafeRedirect()
    monkeypatch.setattr(web, "_resolve", lambda host: ["127.0.0.1"] if "evil" in host else ["93.184.216.34"])
    import urllib.request
    req = urllib.request.Request("https://example.org/feed")
    with pytest.raises(ValueError):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example.org/admin")
    with pytest.raises(ValueError):
        handler.redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data/")


# ---- TLS verification (stdlib defaults do not verify)
def test_tls_context_verifies_certificates():
    ctx = web.tls_context()
    assert ctx.verify_mode == 2 and ctx.check_hostname is True


def test_mailbox_default_connection_uses_verified_tls(monkeypatch, cfg):
    seen = {}

    class Boom(Exception):
        pass

    def fake_imap(host, port, **kw):
        seen.update(kw)
        raise Boom

    monkeypatch.setattr(mailbox.imaplib, "IMAP4_SSL", fake_imap)
    with pytest.raises(Boom):
        mailbox.read_mailbox(cfg, "u", "p")
    assert seen["ssl_context"].verify_mode == 2 and seen["ssl_context"].check_hostname


# ---- denial of service through hostile input
def _fast(fn, limit=2.0):
    t = time.time()
    fn()
    assert time.time() - t < limit


def test_hostile_html_does_not_hang_the_mail_parser():
    _fast(lambda: mailbox.alert_jobs('<a href="linkedin.com/jobs/view/123456/">' * 30000))
    _fast(lambda: mailbox.alert_jobs('href="https://linkedin.com/jobs/view/123456/"' * 30000))
    _fast(lambda: mailbox.alert_jobs("<a " * 200000))


def test_privacy_scan_is_bounded_on_huge_lines(tmp_path):
    (tmp_path / "x.md").write_text("a" * 800_000 + "\n" + "/ho" + "me/" + "a" * 800_000)
    _fast(lambda: privacy.scan(tmp_path))


def test_other_parsers_survive_huge_inputs():
    _fast(lambda: required_years("1 " * 400_000))
    _fast(lambda: mailbox.classify("Your application to " + "a " * 100_000 + " at " + "b " * 10_000, "x" * 100_000))
    _fast(lambda: recruiters.parse_people({"sections": {"m": "Name • 2nd\nHeadline\n" * 50_000}, "references": {}}))


# ---- output injection
def test_digest_never_emits_javascript_links(root, cfg, profile, store):
    job = {"id": "x", "source": "t", "title": "T", "company": "C", "location": "L", "description": "", "score": 90,
           "tier": "best", "why": "w", "easy_apply": 0}
    store.upsert_job({**job, "url": "javascript:alert(1)"})
    page = notify.build_digest(root, store, profile, cfg, True, [], [])
    assert "javascript:" not in page and "Content-Security-Policy" in page


# ---- path traversal through config
def test_output_paths_cannot_escape_the_project(tmp_path, cfg):
    cfg["paths"]["output_dir"] = "../../escape"
    with pytest.raises(ValueError):
        notify.write_digest(tmp_path, cfg, "x")
    with pytest.raises(ValueError):
        resolve(tmp_path, "/etc")
    cfg["paths"]["output_dir"] = "output"
    assert notify.save_draft(tmp_path, cfg, "cover", "../../etc/passwd", "x").parent.name == "drafts"


# ---- plugins: importing runs code, so only enabled ones are imported
def test_only_enabled_plugins_are_imported(tmp_path):
    (tmp_path / "plugins").mkdir()
    marker = tmp_path / "ran.txt"
    (tmp_path / "plugins" / "evil.py").write_text(f"open({str(marker)!r}, 'w').write('x')")
    assert loader.load_plugins(tmp_path, only=["demo"]) == [] and not marker.exists()
    loader.load_plugins(tmp_path, only=["evil"])
    assert marker.exists()


# ---- config validation
@pytest.mark.parametrize("path,value", [
    (("mailbox", "senders"), ['linkedin.com" OR ALL']),
    (("mailbox", "folders"), ['INBOX"\r\nA1 DELETE']),
    (("mailbox", "imap_host"), "evil.com;rm"),
    (("notify", "smtp_host"), "a b"),
    (("llm", "model"), "--dangerously-skip-permissions"),
])
def test_unsafe_config_values_are_rejected(cfg, path, value):
    bad = copy.deepcopy(cfg)
    bad[path[0]][path[1]] = value
    assert cfgmod.validate(bad)


def test_email_to_must_be_a_single_address(cfg):
    for bad in ("a@example.com\nBcc: x@example.com", "a@example.com, b@example.com", "a b@example.com"):
        c = copy.deepcopy(cfg)
        c["notify"].update(mode="email", email_to=bad)
        assert any("email_to" in p for p in cfgmod.validate(c))


# ---- profile / CLI
def test_answer_command_rejects_newlines(root, monkeypatch, capsys):
    monkeypatch.setenv("FORSA_HOME", str(root))
    before = (root / "profile.md").read_text()
    assert cli.main(["answer", "q\n## Skills", "- python: 99"]) == 2
    assert cli.main(["answer", "q", "a\n## Skills\n- python: 99"]) == 2
    assert (root / "profile.md").read_text() == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_env_and_data_are_owner_only(tmp_path, monkeypatch):
    monkeypatch.setenv("FORSA_HOME", str(tmp_path))
    cli.main(["init", "--yes"])
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600
    Store(tmp_path / "data" / "x.sqlite").close()
    assert stat.S_IMODE((tmp_path / "data").stat().st_mode) == 0o700


# ---- fuzzing: untrusted-input parsers must never crash
def _junk(rng, n=400):
    alphabet = ["<", ">", "&", "\n", " ", "a", "Z", "0", "9", ":", "@", "•", "\x00", "'", '"', "/", "=", "-", "http://",
                "href=", "<a ", "</a>", "<!DOCTYPE", "Your application to ", " at ", "2nd", "Connect", "years", "## ", "- "]
    return "".join(rng.choice(alphabet) for _ in range(n))


def test_fuzz_parsers_never_crash():
    rng = random.Random(1234)
    for _ in range(400):
        s = _junk(rng)
        mailbox.classify(s, s)
        mailbox.alert_jobs(s)
        required_years(s)
        parse(s)
        recruiters.parse_people({"sections": {"a": s}, "references": {"b": [{"url": s, "text": s}]}})
        answer(s, "text", [], Profile(fields={"phone": s}, skills={"x": 1.0}, answers={"a": s}))
        answer(s, "radio", [s, "Yes"], Profile())
        try:
            parse_feed(s.encode())
        except (ValueError, ParseError, DefusedXmlException):
            pass
