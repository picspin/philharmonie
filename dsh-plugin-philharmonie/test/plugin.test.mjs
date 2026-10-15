import assert from "node:assert/strict";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { apply, name, resolvePhilRoot } from "../index.js";

// Mock Cordis Context
function createMockContext() {
  const tools = new Map();
  const listeners = new Map();

  return {
    tools: {
      register(def) {
        tools.set(def.name, def);
      },
      get(toolName) {
        return tools.get(toolName);
      },
      has(toolName) {
        return tools.has(toolName);
      }
    },
    on(event, handler) {
      if (!listeners.has(event)) {
        listeners.set(event, []);
      }
      listeners.get(event).push(handler);
    },
    async emit(event, ...args) {
      const handlers = listeners.get(event) || [];
      for (const h of handlers) {
        return await h(...args);
      }
    }
  };
}

test("plugin metadata and root resolution", () => {
  assert.equal(name, "dsh-plugin-philharmonie");
  const root = resolvePhilRoot();
  assert.ok(root && root.length > 0, "Philharmonie root should resolve");
});

test("plugin registers expected tools", () => {
  const ctx = createMockContext();
  apply(ctx);

  assert.ok(ctx.tools.has("symphony_audition"), "symphony_audition registered");
  assert.ok(ctx.tools.has("symphony_snare_verify"), "symphony_snare_verify registered");
  assert.ok(ctx.tools.has("symphony_dispatch_cue"), "symphony_dispatch_cue registered");
});

test("symphony_dispatch_cue formats movement cues", async () => {
  const ctx = createMockContext();
  apply(ctx);

  const tool = ctx.tools.get("symphony_dispatch_cue");
  const res = await tool.execute({
    cue: "SPEC_LOCKED",
    section: "violin_1",
    notes: "Oboe contract sealed; begin Variation I"
  });

  assert.equal(res.status, "dispatched");
  assert.equal(res.cue, "SPEC_LOCKED");
  assert.equal(res.section, "violin_1");
  assert.ok(res.timestamp);
  assert.match(res.notes, /Oboe contract sealed/);

  const rendered = tool.output.render({}, res);
  assert.match(rendered[0].text, /symphony_dispatch_cue: \[SPEC_LOCKED\] -> violin_1/);
});

test("symphony_audition enforces admit=false and schema validation", async () => {
  const ctx = createMockContext();
  apply(ctx);

  const tool = ctx.tools.get("symphony_audition");

  // Incomplete envelope: must fail with reasons and admit=false
  const failRes = await tool.execute({
    envelope: {
      sender: { section: "violin_1" }
    }
  });

  assert.equal(failRes.status, "success");
  assert.equal(failRes.audition, "fail");
  assert.equal(failRes.admit, false);
  assert.ok(failRes.reasons.length > 0);

  const rendered = tool.output.render({}, failRes);
  assert.match(rendered[0].text, /audition=fail, admit=false/);
});

test("symphony_snare_verify checks 4-rung verification ladder", async () => {
  const ctx = createMockContext();
  apply(ctx);

  const tool = ctx.tools.get("symphony_snare_verify");

  // Temp dir without AGENTS.md
  const emptyDir = join(tmpdir(), `test_snare_empty_${Date.now()}`);
  mkdirSync(emptyDir, { recursive: true });

  try {
    const res = await tool.execute({ target_root: emptyDir });
    assert.equal(res.status, "success");
    assert.equal(res.ok, false);
    assert.ok(res.errors.length > 0);
  } finally {
    rmSync(emptyDir, { recursive: true, force: true });
  }

  // Temp dir with valid 4-rung AGENTS.md
  const validDir = join(tmpdir(), `test_snare_valid_${Date.now()}`);
  mkdirSync(validDir, { recursive: true });
  const validAgentsMd = `# AGENTS.md\n\n## Verification\n- lint: \`npm run lint\`\n- unit: \`npm test\`\n- e2e: \`npm run e2e\`\n- security: \`npm audit\`\n`;
  writeFileSync(join(validDir, "AGENTS.md"), validAgentsMd, "utf-8");

  try {
    const res = await tool.execute({ target_root: validDir });
    assert.equal(res.status, "success");
    assert.equal(res.ok, true);
    assert.equal(res.errors.length, 0);
    assert.ok(res.rungs.lint);
    assert.ok(res.rungs.unit);
    assert.ok(res.rungs.e2e);
    assert.ok(res.rungs.security);
  } finally {
    rmSync(validDir, { recursive: true, force: true });
  }
});

test("tools/pre-execute Tacet guard blocks forbidden write operations", async () => {
  const ctx = createMockContext();
  apply(ctx);

  const prevSection = process.env.MADA_SECTION;
  process.env.MADA_SECTION = "violin_1";

  try {
    let nextCalled = false;
    const next = () => {
      nextCalled = true;
      return "ALLOW";
    };

    // Attempting to write SPEC.md should be blocked
    const denyRes = await ctx.emit(
      "tools/pre-execute",
      {
        name: "write_file",
        arguments: { path: "SPEC.md", content: "forbidden overwrite" }
      },
      next
    );

    assert.equal(denyRes.kind, "deny");
    assert.match(denyRes.reason, /blocked by Symphony Tacet Guard/);
    assert.equal(nextCalled, false);

    // Reading SPEC.md should be allowed
    const allowRes = await ctx.emit(
      "tools/pre-execute",
      {
        name: "read_file",
        arguments: { path: "SPEC.md" }
      },
      next
    );

    assert.equal(allowRes, "ALLOW");
    assert.equal(nextCalled, true);
  } finally {
    if (prevSection === undefined) {
      delete process.env.MADA_SECTION;
    } else {
      process.env.MADA_SECTION = prevSection;
    }
  }
});
