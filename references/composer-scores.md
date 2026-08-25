# Composer Scores — extra Philharmonie forms

Bach / Mahler / Shostakovich stay the **default** (ground bass, Tacet, 0-token ladder).
Use a named composer only when the **task shape** matches. Do not narrate the composer unless the user asks for a score.

Transport rule: a parent-spawn (`delegate_task`, nested chat, …) **cannot** pin a per-child model unless the runtime says so. Mixed chairs need an explicit spawn (`hermes chat --provider <p> -m <id> …`, or your agent's equivalent). Codex / Cloud / ACP stay on their own CLIs.

The tables below are **roles**, not a vendor catalog. Pin ids in *your* hall. Do not invent model ids you have not probed.

| Pool (example hall) | Typical reach | Use for |
|------|--------|---------|
| Cheap flash / vision | high-reasoning flash, multimodal | Conductor, counterpoint, screenshot chairs |
| Mid / long ctx | long-context + contract models | Oboe, Cello |
| Free / cheap workers | free multimodal + small coders | Flute, Harp, Brahms slices |
| Local coding CLI | lead + review/subagent split | Violin I slices, Violin II |
| Hosted coding VM | one-shot locked wave | Beethoven Violin I. Not a `/goal` loop |
| Other ACP | only when the user names that ACP | Independent of Cloud |

429 on a cheap pool → flip that chair to another cheap pool. Do **not** spend Brass.

Hermes binary: `MADA_HERMES` / `HERMES` / `$PATH` / default pin. See `spawn-chair.md`.

---

## Role → cheapest correct chair

| Chair | Default | Cheap swap | Multimodal | Heavy (`ffff`, cue only) |
|-------|---------|------------|------------|------------------------|
| Conductor | cheap high-reasoning flash | same | — | frontier only if the score is the job |
| Oboe (SPEC) | mid/high contract model | cheap coder | only if SPEC cites a figure | Brass only if the contract is NP-hard |
| Violin I (impl) | heavy coding, **one** wave | luna / small coder for slices | vision model if UI/figure | Brass once |
| Violin II (review) | cheap review / luna | cheaper luna | free multimodal on screenshots | Brass only if review missed a breaker |
| Viola (glue) | cheap coder | cheaper | — | — |
| Cello (long ctx) | long-context model | shorter ctx | — | long frontier |
| Flute (probe) | cheapest probe | same | free multimodal | — |
| Horn (2nd impl island) | second impl model | cheap coder | vision if needed | — |
| Trumpet (release notes) | cheap writer | same | — | — |
| Harp (UI / caption) | multimodal cheap | cheap writer | required | — |
| Heavy Brass | frontier coding | — | — | cue + immediate TACET |
| Snare / Cymbals | local shell | — | — | 0-token |

Example Hermes pins (this is *a* hall, not the protocol):

```bash
# cheap review
hermes chat -q "<brief>" --provider <cheap> -m <flash> -t terminal,file --yolo

# review when the cheap pool 429s
hermes chat -q "<brief>" --provider <mid> -m <luna> -t terminal,file --yolo

# alias workers (no --provider if your hall registered aliases)
hermes chat -q "<brief>" -m ox-alpha -t terminal,file --yolo
hermes chat -q "<brief>" -m mimo -t terminal,file --yolo
```

Coding CLI (lead / review split lives in *that* CLI's config, not in Hermes `delegate_task`):

```bash
codex exec --sandbox danger-full-access "<impl>"
codex review --base origin/main
```

---

## Mozart — Classical sonata (small well-posed coding)

**When:** one module, contract already almost clear, ≤1 day, no research fork.
**Form:** Exposition (Oboe 8k) → Development (one Violin I + Snare) → Recapitulation (Violin II, then 0-token).
**Tacet:** Cello, Heavy Brass, second impl island, Organ.
**Budget:** Oboe *mp*, Violin I *mf*, review *p*. Recap must reuse Exposition themes (no new API).

## Beethoven — Motive development (hard scientific / kernel wave)

**When:** one stubborn kernel invariant (truth-source, fail-closed RUN, identity-over-index).
**Form:** Motive (Oboe locks 1–3 invariants) → Development (Violin I **one** Brass/heavy wave) → Scherzo (Snare 0-token, fail → same motive, not a new feature) → Finale (human compare / review).
**Rule:** do not add a second theme before the motive is green.
**Tacet:** extra product surfaces and a second Brass re-impl until the locked wave lands.

## Brahms — Developing variation (long-horizon refactor)

**When:** same ground bass, many small variations (API rename, glue, dual-stack parity).
**Form:** each variation is a **tiny** Violin I slice; Snare after every variation; Cello only every 3rd variation for debt.
**Forbid:** one *ffff* Brass pass that “does the whole rewrite”.

## Tchaikovsky — Ballet scenes (UI + multimodal)

**When:** screenshot, caption, preview, figure handoff.
**Form:** Scene 1 Harp reads the screenshot → Scene 2 Viola glue → Scene 3 Snare tests + browser snapshot → Scene 4 Trumpet notes.
**Tacet:** Heavy Brass unless the numbers are wrong (then Beethoven, not more pixels).
**Paint vs vector:** weak geometry after 1–2 image tries → a real drawing tool. Do not keep painting.

## Rachmaninoff — Late-Romantic climax (NP-hard / milestone audit)

**When:** the user explicitly unlocks a climax (final architecture audit, unblocking NP-hard, last-wave merge review).
**Form:** long Cello prepares; **one** Heavy Brass tutti; immediate TACET; Violin II writes the finding list; Snare verifies.
**Budget:** Brass once. A second tutti needs a new human cue.

---

## Scientific vs project-coding pick

| Job | Composer | Violin I | Violin II | Extra |
|-----|----------|----------|-----------|--------|
| Locked kernel wave | Beethoven | one heavy/Brass wave | cheap review | Snare; human compare |
| Slice / glue / rename | Brahms | luna / small coder | review CLI / luna | Snare each slice |
| Small well-posed ticket | Mozart | cheap coder or luna | cheap review | — |
| UI / figure / preview QA | Tchaikovsky | vision cheap | vision on screenshot | browser snapshot |
| Architecture / huge-ctx audit | Rachmaninoff | Cello first | luna | one Brass tutti |
| Multimodal free pass | Tchaikovsky (lite) | free multimodal | — | text+image only |

Do not send a model through a pool that does not list it.

## Fugue isolation (coding projects)

Parallel Subject / Horn rehearse in **separate worktrees**. Violin II + Snare stay on the **shared** sounding tree. We do **not** spin a per-worktree observability stack — Hermes `-w` removes the tree on exit if nothing is unpushed.

```bash
# Prefer the wrapper so envelope fields cannot drift from argv/env.
python3 scripts/spawn_chair.py --envelope subject.json -q "<impl brief>"
python3 scripts/spawn_chair.py --envelope horn.json -q "<counter-impl brief>"
python3 scripts/spawn_chair.py --envelope review.json -q "<review brief>"

# Equivalent raw (only if you must type it):
# Subject / Horn — isolated piano rooms
hermes chat -w -q "<impl brief>" -m <chair> -t terminal,file --yolo
hermes chat -w -q "<counter-impl brief>" -m <horn> -t terminal,file --yolo
# Violin II + Snare — shared tree
hermes chat -q "<review brief>" -m <review> -t terminal,file --yolo
```

Stretto = conductor merge after both islands exit. Forbid simultaneous push to the same branch.

Envelope must match spawn: `isolation: worktree` + `sidechain: true` → worktree chat (or a context-only subagent). `isolation: shared` for review/Snare. Conversation isolation ≠ git isolation — a coding fugue that writes files needs a worktree.

Tacet is heteronomous via the tool gate / `allowed_toolsets`, not courtesy. A Tacet chair does not get `file` write or `terminal`.

First latch: `scripts/spawn_chair.py` (envelope → `-w`/`-t`/`MADA_*`; default `evaluate()`, `--force` skips). `admit` always false. Second latch: `scripts/tacet-guard.sh` on the child `pre_tool_call`. Unset section = no-op. Does not cover foreign CLIs unless you install the hook there. Recipe: `spawn-chair.md` + `audition-chair.md` + `tacet-guard.md`.

## Pitfalls

1. Naming a composer is not a license to wake Brass.
2. Parent-spawn inherits the parent model. Mixed chairs = mixed transports.
3. Alias workers live on the pool that registered them. Do not invent `--provider` names.
4. A coding-CLI `review_model` does not apply to Hermes `delegate_task`.
5. Hosted VM `[PENDING] no diff` → fetch the diff, then land. Not another tutti.
6. Cheap-pool 429 → another cheap chair, not a second Brass.
