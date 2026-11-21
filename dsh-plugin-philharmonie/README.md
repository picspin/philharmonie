# DSH Concert Hall adapter

This adapter contributes only the supported `main`, `sidebar.panellist` and
`conversation.session.header.actions` slots. It does not replace the native
conversation header or claim a native full-width Ribbon slot. The main panel
embeds the independent workbench; it owns that panel's collapsible graph.

The installable package is now the **repository root**, not this subdirectory.
The tarball includes Python scripts, schemas and web assets. No pre-existing
`/home/.../philharmonie` checkout or global fallback search is required.

## Install into an isolated profile

Use Node >=24.9 and DSH 0.2.2-alpha.2 (the source contract reviewed here is
`deepseek-ai/deepseek-harness@ce7073d51254c26cd63b22a60835b8f948deb447`).
The target machine also needs Python 3.10+ and `jsonschema>=4.18`.

The npm release's dependency ranges currently mix incompatible Cordis alpha
versions: `dsh-app-boot@0.2.2-alpha.2` calls the three-argument `internal/update`
hook, whereas `cordis@4.0.6-alpha.2` supplies two arguments. This breaks native
settings saves (`settings/rejected: next is not a function`), including the
first-run Preview Notice. Our smoke runtime pins the matching alpha.1 core
family in `tests/official-runtime/package.json`; it does not patch runtime code
or pre-acknowledge the notice. Reproduce that isolated runtime with:

```bash
mkdir -p /tmp/phil-dsh-runtime
cp dsh-plugin-philharmonie/tests/official-runtime/package.json /tmp/phil-dsh-runtime/package.json
npm install --prefix /tmp/phil-dsh-runtime --no-audit --no-fund
export PATH="/tmp/phil-dsh-runtime/node_modules/.bin:$PATH"
```

Use this runtime for the installation below when testing this pinned DSH
release. A future DSH upgrade needs its own compatibility validation.

```bash
python3 -m pip install -r requirements.txt
node dsh-plugin-philharmonie/build.mjs --check
npm pack
# Initialize the shipped web profile without launching it:
dsh --profile web --dump-default-config
# Install the packed repository, not ./dsh-plugin-philharmonie:
dsh plugin --profile web add /absolute/path/dsh-plugin-philharmonie-0.1.0.tgz
```

Before booting, create an owner-controlled overlay `philharmonie.local.yml`:

```yaml
- id: philharmonie
  config:
    state: /absolute/path/outside-task/philharmonie-state
    demo: true
```

```bash
dsh --profile web --patch /absolute/path/philharmonie.local.yml --no-open
```

The bundle's placeholder state path deliberately refuses activation until
configured. For a real task, replace the complete config with `root` and `state`
absolute paths (state must be outside the task root), omit `demo`, and optionally
set `registry`, `python`, and `modelBindings`.

```yaml
- id: philharmonie
  config:
    root: /absolute/path/disposable-task
    state: /absolute/path/outside-task/philharmonie-state
    registry: /absolute/path/hall-registry.json
    modelBindings:
      - id: the-model-id-accepted-by-your-hall-cli
        provider: the-dsh-provider-id
        model: the-dsh-model-id
```

Tier support still comes from the explicit hall registry. Each enabled registry
model must have an explicit runtime-id → DSH provider/model binding present in
the active Host catalog. Missing/failed provider discovery disables the candidate.
The host never invents tier support from a name or assumes DSH provider ids are
valid Hermes/Claude/Codex flags. Running agent movements still use the existing
hall adapters; this does not implement a new DSH-native model-pinning runtime.
The offline shell demo needs no model mapping or paid API calls.

## Session and task identity

The global sidebar entry works without a selected Session. The compact action
on a nonblank Session opens the Hall for that Session, preserving DSH's own
selection/title/navigation. In the Hall, explicitly bind the current task to the
Session. Merely opening or switching Sessions does not reassign a task. Multiple
Sessions can refer to the same task id and observe its latest run. Binding and
run identity survive Host/plugin restart in the configured state directory.
The Hall navigation provides “返回 DSH 会话” without changing the native
Session selection, and “全局大厅” to clear the Hall's Session context. The chosen
Hall context is retained per browser tab when session storage is available.
Embedded run history follows the edited task id; choosing a different task
clears its controls instead of exposing another task's run. The standalone
workbench retains its global run history. Unapplied JSON must be applied before
binding. Changing an existing task's summary does not mint a new task identity.
Uncertain runs require the existing CLI reconciliation; there is no blind retry.

Owner-only Fetch routes run through the authenticated DSH Connection carrier.
Browser requests cannot supply task roots, registry paths or Python commands.
Plugin disposal releases routes, panel subscriptions and the bridge; independent
workers and their journal remain recoverable. No cross-origin standalone-server
port or local bearer token is exposed in the iframe.

## Verification

```bash
node dsh-plugin-philharmonie/tests/plugin.test.mjs
node dsh-plugin-philharmonie/build.mjs --check
python3 concert-hall/tests/e2e_workbench.py  # optional Playwright + Chromium
```

The seven local plugin tests cover wire/config validation, explicit Host model
mapping, real persistent bridge/runner decisions, multi-Session binding across
restart, additive slot registration, closure-factory loading and lifecycle routes.
Those focused tests are complemented by the browser workflow: standalone
HTTP/compiler/runner behavior and installation of the actual packed bundle into
an official DSH profile. The official smoke persists two closed offline Session
recordings through DSH's JSONL provider, then uses the native sidebar and header
slots. It verifies binding, real loop execution, per-task history, return to the
unchanged conversation, reload restoration, and anonymous route rejection.
It needs no provider credentials or model calls; it does not verify paid model
execution through a DSH-native agent adapter.

The separate remote Cordis branch adds agent tools and a global Tacet hook, not
this UI. Its source and limitations are reviewed in `design/REMOTE_ALIGNMENT.md`;
those tool/runtime capabilities have not been silently merged or advertised here.

`Concert Hall browser` CI also installs the packed bundle into the pinned official
DSH profile and exercises the real authenticated panel and nonblank-Session
header flow. Artifacts include `dsh-session-header.png` and
`dsh-session-restored.png` alongside desktop/mobile panel screenshots.


## Event instrumentation / 事件音效

The Hall has an opt-in Web Audio sound desk in both standalone and DSH views.
Every newly opened view starts muted; only volume is saved locally. Enable it
with the visible button, choose a volume, and use “试听”. Audio is synthesized
locally with short motifs; no sound files, permissions, model tokens, network
requests, or background music are required. Coding uses triangle-wave tones;
AI4Science uses sine-wave tones. This is synthetic instrumentation, not sampled
acoustic instruments. Sound never changes a verdict or controls execution.

| Event | Motif |
| --- | --- |
| Start / resume | Rising entry |
| Compile ready / hook pass | Two short high notes |
| Unresolved route / hook blocked / reconciliation | Low semitone warning |
| Loop keep / discard / crash | Rising triad / soft descent / low tension |
| Completed / failed / cancelled / paused | Cadence / low descent / falling pair / repeated pair |
| Save or bind a task | Single confirmation note |
| Step completed | Optional short note; disabled by default |

A poll burst plays its highest-priority cue; rapid lower-priority cues are
coalesced. History selection and repeat polls are silent. Hidden views consume
events silently and stop pending notes, so returning does not replay a backlog.
Unsupported or suspended audio leaves all visual controls working.

Hook adapters can append `{type: "hook_result", outcome: "pass" | "fail" |
"blocked"}` to an observed event stream. A frontend integration can instead
announce an already-decided outcome in the Hall document:

```js
document.dispatchEvent(new CustomEvent('philharmonie:cue', {
  detail: { cue: 'hook_pass' } // or hook_block, failure
}));
```

This document-local channel accepts only the predefined motif names; it does
not execute a hook or load URLs. Existing CLI-only hooks are not automatically
streamed into the Hall: their adapter must publish the outcome. Visual status
remains the authoritative, accessible feedback.
