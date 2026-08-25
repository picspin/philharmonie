#!/usr/bin/env python3
"""Envelope → hall spawn. Isolation fields drive argv/env; they are not costume.

Usage:
  spawn_chair.py --envelope chair.json -q "<brief>"
  spawn_chair.py --hall claude --dry-run --envelope chair.json -q "<brief>"
  spawn_chair.py --dry-run -q "<brief>" < chair.json

Default hall is Hermes. --hall / MADA_HALL selects Codex / Claude / Pi.
Refuses: audition fail (unless --force), missing/empty allowed_toolsets,
unknown section, cheap chair + sol without --brass-cue.
Does not auto-admit a model into the pool.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from audition_chair import evaluate  # noqa: E402
from halls import HALLS, HallError, csv_of, resolve_hall  # noqa: E402

# Re-export for callers / tests that imported these from spawn_chair.
HERMES_DEFAULT = "/opt/hermes/.venv/bin/hermes"
ALIASES = {"ox-alpha", "ox-alpha-free", "mimo", "mimo-v2.5", "mimo-v2-omni"}

SECTIONS = {
    "conductor",
    "oboe",
    "violin_1",
    "violin_2",
    "viola",
    "cello",
    "contrabass",
    "horn",
    "flute",
    "organ",
    "heavy_brass",
    "snare_drum",
    "cymbals",
    "harp",
    "bassoon",
    "trumpet",
}

BRASS_MODELS = (
    "gpt-5.6-sol",
    "code1-gpt-5.6-sol",
    "code2-claude-opus-4-6-thinking",
)


class SpawnError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def die(msg: str, code: int = 2) -> None:
    payload = {"ok": False, "error": msg}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    raise SystemExit(code)


def load_envelope(path: Optional[str]) -> Dict[str, Any]:
    try:
        if path:
            raw = open(path, encoding="utf-8").read()
        else:
            raw = sys.stdin.read()
    except OSError as exc:
        raise SpawnError(f"cannot read envelope: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SpawnError(f"invalid envelope json: {exc}") from exc
    if not isinstance(data, dict):
        raise SpawnError("envelope must be a JSON object")
    return data


def is_brass_model(model: str) -> bool:
    if model in BRASS_MODELS:
        return True
    if model.endswith("-sol") or model == "sol":
        return True
    return False


def plan(env_obj: Dict[str, Any], *, query: Optional[str], section_override: Optional[str],
         brass_cue: bool, hall_name: Optional[str] = None) -> Tuple[List[str], Dict[str, str], str]:
    raw_sender = env_obj.get("sender")
    sender: Dict[str, Any] = raw_sender if isinstance(raw_sender, dict) else {}
    section = section_override or str(sender.get("section") or "")
    if section not in SECTIONS:
        raise SpawnError(f"unknown section: {section!r}")

    model = str(sender.get("model") or "")
    if not model:
        raise SpawnError("sender.model is required")

    if "allowed_toolsets" not in env_obj:
        raise SpawnError("allowed_toolsets is required (empty = mute = refuse)")
    raw_tools = env_obj.get("allowed_toolsets")
    if not isinstance(raw_tools, list):
        raise SpawnError("allowed_toolsets must be an array")
    tools = [str(x).strip() for x in raw_tools if str(x).strip()]
    if not tools:
        raise SpawnError("allowed_toolsets is empty — Tacet chair, will not spawn")

    isolation = str(env_obj.get("isolation") or "shared")
    if isolation not in {"worktree", "shared"}:
        raise SpawnError(f"isolation must be worktree|shared, got {isolation!r}")

    tacet = env_obj.get("tacet_paths") or []
    if tacet and not isinstance(tacet, list):
        raise SpawnError("tacet_paths must be an array")
    tacet_csv = csv_of([str(x) for x in tacet]) if isinstance(tacet, list) else ""

    if is_brass_model(model):
        if section == "heavy_brass":
            pass
        elif section == "conductor" and brass_cue:
            pass
        else:
            raise SpawnError(
                f"{section} must not wake Heavy Brass ({model}) without --brass-cue"
            )

    raw_payload = env_obj.get("payload")
    payload: Dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    q = query if query is not None else str(payload.get("summary") or "")
    if not q:
        raise SpawnError("need -q or payload.summary")

    try:
        hall = resolve_hall(hall_name)
        argv = hall.argv(model=model, query=q, isolation=isolation, tools=tools)
    except HallError as exc:
        raise SpawnError(exc.message) from exc

    child_env = {
        "MADA_SECTION": section,
        "MADA_ALLOWED_TOOLSETS": csv_of(tools),
        "MADA_HALL": hall.name,
    }
    if tacet_csv:
        child_env["MADA_TACET_PATHS"] = tacet_csv
    if brass_cue:
        child_env["MADA_BRASS_CUE"] = "1"

    return argv, child_env, hall.name


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Spawn a Mada Symphony chair from an envelope")
    p.add_argument("--envelope", help="Path to envelope JSON (default: stdin)")
    p.add_argument("-q", "--query", help="Brief; defaults to payload.summary")
    p.add_argument("--section", help="Override sender.section")
    p.add_argument("--brass-cue", action="store_true", help="Allow conductor to wake sol")
    p.add_argument("--force", action="store_true", help="Skip audition; spawn latches still apply")
    p.add_argument("--dry-run", action="store_true", help="Print argv+env JSON, do not exec")
    p.add_argument(
        "--hall",
        help=f"Runtime adapter: {'|'.join(HALLS)} (default hermes / MADA_HALL)",
    )
    return p.parse_args(argv)


def effective_envelope(env_obj: Dict[str, Any], section_override: Optional[str]) -> Dict[str, Any]:
    effective = deepcopy(env_obj)
    if section_override:
        sender = effective.get("sender")
        if not isinstance(sender, dict):
            sender = {}
            effective["sender"] = sender
        sender["section"] = section_override
    return effective


def audition_or_die(env_obj: Dict[str, Any], *, force: bool) -> str:
    if force:
        return "skipped"
    result = evaluate(env_obj)
    if result.get("audition") != "pass":
        reasons = result.get("reasons") or ["audition failed"]
        raise SpawnError("audition failed: " + "; ".join(str(r) for r in reasons))
    return "pass"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        envelope = load_envelope(args.envelope)
        gate = audition_or_die(
            effective_envelope(envelope, args.section),
            force=bool(args.force),
        )
        cmd, child_env, hall = plan(
            envelope,
            query=args.query,
            section_override=args.section,
            brass_cue=bool(args.brass_cue),
            hall_name=args.hall,
        )
    except SpawnError as exc:
        die(exc.message)
        return 2

    if args.dry_run:
        sys.stdout.write(
            json.dumps(
                {"ok": True, "hall": hall, "argv": cmd, "env": child_env, "audition": gate},
                ensure_ascii=False,
            )
            + "\n"
        )
        return 0

    merged = os.environ.copy()
    merged.update(child_env)
    os.execvpe(cmd[0], cmd, merged)
    return 1  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
