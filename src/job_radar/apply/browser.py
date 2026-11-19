# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""EXPERIMENTAL browser driver for "Easy Apply"-style dialogs (patchright, optional extra: [apply]).

Uses its OWN browser profile in sessions/apply-browser. You sign in once yourself with
`job-radar login --apply-browser`; this code never reads cookies from other tools and never sees a password.
Required fields are detected from html attributes only (see apply/forms.py).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from ..models import Job
from .forms import FormField

DIALOG = "dialog[open], div[role='dialog']"

_FIELDS_JS = """
(root) => {
  const out = [];
  const seenRadio = new Set();
  const label = (e) => {
    if (e.type === 'radio' || e.type === 'checkbox') {
      const fs = e.closest('fieldset'); const lg = fs && fs.querySelector('legend');
      if (lg && e.type === 'radio') return lg.innerText.trim();
    }
    if (e.id) { const l = document.querySelector('label[for="' + CSS.escape(e.id) + '"]'); if (l) return l.innerText.trim(); }
    const l2 = e.closest('label'); if (l2) return l2.innerText.trim();
    return (e.getAttribute('aria-label') || e.getAttribute('placeholder') || '').trim();
  };
  root.querySelectorAll('input, select, textarea').forEach((e, i) => {
    const t = (e.type || e.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'search'].includes(t)) return;
    if (t !== 'radio' && t !== 'checkbox' && t !== 'file' && e.offsetParent === null) return;
    if (t === 'radio') { if (seenRadio.has(e.name)) return; seenRadio.add(e.name); }
    e.setAttribute('data-jr', String(i));
    const kind = t === 'select-one' || t === 'select' ? 'select' : t === 'textarea' ? 'textarea' : ['radio', 'checkbox', 'file'].includes(t) ? t : 'text';
    let options = [], value = e.value || '', checked = !!e.checked;
    if (kind === 'select') options = [...e.options].map(o => o.text.trim());
    if (kind === 'radio') {
      const group = [...root.querySelectorAll('input[type=radio]')].filter(r => r.name === e.name);
      const text = (r) => { const l = (r.id && document.querySelector('label[for="' + CSS.escape(r.id) + '"]')) || r.closest('label'); return (l ? l.innerText : r.value || '').trim(); };
      options = group.map(text);
      const c = group.find(r => r.checked); value = c ? text(c) : '';
    }
    const fs = e.closest('fieldset');
    const required = !!(e.required || e.getAttribute('aria-required') === 'true' || (kind === 'radio' && fs && fs.querySelector('[required],[aria-required=true]')));
    out.push({idx: String(i), kind, label: label(e), required, value, checked, options, invalid: e.getAttribute('aria-invalid') === 'true', name: e.name || ''});
  });
  return out;
}
"""


class PatchrightDriver:
    def __init__(self, sessions_dir: Path, headless: bool = True, resume_path: str | None = None, pw=None):
        try:
            from patchright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError as ex:
            raise RuntimeError("install the extra: pip install 'job-radar-agent[apply]' and run: patchright install chromium") from ex
        self._pw = pw or sync_playwright().start()
        profile = sessions_dir / "apply-browser"
        profile.mkdir(parents=True, exist_ok=True)
        self.ctx = self._pw.chromium.launch_persistent_context(str(profile), headless=headless, locale="en-US",
                                                              viewport={"width": 1280, "height": 900})
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.resume_path = resume_path

    def close(self) -> None:
        self.ctx.close()
        self._pw.stop()

    # ---- FormDriver protocol
    def open(self, job: Job) -> None:
        self.page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(1500)
        if re.search(r"login|authwall|checkpoint", self.page.url):
            raise RuntimeError("not signed in: run `job-radar login --apply-browser`")
        btn = self.page.locator("button[aria-label*='Easy Apply']:visible, button.jobs-apply-button:visible").first
        if not btn.count():
            raise RuntimeError("no Easy Apply button (external application)")
        btn.click()
        self.page.wait_for_selector(DIALOG, timeout=20000)
        self.page.wait_for_timeout(800)

    def _dialog(self):
        return self.page.locator(DIALOG).last

    def fields(self) -> list[FormField]:
        raw = self._dialog().evaluate(_FIELDS_JS)
        return [FormField(kind=r["kind"], label=r["label"], required=r["required"], value=r["value"], checked=r["checked"],
                          options=r["options"], invalid=r["invalid"], handle=r) for r in raw]

    def fill(self, f: FormField, value: str) -> None:
        r = f.handle
        el = self._dialog().locator(f'[data-jr="{r["idx"]}"]')
        if f.kind == "select":
            el.select_option(label=value)
        elif f.kind == "radio":
            self._dialog().evaluate(
                """(root, a) => { const t = (r) => { const l = (r.id && document.querySelector('label[for="' + CSS.escape(r.id) + '"]')) || r.closest('label'); return (l ? l.innerText : r.value || '').trim(); };
                   const hit = [...root.querySelectorAll('input[type=radio]')].find(r => r.name === a.name && t(r) === a.value); if (hit) hit.click(); }""",
                {"name": r["name"], "value": value})
        else:
            el.fill(value)
        f.value = value

    def primary_button(self) -> str:
        for _ in range(40):
            d = self._dialog()
            for text, kind in (("Submit application", "submit"), ("Submit", "submit"), ("Review", "review"), ("Next", "next"),
                               ("Continue", "next")):
                if d.locator(f"button:visible:has-text('{text}')").count():
                    return kind
            time.sleep(0.25)
        return "unknown"

    def advance(self) -> str:
        kind = self.primary_button()
        names = {"submit": ["Submit application", "Submit"], "review": ["Review"], "next": ["Next", "Continue"]}.get(kind, [])
        for n in names:
            b = self._dialog().locator(f"button:visible:has-text('{n}')")
            if b.count():
                b.first.click()
                break
        self.page.wait_for_timeout(1200)
        return kind

    def discard(self) -> None:
        try:
            self._dialog().locator("button[aria-label*='Dismiss'], button[aria-label*='Close']").first.click(timeout=3000)
            self.page.locator("button:has-text('Discard')").first.click(timeout=3000)
        except Exception:  # noqa: BLE001
            pass

    def confirmed(self) -> bool:
        text = self.page.inner_text("body")
        return bool(re.search(r"application was sent|application submitted|applied (just now|\d+ (seconds?|minutes?) ago)", text, re.I))


def sign_in_interactively(sessions_dir: Path) -> None:
    """Open a visible browser on the sign-in page; the user logs in; the profile is kept in sessions/."""
    drv = PatchrightDriver(sessions_dir, headless=False)
    try:
        drv.page.goto("https://www.linkedin.com/login")
        input("Sign in in the browser window, then press Enter here to save the session... ")
    finally:
        drv.close()
