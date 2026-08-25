---
name: philharmonie
description: "Philharmonie / 金色大厅 — multi-agent harness as a classical orchestra. Bach ground-bass, Mahler Tacet, Shostakovich 0-token ladders, named composer forms. Envelope fields drive spawn; they are not costume. Default adapter is Hermes; other agents honor the same latches."
tags: [multi-agent, orchestration, swarm, token-optimization, symphony, a2a, anp, hermes]
---

# Philharmonie (Katalog)

Token economy + structural correctness: peak expression with minimal sounding bodies, strict cue/exit, deterministic verification.

**This file is the catalog page.** Chair recipes and latch contracts live in the parts. Do not paste wave-specific product physics back here.

| Part | Load when |
|------|-----------|
| `templates/envelope.json` | A2A/ANP schema + isolation contract |
| `references/composer-scores.md` | Cheap-chair map, named forms, **fugue worktree** |
| `references/tacet-guard.md` | Opt-in `pre_tool_call` latch |
| `references/spawn-chair.md` | Envelope → `-w`/`-t`/`MADA_*`. First latch. |
| `references/audition-chair.md` | `sender.section` contract. Pass ≠ admit. |
| `templates/section-contract.json` | Chair toolset ceilings + shared-tree lock |
| `references/harness-verdict.md` | Locked adopt/refuse |
| `references/garden-score.md` | Katalog freshness latch. 0-token. |
| `references/snare-score.md` | Target-repo `AGENTS.md` 4-rung latch. |
| `scripts/tacet-guard.sh` | Child-process latch. `scripts/test_tacet_guard.sh` = 16 |
| `scripts/spawn_chair.py` | Spawn. Default audition; `--force` skips. `scripts/test_spawn_chair.sh` = 41 |
| `references/halls.md` | `--hall` / `MADA_HALL`. `scripts/halls.py` + `scripts/test_halls.sh` |
| `scripts/audition_chair.py` | Audition. `scripts/test_audition_chair.sh` = 36 |
| `scripts/garden_score.py` | Doc-garden. `scripts/test_garden_score.sh` |
| `scripts/snare_score.py` | Target AGENTS.md. `scripts/test_snare_score.sh` |

## 1. Chairs

| Section | Role | Default routing | Dynamics |
|---|---|---|---|
| **Conductor** | Score | cheap high-reasoning flash | Tacet, Stretto. Never inherit sol. |
| **Oboe** | Contract | mid/high contract model | $p \to mf$ Pitch A |
| **Violin I** | Impl | heavy coding model, **one** wave | $mf \to f$ |
| **Violin II** | Review | cheap review / luna | $mp$. Do not spend sol. |
| **Viola** | Glue | cheap coder | $mp$ |
| **Cello** | Long ctx | long-context model | $p \to f$ |
| **Horn** | 2nd island | second impl model | Counter-impl, not a second sol |
| **Flute** | Probe | cheapest probe | $pp \to p$ |
| **Harp** | UI / figure | multimodal cheap | Weak geometry → vector, not more paint |
| **Organ** | Memory | long-term store | $ppp$ |
| **Heavy Brass** | Ultra-heavy | frontier coding, cue only | $ffff$. Cue + TACET |
| **Snare / Cymbals** | Lint / tests / breaker | Local shell | **0 token** |

Pin models in *your* hall. `delegate_task` inherits the parent — mixed chairs need an explicit spawn (`hermes chat --provider … -m …`, or your agent's equivalent).

## 2. Default protocol

**Bach — ground bass.** `SPEC.md`, API contracts, locked tests are immutable during variations. Mute anyone who rewrites them without conductor cue.

**Bach — fugue.** Subject (Violin I) / Countersubject (Violin II) / Episode (woodwinds) / Stretto (conductor merge) / Pedal (original goal). Coding Subject + Horn rehearse in **separate worktrees**. Violin II + Snare stay on the **shared** tree. No per-worktree observability stack. Details: `composer-scores.md` § Fugue isolation.

**Mahler — every chair declares** Cue / Exit deliverable / Budget.

| Movement | Sounds | Budget | Tacet | Deliverable |
|---|---|---|---|---|
| **I. Overture** | Oboe, Cello | $mp$ 8k | Violin I/II, Brass | `SPEC.md` + stubs |
| **II. Variation** | Violin I, Viola | $mf$ 32k | Oboe, Cello, Brass | patch + local stubs |
| **III. Counterpoint** | Violin II, Snare | $mp$ 16k | Violin I standby | review / lint diff |
| **IV. Tutti** | Snare, Cymbals | **0 token** | All LLMs | green suite or stacktrace |
| **V. Finale** | Harp, Bassoon, Trumpet | $p$ 12k | Lead coders, Brass | docs + notes |

Named composers change **who enters** and **how many tutti** — not the protocol. Full chairs: `composer-scores.md`.

| Composer | Task shape | Sounds | Tacet |
|----------|------------|--------|-------|
| **Mozart** | Small well-posed ticket | Oboe → one cheap Violin I → review + Snare | Cello, Brass, 2nd island |
| **Beethoven** | Hard scientific / kernel wave | Oboe 1–3 invariants → **one** Brass wave → Snare | New theme before motive is green |
| **Brahms** | Long refactor, same bass | Tiny slices + Snare each | One giant Brass rewrite |
| **Tchaikovsky** | UI / screenshot | Harp → Viola → browser Snare | Brass unless numbers are wrong |
| **Rachmaninoff** | Explicit milestone / NP-hard | Cello → **one** Brass tutti → review + Snare | Second tutti without a new human cue |

### 0-token ladder (every chair, first screen)

```
[ Patch ]
   → Snare ppp  lint/format     fail → Viola
   → Snare p    unit tests      fail → Violin I
   → Snare mf   integration/E2E fail → Oboe
   → Cymbals fff security gates fail → hard break
【 All Green 】
```

Never wake an LLM when a script can fail. Target verify list: `scripts/snare_score.py --root <project>`.

### Diminuendo (compaction)

The host compressor is threshold/target, **not** five Claude-Code tiers. Do not invent `compaction_tier` on the envelope.

1. Last 3 exchanges: full tool results.
2. Older tool results: one-line placeholder / path.
3. Compress only at a **movement boundary**.

A mid-movement ff summary murders the theme.

## 3. Envelope contract

Schema: `templates/envelope.json`. Spawn reader: `scripts/spawn_chair.py`. Audition reader: `scripts/audition_chair.py`. Child and hook never parse the JSON.

| Field | Drives |
|-------|--------|
| `sidechain` | Isolated conversation (subagent or worktree chat) |
| `isolation` | `worktree` (writers) vs `shared` (review / Snare) |
| `allowed_toolsets` | Heteronomous Tacet → spawn tool gate. Empty = mute |
| `tacet_paths` | Ground-bass paths this chair must not write |

`sender.section` is an **interface**. `audition_chair.py` pass = may try; `admit` is always false. Routing / quota / Brass stay with the conductor. Auto-admit plugins are refused.

ANP = lifecycle bus (`SPEC_LOCKED`, `TEST_PASSED`, `CIRCUIT_BREAK`). A2A = fugue handover. AGUI = human waveform.

## 4. Conduct

1. Score: 3–5 movements with explicit Tacet columns.
2. Pitch A: Oboe locks `SPEC.md` + test signatures.
3. Variation: Violin I in a worktree + local Snare.
4. Counterpoint: Violin II on the shared tree.
5. Stretto: conductor merge, then the 0-token ladder.

Spawn 403/429 → in-session TDD + Snare. Do not stall.

Default hall Hermes. `--hall` / `MADA_HALL` = `claude` / `codex` / `pi`. Adapters plug in; chairs do not auto-admit.

## Pitfalls

- Parent-spawn inherits the parent model. Mixed chairs = explicit pin.
- Conversation isolation ≠ git isolation. File-writing fugue needs a worktree.
- Naming a composer is not a license to wake Brass. Quota 429 → cheaper chair, not a second Brass.
- Envelope fields do not auto-spawn. `spawn_chair.py` auditions first; `--force` skips. Pass ≠ admit.
- `tacet-guard.sh` is opt-in. Unset `MADA_SECTION` = fail-open. Do not flip `hooks_auto_accept`.
- `harness-verdict.md` Remaining = **None**. After Katalog edits run `scripts/garden_score.py`.
