# Contributing

## Setup
```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && pytest && forsa eval
```

## Ground rules
- Never commit personal data, real job postings, recruiter names, CVs, cookies or sessions. Tests and evals
  use synthetic fixtures only. `tests/test_privacy_repo.py` and the CI secret scan enforce this.
- Safe by default: new actions must respect `safety.*` and go through `retry.RateLimiter`.
- Nothing may invent application answers; answers come from `profile.md`.
- Every source file starts with `# SPDX-License-Identifier: MIT`.
- **Sign your commits off (DCO):** `git commit -s`. By contributing you agree your work is licensed under
  this project's MIT license and that you have the right to submit it.

## Add a new source provider (Bayt, Wuzzuf, Indeed, ...)
Quick local try: `forsa new-provider NAME` creates `plugins/NAME.py`. To contribute it to the project:

1. Create `src/forsa/providers/<name>.py`:
   ```python
   from ..models import Job
   from .base import Provider, register

   @register("mysource")
   class MySource(Provider):
       name = "mysource"
       def search(self, search_cfg: dict) -> list[Job]:
           ...  # read-only; return Job(id, source, title, company, location, url, description, ...)
       def details(self, job: Job) -> Job:
           return job
   ```
2. Import it in `cli.py` next to the other providers (one line).
3. Add tests with a mocked HTTP layer (see `tests/test_providers.py`). Do not scrape sites whose terms forbid it.
4. Enable it with `"sources": {"enabled": ["mysource"]}`. The pipeline, scoring, store and digest need no changes.

## Releases
Update `CHANGELOG.md` and the version in `pyproject.toml`, tag `vX.Y.Z`, push the tag. The release workflow
publishes to PyPI with trusted publishing (configure a pending publisher on pypi.org first).
