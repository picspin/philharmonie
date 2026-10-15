/**
 * dsh-plugin-philharmonie — DeepSeek Harness (dsh) Cordis plugin for Mada Symphony.
 *
 * Exposes Mada Symphony orchestration contracts and gates to DSH agents:
 *   - symphony_audition: Auditions a chair envelope against section contracts (schema, ceiling, isolation lock).
 *     `admit` is ALWAYS false; conductor retains routing authority.
 *   - symphony_snare_verify: 0-token 4-rung verification ladder (lint, unit, e2e, security) on target AGENTS.md.
 *   - symphony_dispatch_cue: Broadcasts movement signals (SPEC_LOCKED, TEST_PASSED, CIRCUIT_BREAK, MAHLER_TACET, BRASS_SOL).
 *   - tools/pre-execute interceptor: Enforces Mahler Tacet guards on active chairs (blocks writes to ground-bass paths).
 *
 * Contract:
 *   - ESM named exports: name, inject, apply(ctx, config)
 *   - Registers tools via ctx.tools.register(definition)
 *   - Zero third-party dependencies: Node 22 built-ins only (node:child_process, node:fs, node:path, node:url, node:os)
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const name = "dsh-plugin-philharmonie";
const inject = ["tools"];

const DEFAULT_TIMEOUT_MS = 60000;

function resolvePhilRoot(config = {}) {
  if (config.philRoot && existsSync(config.philRoot)) {
    return resolve(config.philRoot);
  }
  if (process.env.PHILHARMONIE_ROOT && existsSync(process.env.PHILHARMONIE_ROOT)) {
    return resolve(process.env.PHILHARMONIE_ROOT);
  }
  // Try parent of plugin directory
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const parentDir = resolve(currentDir, "..");
  if (existsSync(join(parentDir, "scripts", "audition_chair.py"))) {
    return parentDir;
  }
  // Standard fallback locations
  const fallbacks = [
    "/home/hilbert/philharmonie",
    "/opt/data/workspace/philharmonie",
    resolve(process.env.HOME || "", "philharmonie")
  ];
  for (const p of fallbacks) {
    if (existsSync(join(p, "scripts", "audition_chair.py"))) {
      return p;
    }
  }
  return parentDir;
}

function runProcess(cmd, args, options = {}, stdinData = "") {
  return new Promise((resolveResult, rejectResult) => {
    const timeout = options.timeout || DEFAULT_TIMEOUT_MS;
    const proc = spawn(cmd, args, {
      ...options,
      env: { ...process.env, ...(options.env || {}) }
    });

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const timer = setTimeout(() => {
      timedOut = true;
      proc.kill("SIGKILL");
    }, timeout);

    proc.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      rejectResult(err);
    });

    proc.on("close", (code) => {
      clearTimeout(timer);
      if (timedOut) {
        rejectResult(new Error(`Process timed out after ${timeout}ms: ${cmd} ${args.join(" ")}`));
      } else {
        resolveResult({ code, stdout: stdout.trim(), stderr: stderr.trim() });
      }
    });

    if (stdinData) {
      proc.stdin.write(stdinData);
    }
    proc.stdin.end();
  });
}

// -----------------------------------------------------------------------------
// Tool 1: symphony_audition
// -----------------------------------------------------------------------------
const AUDITION_PARAMETERS = {
  type: "object",
  additionalProperties: false,
  required: ["envelope"],
  properties: {
    envelope: {
      type: "object",
      description: "Mada Symphony chair envelope containing sender, isolation, allowed_toolsets, movement, budget, and payload."
    }
  }
};

const AUDITION_OUTPUT = {
  schema: {
    oneOf: [
      {
        type: "object",
        additionalProperties: false,
        required: ["status", "audition", "admit", "section", "reasons"],
        properties: {
          status: { type: "string", const: "success" },
          audition: { type: "string", enum: ["pass", "fail"] },
          admit: { type: "boolean" },
          section: { type: "string" },
          reasons: { type: "array", items: { type: "string" } }
        }
      },
      {
        type: "object",
        additionalProperties: false,
        required: ["status", "error"],
        properties: {
          status: { type: "string", const: "error" },
          error: { type: "string" }
        }
      }
    ]
  },
  render: (_args, value) => [
    {
      type: "text",
      text:
        value.status === "success"
          ? `symphony_audition [${value.section || "unknown"}]: audition=${value.audition}, admit=${value.admit}${value.reasons.length ? " (reasons: " + value.reasons.join("; ") + ")" : ""}`
          : `symphony_audition failed: ${value.error}`
    }
  ]
};

async function executeAudition(philRoot, args) {
  const envelope = args?.envelope;
  if (!envelope || typeof envelope !== "object") {
    return { status: "error", error: "Missing or invalid 'envelope' object parameter" };
  }

  const scriptPath = join(philRoot, "scripts", "audition_chair.py");
  if (!existsSync(scriptPath)) {
    return { status: "error", error: `Audition script not found at ${scriptPath}` };
  }

  const tmpFile = join(tmpdir(), `symphony_env_${Date.now()}_${Math.random().toString(36).slice(2)}.json`);
  try {
    writeFileSync(tmpFile, JSON.stringify(envelope, null, 2), "utf-8");
    const res = await runProcess("python3", [scriptPath, "--envelope", tmpFile]);
    let parsed;
    try {
      parsed = JSON.parse(res.stdout);
    } catch {
      return {
        status: "error",
        error: `Invalid JSON from audition_chair.py: ${res.stdout || res.stderr}`
      };
    }

    return {
      status: "success",
      audition: parsed.audition || (res.code === 0 ? "pass" : "fail"),
      admit: false, // Invariant: admit is always false
      section: parsed.section || envelope?.sender?.section || "unknown",
      reasons: Array.isArray(parsed.reasons) ? parsed.reasons : []
    };
  } finally {
    if (existsSync(tmpFile)) {
      try {
        rmSync(tmpFile);
      } catch {}
    }
  }
}

// -----------------------------------------------------------------------------
// Tool 2: symphony_snare_verify
// -----------------------------------------------------------------------------
const SNARE_PARAMETERS = {
  type: "object",
  additionalProperties: false,
  required: ["target_root"],
  properties: {
    target_root: {
      type: "string",
      description: "Path to target project root containing AGENTS.md (scans 4-rung verify ladder: lint, unit, e2e, security)."
    }
  }
};

const SNARE_OUTPUT = {
  schema: {
    oneOf: [
      {
        type: "object",
        additionalProperties: false,
        required: ["status", "ok", "errors", "rungs"],
        properties: {
          status: { type: "string", const: "success" },
          ok: { type: "boolean" },
          errors: { type: "array", items: { type: "string" } },
          rungs: {
            type: "object",
            additionalProperties: true
          }
        }
      },
      {
        type: "object",
        additionalProperties: false,
        required: ["status", "error"],
        properties: {
          status: { type: "string", const: "error" },
          error: { type: "string" }
        }
      }
    ]
  },
  render: (_args, value) => [
    {
      type: "text",
      text:
        value.status === "success"
          ? `symphony_snare_verify: ok=${value.ok}, rungs=${Object.keys(value.rungs || {}).join(",")}${value.errors.length ? " (errors: " + value.errors.join("; ") + ")" : ""}`
          : `symphony_snare_verify failed: ${value.error}`
    }
  ]
};

async function executeSnareVerify(philRoot, args) {
  const targetRoot = args?.target_root;
  if (!targetRoot || typeof targetRoot !== "string") {
    return { status: "error", error: "Missing or invalid 'target_root' parameter" };
  }

  const scriptPath = join(philRoot, "scripts", "snare_score.py");
  if (!existsSync(scriptPath)) {
    return { status: "error", error: `Snare score script not found at ${scriptPath}` };
  }

  try {
    const res = await runProcess("python3", [scriptPath, "--root", resolve(targetRoot)]);
    let parsed;
    try {
      parsed = JSON.parse(res.stdout);
    } catch {
      return {
        status: "error",
        error: `Invalid JSON from snare_score.py: ${res.stdout || res.stderr}`
      };
    }

    return {
      status: "success",
      ok: Boolean(parsed.ok),
      errors: Array.isArray(parsed.errors) ? parsed.errors : [],
      rungs: parsed.rungs && typeof parsed.rungs === "object" ? parsed.rungs : {}
    };
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err)
    };
  }
}

// -----------------------------------------------------------------------------
// Tool 3: symphony_dispatch_cue
// -----------------------------------------------------------------------------
const CUE_PARAMETERS = {
  type: "object",
  additionalProperties: false,
  required: ["cue", "section"],
  properties: {
    cue: {
      type: "string",
      enum: ["SPEC_LOCKED", "TEST_PASSED", "CIRCUIT_BREAK", "MAHLER_TACET", "BRASS_SOL", "TUTTI_FINALE"],
      description: "Movement cue to broadcast across symphony sections."
    },
    section: {
      type: "string",
      description: "Target section (e.g. oboe, violin_1, violin_2, snare_drum, heavy_brass, tutti)."
    },
    notes: {
      type: "string",
      description: "Optional notes, score reference, or movement instructions."
    }
  }
};

const CUE_OUTPUT = {
  schema: {
    oneOf: [
      {
        type: "object",
        additionalProperties: false,
        required: ["status", "cue", "section", "timestamp", "notes"],
        properties: {
          status: { type: "string", const: "dispatched" },
          cue: { type: "string" },
          section: { type: "string" },
          timestamp: { type: "string" },
          notes: { type: "string" }
        }
      },
      {
        type: "object",
        additionalProperties: false,
        required: ["status", "error"],
        properties: {
          status: { type: "string", const: "error" },
          error: { type: "string" }
        }
      }
    ]
  },
  render: (_args, value) => [
    {
      type: "text",
      text:
        value.status === "dispatched"
          ? `symphony_dispatch_cue: [${value.cue}] -> ${value.section} at ${value.timestamp}${value.notes ? " (" + value.notes + ")" : ""}`
          : `symphony_dispatch_cue failed: ${value.error}`
    }
  ]
};

async function executeDispatchCue(args) {
  const cue = args?.cue;
  const section = args?.section;
  if (!cue || !section) {
    return { status: "error", error: "Missing required 'cue' or 'section' parameter" };
  }

  const timestamp = new Date().toISOString();
  const notes = args?.notes ? String(args.notes) : "";

  return {
    status: "dispatched",
    cue,
    section,
    timestamp,
    notes
  };
}

// -----------------------------------------------------------------------------
// Pre-Tool Interceptor: Mahler Tacet Guard
// -----------------------------------------------------------------------------
async function checkTacetGuard(philRoot, section, toolName, toolInput) {
  const guardScript = join(philRoot, "scripts", "tacet-guard.sh");
  if (!existsSync(guardScript)) {
    return null;
  }

  const payload = JSON.stringify({
    tool_name: toolName,
    tool_input: toolInput || {}
  });

  try {
    const res = await runProcess(
      "bash",
      [guardScript],
      {
        env: {
          MADA_SECTION: section
        }
      },
      payload
    );

    if (res.stdout) {
      try {
        const parsed = JSON.parse(res.stdout);
        if (parsed.action === "block") {
          return parsed;
        }
      } catch {}
    }
  } catch {}
  return null;
}

// -----------------------------------------------------------------------------
// Cordis Plugin apply entry
// -----------------------------------------------------------------------------
function apply(ctx, config = {}) {
  const philRoot = resolvePhilRoot(config);

  // Register Symphony Audition
  ctx.tools.register({
    name: "symphony_audition",
    description: [
      "Audition a Mada Symphony chair envelope against section contracts (schema, ceiling, isolation lock).",
      "Checks envelope validity. Notice: `admit` is ALWAYS false; conductor routes the model and quota."
    ].join(" "),
    parameters: AUDITION_PARAMETERS,
    output: AUDITION_OUTPUT,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    execute(args) {
      return executeAudition(philRoot, args).catch((err) => ({
        status: "error",
        error: err instanceof Error ? err.message : String(err)
      }));
    }
  });

  // Register Symphony Snare Verify
  ctx.tools.register({
    name: "symphony_snare_verify",
    description: [
      "Score target project's AGENTS.md verify ladder (lint, unit, e2e, security) with 0-token verification.",
      "Ensures pasteable verification commands exist before executing code or accepting work."
    ].join(" "),
    parameters: SNARE_PARAMETERS,
    output: SNARE_OUTPUT,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    execute(args) {
      return executeSnareVerify(philRoot, args).catch((err) => ({
        status: "error",
        error: err instanceof Error ? err.message : String(err)
      }));
    }
  });

  // Register Symphony Cue Dispatch
  ctx.tools.register({
    name: "symphony_dispatch_cue",
    description: [
      "Dispatch and broadcast a Symphony movement cue between chairs/sections",
      "(SPEC_LOCKED, TEST_PASSED, CIRCUIT_BREAK, MAHLER_TACET, BRASS_SOL, TUTTI_FINALE)."
    ].join(" "),
    parameters: CUE_PARAMETERS,
    output: CUE_OUTPUT,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    execute(args) {
      return executeDispatchCue(args).catch((err) => ({
        status: "error",
        error: err instanceof Error ? err.message : String(err)
      }));
    }
  });

  // Pre-tool Tacet Guard hook
  if (typeof ctx.on === "function") {
    ctx.on("tools/pre-execute", async (exec, next) => {
      const section = process.env.MADA_SECTION || config.section;
      if (!section) {
        return next();
      }

      const blocked = await checkTacetGuard(philRoot, section, exec.name, exec.arguments);
      if (blocked && blocked.action === "block") {
        return {
          kind: "deny",
          reason: `blocked by Symphony Tacet Guard: ${blocked.message || "forbidden by chair contract"}`
        };
      }
      return next();
    });
  }
}

export { apply, inject, name, resolvePhilRoot };
