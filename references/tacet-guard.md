# Tacet guard (heteronomous, opt-in)

Script: `scripts/tacet-guard.sh`. Contract: `scripts/test_tacet_guard.sh` (16 cases).

This is **not** Claude-Code six-layer hooks. One `pre_tool_call` script. Fail-open. Opt-in.

## What it actually blocks

Only when `MADA_SECTION` is set (conductor exports it on spawn):

| Rule | Trigger | Example |
|------|---------|---------|
| Ground-bass write | `write_file` / `patch` hitting `SPEC.md`, `AGENTS.md`, `contracts/`, `src/contracts/`, `locked_tests/`, `tests/locked/`, plus `MADA_TACET_PATHS` | Violin II cannot rewrite `SPEC.md` |
| Terminal mutate bass | `sed -i` / `tee` / `>` onto those paths | `sed -i s/a/b/ SPEC.md` |
| Toolset gate | tool's mapped set ∉ `MADA_ALLOWED_TOOLSETS` | Snare with `terminal,file` cannot `web_search` |
| Brass lock | cheap chair's `terminal` argv contains `gpt-5.6-sol` / `code1-gpt-5.6-sol` | Horn cannot `hermes chat -m gpt-5.6-sol` |

`read_file` of bass paths is **allowed**. Unset `MADA_SECTION` → no-op. Bad/empty JSON → no-op.

## What it does **not** block

- A parent session that started before the hook was registered. New child chats load it. Unset `MADA_SECTION` → still no-op.
- A child chat that the conductor forgot to export `MADA_SECTION` into.
- Codex Cloud / `codex exec` / Pi — install this same script as *that* runtime's pre-tool hook (`halls.md`). Unset `MADA_SECTION` still fail-open.
- `delegate_task` children unless the parent process itself has the hook **and** the env is inherited.
- Model routing / 429 / Brass quota. Schema-valid ≠ auto-admit.

Primary Tacet remains spawn `-t` / `allowed_toolsets`. This script is the second latch for chairs that still got `file`/`terminal`. OS latch is spawn `--lock-bass` (chmod). Tacet does **not** catch `cp` / `git add` / `chmod +w`. Tacet ≠ sandbox.

## Deploy (`hooks:` + allowlist)

Human cue required. Keep `hooks_auto_accept: false`.

Do **not** use a generic file-patch tool on the host `config.yaml` if the runtime marks it security-sensitive. Do **not** assume `hermes config set hooks.…` can write a list of hook specs. Backup, then exact-replace the `hooks: {}` stanza:

```yaml
hooks:
  pre_tool_call:
  - matcher: write_file|patch|terminal|web_search|web_extract|delegate_task
    command: /absolute/path/to/philharmonie/scripts/tacet-guard.sh
    timeout: 5
```

Allowlist is per `(event, command)` (Hermes: `shell-hooks-allowlist.json`). Non-TTY gateway cannot confirm interactively. Record once (do not flip auto-accept):

```python
from agent.shell_hooks import _record_approval
_record_approval("pre_tool_call", "/absolute/path/to/philharmonie/scripts/tacet-guard.sh")
```

Then `hermes hooks doctor`. Prove with a **child** chat (`MADA_SECTION=violin_2` write `SPEC.md` must block). Hook is per-process: a gateway that started with `hooks: {}` stays fail-open until a **human** `/restart`. Do not auto-restart. New children already load it. Unapproved hooks are skipped, not crash.

## Spawn (conductor)

Prefer the wrapper — it is the only place that keeps envelope fields, `-t`, and `MADA_*` in lockstep:

```bash
python3 scripts/spawn_chair.py --envelope chair.json -q "<brief>"
```

Raw equivalent (do not invent a different `-t`):

```bash
export MADA_SECTION=violin_1
export MADA_ALLOWED_TOOLSETS=terminal,file
export MADA_TACET_PATHS=tests/test_locked_kernel.py
# only on an explicit climax:
# export MADA_BRASS_CUE=1

hermes chat -w -q "<brief>" -m <chair> -t terminal,file --yolo
```

The hook does not read `envelope.json`. Details: `references/spawn-chair.md`.

## Verify

```bash
bash scripts/test_tacet_guard.sh
# expect: ALL 16 PASSED
```

Live (only after hooks are registered + allowlisted):

```bash
hermes hooks test pre_tool_call --for-tool write_file \
  --payload-file /tmp/tacet-payload.json
```
