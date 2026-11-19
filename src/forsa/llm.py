# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Omar Qenawy
"""LLM access: one narrow function, no tools, no permissions.

Rules that make prompt injection harmless here:
  * every LLM call is text in, text out. The model can not send, apply, connect or run anything;
  * untrusted text (job descriptions, emails, scraped pages) is fenced and only used by steps that write
    drafts or advice;
  * the output is validated (length, placeholders, forbidden patterns) before it is stored.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from .config import env

FENCE_RE = re.compile(r"</?\s*(untrusted|job|cv|profile)[^>]*>", re.I)
MAX_CALLS_DEFAULT = 10


class LLMError(RuntimeError):
    pass


def fence(text: str, tag: str = "untrusted") -> str:
    """Wrap untrusted text so the prompt can tell the model it is data; strip anything that fakes the tag."""
    clean = FENCE_RE.sub("", str(text or ""))
    return f"<{tag}>\n{clean}\n</{tag}>"


class LLM:
    def __init__(self, provider: str = "none", model: str = "", max_calls: int = MAX_CALLS_DEFAULT, runner=None):
        self.provider, self.model, self.max_calls = provider, model, max_calls
        self.calls = 0
        self._runner = runner  # injected in tests

    @property
    def enabled(self) -> bool:
        return self.provider != "none"

    def complete(self, prompt: str, max_tokens: int = 800) -> str | None:
        """Text answer, or None when no provider is configured / the call budget is used up."""
        if not self.enabled or self.calls >= self.max_calls:
            return None
        self.calls += 1
        if self._runner:
            return self._runner(prompt)
        if self.provider == "anthropic":
            return self._anthropic(prompt, max_tokens)
        if self.provider == "claude-cli":
            return self._cli(prompt)
        raise LLMError(f"unknown provider {self.provider}")

    def _anthropic(self, prompt: str, max_tokens: int) -> str:
        key = env("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as ex:
            raise LLMError("install the extra: pip install 'forsa[llm]'") from ex
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(model=self.model or "claude-haiku-5-5", max_tokens=max_tokens,
                                     messages=[{"role": "user", "content": prompt}])  # no tools passed
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    def _cli(self, prompt: str) -> str:
        exe = shutil.which("claude")
        if not exe:
            raise LLMError("the 'claude' CLI is not on PATH")
        cmd = [exe, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--no-session-persistence"]
        if self.model:
            cmd += ["--model", self.model]
        out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300, check=False)
        try:
            data = json.loads(out.stdout)
        except json.JSONDecodeError as ex:
            raise LLMError(f"bad output from claude CLI (rc {out.returncode})") from ex
        if data.get("is_error") or not data.get("result"):
            raise LLMError("claude CLI returned an error")
        return str(data["result"])


FORBIDDEN_OUTPUT = re.compile(
    r"(?i)ignore (all|previous|the above)|system prompt|api[_ -]?key|password|\bBEGIN [A-Z ]*KEY\b")


def validate_text(text: str | None, max_words: int = 300) -> str | None:
    """Reason the text must be rejected, or None if it is fine (empty, too long, placeholders, leaks)."""
    if not text or not text.strip():
        return "empty answer"
    if len(text.split()) > max_words:
        return "too long"
    if re.search(r"\{[a-z_]+\}|\[[A-Z][A-Za-z ]+\]", text):
        return "unfilled placeholder"
    if FORBIDDEN_OUTPUT.search(text):
        return "suspicious content"
    return None
