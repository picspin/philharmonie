# Audition chair (contract, not admission)

Script: `scripts/audition_chair.py`. Contract: `scripts/test_audition_chair.sh` (36 cases).
Ceilings: `templates/section-contract.json`.

`sender.section` is an **interface**. Schema-valid + toolset ⊆ ceiling + isolation lock + Mahler cue/budget/summary = **may audition**. `admit` is **always false**. Model routing / 429 / sol quota stay with the conductor. DeepSeek “everything is a plugin” = adapters plug in (`halls.md`). It does **not** auto-admit a chair.

## Pass vs spawn

| Check | Audition | `spawn_chair.py` |
|-------|----------|------------------|
| empty `allowed_toolsets` | pass, `tacet: true` | refuse (mute ≠ spawn) |
| `violin_2` / Snare `isolation: worktree` | fail | spawn would emit `-w` — do not |
| flute + `terminal` | fail (overflow) | would emit `-t` — do not |
| horn + `gpt-5.6-sol` | fail | fail |
| `heavy_brass` + sol | pass, still `admit: false` | ok |
| unknown section / bad JSON | fail | fail |

Audition never writes argv. `spawn_chair.py` calls `evaluate()` by default; `--force` skips. Pass ≠ admit.

## Ceilings (sounding-tree lock)

| Section | Max toolsets | Isolation |
|---------|--------------|-----------|
| conductor | terminal, file, web, delegation, vision | — |
| violin_1 / horn / viola / heavy_brass | terminal, file | — |
| violin_2 / snare_drum / cymbals | terminal, file | **shared** |
| flute / harp | file, web | — |
| oboe / cello / organ / bassoon / trumpet / contrabass | file | — |

Unknown toolset names (`browser`, …) fail. Use `web`.

## Usage

```bash
python3 scripts/audition_chair.py --envelope chair.json
# {"audition":"pass","admit":false,"section":"violin_1",...}

# then, only if the conductor still wants the chair:
python3 scripts/spawn_chair.py --envelope chair.json -q "<brief>"
```

## Verify

```bash
bash scripts/test_audition_chair.sh
# expect: ALL 36 PASSED
```
