# dsh-plugin-philharmonie

DeepSeek Harness (dsh) native Cordis plugin for **Mada Symphony (Philharmonie)** orchestration.

English | [中文](#中文说明)

---

## Overview

`dsh-plugin-philharmonie` bridges Mada Symphony's classical orchestration contracts into the DeepSeek Harness runtime. It equips DSH agents with section auditing, 0-token verification latches, movement cue dispatching, and process-level Tacet protection.

### Features

1. **`symphony_audition`**:
   - Audits a chair envelope against section contracts (`templates/envelope.json`, `templates/section-contract.json`).
   - Checks schema compliance, allowed toolset ceilings, and isolation locks.
   - **Fail-closed invariant**: `admit` is **always `false`**. Conductor retains routing and quota authority.

2. **`symphony_snare_verify`**:
   - 0-token verification latch scanning target project `AGENTS.md`.
   - Requires pasteable commands for all four Snare rungs: `lint`, `unit`, `e2e`, `security`.
   - Fails closed before code execution or PR acceptance.

3. **`symphony_dispatch_cue`**:
   - Broadcasts structured movement signals across sections (`SPEC_LOCKED`, `TEST_PASSED`, `CIRCUIT_BREAK`, `MAHLER_TACET`, `BRASS_SOL`, `TUTTI_FINALE`).
   - Emits structured timestamped records for traceability.

4. **Mahler Tacet Guard (`tools/pre-execute` Interceptor)**:
   - Hooks into DSH's tool execution lifecycle.
   - When `MADA_SECTION` is active, intercepts tool invocations before execution.
   - Denies unauthorized modifications to ground-bass paths (e.g. `SPEC.md`, `contracts`, `templates`) with `{ kind: "deny", reason: "..." }`.

---

## Mounting in DeepSeek Harness

### 1. In `cordis.patch.yml`

Add an insert entry to your profile's `cordis.patch.yml` (e.g. `~/.dsh/profiles/headless/cordis.patch.yml`):

```yaml
- insert:
    - id: philharmonie
      name: file:///home/hilbert/philharmonie/dsh-plugin-philharmonie/index.js
      inject:
        - tools
      config:
        philRoot: /home/hilbert/philharmonie
```

### 2. Ephemeral Overlay via CLI

Boot any profile with an extra patch overlay:

```bash
dsh headless --patch /path/to/philharmonie/dsh-plugin-philharmonie/cordis.patch.yml "run symphony verification"
```

---

## Testing

Run unit tests via Node test runner:

```bash
node --test test/plugin.test.mjs
```

---

<a id="中文说明"></a>
## 中文说明

`dsh-plugin-philharmonie` 是专为 DeepSeek Harness (dsh) 打造的原生 Cordis 插件，用于将 Mada Symphony 交响乐团多 Agent 编排契约与断路闸门接入 DSH 运行时。

### 导出工具与拦截器

1. **`symphony_audition`（席位入团审查）**：
   - 审查 Envelope 契约、工具集上限（Ceiling）及隔离锁。
   - **核心契约**：`admit` 恒为 `false`，过谱不等于入团，路由与配额由指挥掌控。
2. **`symphony_snare_verify`（小军鼓 0-Token 验证阶梯）**：
   - 静态扫描目标项目 `AGENTS.md`，检查 `lint`、`unit`、`e2e`、`security` 四级验证命令。
3. **`symphony_dispatch_cue`（乐章信号广播）**：
   - 在各席位与会话间广播严格的乐章阶段信号（如 `SPEC_LOCKED` 契约锁定、`TEST_PASSED` 测试通过）。
4. **Mahler Tacet 守卫（`tools/pre-execute` 拦截器）**：
   - 进程级静音守卫，当指定席位（如 `violin_1`）试图篡改底座契约（`SPEC.md`）时直接熔断拦截。
