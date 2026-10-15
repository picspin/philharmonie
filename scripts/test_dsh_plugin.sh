#!/usr/bin/env bash
# Contract tests for dsh-plugin-philharmonie. Exit 0 = all pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$ROOT/dsh-plugin-philharmonie"

echo "== dsh-plugin-philharmonie contract =="

if ! command -v node >/dev/null 2>&1; then
  echo "  SKIP node not installed"
  exit 0
fi

node --test "$PLUGIN_DIR/test/plugin.test.mjs"
