# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""Static dashboard: one self-contained HTML file (output/dashboard.html). No server, no network, no external scripts.

Everything that came from the outside (job titles, company names, email subjects, people) is HTML-escaped, links are
only emitted for http(s) URLs, and a Content-Security-Policy meta tag blocks any remote resource.
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

from .paths import resolve

CSS = """
:root{--bg:#f6f7f9;--panel:#fff;--text:#16181d;--muted:#5b6472;--line:#e3e6ec;--accent:#2457d6;--ok:#15803d;--warn:#a16207;--bad:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--panel:#181b21;--text:#e8eaee;--muted:#9aa3b2;--line:#2a2f39;--accent:#7aa2ff;--ok:#4ade80;--warn:#facc15;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,Segoe UI,Arial,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}h1{margin:.2em 0}h2{margin:28px 0 8px;font-size:18px}
.banner{padding:10px 14px;border-radius:10px;border:1px solid var(--line);background:var(--panel)}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
.stat b{font-size:20px;display:block}table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}th{color:var(--muted);font-weight:600}
.pill{display:inline-block;padding:0 9px;border-radius:99px;font-size:12px;font-weight:700;color:#fff;background:var(--muted)}
.best,.offer,.interview{background:var(--ok)}.stretch,.viewed{background:var(--warn)}.rejected,.failed{background:var(--bad)}.applied{background:var(--accent)}
input{padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--text);width:100%;max-width:340px}
small{color:var(--muted)}.wrap{overflow-x:auto}
"""
JS = """document.getElementById('q').addEventListener('input',function(e){var v=e.target.value.toLowerCase();
document.querySelectorAll('tr.row').forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(v)>=0?'':'none'})});"""


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def safe_url(u: str) -> str:
    u = (u or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else ""


def _link(url: str, text: str) -> str:
    u = safe_url(url)
    return f'<a href="{esc(u)}" rel="noopener noreferrer nofollow">{esc(text)}</a>' if u else esc(text)


def _table(head: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f"<p><small>{esc(empty)}</small></p>"
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join('<tr class="row">' + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _opinion(store, job: dict) -> str:
    v = store.judge(job["id"])
    return f" · LLM opinion: {v['fit']} ({v['reason']})" if v else ""


def pill(label: str) -> str:
    return f'<span class="pill {esc(label)}">{esc(label)}</span>'


def build(store, cfg: dict, profile_name: str = "") -> str:
    jobs = store.jobs(min_score=cfg["scoring"]["thresholds"]["stretch"])[:40]
    apps = store.applications()
    people = store.people()[:40]
    flags = store.flags()
    last = store.last_run()
    all_jobs = store.jobs()
    tiers = {t: sum(j["tier"] == t for j in all_jobs) for t in ("best", "stretch", "skip")}
    dry = cfg["safety"]["dry_run"]
    mode = ("DRY RUN mode: nothing is sent, applied or connected." if dry
            else "LIVE mode: actions are allowed by your safety settings.")
    summary = (last or {}).get("summary", {})
    stat = lambda label, n: f'<div class="stat"><b>{esc(n)}</b>{esc(label)}</div>'  # noqa: E731
    open_apps = sum(a["status"] not in ("rejected",) for a in apps)

    jobs_t = _table(["Score", "Tier", "Job", "Company", "Location", "Why"],
                    [[esc(j["score"]), pill(j["tier"]), _link(j["url"], j["title"] or "(untitled)"), esc(j["company"]),
                      esc(j["location"]), f"<small>{esc(j['why'])}{esc(_opinion(store, j))}</small>"] for j in jobs], "No matching jobs yet.")
    apps_t = _table(["Status", "Company", "Role", "Updated", "Source"],
                    [[pill(a["status"]), esc(a["company"]), esc(a["title"]), esc((a["updated"] or "")[:10]),
                      esc(a["source"])] for a in apps], "No applications tracked yet.")
    ppl_t = _table(["Name", "Headline", "Location", "Degree", "Status"],
                   [[_link(f"https://www.linkedin.com/in/{p['username']}/", p["name"] or p["username"]),
                     esc(p["headline"]), esc(p["location"]), esc(p["degree"]), pill(p["status"])] for p in people],
                   "Recruiter search is off or found nobody yet (search.recruiters.enabled).")
    flags_t = _table(["Job", "Needs"], [[esc(f"{f['title'] or f['job_id']} at {f['company'] or ''}"), esc(f["reason"])]
                                        for f in flags], "Nothing is waiting for your answer.")
    steps = "".join(f"<li>{esc(s)}</li>" for s in summary.get("steps", [])) or "<li>no run yet</li>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<meta name="robots" content="noindex,nofollow"><title>Forsa dashboard</title><style>{CSS}</style></head>
<body><main>
<h1>Forsa dashboard{(' for ' + esc(profile_name)) if profile_name else ''}</h1>
<div class="banner">{esc(mode)} <small>Generated {esc(dt.datetime.now().strftime('%Y-%m-%d %H:%M'))}. Last run: {esc((last or {}).get('at', 'never'))}.</small></div>
<div class="stats">{stat('best matches', tiers['best'])}{stat('stretch', tiers['stretch'])}{stat('jobs seen', len(all_jobs))}{stat('applications', len(apps))}{stat('open applications', open_apps)}{stat('recruiters found', len(people))}{stat('need your answer', len(flags))}</div>
<input id="q" placeholder="Filter rows..." aria-label="Filter rows">
<h2>Needs you</h2>{flags_t}
<h2>Best jobs</h2>{jobs_t}
<h2>Applications</h2>{apps_t}
<h2>Recruiters and hiring contacts</h2>{ppl_t}
<h2>Last run</h2><ul>{steps}</ul>
<p><small>Local file: nothing here is sent anywhere. Data: {esc(json.dumps({'dry_run': dry}))}</small></p>
</main><script>{JS}</script></body></html>"""


def write(root: Path, cfg: dict, store, profile_name: str = "") -> Path:
    out = resolve(root, cfg["paths"]["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    p = out / "dashboard.html"
    p.write_text(build(store, cfg, profile_name), encoding="utf-8")
    return p
