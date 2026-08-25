#!/usr/bin/env python3
"""Audition a chair envelope against the section contract.

Pass = schema-valid + toolset ⊆ ceiling + isolation lock + Mahler cue/budget/summary.
admit is ALWAYS false. Conductor still routes the model. DeepSeek auto-plugin is refused.

Usage:
  audition_chair.py --envelope chair.json
  audition_chair.py < chair.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "templates" / "envelope.json"
CONTRACT_PATH = ROOT / "templates" / "section-contract.json"

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


def is_brass_model(model: str) -> bool:
    if model in {"gpt-5.6-sol", "code1-gpt-5.6-sol", "code2-claude-opus-4-6-thinking"}:
        return True
    return model.endswith("-sol") or model == "sol"


def emit(payload: Dict[str, Any], code: int) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return code


def fail(reasons: List[str], extra: Optional[Dict[str, Any]] = None) -> int:
    body: Dict[str, Any] = {
        "audition": "fail",
        "admit": False,
        "reasons": reasons,
    }
    if extra:
        body.update(extra)
    return emit(body, 2)


def load_json(path: Optional[str]) -> Any:
    raw = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    return json.loads(raw)


def evaluate(envelope: Any) -> Dict[str, Any]:
    """Pure check. `admit` is always False. Caller prints / exits."""
    if not isinstance(envelope, dict):
        return {"audition": "fail", "admit": False, "reasons": ["envelope must be a JSON object"]}

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "audition": "fail",
            "admit": False,
            "reasons": [f"cannot load schema/contract: {exc}"],
        }

    reasons: List[str] = []
    for err in Draft7Validator(schema).iter_errors(envelope):
        path = ".".join(str(x) for x in err.absolute_path) or "$"
        reasons.append(f"schema {path}: {err.message}")

    raw_sender = envelope.get("sender")
    sender: Dict[str, Any] = raw_sender if isinstance(raw_sender, dict) else {}
    section = str(sender.get("section") or "")
    model = str(sender.get("model") or "")

    ceilings = contract.get("ceilings") if isinstance(contract.get("ceilings"), dict) else {}
    known_tools = set(contract.get("toolsets") or [])
    locks = contract.get("isolation_lock") if isinstance(contract.get("isolation_lock"), dict) else {}

    if section and section not in SECTIONS:
        reasons.append(f"unknown section: {section!r}")
    if section and section not in ceilings:
        reasons.append(f"no ceiling for section: {section!r}")

    if "allowed_toolsets" not in envelope:
        reasons.append("allowed_toolsets is required (empty = tacet)")
        tools: List[str] = []
    else:
        raw_tools = envelope.get("allowed_toolsets")
        if not isinstance(raw_tools, list):
            reasons.append("allowed_toolsets must be an array")
            tools = []
        else:
            tools = [str(x).strip() for x in raw_tools if str(x).strip()]
            unknown = [t for t in tools if t not in known_tools]
            if unknown:
                reasons.append(f"unknown toolset(s): {','.join(unknown)}")
            ceiling = set(ceilings.get(section) or [])
            if section in ceilings:
                overflow = [t for t in tools if t not in ceiling]
                if overflow:
                    reasons.append(
                        f"{section} toolset overflow: {','.join(overflow)} "
                        f"(ceiling={','.join(sorted(ceiling)) or '∅'})"
                    )

    isolation = envelope.get("isolation")
    if isolation is None:
        isolation = "shared"
    locked = locks.get(section)
    if locked and isolation != locked:
        reasons.append(f"{section} isolation must be {locked!r}, got {isolation!r}")

    budget = envelope.get("budget")
    if not isinstance(budget, dict) or not budget.get("dynamic_mark"):
        reasons.append("Mahler budget.dynamic_mark is required")

    raw_payload = envelope.get("payload")
    payload: Dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    if not str(payload.get("summary") or "").strip():
        reasons.append("payload.summary (exit deliverable) is required")

    if model and is_brass_model(model) and section not in {"heavy_brass", "conductor"}:
        reasons.append(f"{section} must not claim Heavy Brass model {model!r}")

    extra = {
        "section": section or None,
        "tacet": "allowed_toolsets" in envelope
        and isinstance(envelope.get("allowed_toolsets"), list)
        and not tools,
    }
    if reasons:
        body: Dict[str, Any] = {"audition": "fail", "admit": False, "reasons": reasons}
        body.update(extra)
        return body

    return {
        "audition": "pass",
        "admit": False,
        "section": section,
        "tacet": extra["tacet"],
        "ceiling": list(ceilings.get(section) or []),
        "allowed_toolsets": tools,
        "isolation": isolation,
        "model": model,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Audition a Mada Symphony chair envelope")
    p.add_argument("--envelope", help="Path to envelope JSON (default: stdin)")
    args = p.parse_args(argv)

    try:
        envelope = load_json(args.envelope)
    except json.JSONDecodeError as exc:
        return fail([f"invalid envelope json: {exc}"])
    except OSError as exc:
        return fail([f"cannot read envelope: {exc}"])

    result = evaluate(envelope)
    if result.get("audition") != "pass":
        return emit(result, 2)
    return emit(result, 0)


if __name__ == "__main__":
    raise SystemExit(main())
