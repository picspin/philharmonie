#!/usr/bin/env bash
# Contract tests for garden_score.py. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GARDEN="$ROOT/scripts/garden_score.py"
fail=0
n=0
WORKDIR="$(mktemp -d /tmp/mada-garden-XXXX)"
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

clone_tree() {
  local dest="$1"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -a "$ROOT/SKILL.md" "$dest/"
  cp -a "$ROOT/references" "$dest/references"
  cp -a "$ROOT/scripts" "$dest/scripts"
  cp -a "$ROOT/templates" "$dest/templates"
}

echo "== garden_score contract =="

n=$((n + 1))
if [[ -f "$GARDEN" ]]; then
  printf '  ok  garden_score.py exists\n'
else
  printf '  FAIL garden_score.py exists\n'
  fail=$((fail + 1))
fi

run "live tree pass" ok python3 "$GARDEN" --root "$ROOT"

clone_tree "$WORKDIR/missing"
rm -f "$WORKDIR/missing/references/spawn-chair.md"
run "catalog path missing fail" err python3 "$GARDEN" --root "$WORKDIR/missing"
check "mentions spawn-chair.md" has_reason "spawn-chair.md"

clone_tree "$WORKDIR/orphan"
printf '# stray\n' > "$WORKDIR/orphan/references/stray-part.md"
run "orphan part fail" err python3 "$GARDEN" --root "$WORKDIR/orphan"
check "mentions stray-part.md" has_reason "stray-part.md"

clone_tree "$WORKDIR/long"
python3 - "$WORKDIR/long/SKILL.md" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
# pad past 140 without adding new backtick catalog paths
pad = "\n".join(f"<!-- pad {i} -->" for i in range(20))
p.write_text(text.rstrip() + "\n" + pad + "\n", encoding="utf-8")
PY
run "katalog over budget fail" err python3 "$GARDEN" --root "$WORKDIR/long"
check "mentions line budget" has_reason "140"

clone_tree "$WORKDIR/tier"
python3 - "$WORKDIR/tier/templates/envelope.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
data["properties"]["compaction_tier"] = {"type": "integer"}
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
run "compaction_tier costume fail" err python3 "$GARDEN" --root "$WORKDIR/tier"
check "mentions compaction_tier" has_reason "compaction_tier"

clone_tree "$WORKDIR/costume"
python3 - "$WORKDIR/costume/templates/envelope.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
props = data.setdefault("properties", {})
props["protocol"] = {"type": "string"}
props["message_type"] = {"type": "string"}
props["sidechain"] = {"type": "boolean"}
sender = props.setdefault("sender", {})
sprops = sender.setdefault("properties", {})
sprops["agent_id"] = {"type": "string"}
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
run "costume fields fail" err python3 "$GARDEN" --root "$WORKDIR/costume"
check "mentions protocol costume" has_reason "protocol"

clone_tree "$WORKDIR/enum"
python3 - "$WORKDIR/enum/templates/section-contract.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
data["ceilings"]["kazoo"] = ["file"]
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
run "section enum drift fail" err python3 "$GARDEN" --root "$WORKDIR/enum"
check "mentions kazoo or enum" has_reason "kazoo"

clone_tree "$WORKDIR/notest"
rm -f "$WORKDIR/notest/scripts/test_spawn_chair.sh"
run "missing contract test fail" err python3 "$GARDEN" --root "$WORKDIR/notest"
check "mentions test_spawn_chair" has_reason "test_spawn_chair.sh"

echo
if [[ "$fail" -eq 0 ]]; then
  echo "ALL $n PASSED"
  exit 0
fi
echo "$fail / $n FAILED"
exit 1
