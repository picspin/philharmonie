# Contributing

Philharmonie is a small hall. Patches that add a chair nobody cues, or an envelope key nobody reads, will be refused.

## Before a patch

```bash
python3 -m pip install -r requirements.txt
bash scripts/test_audition_chair.sh   # 44
bash scripts/test_garden_score.sh     # 20
bash scripts/test_snare_score.sh      # 27
bash scripts/test_spawn_chair.sh      # 80
bash scripts/test_tacet_guard.sh      # 16
bash scripts/test_halls.sh            # 39
bash scripts/test_compile_score.sh   # Composite plans / capabilities
bash scripts/test_loop_runner.sh     # Persistent loops / recovery
bash scripts/test_concert_hall.sh    # State service + terminal board
bash scripts/test_score_composer.sh  # Concert Hall plan + routing
python3 scripts/garden_score.py       # Katalog ↔ parts, SKILL.md ≤ 140
```

No API key. No LLM. If garden fails, you either dropped a backtick path from `SKILL.md` or left an orphan under `references/`, `scripts/`, or `templates/`.

## What to touch

| Want | Where | Do not |
|------|-------|--------|
| Score / tier routing | `scripts/score_composer.py` + `scripts/test_score_composer.sh` + score/registry schemas | Model IDs in section-contract; implicit admission |
| Spawn / ticket / lock-bass | `scripts/spawn_chair.py` + `scripts/test_spawn_chair.sh` | New hall |
| Audition / extra keys | `scripts/audition_chair.py` + `templates/envelope.json` | `protocol`, `agent_id`, `compaction_tier` |
| Katalog line | `SKILL.md` (budget 140) | Pasting wave physics back onto the catalog page |
| Part recipe | `references/*.md` | A part that `SKILL.md` does not name |
| Docs for humans | `README.md`, this file, `CHANGELOG.md` | Putting those three under `references/` (garden will call them orphans) |

Root files are outside the garden. Parts are not.

## Rules that already have a verdict

See [`references/harness-verdict.md`](references/harness-verdict.md). Do not re-litigate:

- `admit` is always false. Pass ≠ in the pool.
- Pi cannot pin `sender.model`. Do not invent `-m`.
- `/restart` is human-only. Unset `MADA_SECTION` stays fail-open.
- `--lock-bass` is chmod, not a sandbox. Tacet ≠ sandbox.
- Diminuendo is `/compress` at a movement boundary. No schema field.

## Tests

Contract tests are bash. A new script under `scripts/` that is not `test_*` needs a sibling `test_<stem>.sh` (hyphens become underscores). Garden checks that.

TDD if you change a latch: red case in the sibling `test_*.sh`, then the code.

## Commits / PR

Author on this repo: Xiaolei `<zxl1412@gmail.com>`.

Keep the diff one seam. Do not open a hall. Do not bump a version for a docs nit.

If you cannot use `gh`, push a branch and open:

`https://github.com/picspin/philharmonie/compare/main...<your-branch>?expand=1`
