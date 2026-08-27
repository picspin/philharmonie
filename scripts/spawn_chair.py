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
import signal
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
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


def enforce_hall_capabilities(hall: Any, *, isolation: str, model: str, tools: Sequence[str]) -> Dict[str, Any]:
    cap = getattr(hall, "capabilities", None)
    if not isinstance(cap, dict):
        raise SpawnError(f"hall {hall.name} missing capabilities")
    if isolation == "worktree" and not cap.get("worktree"):
        raise SpawnError(f"hall {hall.name} cannot enforce isolation=worktree")
    if model and not cap.get("model_pin"):
        raise SpawnError(f"hall {hall.name} cannot pin sender.model")
    if tools and not cap.get("tool_allowlist") and cap.get("pre_tool_hook") != "external":
        raise SpawnError(f"hall {hall.name} cannot enforce allowed_toolsets")
    return cap


def plan(env_obj: Dict[str, Any], *, query: Optional[str], section_override: Optional[str],
         brass_cue: bool, hall_name: Optional[str] = None) -> Tuple[List[str], Dict[str, str], str, Dict[str, Any], Optional[int]]:
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

    raw_budget = env_obj.get("budget")
    budget: Dict[str, Any] = raw_budget if isinstance(raw_budget, dict) else {}
    timeout_sec: Optional[int] = None
    if "timeout_sec" in budget and budget["timeout_sec"] is not None:
        try:
            timeout_sec = int(budget["timeout_sec"])
        except (TypeError, ValueError) as exc:
            raise SpawnError("budget.timeout_sec must be an integer") from exc
        if timeout_sec <= 0:
            raise SpawnError("budget.timeout_sec must be > 0")

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
        cap = enforce_hall_capabilities(hall, isolation=isolation, model=model, tools=tools)
        argv = hall.argv(model=model, query=q, isolation=isolation, tools=tools)
    except HallError as exc:
        raise SpawnError(exc.message) from exc

    child_env = {
        "MADA_SECTION": section,
        "MADA_ALLOWED_TOOLSETS": csv_of(tools),
        "MADA_HALL": hall.name,
        "MADA_ISOLATION": isolation,
    }
    if tacet_csv:
        child_env["MADA_TACET_PATHS"] = tacet_csv
    if brass_cue:
        child_env["MADA_BRASS_CUE"] = "1"

    return argv, child_env, hall.name, cap, timeout_sec


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Spawn a Mada Symphony chair from an envelope")
    p.add_argument("--envelope", help="Path to envelope JSON (default: stdin)")
    p.add_argument("-q", "--query", help="Brief; defaults to payload.summary")
    p.add_argument("--section", help="Override sender.section")
    p.add_argument("--brass-cue", action="store_true", help="Allow conductor to wake sol")
    p.add_argument("--force", action="store_true", help="Skip audition; spawn latches still apply")
    p.add_argument("--dry-run", action="store_true", help="Print argv+env JSON, do not exec")
    p.add_argument(
        "--supervise",
        action="store_true",
        help="Wait the child; honor budget.timeout_sec; print result envelope",
    )
    p.add_argument("--jsonl", help="Append spawn/exit JSONL events (requires --supervise)")
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_jsonl(path: Optional[str], event: Dict[str, Any]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def supervise(
    cmd: Sequence[str],
    env: Dict[str, str],
    *,
    hall: str,
    cap: Dict[str, Any],
    audition: str,
    timeout_sec: Optional[int],
    jsonl_path: Optional[str],
) -> int:
    started = _now()
    _append_jsonl(
        jsonl_path,
        {"event": "spawn", "ts": started, "hall": hall, "timeout_sec": timeout_sec},
    )
    try:
        proc = subprocess.Popen(
            list(cmd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        die(f"cannot spawn {cmd[0]}: {exc}")
        return 2
    status, reason, code = "ok", "exited", 0
    try:
        out_b, err_b = proc.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        out_b, err_b = proc.communicate()
        status, reason, code = "timeout", "timeout", 124
    else:
        code = int(proc.returncode or 0)
        if code != 0:
            status, reason = "error", "exited"
    ended = _now()
    exit_code = 124 if status == "timeout" else code
    result = {
        "ok": status == "ok",
        "status": status,
        "exit_reason": reason,
        "exit_code": exit_code,
        "hall": hall,
        "argv": list(cmd),
        "audition": audition,
        "capabilities": cap,
        "timeout_sec": timeout_sec,
        "started_at": started,
        "ended_at": ended,
        "stdout": (out_b or b"").decode("utf-8", "replace"),
        "stderr": (err_b or b"").decode("utf-8", "replace"),
    }
    _append_jsonl(
        jsonl_path,
        {
            "event": "exit",
            "ts": ended,
            "status": status,
            "exit_code": exit_code,
            "exit_reason": reason,
        },
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    if status == "ok":
        return 0
    if status == "timeout":
        return 124
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.jsonl and not args.supervise:
        die("--jsonl requires --supervise")
        return 2
    try:
        envelope = load_envelope(args.envelope)
        gate = audition_or_die(
            effective_envelope(envelope, args.section),
            force=bool(args.force),
        )
        cmd, child_env, hall, cap, timeout_sec = plan(
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
                {
                    "ok": True,
                    "hall": hall,
                    "argv": cmd,
                    "env": child_env,
                    "audition": gate,
                    "capabilities": cap,
                    "timeout_sec": timeout_sec,
                    "supervise": bool(args.supervise),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return 0

    merged = os.environ.copy()
    merged.update(child_env)
    if not args.supervise:
        os.execvpe(cmd[0], cmd, merged)
        return 1  # unreachable
    return supervise(
        cmd,
        merged,
        hall=hall,
        cap=cap,
        audition=gate,
        timeout_sec=timeout_sec,
        jsonl_path=args.jsonl,
    )


if __name__ == "__main__":
    raise SystemExit(main())
