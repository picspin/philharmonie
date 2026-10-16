#!/usr/bin/env python3
"""Compose, validate and resolve Concert Hall plans. Never spawn or admit a chair."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
SHELL_SECTIONS = {"snare_drum", "cymbals"}
SECTION_TIERS = {
    "conductor": "high-reasoning-flash",
    "oboe": "contract-precise",
    "violin_1": "heavy-code",
    "violin_2": "review-critique",
    "viola": "heavy-code",
    "cello": "context-long",
    "contrabass": "context-long",
    "horn": "heavy-code",
    "flute": "high-reasoning-flash",
    "organ": "context-long",
    "heavy_brass": "frontier-heavy",
    "snare_drum": "0-token-shell",
    "cymbals": "0-token-shell",
    "harp": "multimodal-vision",
    "bassoon": "contract-precise",
    "trumpet": "contract-precise",
}
STYLES = (
    "mozart_sonata", "beethoven_symphony", "brahms_variation",
    "tchaikovsky_ballet", "rachmaninoff_climax",
)


def read_json(path: Optional[str]) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    raw = Path(path).read_text(encoding="utf-8") if path and path != "-" else sys.stdin.read()
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def schema_errors(value: Any, name: str) -> list[str]:
    schema = read_json(str(ROOT / "templates" / name))
    return [
        f"{'.'.join(str(p) for p in err.absolute_path) or '$'}: {err.message}"
        for err in Draft7Validator(schema).iter_errors(value)
    ]


def validate_score(score: Any) -> list[str]:
    """Schema plus graph, Tacet, isolation and routing invariants; no host I/O."""
    errors = schema_errors(score, "score-schema.json")
    if errors:
        return errors
    contract = read_json(str(ROOT / "templates" / "section-contract.json"))
    sections = set(contract["ceilings"])
    routing = score["section_routing"]
    if set(SECTION_TIERS) != sections:
        errors.append("section tier defaults drift from section-contract ceilings")
    if not set(routing) <= sections:
        errors.append("routing contains sections without a tool ceiling")
    required = {"conductor"}
    movements = score["movements"]
    brass_movements = 0
    for expected_index, movement in enumerate(movements, 1):
        index = movement["index"]
        prefix = f"movement {expected_index}"
        if index != expected_index:
            errors.append(f"{prefix}: indices must be contiguous and ordered")
        active, tacet = set(movement["active_sections"]), set(movement["tacet_sections"])
        required |= active
        if movement["lead_section"] not in active:
            errors.append(f"{prefix}: lead must be active")
        if active & tacet:
            errors.append(f"{prefix}: active and Tacet sections overlap")
        if active | tacet != sections:
            errors.append(f"{prefix}: every contract section must be active or Tacet")
        for section in active:
            lock = contract["isolation_lock"].get(section)
            if lock and movement["isolation"] != lock:
                errors.append(f"{prefix}: {section} isolation must be {lock}")
        if movement["circuit_breaker"] and not active & SHELL_SECTIONS:
            errors.append(f"{prefix}: circuit breaker requires Snare or Cymbals")
        if "heavy_brass" in active:
            brass_movements += 1
        seen = set()
        for dependency in movement["depends_on"]:
            source = dependency["movement"]
            if source in seen:
                errors.append(f"{prefix}: duplicate dependency movement {source}")
            seen.add(source)
            if source >= index or source < 1 or source > len(movements):
                errors.append(f"{prefix}: dependency must reference an earlier movement")
            elif dependency["cue"] != movements[source - 1]["cue_on_exit"]:
                errors.append(f"{prefix}: dependency cue does not match movement {source}")
    if brass_movements and not str(score.get("brass_cue", "")).strip():
        errors.append("Heavy Brass requires an explicit brass_cue; a style is not a grant")
    if brass_movements > 1:
        errors.append("Heavy Brass permits one wave per score")
    missing = required - set(routing)
    if missing:
        errors.append(f"missing section routing: {', '.join(sorted(missing))}")
    for section, route in routing.items():
        tier = route["tier"]
        state = route["resolution"]
        model = route["assigned_model"]
        resolved = route["resolved_tier"]
        if (section in SHELL_SECTIONS) != (tier == "0-token-shell"):
            errors.append(f"{section}: 0-token-shell is exclusive to Snare/Cymbals")
        if section == "heavy_brass" and tier != "frontier-heavy":
            errors.append("heavy_brass requires frontier-heavy")
        if tier == "frontier-heavy" and section not in {"heavy_brass", "conductor"}:
            errors.append(f"{section}: cannot request frontier-heavy")
        if state == "unresolved":
            if model is not None or resolved is not None or route["source"] != "none":
                errors.append(f"{section}: unresolved routing must have null model/tier and source none")
        elif state == "local":
            if section not in SHELL_SECTIONS or model != "local-bash" or resolved != tier or route["source"] != "local-shell":
                errors.append(f"{section}: invalid local shell routing")
        else:
            if section in SHELL_SECTIONS or model in {None, "auto", "local-bash"}:
                errors.append(f"{section}: resolved LLM routing needs an explicit model")
            if route["source"] not in {"registry", "section-config", "environment"}:
                errors.append(f"{section}: invalid model routing source")
            if state == "resolved" and resolved != tier:
                errors.append(f"{section}: resolved tier must match requested tier")
            if state == "fallback" and (resolved is None or resolved == tier or resolved in {"frontier-heavy", "0-token-shell"}):
                errors.append(f"{section}: invalid fallback tier")
    return errors


def registry_errors(registry: Any) -> list[str]:
    errors = schema_errors(registry, "hall-registry-schema.json")
    if errors:
        return errors
    seen = set()
    for model in registry["models"]:
        name = model["id"]
        if name in seen:
            errors.append(f"duplicate model id: {name}")
        seen.add(name)
        if name in {"auto", "local-bash"} or name != name.strip():
            errors.append(f"reserved or untrimmed model id: {name}")
    for section in registry.get("sections", {}):
        if section in SHELL_SECTIONS:
            errors.append(f"{section}: local shell binding cannot be overridden")
    for tier, fallback in registry.get("fallbacks", {}).items():
        if tier in fallback:
            errors.append(f"{tier}: fallback cannot reference itself")
        if "frontier-heavy" in fallback:
            errors.append(f"{tier}: fallback cannot escalate to frontier-heavy")
    return errors


def needed_sections(score: dict) -> set[str]:
    return {"conductor"} | {
        section for movement in score["movements"] for section in movement["active_sections"]
    }


def resolve_score(score: dict, registry: dict, environ: Mapping[str, str], *,
                  allow_unresolved: bool = False) -> tuple[dict, list[str]]:
    """Resolve only against an explicit enabled inventory. Fallbacks are one hop."""
    errors = validate_score(score) + registry_errors(registry)
    if errors:
        return copy.deepcopy(score), errors
    result = copy.deepcopy(score)
    models = [model for model in registry["models"] if model.get("enabled", True)]
    by_id = {model["id"]: model for model in models}
    unresolved = []
    for section, previous in result["section_routing"].items():
        tier = previous["tier"]
        route = {
            "tier": tier, "assigned_model": None, "resolution": "unresolved",
            "resolved_tier": None, "source": "none",
        }
        result["section_routing"][section] = route
        env_key = f"MADA_SECTION_MODEL_{section.upper()}"
        if section in SHELL_SECTIONS:
            if env_key in environ:
                errors.append(f"{section}: local shell binding cannot be overridden")
            route.update(assigned_model="local-bash", resolution="local",
                         resolved_tier=tier, source="local-shell")
            continue
        compatible = [tier] + registry.get("fallbacks", {}).get(tier, [])
        # A non-Brass chair may not reach a frontier-only model through a cheap fallback.
        def supports(model, candidate_tier):
            return candidate_tier in model["tiers"] and (
                section in {"heavy_brass", "conductor"} or "frontier-heavy" not in model["tiers"]
            )

        explicit = None
        source = "registry"
        if env_key in environ:
            explicit, source = environ[env_key].strip(), "environment"
        elif section in registry.get("sections", {}):
            explicit, source = registry["sections"][section], "section-config"
        selected = None
        resolved_tier = None
        for candidate_tier in compatible:
            candidates = models if explicit is None else [by_id[explicit]] if explicit in by_id else []
            selected = next((model for model in candidates if supports(model, candidate_tier)), None)
            if selected:
                resolved_tier = candidate_tier
                break
        if selected:
            route.update(assigned_model=selected["id"], resolved_tier=resolved_tier,
                         resolution="resolved" if resolved_tier == tier else "fallback", source=source)
        else:
            unresolved.append(section)
            if explicit is not None:
                errors.append(f"{section}: explicit model binding is absent, disabled or incompatible")
    if not allow_unresolved:
        for section in sorted(needed_sections(result) & set(unresolved)):
            errors.append(f"{section}: no enabled model for tier {result['section_routing'][section]['tier']}")
    return result, errors


def compose_score(task: str, style: str = "mozart_sonata", task_type: str = "coding",
                  score_id: Optional[str] = None, brass_cue: Optional[str] = None) -> dict:
    """Deterministic forms chosen by the caller; no remote classifier or LLM."""
    if style not in STYLES:
        raise ValueError(f"unknown style: {style}")
    if not task.strip() or not task_type.strip():
        raise ValueError("task and task_type must not be blank")
    if style == "rachmaninoff_climax" and not (brass_cue or "").strip():
        raise ValueError("rachmaninoff_climax requires --brass-cue")
    lead, first, middle = "oboe", "Overture", "Variation"
    first_deliverable = "SPEC.md + invariant test stubs"
    implementation = "violin_1"
    if style == "beethoven_symphony":
        first, middle = "Motive (Overture)", "Development (Variation)"
    elif style == "brahms_variation":
        middle = "One small variation"
    elif style == "tchaikovsky_ballet":
        lead, implementation, first, middle = "harp", "viola", "Visual brief", "Scene implementation"
        first_deliverable = "UI-SPEC.md + screenshot findings"
    elif style == "rachmaninoff_climax":
        lead, implementation, first, middle = "cello", "heavy_brass", "Long-context brief", "One cued climax"
        first_deliverable = "CONTEXT.md + locked audit scope"
    form = [
        (first, lead, "shared", "SPEC_LOCKED", first_deliverable, 3, False),
        (middle, implementation, "worktree", "PATCH_READY", "implementation.patch", 8, False),
        ("Counterpoint", "violin_2", "shared", "REVIEW_COMPLETE", "review.md", 3, False),
        ("Tutti", "snare_drum", "shared", "TEST_PASSED", "4-rung verification log", 1, True),
    ]
    movements = []
    for index, (name, section, isolation, cue, deliverable, turns, breaker) in enumerate(form, 1):
        dependencies = []
        if movements:
            previous = movements[-1]
            dependencies.append({
                "movement": previous["index"], "cue": previous["cue_on_exit"],
                "artifact": previous["deliverable"],
            })
        movements.append({
            "index": index, "name": name, "lead_section": section, "active_sections": [section],
            "tacet_sections": sorted(set(SECTION_TIERS) - {section}), "isolation": isolation,
            "cue_on_exit": cue, "deliverable": deliverable, "max_turns": turns,
            "circuit_breaker": breaker, "depends_on": dependencies,
        })
    used = {"conductor"} | {section for movement in movements for section in movement["active_sections"]}
    score = {
        "schema_version": 1, "score_id": score_id or f"score-{uuid.uuid4().hex[:12]}",
        "style": style, "task_type": task_type, "summary": task.strip(), "movements": movements,
        "section_routing": {
            section: {"tier": SECTION_TIERS[section], "assigned_model": None,
                      "resolution": "unresolved", "resolved_tier": None, "source": "none"}
            for section in sorted(used)
        },
    }
    if brass_cue:
        score["brass_cue"] = brass_cue
    return score


def emit(value: Any, stream=None) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    compose = commands.add_parser("compose", help="Task -> score; unresolved required tiers exit 2")
    compose.add_argument("--task", required=True)
    compose.add_argument("--style", choices=STYLES, default="mozart_sonata")
    compose.add_argument("--task-type", default="coding")
    compose.add_argument("--score-id")
    compose.add_argument("--brass-cue", help="Explicit one-wave Brass cue description; never an admission")
    compose.add_argument("--draft", action="store_true", help="Allow unresolved tiers for offline planning")
    validate = commands.add_parser("validate", help="Structural validation only; does not verify inventory")
    validate.add_argument("--score", default="-", help="Score JSON path, default stdin")
    resolve = commands.add_parser("resolve", help="Re-resolve all pins against current host inventory")
    resolve.add_argument("--score", default="-", help="Score JSON path, default stdin")
    for command in (compose, resolve):
        command.add_argument("--registry", help="Host inventory JSON, or MADA_HALL_REGISTRY")
    args = parser.parse_args(argv)
    try:
        score = compose_score(args.task, args.style, args.task_type, args.score_id, args.brass_cue) if args.command == "compose" else read_json(args.score)
        errors = validate_score(score)
        if args.command == "validate":
            emit({"ok": not errors, "admit": False, "errors": errors})
            return 2 if errors else 0
        if errors:
            emit({"ok": False, "admit": False, "errors": errors}, sys.stderr)
            return 2
        path = args.registry or os.environ.get("MADA_HALL_REGISTRY")
        registry = read_json(path) if path else {"models": []}
        invalid_registry = registry_errors(registry)
        if invalid_registry:
            emit({"ok": False, "admit": False, "errors": invalid_registry}, sys.stderr)
            return 2
        result, errors = resolve_score(
            score, registry, os.environ,
            allow_unresolved=args.command == "compose" and args.draft,
        )
        emit(result)
        if errors:
            emit({"ok": False, "admit": False, "errors": errors}, sys.stderr)
            return 2
        return 0
    except (OSError, ValueError) as exc:
        emit({"ok": False, "admit": False, "errors": [str(exc)]}, sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
