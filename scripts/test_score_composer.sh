#!/usr/bin/env bash
# 0-token contract tests: pure planner/resolver plus CLI round trips.
set -euo pipefail
SCORE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$SCORE_ROOT" <<'PY'
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

root = Path(sys.argv.pop())
sys.path.insert(0, str(root / "scripts"))
import score_composer as composer

class ScoreContract(unittest.TestCase):
    def setUp(self):
        self.score = composer.compose_score("修复 locked kernel invariant", score_id="score-test")
        self.registry = {"models": [
            {"id": "test-flash", "tiers": ["high-reasoning-flash"]},
            {"id": "test-contract", "tiers": ["contract-precise"]},
            {"id": "test-code", "tiers": ["heavy-code"]},
            {"id": "test-review", "tiers": ["review-critique"]},
            {"id": "test-context", "tiers": ["context-long"]},
            {"id": "test-vision", "tiers": ["multimodal-vision"]},
            {"id": "test-frontier", "tiers": ["frontier-heavy"]},
        ]}

    def invalid(self, change, needle=None):
        change(self.score)
        errors = composer.validate_score(self.score)
        self.assertTrue(errors)
        if needle:
            self.assertIn(needle, " ".join(errors))

    def test_all_forms_resolve_without_mutation(self):
        for style in composer.STYLES:
            with self.subTest(style=style):
                score = composer.compose_score("task", style, brass_cue="human audit cue" if style == "rachmaninoff_climax" else None)
                before = copy.deepcopy(score)
                result, errors = composer.resolve_score(score, self.registry, {})
                self.assertEqual(errors, [])
                self.assertEqual(composer.validate_score(result), [])
                self.assertEqual(score, before)
                self.assertTrue(all(r["resolution"] != "unresolved" for r in result["section_routing"].values()))

    def test_no_automatic_brass(self):
        for style in composer.STYLES[:-1]:
            score = composer.compose_score("NP-hard frontier emergency", style)
            self.assertNotIn("heavy_brass", composer.needed_sections(score))

    def test_climax_requires_explicit_cue(self):
        with self.assertRaisesRegex(ValueError, "brass-cue"):
            composer.compose_score("task", "rachmaninoff_climax")

    def test_blank_task(self):
        with self.assertRaises(ValueError):
            composer.compose_score("  ")

    def test_unknown_style(self):
        with self.assertRaises(ValueError):
            composer.compose_score("task", "unknown")

    def test_unique_ids(self):
        self.assertNotEqual(composer.compose_score("a")["score_id"], composer.compose_score("a")["score_id"])

    def test_extra_score_key(self):
        self.invalid(lambda s: s.update(agent_id="costume"))

    def test_extra_nested_key(self):
        self.invalid(lambda s: s["movements"][0].update(model="invented"))

    def test_non_object(self):
        self.assertTrue(composer.validate_score([]))

    def test_bad_turn_budget(self):
        self.invalid(lambda s: s["movements"][0].update(max_turns=0))

    def test_unknown_section(self):
        self.invalid(lambda s: s["movements"][0].update(lead_section="kazoo"))

    def test_lead_is_active(self):
        self.invalid(lambda s: s["movements"][0].update(lead_section="violin_1"), "lead")

    def test_tacet_overlap(self):
        self.invalid(lambda s: s["movements"][0]["tacet_sections"].append("oboe"), "overlap")

    def test_tacet_complete(self):
        self.invalid(lambda s: s["movements"][0]["tacet_sections"].remove("organ"), "every contract section")

    def test_ordered_indices(self):
        self.invalid(lambda s: s["movements"][1].update(index=7), "indices")

    def test_forward_dependency(self):
        self.invalid(lambda s: s["movements"][0]["depends_on"].append({"movement": 2, "cue": "PATCH_READY", "artifact": "patch"}), "earlier")

    def test_self_dependency(self):
        self.invalid(lambda s: s["movements"][1]["depends_on"][0].update(movement=2), "earlier")

    def test_dependency_cue(self):
        self.invalid(lambda s: s["movements"][1]["depends_on"][0].update(cue="WRONG"), "cue")

    def test_duplicate_dependency_source(self):
        self.invalid(lambda s: s["movements"][1]["depends_on"].append({"movement": 1, "cue": "SPEC_LOCKED", "artifact": "other"}), "duplicate dependency")

    def test_review_isolation_lock(self):
        self.invalid(lambda s: s["movements"][2].update(isolation="worktree"), "isolation")

    def test_snare_isolation_lock(self):
        self.invalid(lambda s: s["movements"][3].update(isolation="worktree"), "isolation")

    def test_breaker_requires_shell(self):
        self.invalid(lambda s: s["movements"][0].update(circuit_breaker=True), "requires Snare")

    def test_missing_routing(self):
        self.invalid(lambda s: s["section_routing"].pop("oboe"), "missing section routing")

    def test_missing_conductor_routing(self):
        self.invalid(lambda s: s["section_routing"].pop("conductor"), "conductor")

    def test_shell_tier_cannot_be_llm(self):
        self.invalid(lambda s: s["section_routing"]["snare_drum"].update(tier="heavy-code"), "0-token-shell")

    def test_llm_tier_cannot_be_shell(self):
        self.invalid(lambda s: s["section_routing"]["oboe"].update(tier="0-token-shell"), "0-token-shell")

    def test_brass_tier_cannot_leak(self):
        self.invalid(lambda s: s["section_routing"]["violin_1"].update(tier="frontier-heavy"), "frontier-heavy")

    def test_unresolved_cannot_claim_model(self):
        self.invalid(lambda s: s["section_routing"]["oboe"].update(assigned_model="fake"), "unresolved")

    def test_resolved_cannot_claim_auto(self):
        self.invalid(lambda s: s["section_routing"]["oboe"].update(
            assigned_model="auto", resolution="resolved", resolved_tier="contract-precise", source="registry"), "explicit model")

    def test_missing_models_fail_closed(self):
        result, errors = composer.resolve_score(self.score, {"models": []}, {})
        self.assertIn("no enabled model", " ".join(errors))
        self.assertIsNone(result["section_routing"]["oboe"]["assigned_model"])
        self.assertEqual(result["section_routing"]["snare_drum"]["assigned_model"], "local-bash")

    def test_resolution_precedence(self):
        self.registry["sections"] = {"oboe": "test-code"}
        self.registry["fallbacks"] = {"contract-precise": ["heavy-code"]}
        result, errors = composer.resolve_score(self.score, self.registry, {"MADA_SECTION_MODEL_OBOE": "test-contract"})
        self.assertEqual(errors, [])
        self.assertEqual(result["section_routing"]["oboe"]["source"], "environment")
        result, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertEqual(errors, [])
        self.assertEqual(result["section_routing"]["oboe"]["assigned_model"], "test-code")
        self.assertEqual(result["section_routing"]["oboe"]["resolution"], "fallback")

    def test_invalid_override_does_not_fall_through(self):
        for pin in ("invented", "test-code", ""):
            result, errors = composer.resolve_score(self.score, self.registry, {"MADA_SECTION_MODEL_OBOE": pin})
            self.assertTrue(errors)
            self.assertIsNone(result["section_routing"]["oboe"]["assigned_model"])

    def test_disabled_model(self):
        self.registry["models"][1]["enabled"] = False
        result, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertTrue(errors)
        self.assertEqual(result["section_routing"]["oboe"]["resolution"], "unresolved")

    def test_explicit_fallback_only(self):
        self.registry["models"].pop(1)
        _, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertTrue(errors)
        self.registry["fallbacks"] = {"contract-precise": ["heavy-code"]}
        result, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertEqual(errors, [])
        route = result["section_routing"]["oboe"]
        self.assertEqual((route["tier"], route["resolved_tier"], route["resolution"]), ("contract-precise", "heavy-code", "fallback"))

    def test_fallback_is_one_hop(self):
        self.registry["models"].pop(1)
        self.registry["fallbacks"] = {"contract-precise": ["context-long"], "context-long": ["heavy-code"]}
        self.registry["models"] = [m for m in self.registry["models"] if m["id"] != "test-context"]
        _, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertTrue(errors)

    def test_no_frontier_escalation(self):
        self.registry["fallbacks"] = {"heavy-code": ["frontier-heavy"]}
        self.assertIn("escalate", " ".join(composer.registry_errors(self.registry)))

    def test_frontier_model_cannot_masquerade(self):
        self.registry["models"][2]["tiers"].append("frontier-heavy")
        _, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertIn("violin_1", " ".join(errors))

    def test_stale_saved_pin_is_re_resolved(self):
        resolved, errors = composer.resolve_score(self.score, self.registry, {})
        self.assertEqual(errors, [])
        self.registry["models"][1]["id"] = "replacement-contract"
        result, errors = composer.resolve_score(resolved, self.registry, {})
        self.assertEqual(errors, [])
        self.assertEqual(result["section_routing"]["oboe"]["assigned_model"], "replacement-contract")

    def test_registry_validation(self):
        bad = [
            {"models": [], "unexpected": True},
            {"models": [{"id": "unknown", "tiers": ["imaginary-tier"]}]},
            {"models": [{"id": "auto", "tiers": ["heavy-code"]}]},
            {"models": [{"id": " spaced ", "tiers": ["heavy-code"]}]},
            {"models": [self.registry["models"][0], self.registry["models"][0]]},
            {"models": [], "sections": {"snare_drum": "llm"}},
            {"models": [], "fallbacks": {"heavy-code": ["heavy-code"]}},
        ]
        for registry in bad:
            with self.subTest(registry=registry):
                self.assertTrue(composer.registry_errors(registry))

    def test_shell_env_override_refused(self):
        _, errors = composer.resolve_score(self.score, self.registry, {"MADA_SECTION_MODEL_SNARE_DRUM": "llm"})
        self.assertIn("cannot be overridden", " ".join(errors))

    def test_draft_still_refuses_invalid_override(self):
        _, errors = composer.resolve_score(self.score, self.registry, {"MADA_SECTION_MODEL_OBOE": "invented"},
                                          allow_unresolved=True)
        self.assertIn("explicit model binding", " ".join(errors))

    def test_example_files(self):
        score = composer.read_json(str(root / "examples/concert-score.json"))
        registry = composer.read_json(str(root / "examples/hall-registry.json"))
        self.assertEqual(composer.validate_score(score), [])
        self.assertEqual(composer.registry_errors(registry), [])
        self.assertTrue(all(m.get("enabled") is False for m in registry["models"]))
        _, errors = composer.resolve_score(score, registry, {})
        self.assertTrue(errors)

    def test_brass_requires_cue_in_imported_score(self):
        self.score = composer.compose_score("audit", "rachmaninoff_climax", brass_cue="explicit")
        self.invalid(lambda s: s.pop("brass_cue"), "brass_cue")

    def test_duplicate_json_key_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"models": [], "models": []}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                composer.read_json(str(path))

    def test_json_nan_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nan.json"
            path.write_text('{"models": NaN}')
            with self.assertRaisesRegex(ValueError, "invalid JSON constant"):
                composer.read_json(str(path))

    def test_environment_inventory(self):
        registry = composer.environment_registry(self.score, {
            "MADA_SECTION_MODEL_OBOE": "host-model",
            "MADA_SECTION_MODEL_VIOLIN_1": "host-model",
            "MADA_SECTION_MODEL_SNARE_DRUM": "ignored-shell-override",
        })
        self.assertEqual(composer.registry_errors(registry), [])
        self.assertEqual(registry["models"], [
            {"id": "host-model", "tiers": ["contract-precise", "heavy-code"]},
        ])

    def test_cli_environment_only(self):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("MADA_SECTION_MODEL_") and key != "MADA_HALL_REGISTRY"}
        for section in ("CONDUCTOR", "OBOE", "VIOLIN_1", "VIOLIN_2"):
            env[f"MADA_SECTION_MODEL_{section}"] = "declared-host-model"
        def run(*args):
            return subprocess.run([sys.executable, str(root / "scripts/score_composer.py"),
                                   "compose", "--task", "env-only task", *args],
                                  capture_output=True, text=True, env=env)
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["section_routing"]["oboe"]["source"], "environment")
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "empty.json"
            registry.write_text('{"models": []}')
            self.assertEqual(run("--registry", str(registry)).returncode, 2)
        env.pop("MADA_SECTION_MODEL_OBOE")
        self.assertEqual(run().returncode, 2)
        env["MADA_SECTION_MODEL_OBOE"] = "declared-host-model"
        env["MADA_SECTION_MODEL_SNARE_DRUM"] = "llm"
        self.assertEqual(run("--draft").returncode, 2)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "registry.json"
            inventory.write_text(json.dumps(self.registry))
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("MADA_SECTION_MODEL_") and key != "MADA_HALL_REGISTRY"}
            def run(*args, data=None):
                return subprocess.run([sys.executable, str(root / "scripts/score_composer.py"), *args],
                                      input=data, capture_output=True, text=True, env=env)
            good = run("compose", "--task", "修复边界", "--registry", str(inventory))
            self.assertEqual(good.returncode, 0, good.stderr)
            score = json.loads(good.stdout)
            self.assertEqual(score["summary"], "修复边界")
            check = run("validate", data=good.stdout)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertFalse(json.loads(check.stdout)["admit"])
            missing = run("compose", "--task", "task")
            self.assertEqual(missing.returncode, 2)
            self.assertIsNone(json.loads(missing.stdout)["section_routing"]["oboe"]["assigned_model"])
            draft = run("compose", "--task", "task", "--draft")
            self.assertEqual(draft.returncode, 0)
            self.assertEqual(run("validate", data=draft.stdout).returncode, 0)
            self.assertEqual(run("resolve", "--registry", str(inventory), data=draft.stdout).returncode, 0)
            self.assertEqual(run("resolve", data=good.stdout).returncode, 2)
            self.assertEqual(run("validate", data="{").returncode, 2)
            self.assertEqual(run("validate", "--score", str(Path(directory) / "missing")).returncode, 2)
            self.assertEqual(run("compose", "--task", " ", "--draft").returncode, 2)
            inventory.write_text('{"models": [], "typo": true}')
            self.assertEqual(run("compose", "--task", "task", "--registry", str(inventory), "--draft").returncode, 2)

unittest.main(verbosity=2)
PY
