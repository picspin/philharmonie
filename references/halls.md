# Halls (runtime adapters)

Script: `scripts/halls.py`. Contract: `scripts/test_halls.sh`.
Spawn flag: `--hall` / `MADA_HALL` (default `hermes`).

The hall is the envelope + audition + Tacet + garden + snare. A **hall adapter**
is the only place that may speak a vendor CLI. DeepSeek “everything is a plugin”
= chairs / adapters / hooks plug in. It does **not** auto-admit a chair.

## Adapters (probed, not costume)

| Hall | Binary pin | Isolation | Tool gate | Notes |
|------|------------|-----------|-----------|-------|
| `hermes` | `MADA_HERMES` / `HERMES` / `$PATH` / default | `-w` | `-t` csv + `--yolo` | Default. `cliproxy` / `litellm-gateway` / alias routing stays here. |
| `claude` | `MADA_CLAUDE` / `CLAUDE` / `claude` | `--worktree` | `--allowedTools` (Bash/Read/Edit/Write/…) | `-p --model`. `--permission-mode acceptEdits` = unattended analog of `--yolo`, not a sandbox bypass. |
| `codex` | `MADA_CODEX` / `CODEX` / `codex` | *none* (no `-w`) | *none* (no `-t`) | `codex exec -m -s workspace-write`. Override sandbox with `MADA_CODEX_SANDBOX`. Tacet is hook + `MADA_*` only. |
| `pi` | `MADA_PI` / `PI` / `pi` | *none* | *none* | Prompt positional. Do not invent `-m`/`-t`/`-w`. |

Unknown `--hall` refuses. Mute / brass / audition latches apply **before** the adapter.

## Install the second latch

Hermes: `pre_tool_call` → `scripts/tacet-guard.sh` (see `tacet-guard.md`).

Claude Code `.claude/settings.json` (or a plugin `hooks/hooks.json`):

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Write|Edit|Bash|WebSearch|WebFetch|Task",
      "hooks": [{ "type": "command", "command": "/abs/philharmonie/scripts/tacet-guard.sh" }]
    }]
  }
}
```

Codex: a `[[hooks.PreToolUse]]` command hook pointing at the same script
(`--dangerously-bypass-hook-trust` only in already-vetted CI). Guard understands
`Write` / `Bash` / `apply_patch` / `shell` names. Unset `MADA_SECTION` = fail-open.

Pi: no standard pre-tool hook. Honor `allowed_toolsets` yourself or wrap `pi`.

## Verify

```bash
bash scripts/test_halls.sh
python3 scripts/spawn_chair.py --hall claude --dry-run --envelope examples/violin-1.json
```
