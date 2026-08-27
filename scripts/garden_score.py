#!/usr/bin/env python3
"""Freshness latch for the Mada Symphony Katalog.

Checks (no LLM):
  1. Every `references|scripts|templates/...` path in SKILL.md exists.
  2. Every file in those dirs is named in SKILL.md (no orphan parts).
  3. SKILL.md ≤ 140 lines.
  4. envelope.json has no compaction_tier / protocol / message_type / sidechain / agent_id (refused costume). Root additionalProperties is false.
  5. sender.section enum == section-contract ceilings == spawn/audition SECTIONS.
  6. Each non-test script has a sibling test_*.sh.

Usage:
  garden_score.py
  garden_score.py --root /path/to/mada-symphony
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

CAT_RE = re.compile(r"`((?:references|scripts|templates)/[^`\s]+)`")
SECTION_SET_RE = re.compile(
    r"SECTIONS\s*=\s*\{([^}]+)\}",
    re.MULTILINE | re.DOTALL,
)
IDENT_RE = re.compile(r'"([a-z0-9_]+)"')
SKIP_NAMES = {".DS_Store", "__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
KATALOG_MAX = 140


def emit(ok: bool, errors: List[str], extra: Optional[Dict[str, Any]] = None) -> int:
    body: Dict[str, Any] = {"ok": ok, "errors": errors}
    if extra:
        body.update(extra)
    sys.stdout.write(json.dumps(body, ensure_ascii=False) + "\n")
    return 0 if ok else 2


def listed_paths(skill: str) -> Set[str]:
    return set(CAT_RE.findall(skill))


def on_disk(root: Path, rel_dir: str) -> Set[str]:
    d = root / rel_dir
    if not d.is_dir():
        return set()
    out: Set[str] = set()
    for p in d.rglob("*"):
        if p.is_dir():
            continue
        if p.name in SKIP_NAMES or p.suffix in SKIP_SUFFIXES:
            continue
        out.add(str(p.relative_to(root)))
    return out


def parse_sections_py(text: str) -> Optional[Set[str]]:
    m = SECTION_SET_RE.search(text)
    if not m:
        return None
    return set(IDENT_RE.findall(m.group(1)))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def garden(root: Path) -> List[str]:
    errors: List[str] = []
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        return [f"missing {skill_path}"]
    skill = skill_path.read_text(encoding="utf-8")
    lines = skill.count("\n") + (0 if skill.endswith("\n") or not skill else 1)
    if lines > KATALOG_MAX:
        errors.append(f"Katalog SKILL.md is {lines} lines (budget {KATALOG_MAX})")

    named = listed_paths(skill)
    if not named:
        errors.append("Katalog table lists no references|scripts|templates paths")

    for rel in sorted(named):
        if not (root / rel).exists():
            errors.append(f"catalog path missing: {rel}")

    disk: Set[str] = set()
    for folder in ("references", "scripts", "templates"):
        disk |= on_disk(root, folder)
    orphans = sorted(disk - named)
    for rel in orphans:
        errors.append(f"orphan part not in Katalog: {rel}")

    envelope_path = root / "templates" / "envelope.json"
    if envelope_path.is_file():
        raw = envelope_path.read_text(encoding="utf-8")
        if "compaction_tier" in raw:
            errors.append("compaction_tier costume in templates/envelope.json")
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"envelope.json invalid: {exc}")
            envelope = None
        else:
            props = envelope.get("properties") if isinstance(envelope, dict) else None
            if isinstance(envelope, dict) and envelope.get("additionalProperties") is not False:
                errors.append("additionalProperties must be false in templates/envelope.json")
            if isinstance(props, dict):
                for key in ("protocol", "message_type", "sidechain"):
                    if key in props:
                        errors.append(f"{key} costume in templates/envelope.json")
                sender_obj = props.get("sender")
                sender = sender_obj if isinstance(sender_obj, dict) else {}
                sprops_obj = sender.get("properties")
                sprops = sprops_obj if isinstance(sprops_obj, dict) else {}
                if "agent_id" in sprops:
                    errors.append("agent_id costume in templates/envelope.json")
                rec_obj = props.get("recipient")
                rec = rec_obj if isinstance(rec_obj, dict) else {}
                rprops_obj = rec.get("properties")
                rprops = rprops_obj if isinstance(rprops_obj, dict) else {}
                if "agent_id" in rprops:
                    errors.append("agent_id costume in templates/envelope.json")
    else:
        envelope = None

    contract_path = root / "templates" / "section-contract.json"
    contract = None
    if contract_path.is_file():
        try:
            contract = load_json(contract_path)
        except json.JSONDecodeError as exc:
            errors.append(f"section-contract.json invalid: {exc}")

    enum: Optional[Set[str]] = None
    if isinstance(envelope, dict):
        try:
            enum = set(
                envelope["properties"]["sender"]["properties"]["section"]["enum"]
            )
        except (KeyError, TypeError):
            errors.append("envelope.json missing sender.section.enum")

    ceilings: Optional[Set[str]] = None
    if isinstance(contract, dict):
        raw_c = contract.get("ceilings")
        if isinstance(raw_c, dict):
            ceilings = set(raw_c)
        else:
            errors.append("section-contract.json missing ceilings object")

    spawn_set = None
    spawn_path = root / "scripts" / "spawn_chair.py"
    if spawn_path.is_file():
        spawn_set = parse_sections_py(spawn_path.read_text(encoding="utf-8"))
        if spawn_set is None:
            errors.append("spawn_chair.py SECTIONS set not found")

    aud_set = None
    aud_path = root / "scripts" / "audition_chair.py"
    if aud_path.is_file():
        aud_set = parse_sections_py(aud_path.read_text(encoding="utf-8"))
        if aud_set is None:
            errors.append("audition_chair.py SECTIONS set not found")

    labeled = [
        ("envelope.enum", enum),
        ("section-contract.ceilings", ceilings),
        ("spawn_chair.SECTIONS", spawn_set),
        ("audition_chair.SECTIONS", aud_set),
    ]
    present = [(n, s) for n, s in labeled if s is not None]
    if len(present) >= 2:
        base_name, base = present[0]
        for name, s in present[1:]:
            if s != base:
                extra = sorted(s - base)
                missing = sorted(base - s)
                bit = []
                if extra:
                    bit.append(f"extra={extra}")
                if missing:
                    bit.append(f"missing={missing}")
                errors.append(f"section enum drift: {name} ≠ {base_name} ({', '.join(bit)})")

    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        for p in sorted(scripts_dir.iterdir()):
            if not p.is_file() or p.name.startswith("test_"):
                continue
            if p.suffix not in {".py", ".sh"}:
                continue
            stem = p.stem.replace("-", "_")
            want = scripts_dir / f"test_{stem}.sh"
            if not want.is_file():
                errors.append(f"missing contract test: scripts/{want.name}")

    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Garden the Mada Symphony Katalog")
    p.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    errors = garden(root)
    extra = {"root": str(root), "katalog_lines": None}
    skill = root / "SKILL.md"
    if skill.is_file():
        text = skill.read_text(encoding="utf-8")
        extra["katalog_lines"] = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    return emit(not errors, errors, extra)


if __name__ == "__main__":
    raise SystemExit(main())
