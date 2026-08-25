#!/usr/bin/env bash
# Contract tests for tacet-guard.sh. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUARD="$ROOT/scripts/tacet-guard.sh"
fail=0
n=0

run() {
  local name="$1" expect="$2"
  shift 2
  n=$((n + 1))
  local out rc
  set +e
  out="$( "$@" 2>/dev/null )"
  rc=$?
  set -e
  local blocked=0
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

pipe() {
  local json="$1"
  shift
  printf '%s' "$json" | env "$@" "$GUARD"
}

echo "== tacet-guard contract =="

# 1. fail-open: no MADA_SECTION
run "unset section allows write SPEC" allow \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"write_file","tool_input":{"path":"SPEC.md"}}'

# 2. invalid JSON fail-open
run "invalid json fail-open" allow \
  bash -c "printf 'not-json' | env MADA_SECTION=violin_2 '$GUARD'"

# 3. empty stdin fail-open
run "empty stdin fail-open" allow \
  bash -c "printf '' | env MADA_SECTION=violin_2 '$GUARD'"

# 4. ground-bass write blocked
run "violin_2 cannot write SPEC.md" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"write_file","tool_input":{"path":"/tmp/proj/SPEC.md"}}' \
  MADA_SECTION=violin_2

# 5. patch to default contract path blocked
run "patch contracts/ blocked" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"patch","tool_input":{"path":"src/contracts/api.md"}}' \
  MADA_SECTION=horn

# 6. extra tacet path
run "custom tacet_paths blocks locked test" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"write_file","tool_input":{"path":"tests/test_locked_kernel.py"}}' \
  MADA_SECTION=violin_1 MADA_TACET_PATHS='tests/test_locked_kernel.py'

# 7. allowed write elsewhere
run "violin_1 may write src/foo.py" allow \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"write_file","tool_input":{"path":"src/foo.py"}}' \
  MADA_SECTION=violin_1

# 8. toolset gate
run "web_search denied when only file,terminal" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"web_search","tool_input":{"query":"x"}}' \
  MADA_SECTION=snare_drum MADA_ALLOWED_TOOLSETS='terminal,file'

# 9. toolset allow
run "terminal allowed when listed" allow \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"npm test"}}' \
  MADA_SECTION=snare_drum MADA_ALLOWED_TOOLSETS='terminal,file'

# 10. terminal write to SPEC blocked
run "sed -i SPEC.md blocked" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"sed -i s/a/b/ SPEC.md"}}' \
  MADA_SECTION=viola

# 11. read_file SPEC allowed
run "read_file SPEC allowed" allow \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"read_file","tool_input":{"path":"SPEC.md"}}' \
  MADA_SECTION=violin_2

# 12. brass spawn from cheap chair
run "horn cannot wake sol" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"/opt/hermes/.venv/bin/hermes chat -q x --provider cliproxy -m gpt-5.6-sol -t terminal,file --yolo"}}' \
  MADA_SECTION=horn

# 13. brass cue lets conductor spawn sol
run "conductor + MADA_BRASS_CUE may spawn sol" allow \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"hermes chat -q x -m gpt-5.6-sol"}}' \
  MADA_SECTION=conductor MADA_BRASS_CUE=1

# 14. conductor without cue still blocked from sol
run "conductor without cue cannot spawn sol" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"hermes chat -q x -m gpt-5.6-sol"}}' \
  MADA_SECTION=conductor

# 15. heavy_brass may use sol-looking cmds (it IS brass)
run "heavy_brass chair not blocked on sol argv" allow \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"echo using gpt-5.6-sol locally"}}' \
  MADA_SECTION=heavy_brass

# 16. litellm code1 sol spawn blocked from viola
run "viola cannot spawn code1-gpt-5.6-sol" block \
  pipe '{"hook_event_name":"pre_tool_call","tool_name":"terminal","tool_input":{"command":"hermes chat -q x --provider litellm-gateway -m code1-gpt-5.6-sol"}}' \
  MADA_SECTION=viola

echo
if [[ "$fail" -eq 0 ]]; then
  echo "ALL $n PASSED"
  exit 0
fi
echo "$fail / $n FAILED"
exit 1
