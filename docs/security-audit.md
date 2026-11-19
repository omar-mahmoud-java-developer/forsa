# Security audit (pre-release)

Tools run against the repository, the dependency tree and the Docker image before the first release:
bandit, semgrep (python, security-audit, secrets, OWASP top ten, Dockerfile, GitHub Actions rulesets), pip-audit,
trivy (filesystem and image), hadolint, actionlint, gitleaks (working tree and full history), trufflehog (full history),
plus hand-written attack probes and fuzzing (`tests/test_security.py`).

## Found and fixed
| Issue | Fix |
|---|---|
| IMAP/SMTP connections did not verify TLS certificates (Python stdlib default), exposing app passwords to a man in the middle | all mail connections use a verifying context (`reach.web.tls_context`) |
| SSRF: host names such as `127.0.0.1.nip.io` passed the "public URL" check; redirects were not re-checked | host names are resolved and every address must be public; every redirect is re-validated |
| XML: feeds were parsed with the stdlib parser | `defusedxml` plus rejection of DTD/entity declarations |
| ReDoS: a regex over hostile email HTML took quadratic time (8 s+ for 20k anchors) | linear-time HTML parser, input size cap |
| Privacy scanner regexes could stall on huge lines | per-line length bound |
| `javascript:` links in the digest e-mail | only http(s) links are emitted; CSP meta tag added |
| Output paths from config could escape the project folder | every output path is resolved under the project root |
| Plugin files were all imported (importing runs code) | only plugins named in `sources.enabled` are imported |
| Config values could inject IMAP search syntax, flags (`--model`) or headers | strict validation of senders, folders, hosts, model and `notify.email_to` |
| `forsa answer` could inject lines/sections into `profile.md` | single-line input enforced |
| `.env` and data folders were created with default permissions | `.env` 0600, data and sessions 0700 |
| CI actions pinned to mutable tags | pinned to commit SHAs; Dependabot cooldown added |
| Docker: numeric user, no healthcheck declaration, fixable zlib CVE in the base image | `USER 1000`, `HEALTHCHECK NONE`, zlib upgraded |

## Residual risks (by design, documented)
- Importing an enabled plugin or an installed entry point runs its code. Only enable code you trust and never run
  `forsa` inside a folder you do not trust (its `config.json` and `plugins/` are executable configuration).
- DNS rebinding between the check and the request is not fully eliminated for feed URLs.
- Jina Reader (`r.jina.ai`) sees the public URLs you ask it to fetch.
- Automating LinkedIn may violate its Terms; see DISCLAIMER.md.
