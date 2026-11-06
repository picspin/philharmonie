# Remote review and alignment

This review covers the five open PRs and two additional DSH branches observed on
2026-11-03. It is a local/code review and regression record, not approval to merge
or a posted GitHub review. None of the source branches was force-pushed or merged.

| PR | Reviewed head | Scope | Review outcome |
|---|---|---|---|
| #5 | b81b790d5a978821ff7fc929a56e9504f6baa3fc | v1 composer and tiers | Fix frontier downgrade and integer-valued JSON dependency indexing before release. |
| #6 | 15f6def83fe308bf051805425e6f1ddade7a09ff | state/TUI | Fix per-line UTF-8 recovery and blank run ids; clarify observational states and ordered logs. |
| #7 | ff46f74a6f0a2bd79f0882b270c838d6f6265f25 | design RFC | No runtime gate; clarify optional roster vs compact example and implicit group ordering. |
| #8 | e4b377c9c13ac19c9f486f4842450b192889fc81 | compiler/durable loops | P1: actual hall survived cancellation; P1: obsolete nested journals could revert settled best. Both reproduced and fixed here. Also reject shared nested metric paths. |
| #9 | 764b7bc8dceb53902d957d4e0a886e7a40ba9c36 | independent workbench | This is not a finished DSH plugin. Unapplied JSON edits now invalidate compile/consent. Browser and official-host acceptance remain separate gates. |

## Reproductions and fixes

The new regression tests were run against the original source first:

- Schema-valid dependency `movement: 1.0` raised TypeError in v1 validation.
- `frontier-heavy -> heavy-code` fallback was accepted instead of failing closed.
- One invalid UTF-8 event line hid all valid lines.
- Whitespace run identity silently ignored observations.
- A fake Hermes hall wrote `late-write` after the runner reported cancellation.
- An outer loop retained candidate 7, but a later unrelated failure restored 10
  from the abandoned first inner iteration.

All six reproduced as failures before their fixes and passed afterward. Integer
indices are normalized at lookups; frontier fallback is forbidden in both registry
and resolved-score checks; log decoding degrades per line. Worker-owned supervised
halls share the job group, so group termination includes the real agent. Nested
rollback includes only transactions belonging to still-active ancestor scopes.
No test weakens admission, isolation, frozen contracts or metric validity.

## Other remote DSH branches

### feat/dsh-hall-adapter @ f2dd8d83fe1c8f65c0256314c93063c5d28ab0b5

Adds `DshHall`, declaring `model_pin=False` and `worktree=False`. Those declarations
are honest, but the existing spawn contract requires an explicit model pin. Thus
registering this hall does not make an agent movement dispatchable; ordinary
spawn rejects it. Do not flip its capability flags or invent CLI flags to make a
UI dropdown look usable. This branch remains separate pending a real supported
model/tool/isolation enforcement design.

### feat/dsh-cordis-plugin @ 8e1077f8f5ca63081788e52d456e8108beb81f4d

Adds three agent-facing tools and a global `tools/pre-execute` hook, plus the same
conservative DSH hall. It has no client bundle/sidebar/main/header implementation.
Its package patch hard-codes an author's checkout; publishing just that subfolder
does not include the Python/schema dependencies. `symphony_snare_verify` inventories
commands; it does not execute the four rungs. `symphony_dispatch_cue` returns a
structured record but does not actually broadcast a cue or grant Brass admission.
The global environment/config Section is not a per-Session orchestration identity.
These boundaries must be explicit before promoting that branch as runtime support.

The new adapter keeps the same product/package name, but packages from the root,
includes its runtime dependencies, uses supported additive slots and the official
closure-factory protocol, and binds Session metadata explicitly to task identities.
It does not overwrite the other branch or claim to include its agent tools. Any
future tools integration should be an explicit, tested capability addition.

## Stack and migration

PRs #5 → #6 → #7 → #8 → #9 remain the reviewed remote stack. The alignment changes
are a follow-up based on #9; the earlier heads themselves still contain the issues
listed above until these fixes are backported or the full stack plus follow-up is
merged. Do not describe those old heads as independently release-ready.

The previous local DSH work was preserved in checkpoint commit `0f64237` before
alignment. The imported local snapshot git history is not pushed as canonical
history; remote Git trees/commits are based on the actual #9 head. Existing runtime
journals are fingerprinted: recover/finish them on their pinned old checkout before
upgrading. No journal fingerprint rewrite or destructive repository reset is used.

Real official DSH installation, native header/session interaction, keyboard and
browser layout are not established by mocked slot tests. CI browser results and
an actual supported-profile smoke must be inspected before declaring the plugin
complete or merging it as a fully verified DSH frontend.

## Local validation after alignment

All 369 non-browser checks passed: audition 44, garden 20, Snare 27, spawn 80,
Tacet 16, halls 39, score composer 50, monitor 28, composite compiler 13, durable
runner 26, web service 13, frontend templates 6 and DSH adapter 7. The catalog is
140 lines. Build freshness, syntax and diff whitespace checks pass. Browser and
official-profile scripts are added as CI gates and are not counted as passed here.

Blob comparison of the pre-alignment local workbench snapshot against canonical
remote #9 found matching tracked text files; the only missing imported artifact
was the unchanged hero PNG. Remote publication uses #9's original Git tree so
that binary remains intact.
