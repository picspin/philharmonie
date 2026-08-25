#!/usr/bin/env bash
# Contract tests for spawn_chair.py. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPAWN="$ROOT/scripts/spawn_chair.py"
fail=0
n=0
WORKDIR="$(mktemp -d /tmp/mada-spawn-XXXX)"
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
    argv = data.get("argv") or []
    token = key
    sys.exit(0 if token in argv else 1)
if kind == "argv_absent":
    argv = data.get("argv") or []
    sys.exit(0 if key not in argv else 1)
if kind == "flag":
    argv = data.get("argv") or []
    flag, val = key, rest[0]
    try:
        i = argv.index(flag)
    except ValueError:
        sys.exit(1)
    sys.exit(0 if i + 1 < len(argv) and argv[i + 1] == val else 1)
if kind == "no_flag":
    argv = data.get("argv") or []
    sys.exit(0 if key not in argv else 1)
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

env_json() {
  local path="$1"
  cat > "$path"
}

echo "== spawn_chair contract =="

# 1. missing script would 127 — existence
n=$((n + 1))
if [[ -x "$SPAWN" || -f "$SPAWN" ]]; then
  printf '  ok  spawn_chair.py exists\n'
else
  printf '  FAIL spawn_chair.py exists\n'
  fail=$((fail + 1))
fi

# 2. worktree + toolsets + env
env_json "$WORKDIR/v1.json" <<'JSON'
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
run "violin_1 worktree dry-run" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/v1.json" -q "impl brief"
check "exports MADA_SECTION=violin_1" has env MADA_SECTION violin_1
check "exports toolsets csv" has env MADA_ALLOWED_TOOLSETS "terminal,file"
check "exports tacet_paths" has env MADA_TACET_PATHS "tests/test_locked_kernel.py"
check "argv has -w" has argv -w
check "argv -t terminal,file" has flag -t terminal,file
check "argv -m grok-4.6" has flag -m grok-4.6
check "argv --provider cliproxy" has flag --provider cliproxy
check "argv --yolo" has argv --yolo

has_env_absent() {
  python3 - "$WORKDIR/last.json" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read())
v = (d.get("env") or {}).get("MADA_BRASS_CUE")
sys.exit(0 if not v else 1)
PY
}
check "no MADA_BRASS_CUE" has_env_absent

# 3. shared isolation → no -w
env_json "$WORKDIR/v2.json" <<'JSON'
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
run "violin_2 shared dry-run" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/v2.json" -q "review brief"
check "shared has no -w" has argv_absent -w
check "gemini still cliproxy" has flag --provider cliproxy

# 4. empty toolsets = mute = refuse
env_json "$WORKDIR/mute.json" <<'JSON'
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
run "empty allowed_toolsets refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/mute.json" -q "no"

# 5. missing allowed_toolsets refuse
env_json "$WORKDIR/missing-t.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "II. Variation",
  "sender": {"section": "horn", "agent_id": "h", "model": "grok-4.6"},
  "cue": "GO",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "budget": {"dynamic_mark": "mp"},
  "payload": {"summary": "x"}
}
JSON
run "missing allowed_toolsets refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/missing-t.json" -q "x"

# 6. brass without cue refuse
env_json "$WORKDIR/brass.json" <<'JSON'
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
run "horn + sol refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/brass.json" -q "no"

# 7. brass cue allows sol
run "conductor brass cue allows sol" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/brass.json" --section conductor --brass-cue -q "climax"
check "brass cue env=1" has env MADA_BRASS_CUE 1
check "section override conductor" has env MADA_SECTION conductor

# 8. heavy_brass may use sol
env_json "$WORKDIR/hb.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "climax",
  "sender": {"section": "heavy_brass", "agent_id": "br", "model": "gpt-5.6-sol"},
  "cue": "TUTTI",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "ffff"},
  "payload": {"summary": "tutti"}
}
JSON
run "heavy_brass sol ok" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/hb.json" -q "tutti"

# 9. litellm prefix
env_json "$WORKDIR/luna.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "III. Counterpoint",
  "sender": {"section": "violin_2", "agent_id": "v2", "model": "code1-gpt-5.6-luna"},
  "cue": "REVIEW",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["file"],
  "budget": {"dynamic_mark": "mp"},
  "payload": {"summary": "review"}
}
JSON
run "code1 → litellm-gateway" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/luna.json" -q "review"
check "provider litellm-gateway" has flag --provider litellm-gateway

# 10. alias omits --provider
env_json "$WORKDIR/ox.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "V. Finale",
  "sender": {"section": "harp", "agent_id": "hp", "model": "ox-alpha"},
  "cue": "CAPTION",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["file", "web"],
  "budget": {"dynamic_mark": "p"},
  "payload": {"summary": "caption"}
}
JSON
run "ox-alpha alias no provider" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/ox.json" -q "caption"
check "ox-alpha has no --provider" has no_flag --provider
check "ox-alpha -m ox-alpha" has flag -m ox-alpha

# 11. invalid json
printf 'not-json' > "$WORKDIR/bad.json"
run "invalid json refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/bad.json" -q "x"

# 12. unknown section
env_json "$WORKDIR/badsec.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "x",
  "sender": {"section": "kazoo", "agent_id": "k", "model": "grok-4.6"},
  "cue": "x",
  "ground_bass_ref": "SPEC.md",
  "isolation": "shared",
  "allowed_toolsets": ["file"],
  "budget": {"dynamic_mark": "p"},
  "payload": {"summary": "x"}
}
JSON
run "unknown section refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/badsec.json" -q "x"

# 13. query from payload.summary when -q omitted
run "query from payload.summary" ok \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/v2.json"
check "uses payload.summary as -q" has flag -q review

# 14. stdin envelope
run "stdin envelope" ok \
  python3 "$SPAWN" --dry-run -q "from stdin" < "$WORKDIR/v1.json"
check "stdin still violin_1" has env MADA_SECTION violin_1

has_audition() {
  python3 - "$WORKDIR/last.json" "$1" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read())
sys.exit(0 if d.get("audition") == sys.argv[2] else 1)
PY
}
check "default audition=pass" has_audition pass

# 15. missing budget fails audition
env_json "$WORKDIR/nobudget.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "agent_id": "v1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "payload": {"summary": "impl"}
}
JSON
run "missing budget refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/nobudget.json" -q "impl"

# 16. --force skips audition (still emits argv)
run "force skips audition" ok \
  python3 "$SPAWN" --dry-run --force --envelope "$WORKDIR/nobudget.json" -q "impl"
check "force audition=skipped" has_audition skipped
check "force still -w" has argv -w

# 17. --force does not lift spawn mute
run "force still refuses empty toolsets" err \
  python3 "$SPAWN" --dry-run --force --envelope "$WORKDIR/mute.json" -q "no"

# 18. flute overflow blocked without --force
env_json "$WORKDIR/flute.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "message_type": "POINT_TO_POINT_HANDOVER",
  "movement": "probe",
  "sender": {"section": "flute", "agent_id": "fl", "model": "mimo-v2.5"},
  "cue": "PROBE",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "pp"},
  "payload": {"summary": "probe"}
}
JSON
run "flute + terminal refuse" err \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/flute.json" -q "probe"

# 19. MADA_HERMES overrides the binary pin (other halls / agents)
run "MADA_HERMES override" ok \
  env MADA_HERMES=/usr/local/bin/other-hermes \
  python3 "$SPAWN" --dry-run --envelope "$WORKDIR/v1.json" -q "impl brief"
check "argv[0] is MADA_HERMES" has argv /usr/local/bin/other-hermes

echo
if [[ "$fail" -eq 0 ]]; then
  echo "ALL $n PASSED"
  exit 0
fi
echo "$fail / $n FAILED"
exit 1
