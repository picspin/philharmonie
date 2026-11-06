# Independent Concert Hall workbench

This experimental local frontend sits on the v2 compiler and durable runner. It
owns its page layout and collapsible Org-Graph; it does not require a DSH Ribbon
slot. No DSH integration or official plugin loading is claimed by this change.

## Start offline

```bash
python3 -m pip install -r requirements.txt
python3 concert-hall/server.py --demo --state /tmp/philharmonie-hall
```

Open **http://127.0.0.1:8787** (use that exact host; `localhost` is deliberately
rejected by the Host check). `--port 0` selects an available port and prints its
URL. The demo copies the existing search example to `STATE/demo-task` only when
that directory is absent. It never writes the repository's example files.

1. Review the task, graph and full JSON command/file manifests.
2. Compile. This validates structure/routing without starting anything.
3. Check the explicit execution authorization box and start the score.
4. Watch run state, `keep / discard / crash`, metrics and ordered events.
5. Pause, resume or cancel from the run panel. Choose historical runs separately
   from the current draft. Saved score library entries do not imply successful runs.

On a fresh demo root, comparisons progress 1024 → 64 → 11; an invalid candidate
crashes and an equal metric is discarded. Later runs start from the retained best,
so they need not reproduce the first run's metrics. Use a fresh state directory
to reset the whole demo; do not edit a live task root.

## Real task

```bash
python3 concert-hall/server.py --root /path/to/disposable-task \
  --state /path/outside-task --registry /path/to/host-models.json
```

The registry uses the existing hall inventory schema, without API keys. Provider
credentials stay in the host environment and are never returned by the API.
Missing/disabled/incompatible models produce an unresolved draft and block start.
The host chooses the task root at server startup; HTTP clients cannot choose
arbitrary execution roots. State must be outside that root. Run one workbench
per task root; the state directory also has an exclusive server lease.

Task choices combine deployment (including serverless) with EDA **event-driven
architecture**, Microkernel and DDD. Architecture/taste context enters agent
briefs; it is not evidence of architectural correctness. The AI4Science family
marks research intent; new research chapters get a baseline/body loop skeleton.
Changing the family does not silently replace existing chapters.

The chapter editor adds/removes/renames chapters and selects a form. Structural
checks remain authoritative: selecting Fugue needs actual parallel children;
selecting a variation needs a bounded loop. The full JSON editor exposes node
order/dependencies, agent prompts, tools, hall/isolation, files, verification
commands and stop limits. Apply JSON validates before replacing the draft.

Starter scores are **templates**: `SPEC.md`, `candidate.py`, `evaluate.py`, unit
commands and manifests must be adapted to the task. Coding templates deliberately
start with an unresolved agent; no placeholder model or silent shell substitute
is invented. A template's test command is not a claim of test coverage.
Compilation and UI consent do not elevate tool ceilings or imply admission.

A source change resets compilation and execution consent. Model changes affect
the next compiled score; the current runner keeps its sealed plan. Pause/cancel
semantics, wall budgets, file rollback and uncertainty handling are those of
[the durable runner](composite-runner.md). Uncertain jobs are shown explicitly;
manual reconciliation remains a CLI operation requiring evidence, not an easy
"retry" button. Stopping the web server does not cancel independent workers;
restart with the same root/state and recover the existing run. External CLI
coordinators still enforce the runner lock even after a server restart.

## Local trust boundary

The server binds only IPv4 loopback, serves a fixed asset allowlist, checks the
exact Host and Origin, and requires a random per-start token for all `/api/`
requests. The token is bootstrapped into the same-origin HTML and never logged.
JSON mutations have a 1 MiB limit. No CORS access, remote authentication, public
hosting, multi-user tenancy or network security boundary is provided. Do not
forward this port to untrusted clients. Trusted argv executors and model agents
retain the runner's documented limitations; declarations are not an OS sandbox.
Do not run two state directories against the same task root concurrently.

## Validation and current limits

```bash
python3 -m unittest discover -s concert-hall/tests -v  # 13 service/handler tests
node concert-hall/tests/composer.test.mjs      # 6 template/compiler tests
node --check concert-hall/web/app.mjs
```

Node >=20 is needed for development tests only. The runtime has no Node/package
or CDN dependency: Python serves static HTML/CSS/ESM and invokes the existing
Python runner. Tests execute real local worker jobs and use the real compiler
for frontend-generated templates. HTTP handler tests use in-memory streams;
they do not claim a live network round trip.

The implementation environment denied both loopback binding and Chromium's
socket setup. **Browser layout, accessibility interaction, and HTTP-to-browser
end-to-end behavior are not verified yet.** The workbench should remain
experimental until those checks can run. The independent monitor draft under
`dsh-plugin-philharmonie` is not included in this implementation.
