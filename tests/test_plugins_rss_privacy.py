# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
import json

import pytest

from job_radar import cli, privacy
from job_radar.providers import base as pb
from job_radar.providers import loader
from job_radar.providers.rss import RssProvider, parse_feed

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Backend Engineer</title><link>https://example.com/j/1</link>
<description>&lt;p&gt;Python, 3 years. Remote.&lt;/p&gt;</description><author>Acme</author></item>
<item><title>Nurse</title><link>https://example.com/j/2</link><description>ICU</description></item>
<item><link>https://example.com/j/3</link></item></channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Data Analyst</title><link href="https://example.com/a/1"/><summary>SQL</summary></entry></feed>"""


class Resp:
    def __init__(self, b):
        self.b = b

    def read(self, n):
        return self.b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def test_parse_rss_and_atom():
    jobs = parse_feed(RSS)
    assert [j.title for j in jobs] == ["Backend Engineer", "Nurse"]
    assert jobs[0].company == "Acme" and "Python" in jobs[0].description and jobs[0].work_mode == "remote"
    assert parse_feed(ATOM)[0].url == "https://example.com/a/1"


def test_rss_provider_with_fake_http(cfg):
    p = RssProvider([{"name": "board", "url": "https://example.com/feed.xml"}], opener=lambda req, timeout: Resp(RSS))
    assert len(p.search(cfg["search"])) == 2
    with pytest.raises(ValueError, match="no feeds"):
        RssProvider([]).search(cfg["search"])


def test_rss_refuses_private_urls(cfg):
    p = RssProvider([{"name": "x", "url": "http://127.0.0.1/feed"}], opener=lambda r, timeout: Resp(RSS))
    with pytest.raises(ValueError):
        p.search(cfg["search"])


def test_scaffold_plugin_is_loaded_and_runs(tmp_path, cfg):
    path = loader.scaffold(tmp_path, "My Board!")
    assert path.name == "my_board.py"
    with pytest.raises(FileExistsError):
        loader.scaffold(tmp_path, "My Board!")
    assert loader.load_plugins(tmp_path) == []
    cfg["sources"]["enabled"] = ["my_board"]
    prov = loader.create_from_config("my_board", tmp_path, cfg)
    assert prov.search(cfg["search"])[0].source == "my_board"
    pb._REGISTRY.pop("my_board", None)


def test_broken_plugin_is_reported_not_fatal(tmp_path):
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "bad.py").write_text("raise RuntimeError('oops')")
    probs = loader.load_plugins(tmp_path)
    assert len(probs) == 1 and "oops" in probs[0]


def test_unknown_source_message(cfg, tmp_path):
    with pytest.raises(KeyError, match="new-provider"):
        loader.create_from_config("nope", tmp_path, cfg)


def test_privacy_scan_finds_and_masks(tmp_path):
    # sample values are assembled at runtime so this file itself stays clean for the scanner
    mail, home, key = "real.person" + "@gmail.com", "/ho" + "me/someone/x", "api_key = " + "abcdefghijklmnop12345"
    (tmp_path / "a.md").write_text(f"mail me at {mail} or me@example.com\nhome {home}\n{key}\nBy Jane Roe\n")
    found = privacy.scan(tmp_path, ["jane roe"])
    assert {f.kind for f in found} == {"email", "absolute home path", "secret-looking token", "your term"}
    rep = privacy.format_report(found)
    assert "real.person" not in rep and "gmail" not in rep and "someone" not in rep


def test_privacy_clean_folder(tmp_path):
    (tmp_path / "a.md").write_text("hello me@example.com")
    assert privacy.scan(tmp_path) == []


def test_repo_itself_passes_privacy_check():
    from pathlib import Path
    assert privacy.scan(Path(__file__).resolve().parent.parent) == []


def test_cli_new_provider_providers_and_privacy(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JOB_RADAR_HOME", str(tmp_path))
    cli.main(["init", "--yes"])
    assert cli.main(["new-provider", "board2"]) == 0
    assert cli.main(["providers"]) == 0
    out = capsys.readouterr().out
    assert "board2" in out and "* demo" in out
    pb._REGISTRY.pop("board2", None)
    # the generated config/profile hold only fake example data
    assert cli.main(["privacy-check"]) == 0
    d = json.loads((tmp_path / "config.json").read_text())
    d["sources"]["enabled"] = ["rss"]
    (tmp_path / "config.json").write_text(json.dumps(d))
    from job_radar import doctor
    assert any(c.name == "rss" and c.status == "warn" for c in doctor.run_all(tmp_path, probe_linkedin=False))
