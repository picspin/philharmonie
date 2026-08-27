#!/usr/bin/env bash
# Contract tests for audition_chair.py. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUD="$ROOT/scripts/audition_chair.py"
fail=0
n=0
WORKDIR="$(mktemp -d /tmp/mada-audition-XXXX)"
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
  printf '%s' "$out" > "$WORKDIR/last.json"
  local audition admit
  audition="$(python3 -c 'import json,sys; d=json.loads(open(sys.argv[1]).read() or "{}"); print(d.get("audition",""))' "$WORKDIR/last.json" 2>/dev/null || echo x)"
  admit="$(python3 -c 'import json,sys; d=json.loads(open(sys.argv[1]).read() or "{}"); print(d.get("admit"))' "$WORKDIR/last.json" 2>/dev/null || echo x)"
  if [[ "$expect" == "pass" && "$audition" == "pass" && "$rc" -eq 0 ]]; then
    printf '  ok  %s\n' "$name"
  elif [[ "$expect" == "fail" && "$audition" == "fail" && "$rc" -ne 0 ]]; then
    printf '  ok  %s\n' "$name"
  else
    printf '  FAIL %s (expect=%s audition=%s rc=%s out=%s err=%s)\n' \
      "$name" "$expect" "$audition" "$rc" "${out:0:180}" "$(head -c 120 "$WORKDIR/err" 2>/dev/null || true)"
    fail=$((fail + 1))
  fi
  if [[ "$admit" != "False" && "$admit" != "false" ]]; then
    n=$((n + 1))
    printf '  FAIL %s admit must be false (got %s)\n' "$name" "$admit"
    fail=$((fail + 1))
  else
    n=$((n + 1))
    printf '  ok  %s admit=false\n' "$name"
  fi
}

field() {
  python3 - "$WORKDIR/last.json" "$@" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read())
key = sys.argv[2]
want = sys.argv[3] if len(sys.argv) > 3 else None
val = d.get(key)
if want is None:
    sys.exit(0 if val else 1)
if want == "true":
    sys.exit(0 if val is True else 1)
if want == "false":
    sys.exit(0 if val is False else 1)
sys.exit(0 if str(val) == want else 1)
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

env_json() { cat > "$1"; }

echo "== audition_chair contract =="

n=$((n + 1))
if [[ -f "$AUD" ]]; then
  printf '  ok  audition_chair.py exists\n'
else
  printf '  FAIL audition_chair.py exists\n'
  fail=$((fail + 1))
fi

env_json "$WORKDIR/v1.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "tacet_paths": ["tests/test_locked_kernel.py"],
  "budget": {"dynamic_mark": "mf", "max_tokens": 32000},
  "payload": {"summary": "impl"}
}
JSON
run "violin_1 worktree pass" pass python3 "$AUD" --envelope "$WORKDIR/v1.json"
check "section violin_1" field section violin_1
check "not tacet" field tacet false

env_json "$WORKDIR/v2.json" <<'JSON'
{
  "movement": "III. Counterpoint",
  "sender": {"section": "violin_2", "model": "gemini-3.7-flash-high"},
  "cue": "PATCH_READY",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "mp"},
  "payload": {"summary": "review"}
}
JSON
run "violin_2 shared pass" pass python3 "$AUD" --envelope "$WORKDIR/v2.json"

env_json "$WORKDIR/v2w.json" <<'JSON'
{
  "movement": "III. Counterpoint",
  "sender": {"section": "violin_2", "model": "gemini-3.7-flash-high"},
  "cue": "PATCH_READY",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["file"],
  "budget": {"dynamic_mark": "mp"},
  "payload": {"summary": "review"}
}
JSON
run "violin_2 worktree fail" fail python3 "$AUD" --envelope "$WORKDIR/v2w.json"

env_json "$WORKDIR/flute-term.json" <<'JSON'
{
  "movement": "I. Overture",
  "sender": {"section": "flute", "model": "mimo-v2.5"},
  "cue": "PROBE",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "pp"},
  "payload": {"summary": "probe"}
}
JSON
run "flute overflow terminal fail" fail python3 "$AUD" --envelope "$WORKDIR/flute-term.json"

env_json "$WORKDIR/mute.json" <<'JSON'
{
  "movement": "IV. Tutti",
  "sender": {"section": "oboe", "model": "mga-glm-5"},
  "cue": "TACET",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": [],
  "budget": {"dynamic_mark": "ppp"},
  "payload": {"summary": "mute"}
}
JSON
run "empty toolsets tacet pass" pass python3 "$AUD" --envelope "$WORKDIR/mute.json"
check "tacet true" field tacet true

env_json "$WORKDIR/missing-t.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "horn", "model": "grok-4.6"},
  "cue": "GO",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "budget": {"dynamic_mark": "mf"},
  "payload": {"summary": "x"}
}
JSON
run "missing allowed_toolsets fail" fail python3 "$AUD" --envelope "$WORKDIR/missing-t.json"

env_json "$WORKDIR/nocue.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["file"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {"summary": "x"}
}
JSON
run "schema missing cue fail" fail python3 "$AUD" --envelope "$WORKDIR/nocue.json"

env_json "$WORKDIR/kazoo.json" <<'JSON'
{
  "movement": "x",
  "sender": {"section": "kazoo", "model": "grok-4.6"},
  "cue": "x",
  "ground_bass_ref": "SPEC.md",
  "isolation": "shared",
  "allowed_toolsets": ["file"],
  "budget": {"dynamic_mark": "p"},
  "payload": {"summary": "x"}
}
JSON
run "unknown section fail" fail python3 "$AUD" --envelope "$WORKDIR/kazoo.json"

printf 'not-json' > "$WORKDIR/bad.json"
run "invalid json fail" fail python3 "$AUD" --envelope "$WORKDIR/bad.json"

env_json "$WORKDIR/horn-sol.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "horn", "model": "gpt-5.6-sol"},
  "cue": "GO",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "f"},
  "payload": {"summary": "no"}
}
JSON
run "horn + sol fail" fail python3 "$AUD" --envelope "$WORKDIR/horn-sol.json"

env_json "$WORKDIR/hb.json" <<'JSON'
{
  "movement": "climax",
  "sender": {"section": "heavy_brass", "model": "gpt-5.6-sol"},
  "cue": "TUTTI",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "ffff"},
  "payload": {"summary": "tutti"}
}
JSON
run "heavy_brass sol pass still not admit" pass python3 "$AUD" --envelope "$WORKDIR/hb.json"

env_json "$WORKDIR/badts.json" <<'JSON'
{
  "movement": "V. Finale",
  "sender": {"section": "harp", "model": "ox-alpha"},
  "cue": "CAPTION",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["browser"],
  "budget": {"dynamic_mark": "p"},
  "payload": {"summary": "caption"}
}
JSON
run "unknown toolset name fail" fail python3 "$AUD" --envelope "$WORKDIR/badts.json"

env_json "$WORKDIR/harp.json" <<'JSON'
{
  "movement": "V. Finale",
  "sender": {"section": "harp", "model": "ox-alpha"},
  "cue": "CAPTION",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "shared",
  "allowed_toolsets": ["file", "web"],
  "budget": {"dynamic_mark": "p"},
  "payload": {"summary": "caption"}
}
JSON
run "harp file+web pass" pass python3 "$AUD" --envelope "$WORKDIR/harp.json"

run "stdin envelope pass" pass python3 "$AUD" < "$WORKDIR/v1.json"

env_json "$WORKDIR/nobudget.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["file"],
  "payload": {"summary": "impl"}
}
JSON
run "missing budget fail" fail python3 "$AUD" --envelope "$WORKDIR/nobudget.json"

env_json "$WORKDIR/nosum.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["file"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {}
}
JSON
run "missing payload.summary fail" fail python3 "$AUD" --envelope "$WORKDIR/nosum.json"

env_json "$WORKDIR/bare.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {"summary": "impl"}
}
JSON
run "bare envelope pass" pass python3 "$AUD" --envelope "$WORKDIR/bare.json"

env_json "$WORKDIR/extra.json" <<'JSON'
{
  "protocol": "Mada-A2A/1.0",
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {"summary": "impl"}
}
JSON
run "extra protocol fail" fail python3 "$AUD" --envelope "$WORKDIR/extra.json"

env_json "$WORKDIR/agent.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6", "agent_id": "v1"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {"summary": "impl"}
}
JSON
run "extra sender.agent_id fail" fail python3 "$AUD" --envelope "$WORKDIR/agent.json"

env_json "$WORKDIR/art.json" <<'JSON'
{
  "movement": "II. Variation",
  "sender": {"section": "violin_1", "model": "grok-4.6"},
  "cue": "SPEC_LOCKED",
  "ground_bass_ref": "SPEC.md#v1",
  "isolation": "worktree",
  "allowed_toolsets": ["terminal", "file"],
  "budget": {"dynamic_mark": "mf"},
  "payload": {
    "summary": "impl",
    "artifacts": [{"type": "spec", "path_or_uri": "SPEC.md", "costume": true}]
  }
}
JSON
run "extra artifact key fail" fail python3 "$AUD" --envelope "$WORKDIR/art.json"

echo
if [[ "$fail" -eq 0 ]]; then
  echo "ALL $n PASSED"
  exit 0
fi
echo "$fail / $n FAILED"
exit 1
