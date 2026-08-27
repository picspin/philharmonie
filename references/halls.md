# Halls (runtime adapters)

Script: `scripts/halls.py`. Contract: `scripts/test_halls.sh`.
Spawn flag: `--hall` / `MADA_HALL` (default `hermes`).

The hall is the envelope + audition + Tacet + garden + snare. A **hall adapter**
is the only place that may speak a vendor CLI. DeepSeek “everything is a plugin”
= chairs / adapters / hooks plug in. It does **not** auto-admit a chair.

## Capabilities (probed, fail-closed)

Each adapter declares a fixed table. Spawn intersects
`chair ceiling ∩ envelope ∩ hall.capabilities` **before** `hall.argv`.
Cannot enforce → exit 2, dry-run included. No degraded argv.

| Hall | worktree | tool_allowlist | model_pin | pre_tool_hook |
|------|----------|----------------|-----------|---------------|
| `hermes` | argv `-w` | argv `-t` | argv `-m` | external |
| `claude` | argv `--worktree` | argv `--allowedTools` | argv `--model` | external |
| `codex` | refuse if envelope `worktree` | env + external hook | argv `-m` | external |
| `pi` | refuse `worktree` | refuse tools (no hook) | refuse (cannot pin) | none |

Binary pins: `MADA_HERMES` / `MADA_CLAUDE` / `MADA_CODEX` / `MADA_PI` (env, then `$PATH`).

Hermes routing (`cliproxy` / `litellm-gateway` / alias) stays in the Hermes adapter.
Claude `--permission-mode acceptEdits` = unattended analog of `--yolo`, not a sandbox bypass.
Codex sandbox: `codex exec -m -s workspace-write`; override with `MADA_CODEX_SANDBOX`.
Pi this wave cannot spawn: it cannot pin `sender.model`. Do not invent `-m`.

Unknown `--hall` refuses. Mute / brass / audition latches apply **before** the adapter.

## Fail-closed

`spawn_chair.plan()` in `hall.argv` 之前：

```
chair ceiling ∩ envelope ∩ hall.capabilities
兑不了 → exit 2，dry-run 也失败。没有降级 argv。
```

Codex + `isolation: worktree` → refuse.
Codex + `isolation: shared` + tools → ok (hook is the tool gate).
Pi + any schema-valid envelope with `sender.model` → refuse.

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
Tacet is **not** a sandbox.

## Verify

```bash
bash scripts/test_halls.sh
python3 scripts/spawn_chair.py --hall claude --dry-run --envelope examples/violin-1.json
python3 scripts/spawn_chair.py --hall codex --dry-run --envelope examples/violin-1.json
# {"ok": false, "error": "hall codex cannot enforce isolation=worktree"}
```
