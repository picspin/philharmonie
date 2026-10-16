# Concert Hall score composer

The score is a plan shared by future TUI / WebUI readers. It does not run a graph,
spawn a chair, grant admission, or report live execution state. Schema version 1
lives in `templates/score-schema.json`; `scripts/score_composer.py` is its reader.
The existing section contract, audition, spawn, tickets and tool ceilings still apply.

## Compose and validate

```bash
# Offline planning: unresolved tiers are valid draft data.
python3 scripts/score_composer.py compose \
  --task "Fix CEST exchange fail-closed boundary" \
  --task-type ai4s_kernel_invariant --style beethoven_symphony \
  --draft > score.json

python3 scripts/score_composer.py validate --score score.json
# {"ok": true, "admit": false, "errors": []}

# Resolve using the CURRENT host inventory. Missing required tiers -> exit 2.
python3 scripts/score_composer.py resolve \
  --score score.json --registry /path/to/host-registry.json > resolved-score.json
```

Without `--draft`, compose also exits 2 when Conductor or any active section is
unresolved. The score remains on stdout so a UI can show the missing assignments;
diagnostics are JSON on stderr. Structural/configuration errors always exit 2.
`validate` checks structure and invariants only, including on stdin; it does not
attest that saved model assignments are available now. Always re-resolve on load
or after changing the active host/Profile.

Forms are deterministic, selected explicitly with `--style`:

| Form | Leads |
|---|---|
| `mozart_sonata` (default) | Oboe -> Violin I -> Violin II -> Snare |
| `beethoven_symphony` | Same seats; locked invariant motive, one implementation wave |
| `brahms_variation` | Same seats; one small slice per score, then verify |
| `tchaikovsky_ballet` | Harp -> Viola -> Violin II -> Snare |
| `rachmaninoff_climax` | Cello -> one Heavy Brass wave -> Violin II -> Snare |

Rachmaninoff requires an explicit `--brass-cue "scope of the human cue"`.
Naming a style or resolving a model never grants execution permission. Composer
does not infer a model, change styles based on keywords, or make an API call.
There is no automatic progression, retry or loop in this first iteration.

## Host inventory and capability tiers

`templates/hall-registry-schema.json` defines the normalized inventory. The
disabled placeholders in `examples/hall-registry.json` must be replaced with real
host IDs and enabled after checking availability. The composer trusts the host's
declared capabilities; it does not probe provider APIs.

```json
{
  "models": [
    {"id": "YOUR_ACTUAL_MODEL_ID", "tiers": ["heavy-code"], "enabled": true}
  ],
  "sections": {"violin_1": "YOUR_ACTUAL_MODEL_ID"},
  "fallbacks": {"contract-precise": ["heavy-code"]}
}
```

Tier names are `high-reasoning-flash`, `contract-precise`, `heavy-code`,
`review-critique`, `context-long`, `multimodal-vision`, `frontier-heavy` and
`0-token-shell`. One model may declare several tiers. Tier defaults live in the
composer, outside `templates/section-contract.json`.

Inventory path: `--registry` first, then `MADA_HALL_REGISTRY`; absent means an
empty model pool. Selection order:

1. `MADA_SECTION_MODEL_<UPPERCASE_SECTION>`, e.g. `MADA_SECTION_MODEL_VIOLIN_1`.
2. Registry `sections` bindings (also the future model-dropdown write target).
3. First enabled compatible model in inventory order.

Pins must exist in the enabled inventory and declare the requested tier or an
explicit compatible fallback. A bad pin stays unresolved; it never silently
selects another model. Fallbacks are ordered, one hop, and never escalate to
`frontier-heavy`. Frontier-tagged models are restricted to Conductor/Heavy Brass.
Snare/Cymbals always resolve to `local-bash`, never an LLM or a model override.
This is a shell execution kind; do not feed it into `spawn_chair.py` as an LLM.

DSH integration should export only its active Profile's available models and
declared tiers into this format. No native DSH Profile API or plugin entrypoint
is assumed here. Hermes/Mac/Pi can supply the same JSON and environment pins.
Resolution does not override hall limitations: Pi cannot pin models; Codex
cannot enforce worktree envelopes. Existing audition also retains its legacy
Heavy Brass name policy. These downstream latches may still reject a resolved
plan; resolution is not admission.

## Timeline, topology and Tacet

Movement indices are contiguous and ordered. Each dependency references an
earlier movement, its exit cue, and an artifact; forward/self/cyclic references,
duplicate source dependencies and mismatched cues are rejected. Dependencies
express intended handoffs, not proof that an artifact exists or a cue occurred.

A graph reader can key nodes by `(movement.index, section)`, draw timeline edges
from `depends_on`, and display active/Tacet seats, isolation, turn limits and
breakers without parsing prose. Every contract section must appear in exactly
one of active/Tacet for each movement; the lead must be active. Shared-tree
locks are validated against the existing section contract. A breaker requires
Snare/Cymbals. Each score permits at most one explicitly cued Brass wave.

Routing exposes requested `tier`, nullable `assigned_model`, `resolved_tier`,
`resolution` (unresolved/resolved/fallback/local) and `source`. Saved assignments
are recomputed by `resolve`, so an old Profile cannot masquerade as the current
pool. Tacet remains a plan until the executor applies the existing tool gate.

Run `bash scripts/test_score_composer.sh` for the 0-token contract suite.
