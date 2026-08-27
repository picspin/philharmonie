#!/usr/bin/env python3
"""Hall adapters — plug Philharmonie into a runtime.

The hall (envelope, audition, Tacet, garden, snare) is runtime-agnostic.
A hall adapter is the only place that may speak a vendor CLI.

DeepSeek “everything is a plugin” here means: chairs / adapters / hooks
plug in. It does **not** mean a chair auto-admits itself into the pool.
"""
from __future__ import annotations

import os
import shutil
from typing import Dict, List, Optional, Sequence

HALLS = ("hermes", "codex", "claude", "pi")
CAP_KEYS = ("worktree", "tool_allowlist", "model_pin", "pre_tool_hook")


def _caps(**kwargs):
    extra = set(kwargs) - set(CAP_KEYS)
    if extra:
        raise HallError(f"unknown capability keys: {sorted(extra)}")
    missing = set(CAP_KEYS) - set(kwargs)
    if missing:
        raise HallError(f"missing capability keys: {sorted(missing)}")
    return {k: kwargs[k] for k in CAP_KEYS}

HERMES_DEFAULT = "/opt/hermes/.venv/bin/hermes"
ALIASES = {"ox-alpha", "ox-alpha-free", "mimo", "mimo-v2.5", "mimo-v2-omni"}

# Envelope toolsets → Claude Code --allowedTools names (probed 2026-08).
CLAUDE_TOOLS: Dict[str, List[str]] = {
    "terminal": ["Bash"],
    "file": ["Read", "Edit", "Write", "Glob", "Grep"],
    "web": ["WebSearch", "WebFetch"],
    "delegation": ["Task"],
    "vision": ["Read"],
}


class HallError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def csv_of(items: Sequence[str]) -> str:
    return ",".join(x.strip() for x in items if str(x).strip())


def _which_or(keys: Sequence[str], fallback: str) -> str:
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val
    found = shutil.which(fallback)
    return found or fallback


def provider_for(model: str) -> Optional[str]:
    """Hermes-hall routing only. Foreign halls do not invent --provider."""
    if not model:
        raise HallError("sender.model is required")
    if model in ALIASES:
        return None
    if model.startswith(("code1-", "code2-", "mga-", "mga-r-")):
        return "litellm-gateway"
    return "cliproxy"


def _dedupe(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


class HermesHall:
    name = "hermes"
    capabilities = _caps(worktree=True, tool_allowlist=True, model_pin=True, pre_tool_hook="external")

    def binary(self) -> str:
        for key in ("MADA_HERMES", "HERMES"):
            val = os.environ.get(key)
            if val:
                return val
        found = shutil.which("hermes")
        return found or HERMES_DEFAULT

    def argv(self, *, model: str, query: str, isolation: str, tools: Sequence[str]) -> List[str]:
        cmd: List[str] = [self.binary(), "chat"]
        if isolation == "worktree":
            cmd.append("-w")
        cmd.extend(["-q", query])
        provider = provider_for(model)
        if provider:
            cmd.extend(["--provider", provider])
        cmd.extend(["-m", model, "-t", csv_of(tools), "--yolo"])
        return cmd


class ClaudeHall:
    """Claude Code CLI (probed: claude -p --model --worktree --allowedTools)."""

    name = "claude"
    capabilities = _caps(worktree=True, tool_allowlist=True, model_pin=True, pre_tool_hook="external")

    def binary(self) -> str:
        return _which_or(("MADA_CLAUDE", "CLAUDE"), "claude")

    def argv(self, *, model: str, query: str, isolation: str, tools: Sequence[str]) -> List[str]:
        mapped: List[str] = []
        for ts in tools:
            mapped.extend(CLAUDE_TOOLS.get(ts, []))
        mapped = _dedupe(mapped)
        cmd: List[str] = [self.binary(), "-p", "--model", model]
        if isolation == "worktree":
            cmd.append("--worktree")
        if mapped:
            cmd.extend(["--allowedTools", ",".join(mapped)])
        # Unattended analog of hermes --yolo — not a full sandbox bypass.
        cmd.extend(["--permission-mode", "acceptEdits", query])
        return cmd


class CodexHall:
    """Codex CLI (probed: codex exec -m --sandbox). No -t; Tacet is hook + env."""

    name = "codex"
    capabilities = _caps(worktree=False, tool_allowlist=False, model_pin=True, pre_tool_hook="external")

    def binary(self) -> str:
        return _which_or(("MADA_CODEX", "CODEX"), "codex")

    def argv(self, *, model: str, query: str, isolation: str, tools: Sequence[str]) -> List[str]:
        del isolation, tools  # isolation/toolsets travel as MADA_*; Codex has no -t/-w.
        sandbox = os.environ.get("MADA_CODEX_SANDBOX") or "workspace-write"
        return [self.binary(), "exec", "-m", model, "-s", sandbox, query]


class PiHall:
    """Pi / pi-coding-agent. Flags vary — prompt is positional. Wrap if needed."""

    name = "pi"
    capabilities = _caps(worktree=False, tool_allowlist=False, model_pin=False, pre_tool_hook="none")

    def binary(self) -> str:
        return _which_or(("MADA_PI", "PI"), "pi")

    def argv(self, *, model: str, query: str, isolation: str, tools: Sequence[str]) -> List[str]:
        del model, isolation, tools  # no invented -m/-t/-w. Env is the contract.
        return [self.binary(), query]


_REGISTRY = {
    "hermes": HermesHall,
    "claude": ClaudeHall,
    "codex": CodexHall,
    "pi": PiHall,
}


def resolve_hall(name: Optional[str] = None) -> object:
    raw = (name or os.environ.get("MADA_HALL") or "hermes").strip().lower()
    if not raw:
        raw = "hermes"
    cls = _REGISTRY.get(raw)
    if cls is None:
        raise HallError(f"unknown hall: {raw!r} (want {', '.join(HALLS)})")
    return cls()


def hermes_bin() -> str:
    """Compat export — same pin as HermesHall.binary()."""
    return HermesHall().binary()
