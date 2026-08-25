# Spawn chair (envelope → argv + env)

Script: `scripts/spawn_chair.py`. Contract: `scripts/test_spawn_chair.sh` (41 cases).

This is the conductor's **first latch**. Isolation fields on the envelope become `hermes chat` flags and `MADA_*` exports. The JSON is not read by the child — only by this wrapper.

Default gate: `audition_chair.evaluate` on the **effective** envelope (`--section` applied to a deepcopy first, then evaluate). Fail = refuse. `--force` skips audition; spawn latches (`-t` / mute / brass) still apply. Pass ≠ admit.

`--section conductor --brass-cue` on a horn+sol envelope would fail if you auditioned the original. Always override first.

Every spawn fixture now needs Mahler `budget.dynamic_mark`. Wiring audition as the default gate without that field turns the whole 32-case suite red. `--force` does **not** lift empty `allowed_toolsets`.

## What it emits

| Envelope | Spawn |
|----------|--------|
| `sender.section` | `MADA_SECTION` |
| `allowed_toolsets` | `-t` csv + `MADA_ALLOWED_TOOLSETS` |
| `tacet_paths` | `MADA_TACET_PATHS` |
| `isolation: worktree` | `hermes chat -w` |
| `isolation: shared` | no `-w` |
| `sender.model` | `-m` + `--provider` (see routing) |
| `--brass-cue` | `MADA_BRASS_CUE=1` |

Always `--yolo`. Query = `-q` or `payload.summary`.

## Routing

| Model | Provider flag |
|-------|----------------|
| `ox-alpha` / `ox-alpha-free` / `mimo*` | omit `--provider` (alias) |
| `code1-*` / `code2-*` / `mga-*` / `mga-r-*` | `--provider litellm-gateway` |
| everything else | `--provider cliproxy` |

Schema-valid ≠ in the pool. Wrapper does **not** check 429 / sol quota.

## Refuses (exit 2, `{"ok":false}`)

- audition fail (schema / ceiling / isolation lock / missing Mahler `budget`) unless `--force`
- unknown `sender.section`
- missing or empty `allowed_toolsets` (mute = do not spawn; `--force` does not lift this)
- invalid JSON
- cheap chair + `gpt-5.6-sol` / `*-sol` without `--brass-cue`
- `heavy_brass` may use sol; `conductor --brass-cue` may override section and wake it

## Usage

```bash
# dry-run (prints argv + env + audition JSON)
python3 scripts/spawn_chair.py --dry-run --envelope chair.json -q "<brief>"

# skip audition (spawn latches still apply)
python3 scripts/spawn_chair.py --dry-run --force --envelope chair.json -q "<brief>"

# exec (replaces this process)
python3 scripts/spawn_chair.py --envelope chair.json -q "<brief>"

# stdin
python3 scripts/spawn_chair.py --dry-run -q "<brief>" < chair.json
```

Hermes binary: `MADA_HERMES` or `HERMES` or `$PATH` `hermes`, else `/opt/hermes/.venv/bin/hermes`. Non-`--dry-run` is `os.execvpe` — it **replaces** this process. Run it as a child, never in the conductor's own PID.

## Pair with tacet-guard

Wrapper is latch 1 (`-t` + env). `tacet-guard.sh` is latch 2 on the **child** `pre_tool_call`. Unset `MADA_SECTION` → guard is a no-op. Do not hand-export env and then invent a different `-t`.

## Verify

```bash
bash scripts/test_spawn_chair.sh
# expect: ALL 41 PASSED
```
