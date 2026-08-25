#!/usr/bin/env python3
"""0-token latch: target project's AGENTS.md must list the four Snare rungs.

Scans the **target repo**, not this skill. Does not run the commands.
CLAUDE.md / README.md are not substitutes.

Rungs (aliases in parentheses):
  lint      (format, fmt)
  unit      (pytest)
  e2e       (integration)
  security  (fff, audit, gitleaks)

A rung counts only if a pasteable command is attached: `backticks`,
`$ prompt`, or a following fenced block.

Usage:
  snare_score.py --root /path/to/project
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

RUNG_ALIASES = {
    "lint": ("lint", "format", "fmt"),
    "unit": ("unit", "pytest"),
    "e2e": ("e2e", "integration"),
    "security": ("security", "fff", "audit", "gitleaks"),
}
ALIAS_TO_RUNG = {alias: rung for rung, aliases in RUNG_ALIASES.items() for alias in aliases}
ALIAS_RE = "|".join(re.escape(a) for a in sorted(ALIAS_TO_RUNG, key=len, reverse=True))
LABEL_LINE = re.compile(
    rf"""(?ix)
    ^\s*
    (?:\#{{1,6}}\s+)?
    (?:[-*]\s+)?
    \**
    (?P<label>{ALIAS_RE})
    \**
    \s*:?
    \s*
    (?P<rest>.*)$
    """
)
BACKTICK = re.compile(r"`([^`\n]+)`")
DOLLAR = re.compile(r"^\$\s+(\S.*\S|\S)\s*$")
FENCE = re.compile(r"^```")
RUNG_ORDER = ("lint", "unit", "e2e", "security")


def emit(ok: bool, errors: List[str], extra: Optional[Dict[str, Any]] = None) -> int:
    body: Dict[str, Any] = {"ok": ok, "errors": errors}
    if extra:
        body.update(extra)
    sys.stdout.write(json.dumps(body, ensure_ascii=False) + "\n")
    return 0 if ok else 2


def command_from(text: str) -> Optional[str]:
    m = BACKTICK.search(text)
    if m:
        cmd = m.group(1).strip()
        return cmd or None
    m = DOLLAR.match(text.strip())
    if m:
        return m.group(1).strip()
    return None


def fence_body(lines: List[str], start: int) -> Tuple[Optional[str], int]:
    if start >= len(lines) or not FENCE.match(lines[start].strip()):
        return None, start
    body: List[str] = []
    i = start + 1
    while i < len(lines) and not FENCE.match(lines[i].strip()):
        body.append(lines[i].rstrip())
        i += 1
    if i >= len(lines):
        return None, start
    cmd = "\n".join(x for x in body).strip()
    return (cmd or None), i + 1


def next_command(lines: List[str], idx: int) -> Optional[str]:
    i = idx
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return None
    if LABEL_LINE.match(lines[i]):
        return None
    cmd = command_from(lines[i])
    if cmd:
        return cmd
    cmd, _ = fence_body(lines, i)
    return cmd


def parse_rungs(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    found: Dict[str, str] = {}
    i = 0
    while i < len(lines):
        m = LABEL_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        rung = ALIAS_TO_RUNG[m.group("label").lower()]
        rest = (m.group("rest") or "").strip()
        cmd = command_from(rest)
        if not cmd and not rest:
            cmd = next_command(lines, i + 1)
        if cmd and rung not in found:
            found[rung] = cmd
        i += 1
    return found


def score(root: Path) -> Tuple[List[str], Dict[str, Optional[str]]]:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return [f"missing {agents.name} (CLAUDE.md is not a substitute)"], {
            r: None for r in RUNG_ORDER
        }
    found = parse_rungs(agents.read_text(encoding="utf-8"))
    errors: List[str] = []
    rungs: Dict[str, Optional[str]] = {}
    for rung in RUNG_ORDER:
        cmd = found.get(rung)
        rungs[rung] = cmd
        if not cmd:
            aliases = "/".join(RUNG_ALIASES[rung])
            errors.append(f"AGENTS.md missing pasteable {rung} command ({aliases})")
    return errors, rungs


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Score a target project's AGENTS.md verify ladder")
    p.add_argument("--root", required=True, help="Target project root (not this skill)")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    errors, rungs = score(root)
    return emit(not errors, errors, {"root": str(root), "rungs": rungs})


if __name__ == "__main__":
    raise SystemExit(main())
