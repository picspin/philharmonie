# Garden score (Katalog freshness)

Script: `scripts/garden_score.py`. Contract: `scripts/test_garden_score.sh`.

0-token latch. No LLM. Fails the score when the catalog and the parts drift.

## Checks

1. Every `references|scripts|templates/...` backtick path in `SKILL.md` exists.
2. Every file in those three dirs is named in `SKILL.md` (orphan parts fail).
3. `SKILL.md` ≤ 140 lines.
4. `templates/envelope.json` has no `compaction_tier` / `protocol` / `message_type` / `sidechain` / `agent_id`. Every object node `additionalProperties` is false.
5. `sender.section` enum = `section-contract` ceilings = `spawn_chair` / `audition_chair` `SECTIONS`.
6. Each non-test `scripts/*.{py,sh}` has a sibling `test_<stem>.sh`. Hyphens become underscores (`tacet-guard.sh` → `test_tacet_guard.sh`).

Katalog table cells must keep a backtick path for **every** file, including contract tests. Shortening a line and dropping `` `scripts/test_spawn_chair.sh` `` makes garden fail as an orphan. After any Katalog / part / schema edit, run this script before claiming green.

## Usage

```bash
python3 scripts/garden_score.py
# {"ok": true, "errors": [], "katalog_lines": N}

bash scripts/test_garden_score.sh
```

Does not start a cron. Conductor runs this before a wave, or after editing the Katalog.
