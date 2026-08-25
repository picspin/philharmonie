#!/usr/bin/env bash
# tacet-guard.sh — thin PreToolUse Tacet for Mada Symphony.
#
# Opt-in: unset MADA_SECTION → fail-open (exit 0, no stdout).
# Fail-open also on invalid/empty JSON. Never crash the agent.
#
# Env (set by conductor at spawn):
#   MADA_SECTION            chair id (violin_1, horn, …)
#   MADA_ALLOWED_TOOLSETS   comma list mapped to tool names; empty = no gate
#   MADA_TACET_PATHS        extra path prefixes this chair must not write
#   MADA_BRASS_CUE          1 = conductor may spawn sol this movement
#
# Block wire (Hermes + Claude-Code both accepted):
#   {"action":"block","message":"..."}
set -u

export PATH="${PATH:-/usr/bin:/bin}:/usr/bin:/bin"

section="${MADA_SECTION:-}"
if [[ -z "$section" ]]; then
  exit 0
fi

payload="$(cat 2>/dev/null || true)"
if [[ -z "${payload//[[:space:]]/}" ]]; then
  exit 0
fi

# All policy lives in this python so we do not depend on grep/PATH.
exec python3 - "$section" "$payload" <<'PY'
import json, os, re, sys

section = sys.argv[1]
raw = sys.argv[2]

def allow() -> None:
    sys.exit(0)

def block(msg: str) -> None:
    sys.stdout.write(json.dumps({"action": "block", "message": msg}, ensure_ascii=False) + "\n")
    sys.exit(0)

try:
    data = json.loads(raw)
except Exception:
    allow()

if not isinstance(data, dict):
    allow()

tool = str(data.get("tool_name") or "")
tin = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
path = str(tin.get("path") or tin.get("file_path") or tin.get("target") or "")
cmd = str(tin.get("command") or "")

TOOLSET = {
    "terminal": "terminal",
    "process": "terminal",
    "Bash": "terminal",  # Claude Code
    "shell": "terminal",  # Codex
    "read_file": "file",
    "write_file": "file",
    "patch": "file",
    "search_files": "file",
    "Read": "file",
    "Edit": "file",
    "Write": "file",
    "Glob": "file",
    "Grep": "file",
    "apply_patch": "file",
    "web_search": "web",
    "web_extract": "web",
    "WebSearch": "web",
    "WebFetch": "web",
    "browser_navigate": "web",
    "browser_click": "web",
    "browser_type": "web",
    "browser_snapshot": "web",
    "browser_press": "web",
    "browser_scroll": "web",
    "browser_back": "web",
    "browser_console": "web",
    "browser_get_images": "web",
    "browser_vision": "web",
    "delegate_task": "delegation",
    "Task": "delegation",
    "image_generate": "vision",
    "vision_analyze": "vision",
}

allowed_raw = os.environ.get("MADA_ALLOWED_TOOLSETS", "").strip()
if allowed_raw:
    allowed = {x.strip() for x in allowed_raw.split(",") if x.strip()}
    ts = TOOLSET.get(tool)
    if ts and ts not in allowed:
        block(f"TACET: toolset '{ts}' ({tool}) not in MADA_ALLOWED_TOOLSETS={allowed_raw}")

DEFAULT_BASS = [
    "SPEC.md",
    "AGENTS.md",
    "contracts/",
    "src/contracts/",
    "locked_tests/",
    "tests/locked/",
]
extra = [x.strip() for x in os.environ.get("MADA_TACET_PATHS", "").split(",") if x.strip()]
bass = DEFAULT_BASS + extra

def hits_bass(candidate: str) -> bool:
    if not candidate:
        return False
    norm = candidate.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    for item in bass:
        item = item.replace("\\", "/")
        if not item:
            continue
        if item.endswith("/"):
            token = item.strip("/")
            if token and (f"/{token}/" in f"/{norm}/" or norm.startswith(item) or norm.startswith(token + "/")):
                return True
            continue
        if "/" in item:
            if norm == item or norm.endswith("/" + item) or item in norm:
                return True
            continue
        # basename / exact file
        if base == item or norm == item or norm.endswith("/" + item):
            return True
        # also allow the item to appear as a path fragment in a shell command
        if re.search(r"(^|[\s/;])" + re.escape(item) + r"(\s|$)", candidate):
            return True
    return False

WRITE_TOOLS = {"write_file", "patch", "Write", "Edit", "apply_patch"}
if tool in WRITE_TOOLS and hits_bass(path):
    block(f"TACET: {section} must not write ground-bass path '{path}'")

SHELL_TOOLS = {"terminal", "Bash", "shell"}
if tool in SHELL_TOOLS and cmd:
    writer = re.search(
        r"(^|[\s;|&])(sed\s+-+\w*i|sed\s+-\S*\s+-i|tee\s|cat\s.*>|python3?\s)",
        cmd,
    )
    redirect = re.search(
        r">{1,2}\s*\S*(SPEC\.md|AGENTS\.md|/contracts/|/locked_tests/)",
        cmd,
    )
    if (writer and hits_bass(cmd)) or redirect:
        block(f"TACET: {section} terminal must not mutate ground-bass ({cmd[:120]})")

BRASS_RE = re.compile(
    r"(?:^|[\s=])(?:gpt-5\.6-sol|code1-gpt-5\.6-sol|code2-claude-opus-4-6-thinking)(?:\s|$)"
)
SOL_FLAG_RE = re.compile(r"-m\s+\S*sol(?:\s|$)")
is_brass_spawn = tool in SHELL_TOOLS and bool(cmd) and (
    BRASS_RE.search(cmd) or SOL_FLAG_RE.search(cmd)
)

if is_brass_spawn:
    if section == "heavy_brass":
        allow()
    if section == "conductor" and os.environ.get("MADA_BRASS_CUE") == "1":
        allow()
    block(f"TACET: {section} must not wake Heavy Brass (sol) without MADA_BRASS_CUE=1")

allow()
PY
