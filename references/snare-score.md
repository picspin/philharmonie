# Snare score (target AGENTS.md)

Script: `scripts/snare_score.py`. Contract: `scripts/test_snare_score.sh` (27 cases).

0-token latch for the **target project**, not this skill. Does not run the commands.
`CLAUDE.md` / `README.md` are not substitutes. This skill has no `AGENTS.md` — scanning `--root` here must fail.

## Rungs

| Rung | Aliases | Fail → |
|------|---------|--------|
| lint | format, fmt | Viola |
| unit | pytest | Violin I |
| e2e | integration | Oboe |
| security | fff, audit, gitleaks | hard break |

A rung counts only with a pasteable command: `` `backticks` ``, `$ prompt`, or a following fenced block. Non-empty prose on the same line is **not** a command and must **not** look ahead — that steals the next rung (`lint: we should lint` must not take `unit: \`pytest\``). Empty rest may take the next `$` / fence until another label.

## Usage

```bash
python3 scripts/snare_score.py --root /path/to/project
# {"ok": true, "rungs": {"lint": "...", "unit": "...", "e2e": "...", "security": "..."}}

bash scripts/test_snare_score.sh
# expect: ALL 27 PASSED
```

Conductor runs this before a coding wave. Missing rungs = do not wake an LLM.
