# Scheduling

`job-radar schedule cron|systemd|windows` prints ready-to-paste snippets with YOUR project path and the times
from `config.json` (`schedule.times`). The files here are templates; replace `@PROJECT_DIR@` and `@PYTHON@`.

Start with `dry_run: true`. Run at most twice a day, and not at exactly the same minute every day if you
can avoid it: regular robotic patterns are what platforms look for.
