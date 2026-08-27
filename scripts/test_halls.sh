#!/usr/bin/env bash
# Contract tests for hall adapters. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPAWN="$ROOT/scripts/spawn_chair.py"
HALLS="$ROOT/scripts/halls.py"
GUARD="$ROOT/scripts/tacet-guard.sh"
fail=0
n=0
WORKDIR="$(mktemp -d /tmp/mada-halls-XXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

run() {
  local name="$1" expect="$2"
  shift 2
  n=$((n + 1))
  local out rc
  set +e
  out="$("$@" 2>"$WORKDIR/err")"
  rc=$?
  set -e
  local ok
  ok="$(printf '%s' "$out" | python3 -c 'import json,sys
try:
    d=json.loads(sys.stdin.read() or "{}")
    print("1" if d.get("ok") else "0")
except Exception:
    print("x")')"
  if [[ "$expect" == "ok" && "$ok" == "1" && "$rc" -eq 0 ]]; then
    printf '  ok  %s\n' "$name"
    printf '%s' "$out" > "$WORKDIR/last.json"
  elif [[ "$expect" == "err" && "$ok" != "1" && "$rc" -ne 0 ]]; then
    printf '  ok  %s\n' "$name"
    printf '%s' "$out" > "$WORKDIR/last.json"
  else
    printf '  FAIL %s (expect=%s ok=%s rc=%s out=%s err=%s)\n' \
      "$name" "$expect" "$ok" "$rc" "${out:0:180}" "$(head -c 120 "$WORKDIR/err" 2>/dev/null || true)"
    fail=$((fail + 1))
  fi
}

has() {
  python3 - "$WORKDIR/last.json" "$@" <<'PY'
import json, sys
data = json.loads(open(sys.argv[1]).read())
kind, key, *rest = sys.argv[2:]
if kind == "env":
    val = (data.get("env") or {}).get(key)
    want = rest[0] if rest else None
    sys.exit(0 if (want is None and val) or val == want else 1)
if kind == "argv":
    sys.exit(0 if key in (data.get("argv") or []) else 1)
if kind == "argv_absent":
    sys.exit(0 if key not in (data.get("argv") or []) else 1)
if kind == "flag":
    argv = data.get("argv") or []
    flag, val = key, rest[0]
    try:
        i = argv.index(flag)
    except ValueError:
        sys.exit(1)
    sys.exit(0 if i + 1 < len(argv) and argv[i + 1] == val else 1)
if kind == "hall":
    sys.exit(0 if data.get("hall") == key else 1)
if kind == "argv0_endswith":
    argv = data.get("argv") or []
    sys.exit(0 if argv and str(argv[0]).endswith(key) else 1)
sys.exit(2)
PY
}

check() {
  local name="$1"
  shift
  n=$((n + 1))
  if "$@"; then
    printf '  ok  %s\n' "$name"
  else
    printf '  FAIL %s\n' "$name"
    fail=$((fail + 1))
  fi
}

guard() {
  local name="$1" expect="$2" json="$3"
  shift 3
  n=$((n + 1))
  local out rc blocked=0
  set +e
  out="$(printf '%s' "$json" | env "$@" "$GUARD" 2>/dev/null)"
  rc=$?
  set -e
  if printf '%s' "$out" | grep -q '"action"[[:space:]]*:[[:space:]]*"block"'; then
    blocked=1
  fi
  if [[ "$expect" == "block" && "$blocked" -eq 1 && "$rc" -eq 0 ]]; then
    printf '  ok  %s\n' "$name"
  elif [[ "$expect" == "allow" && "$blocked" -eq 0 && "$rc" -eq 0 ]]; then
    printf '  ok  %s\n' "$name"
  else
    printf '  FAIL %s (expect=%s blocked=%s rc=%s out=%s)\n' \
      "$name" "$expect" "$blocked" "$rc" "${out:0:160}"
    fail=$((fail + 1))
  fi
}

echo "== halls contract =="

n=$((n + 1))
if [[ -f "$HALLS" ]]; then
  printf '  ok  halls.py exists\n'
else
  printf '  FAIL halls.py exists\n'
  fail=$((fail + 1))
fi

n=$((n + 1))
set +e
python3 - "$HALLS" "$WORKDIR" <<'PY'
import importlib.util, json, sys
from pathlib import Path
p = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("halls", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
want = {
  "hermes": {"worktree": True,  "tool_allowlist": True,  "model_pin": True,  "pre_tool_hook": "external"},
  "claude": {"worktree": True,  "tool_allowlist": True,  "model_pin": True,  "pre_tool_hook": "external"},
  "codex":  {"worktree": False, "tool_allowlist": False, "model_pin": True,  "pre_tool_hook": "external"},
  "pi":     {"worktree": False, "tool_allowlist": False, "model_pin": False, "pre_tool_hook": "none"},
}
keys = ("worktree", "tool_allowlist", "model_pin", "pre_tool_hook")
bad = []
for name, exp in want.items():
    hall = m.resolve_hall(name)
    cap = getattr(hall, "capabilities", None)
    if not isinstance(cap, dict):
        bad.append(f"{name}: missing capabilities")
        continue
    for k in keys:
        if cap.get(k) != exp[k]:
            bad.append(f"{name}.{k}={cap.get(k)!r} want {exp[k]!r}")
Path(sys.argv[2], "cap.json").write_text(json.dumps({"ok": not bad, "bad": bad}))
sys.exit(0 if not bad else 1)
PY
cap_rc=$?
set -e
if [[ "$cap_rc" -eq 0 ]]; then
  printf '  ok  capabilities table\n'
else
  printf '  FAIL capabilities table (%s)\n' "$(python3 -c 'import json; print(json.load(open("'"$WORKDIR"'/cap.json")).get("bad"))' 2>/dev/null || echo missing)"
  fail=$((fail + 1))
fi

cat > "$WORKDIR/v1.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "agent_id": "v1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "sidechain": true,
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "tacet_paths": ["tests/test_locked_kernel.py"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {"summary": "impl"}
}
JSON

cat > "$WORKDIR/v2.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "III. Counterpoint",
  "sender": {"section": "violin_2", "agent_id": "v2", "model": "gemini-3.7-flash-high"},
  "cue": "PATCH_READY",
  "ground_bass_ref": "SPEC.md#v1",
  "sidechain": true,
  "isolation": "shared",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "mp"},
  "payload": {"summary": "review"}
}
JSON

cat > "$WORKDIR/mute.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "TACET_DIRECTIVE",
  "movement": "IV. Tutti",
  "sender": {"section": "oboe", "agent_id": "ob", "model": "mga-glm-5"},
  "cue": "TACET",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": [],
  "budget": {"dynamic_mark": "ppp"},
  "payload": {"summary": "mute"}
}
JSON

cat > "$WORKDIR/brass.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "II. Variation",
  "sender": {"section": "horn", "agent_id": "h", "model": "gpt-5.6-sol"},
  "cue": "GO",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "f"},
  "payload": {"summary": "no"}
}
JSON

# default hall = hermes (existing 41-case argv shape)
run "default hall hermes" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/v1.json" -q "impl brief"
check "hall=hermes" has hall hermes
check "hermes still -w" has argv -w
check "hermes still --yolo" has argv --yolo
check "env MADA_HALL=hermes" has env MADA_HALL hermes

# claude
run "claude worktree" ok \
  python3 "$SPAWN" --hall claude --dry-run --envelope "$WORKDIR/v1.json" -q "impl brief"
check "hall=claude" has hall claude
check "claude -p" has argv -p
check "claude --worktree" has argv --worktree
check "claude --model" has flag --model grok-4.6
check "claude --allowedTools maps terminal,file" has flag --allowedTools "Bash,Read,Edit,Write,Glob,Grep"
check "claude has no hermes --yolo" has argv_absent --yolo
check "claude env still MADA_SECTION" has env MADA_SECTION violin_1

run "claude shared no worktree" ok \
  python3 "$SPAWN" --hall claude --dry-run --envelope "$WORKDIR/v2.json" -q "review brief"
check "claude shared has no --worktree" has argv_absent --worktree

# codex — no invented -t / -w
run "codex exec" ok \
  python3 "$SPAWN" --hall codex --dry-run --envelope "$WORKDIR/v1.json" -q "impl brief"
check "hall=codex" has hall codex
check "codex exec" has argv exec
check "codex -m" has flag -m grok-4.6
check "codex sandbox workspace-write" has flag -s workspace-write
check "codex has no -w costume" has argv_absent -w
check "codex has no -t costume" has argv_absent -t

# pi — prompt only; do not invent flags
run "pi prompt only" ok \
  python3 "$SPAWN" --hall pi --dry-run --envelope "$WORKDIR/v1.json" -q "impl brief"
check "hall=pi" has hall pi
check "pi argv ends with query" has argv "impl brief"
check "pi has no invented --model" has argv_absent --model

# env override + CLI wins
run "MADA_HALL=claude" ok \
  env MADA_HALL=claude \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/v2.json" -q "review brief"
check "env hall=claude" has hall claude

run "--hall beats MADA_HALL" ok \
  env MADA_HALL=claude \
  python3 "$SPAWN" --hall pi --dry-run --envelope "$WORKDIR/v2.json" -q "review brief"
check "cli wins hall=pi" has hall pi

# latches still apply on a foreign hall
run "unknown hall refuse" err \
  python3 "$SPAWN" --hall musikverein --dry-run --envelope "$WORKDIR/v1.json" -q "x"
run "claude still refuses mute" err \
  python3 "$SPAWN" --hall claude --dry-run --envelope "$WORKDIR/mute.json" -q "no"
run "codex still refuses brass" err \
  python3 "$SPAWN" --hall codex --dry-run --envelope "$WORKDIR/brass.json" -q "no"

# tacet understands Claude / Codex tool names
guard "Claude Write SPEC blocked" block \
  '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"SPEC.md"}}' \
  MADA_SECTION=violin_2
guard "Claude Bash sed SPEC blocked" block \
  '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"sed -i s/a/b/ SPEC.md"}}' \
  MADA_SECTION=viola
guard "Claude WebSearch denied" block \
  '{"hook_event_name":"PreToolUse","tool_name":"WebSearch","tool_input":{"query":"x"}}' \
  MADA_SECTION=snare_drum MADA_ALLOWED_TOOLSETS='terminal,file'
guard "Codex apply_patch SPEC blocked" block \
  '{"tool_name":"apply_patch","tool_input":{"path":"SPEC.md"}}' \
  MADA_SECTION=violin_2
guard "Claude Read SPEC allowed" allow \
  '{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"SPEC.md"}}' \
  MADA_SECTION=violin_2

echo
if [[ "$fail" -eq 0 ]]; then
  echo "ALL $n PASSED"
  exit 0
fi
echo "$fail / $n FAILED"
exit 1
