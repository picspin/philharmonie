# Composite score compiler and durable Bach loops

Version 2 is an executable authoring format, separate from the existing v1
`score_composer.py` timeline and the non-executable Concert Hall RFC examples.
It compiles an explicit program; it does not ask a model to invent a workflow.
Python 3.10+, POSIX, and the existing jsonschema dependency are sufficient.

## Run the local example

From the repository root, create a disposable task checkout and keep state outside it:

```bash
cp -R examples/bach-search /tmp/philharmonie-search
python3 scripts/compile_score.py --program /tmp/philharmonie-search/program.json --output /tmp/search-plan.json
python3 scripts/loop_runner.py run --plan /tmp/search-plan.json --root /tmp/philharmonie-search --state /tmp/search-state
python3 scripts/loop_runner.py status --state /tmp/search-state
python3 scripts/loop_runner.py resume --state /tmp/search-state
```

Use fresh destination paths for another run. The example executes real search
implementations against a locked `SPEC.py`. Comparisons fall from 1024 to 64,
then an invalid implementation fails the contract, then binary search reaches
11 comparisons. Repeating the best yields a discard. No LLM/API is called;
this is a deterministic fixture demonstrating the same transaction machinery
that can wrap a model-authored patch, tests, and a research evaluator.

## Compose by task

A program contains `task`, `score` (id/revision/chapters), `chairs`,
`ground_bass`, `budget.max_wall_sec`, and optional `parallelism` (default 4).
Task and chapter context describe deployment, architecture and taste and are
included in agent briefs. They express intent, not a claim that architecture
fitness has been verified. A new source or routing inventory produces a new
sealed plan; editing the compiled plan is refused.

Chapters have ids, names, forms, `depends_on`, and a recursive `body`:

- `movement`: one named Chair, argv **or** prompt, declared `writes`/`outputs`,
  positive timeout, optional explicit `max_attempts` (default 1).
- `sequence`: ordered children.
- `parallel`: disjoint branch manifests, bounded by the global launch semaphore.
- `loop`: baseline, candidate body, exact editable file paths, metric path/key,
  direction (`min`/`max`) and limits. Iterations are 1-based. Dotted metric keys
  address nested JSON objects; literal dots in object keys are unsupported.

Chapter dependencies are topologically sorted, then chapters execute serially.
Parallelism is explicit inside a chapter. Missing dependencies/cycles, duplicate
sibling ids, unsafe paths and overlapping parallel writes fail compilation.
Fugue requires a parallel group; Bach/Brahms variation requires a bounded loop.
Forms are structural constraints, not automatic agents or extra privileges.
Mix forms across chapters and nest loops (depth <=16, total nodes <=1024).
Inner edits must be within the outer transaction; include inner metric files in
outer `edit_paths` when those files also need rollback.

Chair ids are independent of Section ids. Agent Chairs resolve their Section's
capability tier against `--registry` using the existing fail-closed resolver;
optional per-Chair model pins must be compatible. The compiled plan freezes that
inventory. `--draft` can expose unresolved bindings (exit 2); runners refuse
unready plans. No environment model guessing occurs at runtime. Agent spawns go
through the existing audition and supervised hall adapter, never `--force`.
Brass still needs an explicit cue. Pi model pinning and unsupported worktree
halls are rejected. `admit` remains false in every plan/status.

`executor: command` is a trusted local argv program, requires terminal capability
and shared isolation, and has no model/hall/tier fields. It is useful for Snare
verification and offline fixtures. It is **not** a tool-ceiling sandbox. The runner
uses argv arrays and never invokes a shell implicitly. Commands must not launch
daemons; the worker kills the job process group when its leader exits.

Parallel shared agent writers are refused. Native hall worktrees are supported
outside loop transactions, with outputs explicitly exported to `PHIL_ROOT` by
the agent. Transactional loops currently require shared execution and declared
file rollback; they do not pretend to recover opaque hall-native worktrees.
Manifests are regular relative files, not directories/globs/symlinks. They are a
rollback boundary, not an OS sandbox. Use a disposable checkout for untrusted
or broad file edits. Undeclared edits, network effects, database mutations,
processes that escape their process group and remote model billing are not
transactionally undone.

## Bach progression

The baseline must freshly write a finite numeric metric and leave candidate seed
files unchanged. Each iteration starts from the retained best, removes the old
metric, runs its entire candidate body, then verifies the fresh metric. A body can
sequence an agent mutation, Snare lint/unit/security checks, a critic and an
experiment. All must succeed before the metric can win. The score author owns
the evaluator's scientific validity and benchmark design.

Workers receive `PHIL_ROOT`, `PHIL_STATE`, `PHIL_RUN_ID`, `PHIL_ITERATION`,
`PHIL_ITERATION_PATH` and `PHIL_BEST_METRIC`. Agent briefs carry the same feedback.
This supports progressive strategies in one bounded loop, and nested coarse /
fine loops. No automatic self-modification of the active coordinator is allowed:
its source, adapters and schemas are fingerprinted; resume requires the pinned
runtime. Point the task root at a separate harness checkout to improve it.

Strict improvement is `keep`; an equal/worse valid experiment is `discard`.
Nonzero exit, timeout, missing/bool/NaN/infinite metric or missing declared output
is `crash`. A crash never becomes score zero. Decisions, best file bytes/modes,
metric and counters are committed together in SQLite before settling the files.
Restart during settling restores the committed best without rejudging/replaying.
`max_iterations`, loop wall time and optional no-improvement limits finish the
loop with an explicit reason. Consecutive-failure limits fail the run. Global
wall budget exhaustion also fails. Wall times include pauses and downtime.
Protected ground-bass drift is fatal, even when the metric improves. Ordinary
file drift is restored where safe; symlink substitution refuses unsafe recovery.

## Recovery and controls

State is an owner-only directory containing a SQLite WAL journal, event history,
job specs, stdout/stderr and atomic, fsynced receipts. A single coordinator uses a
POSIX file lock; each worker survives coordinator death, enforces timeout and
writes a receipt. Completed movements are not replayed. Output bytes are
recorded at completion; subsequent movements may intentionally replace them.
The task root and state are single-run resources: do not edit them externally or
run another journal against the same root concurrently.

```bash
python3 scripts/loop_runner.py pause --state /tmp/search-state
python3 scripts/loop_runner.py resume --state /tmp/search-state
python3 scripts/loop_runner.py cancel --state /tmp/search-state
```

Pause finishes in-flight work before stopping further dispatch. Cancel sends
markers to workers and restores active loops once job completion is known. If
the coordinator is dead, run resume to consume receipts/finalize cancellation;
resume preserves a pending cancel. Status reports `needs_reconciliation` if a
launch intent has no receipt. It **never** infers completion from a PID or reruns
that attempt. Wait for a surviving worker and resume again. If no receipt can be
recovered, independently verify the job and descendants have stopped, then:

```bash
python3 scripts/loop_runner.py reconcile --state /tmp/search-state --address CHAPTER/NODE --confirm-stopped --note 'Evidence that this attempt has stopped'
python3 scripts/loop_runner.py resume --state /tmp/search-state
```

This explicit operator attestation records a failed attempt, not success. Only
an explicitly configured retry allowance can retry it. There is no exactly-once
guarantee for external side effects: uncertainty blocks instead of guessing.
Terminal completed/failed/cancelled runs are immutable; start a new run to retry
a terminal score. Exit 0 means completed (or successful control/status request);
uncompleted run/resume exits 2. Status JSON has ordered events suitable for a
future Concert Hall adapter; this change does not claim DSH UI integration.
