# Concert Hall state service and terminal board

`scripts/concert_hall.py` is the read-only aggregation boundary for future DSH
plugin readers. It supplies JSON snapshots and a compact ASCII/ANSI terminal UI;
there is no extra daemon, web framework or terminal dependency. It never spawns
a chair, advances a score, grants admission or executes target-repo commands.

## Preview without models

```bash
python3 scripts/concert_hall.py --score examples/concert-score.json
python3 scripts/concert_hall.py --score examples/concert-score.json --collapsed

# Synthetic event fixture: intentionally demonstrates a failed implementation.
python3 scripts/concert_hall.py --score examples/concert-score.json \
  --events examples/concert-events.jsonl --run-id demo-concert --width 100

# Inspect YOUR target's four configured commands, without running them.
python3 scripts/concert_hall.py --score score.json --root /path/to/target
```

The expanded view shows movement states, cue/artifact edges, active seats, Tacet
roster, observed/configured model, requested tier, elapsed time, turn ceiling and
breaker readiness. The collapsed view is one line. Width defaults to the terminal
and is clamped to 40..240 cells; CJK width and terminal control characters are
handled before truncation. `--color auto|always|never` controls ANSI decoration.
Non-TTY output uses plain text by default.

## Observe a real supervised chair

Use the existing envelope, audition, hall capabilities and ticket workflow first.
The following adds observation tags to an otherwise normal supervised spawn:

```bash
python3 scripts/spawn_chair.py --envelope chair.json --supervise \
  --jsonl run.jsonl --score-id YOUR_SCORE_ID --movement-index 2 --run-id wave-01

python3 scripts/concert_hall.py --score score.json \
  --events run.jsonl --run-id wave-01 --watch
```

All three tags are required together with `--supervise --jsonl`. A ticket can
supply `run_id`; an explicit `--run-id` must match that ticket. Observation labels
do not create a ticket or relax any admission/tool/isolation constraint. The
observer validates that the supplied seat, isolation and known model assignment
match the score. These labels do not make spawn itself a score scheduler.

`Playing` means a start was observed and no matching exit has been observed. It
does not prove PID liveness: there is no heartbeat in the current transport.
A killed supervisor or missing exit requires inspection; overlapping/unclosed
attempts are degraded rather than silently overwritten. Latest valid retries are
selected by start time, so a late old exit cannot replace a newer attempt.

Ctrl-C stops watch. `--interval 1` controls refresh (0.2..60 seconds); `--frames N`
bounds it. A watched missing/replaced/malformed file displays an error and is read
again on the next refresh. JSON watch produces one snapshot per line. Text watch
clears a real terminal; redirected output stays append-only plain text.

## Event and snapshot integration contract

Spawn/exit events carry `schema_version: 1`, `score_id`, `movement_index` (1-based),
`section`, `model`, `isolation`, `run_id`, unique per-child `execution_id`, and a
timezone-aware ISO `ts`. Exit also carries `status` (`ok|error|timeout`) and integer
`exit_code`. `ok` requires code 0; timeout requires 124. Launch failures emit a
matching error exit, code 127. Extra original supervisor fields remain available.
The result envelope also exposes the execution identity and observation labels.

One run log can contain many chairs and movements. `--run-id` is mandatory when
reading logs: unrelated scores/runs are counted and excluded. Old untagged logs
are counted as unattributed; they cannot be guessed into a seat or movement.
Duplicate replay is idempotent. Contradictory duplicates, orphan/mismatched exits,
Tacet/isolation/model violations, future/naive/reversed timestamps, dependencies
that had not succeeded when execution started, and malformed/truncated lines
set `ok: false`, session state `degraded`, and process exit 2. Valid observations
remain visible alongside errors. Fix or rotate a corrupt log to restore trust.

```bash
python3 scripts/concert_hall.py --score score.json --json
python3 scripts/concert_hall.py --score score.json --events run.jsonl \
  --run-id wave-01 --json --watch
```

Python adapters can import `snapshot(score, events, run_id, root=..., now=...)`
after adding `scripts/` to their import path. `read_events(path)` returns parsed
records plus diagnostics; pass those diagnostics as `input_errors` to snapshot.
`render(snapshot, width=..., collapsed=..., color=...)` consumes the same data.
Snapshots are versioned and JSON-serializable. They include per-movement chairs,
edges, Tacet, routing, focus, elapsed times, Snare inventory and error counters.
`admit` is always false. `validate_score` checks the incoming score first.

LLM token usage and cost remain unknown: the current child result transport does
not expose trustworthy usage accounting. Snare/Cymbals have a local-shell token
ceiling of zero and must identify as `local-bash`. Snare's configured-command
count comes from the target `AGENTS.md` parser; per-rung pass counts remain unknown,
even after a generic successful process exit. External shell runners may supply
correlated spawn/exit records with `model: local-bash`; they must run the actual
verification commands independently. The board never invents successful checks.

DSH Profile export, plugin registration/mount points, native WebUI controls and
per-rung/usage telemetry are the next integration seams; no DSH API is assumed.

Verify: `bash scripts/test_concert_hall.sh` plus the existing spawn/garden suites.
