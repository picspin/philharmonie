# Changelog

Dates are UTC. Counts are the contract tests in `scripts/test_*.sh`.

## Unreleased

- Executable v2 composite score compiler: chapter DAGs, recursive sequence/parallel/loop forms, Chair-level tier bindings and sealed plans.
- Persistent Bach variation runner: SQLite best-file checkpoints, strict keep/discard/crash decisions, worker receipts, pause/cancel/reconciliation and bounded retries.
- Offline search-optimization example and 36 compiler/runner tests, including coordinator SIGKILL recovery.

- Concert Hall state aggregation and ASCII/ANSI terminal board: one-line ribbon,
  expanded movement/dependency/Tacet views, JSON snapshots and watch mode.
- Supervised spawn logs gain optional score/movement/run labels and per-child
  execution IDs; launch failures close their observed attempts. Observation
  metadata preserves audition, ticket, tool and hall enforcement.
- Snare command inventory is shown separately from unobserved test outcomes;
  malformed/conflicting observations degrade the board rather than imply success.

- Concert Hall planning: versioned score and host inventory schemas; deterministic
  composer forms, movement dependencies, explicit Tacet, isolation locks and turn budgets.
- Capability-tier resolution: enabled host inventory, section/environment pins,
  explicit one-hop fallbacks, stale-pin re-resolution, and 0-token local shell seats.
  Missing required tiers fail closed; resolution never spawns or admits a chair.
- Add offline score/disabled inventory examples, composer contract tests and CI coverage.

- README rewritten in a less brochure voice.
- shields.io badges: Python 3.10+, jsonschema, 226 contracts, Katalog ≤140, last commit.
- `CONTRIBUTING.md` — how to patch without inventing a hall or an unread field.

## 0.1.0 — 2026-08-27

Merge of [PR #1](https://github.com/picspin/philharmonie/pull/1) (`feat/costume-wave-latches`) onto `main`.

Costume wave closed. Remaining table in `references/harness-verdict.md` is all landed.

| Latch | What landed |
|-------|-------------|
| Halls | Capability table. Spawn fail-closed when a hall cannot enforce the envelope. Pi still cannot pin `-m`. |
| Supervise | `--supervise` waits, honors `budget.timeout_sec`, emits a result envelope / JSONL. Default path is still `execvpe`. |
| Ticket | `--ticket` is a conductor grant (`run_id`, expiry, caps). Extra keys refuse. `--force` does not skip it. No signature. Pass ≠ admit. |
| Lock-bass | `--lock-bass DIR` chmods ground-bass read-only under supervise, then restores. Not a bind-mount. |
| Envelope | Dropped `protocol` / `message_type` / `sidechain` / `agent_id`. `additionalProperties: false` on every object node. Extra instance keys fail audition. |
| Convention | Diminuendo = `/compress` at a movement boundary. `/restart` is human-only. Unset `MADA_SECTION` stays fail-open. |

Contracts after this merge: spawn 80, tacet 16, halls 39, audition 44, garden 20, snare 27.
