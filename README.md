# Philharmonie / 金色大厅

Author: Xiaolei Zhu, zxl1412@gmail.com  
**A multi-agent harness scored as a classical orchestra.**
**把多智能体编排写成一部能验的总谱，而不是一场Costume派对。**

![Philharmonie — vineyard hall, conductor in the well](assets/hero.png)

[![snare](https://github.com/picspin/philharmonie/actions/workflows/snare.yml/badge.svg)](https://github.com/picspin/philharmonie/actions/workflows/snare.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English first, 中文紧随。Mechanism, not costume.

---

## Why *Philharmonie*, not 金色大厅 / Musikverein

| Hall | Geometry | Why it maps — or doesn't |
|------|----------|--------------------------|
| **Musikverein / 金色大厅** | Shoe-box. One resident orchestra. The room *is* the Wien Philharmoniker. | Beautiful, closed. A harness that can swap models / agents is not a resident band. |
| **Berliner Philharmonie** (Scharoun) | Vineyard terraces around a **sunken podium**. Conductor in the well. Sections sit on replaceable terraces. | This is the repo. Chairs are interfaces. The hall stays; the orchestra can change. |

中文诗名仍可叫「金色大厅」——那是音色，不是建筑。仓库名、协议入口源自作者曾经生活的地方：柏林以及热爱的柏林爱乐团大厅：**Philharmonie**。

---

## What this is / 这是什么

Philharmonie is a **small, tested harness** for running several LLM agents (or one agent with several roles) as a symphony:

- **Bach — ground bass.** `SPEC.md`, locked tests, and API contracts do not move during a variation.
- **Mahler — Tacet.** A chair that is not cued does not get tools. Empty `allowed_toolsets` = mute = refuse to spawn.
- **Shostakovich — 0-token ladder.** Lint / unit / e2e / security run as shell *before* anyone wakes an LLM.
- **Fugue rooms.** Writers rehearse in worktrees. Review + tests stay on the sounding tree.

It is **not** a new agent runtime. The default adapter speaks [Hermes](https://github.com/NousResearch/hermes-agent) (`hermes chat -w/-t`). `--hall claude|codex|pi` (or `MADA_HALL`) swaps the podium. Envelope, audition, Tacet, garden, and snare stay the hall.

它不是又一个 agent 框架。默认适配 Hermes；`--hall` 换指挥台，信封和闩是大厅。

---

## Install / 安装

```bash
git clone git@github.com:picspin/philharmonie.git
cd philharmonie

# 0-token contracts (no API key, no LLM)
bash scripts/test_audition_chair.sh   # 36
bash scripts/test_garden_score.sh     # 14
bash scripts/test_snare_score.sh      # 27
bash scripts/test_spawn_chair.sh      # 80
bash scripts/test_tacet_guard.sh      # 16
bash scripts/test_halls.sh            # hall adapters
python3 scripts/garden_score.py       # Katalog ↔ parts
```

Need: `python3` ≥ 3.10, `bash`, and `jsonschema` (`pip install jsonschema`) for audition. Hermes is optional until you actually spawn.

依赖：`python3` ≥ 3.10、`bash`、试音需要 `jsonschema`。真要出声再装 Hermes / 你的 agent CLI。

---

## 5-minute score / 五分钟总谱

1. Lock the bass — a `SPEC.md` plus failing tests. Oboe. No Violin yet.
2. Write an envelope (or start from `examples/`).
3. Audition, then spawn (dry-run first):

```bash
python3 scripts/audition_chair.py --envelope examples/violin-1.json
# {"audition":"pass","admit":false,...}

python3 scripts/spawn_chair.py --dry-run --envelope examples/violin-1.json
# {"ok":true,"argv":[...hermes chat -w -q ...],"env":{"MADA_SECTION":"violin_1",...}}

# mute chair — must refuse
python3 scripts/spawn_chair.py --dry-run --envelope examples/tacet-mute.json
# {"ok":false,"error":"allowed_toolsets is empty — Tacet chair, will not spawn"}
```

4. Before a coding wave, ask the **target** repo (not this one) for its 4-rung list:

```bash
python3 scripts/snare_score.py --root /path/to/your/project
# wants AGENTS.md with pasteable lint / unit / e2e / security commands
```

5. Only then replace the process:

```bash
export MADA_HERMES="$(command -v hermes)"   # or your wrapper
python3 scripts/spawn_chair.py --envelope examples/violin-1.json
```

`spawn_chair.py` without `--dry-run` is `os.execvpe` (process replace; `timeout_sec` is costume). `--supervise` waits, honors `budget.timeout_sec`, and prints a result envelope. `--ticket` is an optional conductor grant (`run_id`, expiry); `--force` does not skip it; no signature; pass ≠ admit. `--lock-bass DIR` chmods ground-bass read-only under the target repo and restores after supervise; not a bind-mount; Tacet ≠ sandbox. Run execvpe as a child, never as the conductor.

---

## Envelope / 信封

Schema: [`templates/envelope.json`](templates/envelope.json).
Ceilings: [`templates/section-contract.json`](templates/section-contract.json).

| Field | Meaning | Latch |
|-------|---------|-------|
| `sender.section` | Chair interface (`violin_1`, `oboe`, …) | audition + `MADA_SECTION` |
| `sender.model` | What *this* hall will pin | argv `-m` / `--provider` |
| `isolation` | `worktree` (writers) / `shared` (review, Snare) | `-w` or not. Violin II / Snare **must** be `shared` |
| `allowed_toolsets` | Heteronomous Tacet | spawn `-t`. Empty = mute = refuse |
| `tacet_paths` | Extra ground-bass paths | `MADA_TACET_PATHS` + hook |
| `budget.dynamic_mark` | Mahler dynamic (`ppp`…`ffff`) | required to audition |
| `payload.summary` | Brief if you omit `-q` | — |

`admit` is **always false**. Schema-valid ≠ in the pool. Quota / Brass stay with the conductor.

`admit` 恒为 false。过谱 ≠ 入团。配额和铜管只听指挥。

---

## Bring your own agent / 换指挥台

`--hall` / `MADA_HALL` selects the podium. Default `hermes`. Adapters plug in; chairs do **not** auto-admit.

```bash
# dry-run any hall — same envelope, different argv
python3 scripts/spawn_chair.py --hall claude --dry-run --envelope examples/violin-1.json
# Codex refuses worktree (violin-1). Use a shared envelope:
python3 scripts/spawn_chair.py --hall codex --dry-run --envelope examples/violin-2.json
# Pi cannot pin sender.model this wave → exit 2

export MADA_HALL=claude          # default for this shell
export MADA_CLAUDE=$(command -v claude)
export MADA_CODEX=$(command -v codex)
export MADA_PI=$(command -v pi)
export MADA_HERMES=$(command -v hermes)   # Hermes binary pin still works
```

| Hall | Isolation | Tool gate | Binary pin |
|------|-----------|-----------|------------|
| `hermes` | `-w` | `-t` + `--yolo` | `MADA_HERMES` / `HERMES` |
| `claude` | `--worktree` | `--allowedTools` | `MADA_CLAUDE` / `CLAUDE` |
| `codex` | refuse envelope `worktree` | env + external hook | `MADA_CODEX` / `CODEX` |
| `pi` | refuse | refuse (no hook) | `MADA_PI` / `PI` — cannot pin model |

Codex shared+tools still spawns; tool gate is the hook, not argv. Pi cannot spawn this wave. Recipe: [`references/halls.md`](references/halls.md).

Do **not** add a costume field for “compaction tier 1–5”. Compress at movement boundaries.

换 Codex / Claude Code / Pi：`--hall` 换台，认信封和闩，不要重写大厅。

---

## Latches / 闩

| Latch | Artifact | Contract |
|-------|----------|----------|
| Katalog | `SKILL.md` ≤ 140 lines | `scripts/garden_score.py` |
| Audition | `scripts/audition_chair.py` | 36 cases. Pass ≠ admit |
| Spawn | `scripts/spawn_chair.py` | 80 cases. Default audition; `--force` skips; `--supervise` waits; `--ticket` grants; `--lock-bass` chmods |
| Halls | `scripts/halls.py` | `--hall` / `MADA_HALL`. `test_halls.sh` |
| Tacet | `scripts/tacet-guard.sh` | 16 cases. Opt-in `pre_tool_call`. Fail-open if `MADA_SECTION` unset |
| Garden | `scripts/garden_score.py` | 14 cases. Catalog ↔ parts, no `compaction_tier` |
| Snare | `scripts/snare_score.py` | 27 cases. Target `AGENTS.md` 4 rungs |

Verdict (what was adopted / refused, and why): [`references/harness-verdict.md`](references/harness-verdict.md).
Named composer forms: [`references/composer-scores.md`](references/composer-scores.md).

Copy **mechanism**, not costume. A field nobody reads is murder.

只抄机制，不抄戏服。没人读的字段是谋杀。

---

## Layout

```
philharmonie/
├── SKILL.md                 # Katalog (≤140). Installable as a skill.
├── LICENSE                  # MIT
├── examples/                # violin-1 / violin-2 / tacet-mute
├── scripts/                 # latches + contract tests
├── templates/               # envelope + section ceilings
├── references/              # parts (garden-scored)
└── assets/hero.png           # Codex gpt-image-2 high, 1672×941. Brief: HERO.md
```

---

## License

[MIT](LICENSE) © 2026 Xiaolei `<zxl1412@gmail.com>`

You may test this hall with any LLM API or agent. Please keep Tacet heteronomous: a mute chair must not receive a pen.
