# Licensing and publishing notes (for maintainers)

*General information, not legal advice.*

## This project: MIT
`LICENSE` is MIT with the copyright line `Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]`. Fill the placeholders:
```bash
python tools/set_owner.py --name "Your Name" --handle your-github-handle --dry-run
python tools/set_owner.py --name "Your Name" --handle your-github-handle
git diff
```
Every source file starts with `# SPDX-License-Identifier: MIT` (a test enforces it).

## Third-party code
- **Agent Reach (MIT, Copyright (c) 2025 Agent Eyes)**: `src/job_radar/reach/{base,probe,process,web}.py` are derived from
  v1.5.0, commit `f65526cbaaad3879473acc1ba6dbefd195caf2be`. Each file keeps the original copyright and records its
  changes in its header. The license text is in `THIRD_PARTY_LICENSES`. To sync, diff against that upstream path.
- **mcp-server-linkedin (Apache-2.0, Daniel Sticker)**: not vendored; a pinned dependency. Using it from PyPI needs no
  extra step. If you ship it inside an image or archive (the Dockerfile does), you must include its LICENSE and NOTICE:
  the Dockerfile copies them to `/usr/share/licenses/mcp-server-linkedin/`. Do not use its name or logo as your own.
- Other dependencies keep their own licenses (see `pip show`).

## Contributions (DCO)
Contributors sign off commits (`git commit -s`), certifying the Developer Certificate of Origin and that their work is
MIT-licensed (inbound = outbound). No CLA is needed unless you plan to relicense.

## Name and trademark
Copyright protects the code and docs, not the project name or ideas. "Job Radar Agent" is a descriptive name used
elsewhere; consider a more distinctive name before launch. The README states the license grants no right to use the name
for forks. Register a trademark only if you plan commercial use.

## Before making the repository public
`job-radar privacy-check --term "your name" --term "your handle"`, `gitleaks detect`, `pytest`, then review `git log -p`.
