# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Find and create providers: built-ins, `<project>/plugins/*.py` (your own), and installed packages
that declare the `job_radar.providers` entry-point group. Adding a source never needs a core change."""

from __future__ import annotations

import importlib.util
import inspect
import logging
from importlib import metadata
from pathlib import Path

from . import base

log = logging.getLogger("job_radar.plugins")
ENTRY_GROUP = "job_radar.providers"


def load_plugins(root: Path) -> list[str]:
    """Import ./plugins/*.py and entry points; return problems (a broken plugin never stops the agent)."""
    problems: list[str] = []
    pdir = root / "plugins"
    if pdir.is_dir():
        for f in sorted(pdir.glob("*.py")):
            if f.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"job_radar_plugin_{f.stem}", f)
                mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
            except Exception as ex:  # noqa: BLE001
                problems.append(f"plugin {f.name}: {ex}")
                log.warning("plugin %s failed: %s", f.name, ex)
    try:
        for ep in metadata.entry_points(group=ENTRY_GROUP):
            try:
                ep.load()
            except Exception as ex:  # noqa: BLE001
                problems.append(f"entry point {ep.name}: {ex}")
    except Exception:  # noqa: BLE001
        pass
    return problems


def create_from_config(name: str, root: Path, cfg: dict) -> base.Provider:
    """Create a provider; pass it only the arguments its constructor accepts (root, cfg, options, ...)."""
    sources = cfg["sources"]
    available = {"root": root, "cfg": cfg, "options": sources.get("plugin_options", {}).get(name, {}),
                 "sessions_dir": root / cfg["paths"]["sessions_dir"],
                 "backend_order": sources["linkedin"]["backend_order"], "feeds": sources["rss"]["feeds"]}
    factory = base._REGISTRY.get(name)
    if factory is None:
        raise KeyError(f"unknown source '{name}' (known: {', '.join(base.known())}); "
                       f"custom sources go in ./plugins/ (see `job-radar new-provider`)")
    params = inspect.signature(factory).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        kwargs = available
    else:
        kwargs = {k: v for k, v in available.items() if k in params}
    return factory(**kwargs)


SCAFFOLD = '''# SPDX-License-Identifier: MIT
"""My own job source: {name}. Loaded automatically from ./plugins/. Enable it with
"sources": {{"enabled": ["{name}"]}} in config.json. Options go in "sources.plugin_options.{name}"."""

from job_radar.models import Job
from job_radar.providers.base import Provider, register


@register("{name}")
class {cls}(Provider):
    name = "{name}"
    description = "describe where these jobs come from"

    def __init__(self, options: dict | None = None):
        self.options = options or {{}}

    def search(self, search_cfg: dict) -> list[Job]:
        # Read-only: fetch jobs from your source and return them. search_cfg has your titles, keywords, locations.
        return [
            Job(id="{name}-1", source="{name}", title="Example Backend Engineer", company="Example Co",
                location="Remote", url="https://example.com/job/1", description="Describe the job here.",
                work_mode="remote"),
        ]
'''


def scaffold(root: Path, name: str) -> Path:
    safe = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_") or "mysource"
    path = root / "plugins" / f"{safe}.py"
    if path.exists():
        raise FileExistsError(str(path))
    path.parent.mkdir(exist_ok=True)
    cls = "".join(p.capitalize() for p in safe.split("_")) + "Provider"
    path.write_text(SCAFFOLD.format(name=safe, cls=cls), encoding="utf-8")
    return path
