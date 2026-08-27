# Changelog

Dates are UTC. Counts are the contract tests in `scripts/test_*.sh`.

## Unreleased

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
