#!/usr/bin/env bash
# Contract tests for snare_score.py. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNARE="$ROOT/scripts/snare_score.py"
fail=0
n=0
WORKDIR="$(mktemp -d /tmp/mada-snare-XXXX)"
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
  local ok
  ok="$(python3 -c 'import json,sys
try:
    d=json.loads(open(sys.argv[1]).read() or "{}")
    print("1" if d.get("ok") else "0")
except Exception:
    print("x")' "$WORKDIR/last.json")"
  if [[ "$expect" == "ok" && "$ok" == "1" && "$rc" -eq 0 ]]; then
    printf '  ok  %s\n' "$name"
  elif [[ "$expect" == "err" && "$ok" != "1" && "$rc" -ne 0 ]]; then
    printf '  ok  %s\n' "$name"
  else
    printf '  FAIL %s (expect=%s ok=%s rc=%s out=%s err=%s)\n' \
      "$name" "$expect" "$ok" "$rc" "${out:0:220}" "$(head -c 160 "$WORKDIR/err" 2>/dev/null || true)"
    fail=$((fail + 1))
  fi
}

has_reason() {
  python3 - "$WORKDIR/last.json" "$1" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read())
needle = sys.argv[2]
blob = " ".join(str(x) for x in (d.get("errors") or []))
sys.exit(0 if needle in blob else 1)
PY
}

rung_cmd() {
  python3 - "$WORKDIR/last.json" "$1" "$2" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1]).read())
got = (d.get("rungs") or {}).get(sys.argv[2])
sys.exit(0 if got == sys.argv[3] else 1)
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

write_agents() {
  local dest="$1"
  mkdir -p "$dest"
  cat > "$dest/AGENTS.md"
}

echo "== snare_score contract =="

n=$((n + 1))
if [[ -f "$SNARE" ]]; then
  printf '  ok  snare_score.py exists\n'
else
  printf '  FAIL snare_score.py exists\n'
  fail=$((fail + 1))
fi

# 1. complete ladder
write_agents "$WORKDIR/good" <<'MD'
# Project

## Verify
- lint: `ruff check .`
- unit: `pytest -q`
- e2e: `npm run e2e`
- security: `gitleaks detect --no-git`
MD
run "complete ladder pass" ok python3 "$SNARE" --root "$WORKDIR/good"
check "lint cmd" rung_cmd lint "ruff check ."
check "unit cmd" rung_cmd unit "pytest -q"
check "e2e cmd" rung_cmd e2e "npm run e2e"
check "security cmd" rung_cmd security "gitleaks detect --no-git"

# 2. missing file
mkdir -p "$WORKDIR/empty"
run "missing AGENTS.md fail" err python3 "$SNARE" --root "$WORKDIR/empty"
check "mentions AGENTS.md" has_reason "AGENTS.md"

# 3. missing one rung
write_agents "$WORKDIR/nolint" <<'MD'
## Verify
- unit: `pytest -q`
- e2e: `npm run e2e`
- security: `gitleaks detect`
MD
run "missing lint fail" err python3 "$SNARE" --root "$WORKDIR/nolint"
check "mentions lint" has_reason "lint"

write_agents "$WORKDIR/nounit" <<'MD'
## Verify
- lint: `ruff check .`
- e2e: `npm run e2e`
- security: `gitleaks detect`
MD
run "missing unit fail" err python3 "$SNARE" --root "$WORKDIR/nounit"
check "mentions unit" has_reason "unit"

write_agents "$WORKDIR/noe2e" <<'MD'
## Verify
- lint: `ruff check .`
- unit: `pytest -q`
- security: `gitleaks detect`
MD
run "missing e2e fail" err python3 "$SNARE" --root "$WORKDIR/noe2e"
check "mentions e2e" has_reason "e2e"

write_agents "$WORKDIR/nosec" <<'MD'
## Verify
- lint: `ruff check .`
- unit: `pytest -q`
- e2e: `npm run e2e`
MD
run "missing security fail" err python3 "$SNARE" --root "$WORKDIR/nosec"
check "mentions security" has_reason "security"

# 4. label without a pasteable command
write_agents "$WORKDIR/prose" <<'MD'
## Verify
- lint: we should lint things
- unit: `pytest -q`
- e2e: `npm run e2e`
- security: `gitleaks detect`
MD
run "prose lint fail" err python3 "$SNARE" --root "$WORKDIR/prose"
check "prose mentions lint" has_reason "lint"

# 5. aliases + $ prompt + heading block
write_agents "$WORKDIR/alias" <<'MD'
# Agents

### Format
$ cargo fmt --check

unit: `go test ./...`

## Integration
```
make e2e
```

fff: `make audit`
MD
run "alias headings pass" ok python3 "$SNARE" --root "$WORKDIR/alias"
check "format→lint" rung_cmd lint "cargo fmt --check"
check "go unit" rung_cmd unit "go test ./..."
check "make e2e" rung_cmd e2e "make e2e"
check "fff→security" rung_cmd security "make audit"

# 6. CLAUDE.md is not a substitute
mkdir -p "$WORKDIR/claude"
printf '# verify\nlint: `ruff check .`\nunit: `pytest`\ne2e: `npm t`\nsecurity: `gitleaks`\n' \
  > "$WORKDIR/claude/CLAUDE.md"
run "CLAUDE.md not a substitute" err python3 "$SNARE" --root "$WORKDIR/claude"
check "still wants AGENTS.md" has_reason "AGENTS.md"

# 7. does not treat this skill as a project (no AGENTS.md here)
run "skill root is not a project" err python3 "$SNARE" --root "$ROOT"
check "skill missing AGENTS.md" has_reason "AGENTS.md"

echo
if [[ "$fail" -eq 0 ]]; then
  echo "ALL $n PASSED"
  exit 0
fi
echo "$fail / $n FAILED"
exit 1
