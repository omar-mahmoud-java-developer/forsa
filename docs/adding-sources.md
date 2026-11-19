# Adding your own job source

A source is a small class that **reads** jobs. Scoring, store, drafts and digest work unchanged.

```bash
forsa new-provider myboard      # creates plugins/myboard.py
```
Edit `plugins/myboard.py`, then enable it:
```json
{"sources": {"enabled": ["myboard"], "plugin_options": {"myboard": {"api_url": "https://..."}}}}
```
`forsa providers` lists what is available and `forsa doctor` reports plugin errors.

Rules: read-only (no applying or messaging inside a provider), respect the site's terms and robots rules, use
`forsa.reach.web.public_url` for any URL you fetch, keep secrets in environment variables.

Share it: put the class in `src/forsa/providers/` with tests and open a pull request
([CONTRIBUTING](../CONTRIBUTING.md)), or publish a package that declares the entry point `forsa.providers`
so it is discovered automatically.
