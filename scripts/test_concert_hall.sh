#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import copy
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv.pop())
sys.path.insert(0, str(ROOT / 'scripts'))
import concert_hall as hall
import score_composer as composer
import spawn_chair

class HallTests(unittest.TestCase):
    def setUp(self):
        self.score = composer.compose_score('测试 concert hall', score_id='score-test')
        self.now = datetime(2026, 10, 18, 0, 1, tzinfo=timezone.utc)

    def event(self, kind='spawn', movement=1, section='oboe', execution='a', second=0, **extra):
        return dict(schema_version=1, event=kind, score_id='score-test', run_id='run-test',
                    execution_id=execution, movement_index=movement, section=section,
                    model='test-model', isolation='shared', ts=f'2026-10-18T00:00:{second:02d}+00:00', **extra)

    def snap(self, events=()):
        return hall.snapshot(self.score, list(events), 'run-test', now=self.now)

    def test_plan_has_no_invented_execution(self):
        data = self.snap()
        self.assertEqual(data['state'], 'planned')
        self.assertIsNone(data['tokens'])
        self.assertEqual(data['movements'][0]['chairs'][0]['state'], 'unresolved')
        self.assertEqual(data['movements'][1]['state'], 'waiting')
        self.assertFalse(data['admit'])

    def test_started_is_playing(self):
        data = self.snap([self.event()])
        self.assertEqual(data['state'], 'playing')
        self.assertEqual(data['movements'][0]['chairs'][0]['elapsed_sec'], 60)

    def test_exit_success_and_dependency(self):
        data = self.snap([self.event(), self.event('exit', second=5, status='ok', exit_code=0)])
        self.assertEqual(data['movements'][0]['state'], 'success')
        self.assertEqual(data['focus'], 2)
        self.assertEqual(data['movements'][1]['state'], 'unresolved')

    def test_failed_and_timeout(self):
        for status, code in [('error', 1), ('timeout', 124)]:
            data = self.snap([self.event(), self.event('exit', second=5, status=status, exit_code=code)])
            self.assertEqual(data['state'], 'failed')
            self.assertNotEqual(data['movements'][0]['state'], 'success')

    def test_other_run_and_score_are_excluded(self):
        event = self.event(); event['run_id'] = 'old-run'
        other = self.event(); other['score_id'] = 'old-score'
        data = self.snap([event, other])
        self.assertEqual(data['state'], 'planned')
        self.assertEqual(data['ignored_events'], 2)

    def test_orphan_exit_is_degraded(self):
        self.assertFalse(self.snap([self.event('exit', status='ok', exit_code=0)])['ok'])

    def test_exit_must_match_spawn(self):
        end = self.event('exit', status='ok', exit_code=0); end['model'] = 'changed'
        self.assertFalse(self.snap([self.event(), end])['ok'])

    def test_false_success_is_rejected(self):
        self.assertFalse(self.snap([self.event(), self.event('exit', status='ok', exit_code=1)])['ok'])

    def test_tacet_and_isolation_violations(self):
        self.assertFalse(self.snap([self.event(section='violin_1')])['ok'])
        event = self.event(); event['isolation'] = 'worktree'
        self.assertFalse(self.snap([event])['ok'])

    def test_duplicate_replay_is_idempotent(self):
        event = self.event()
        self.assertTrue(self.snap([event, copy.deepcopy(event)])['ok'])

    def test_conflicting_duplicate_is_rejected(self):
        event = self.event(); other = self.event(second=1)
        self.assertFalse(self.snap([event, other])['ok'])

    def test_retry_and_late_exit_do_not_replace_new_attempt(self):
        events = [self.event(), self.event('spawn', execution='b', second=10),
                  self.event('exit', second=5, status='error', exit_code=1)]
        data = self.snap(events)
        self.assertTrue(data['ok'])
        self.assertEqual(data['movements'][0]['chairs'][0]['state'], 'playing')

    def test_negative_elapsed_and_naive_dates(self):
        self.assertFalse(self.snap([self.event(second=5), self.event('exit', second=1, status='ok', exit_code=0)])['ok'])
        event = self.event(); event['ts'] = '2026-10-18T00:00:00'
        self.assertFalse(self.snap([event])['ok'])

    def test_overlapping_attempts_are_not_hidden(self):
        self.assertFalse(self.snap([self.event(), self.event(execution='b', second=10)])['ok'])

    def test_dependency_time_violation(self):
        event = self.event(movement=2, section='violin_1', execution='b', second=1)
        event['isolation'] = 'worktree'
        data = self.snap([self.event(), event, self.event('exit', second=5, status='ok', exit_code=0)])
        self.assertFalse(data['ok'])

    def test_unknown_token_totals_even_after_success(self):
        data = self.snap([self.event(), self.event('exit', second=5, status='ok', exit_code=0)])
        self.assertIsNone(data['tokens'])
        self.assertIsNone(data['movements'][0]['chairs'][0]['tokens'])

    def test_shell_observation_cannot_be_an_llm(self):
        self.assertFalse(self.snap([self.event(movement=4, section='snare_drum')])['ok'])

    def test_unknown_schema_and_fields(self):
        event = self.event(); event['schema_version'] = 2
        self.assertFalse(self.snap([event])['ok'])
        event = self.event(); event['movement_index'] = True
        self.assertFalse(self.snap([event])['ok'])

    def test_legacy_logs_are_visible_as_unattributed(self):
        data = self.snap([{'event': 'spawn', 'ts': 'old'}])
        self.assertEqual(data['unattributed_events'], 1)
        self.assertEqual(data['state'], 'planned')

    def test_snare_inventory_is_not_test_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath('AGENTS.md').write_text('\n'.join(f'- {r}: `echo {r}`' for r in ['lint','unit','e2e','security']))
            data = hall.snapshot(self.score, [], 'run-test', root=root, now=self.now)
            self.assertEqual(data['snare']['configured'], 4)
            self.assertIsNone(data['snare']['passed'])

    def test_truncated_log_does_not_claim_clean_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            path.write_text(json.dumps(self.event()) + '\n{"event":')
            rows, errors = hall.read_events(path)
            self.assertEqual(len(rows), 1)
            self.assertTrue(errors)

    def test_render_width_and_terminal_injection(self):
        self.score['summary'] = '恶意\x1b[2J\ntext'
        data = self.snap([self.event()])
        for width in (40, 80, 120):
            output = hall.render(data, width=width)
            self.assertNotIn('\x1b', output)
            self.assertTrue(all(hall.cell_width(line) <= width for line in output.splitlines()))
            self.assertEqual(len(hall.render(data, width=width, collapsed=True).splitlines()), 1)

    def test_cli_json_and_non_tty_watch(self):
        with tempfile.TemporaryDirectory() as directory:
            score = Path(directory) / 'score.json'; score.write_text(json.dumps(self.score))
            cmd = [sys.executable, str(ROOT / 'scripts/concert_hall.py'), '--score', str(score)]
            result = subprocess.run(cmd + ['--json'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['state'], 'planned')
            result = subprocess.run(cmd + ['--watch', '--frames', '2', '--interval', '0.2'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('\x1b', result.stdout)
            self.assertEqual(subprocess.run(cmd + ['--events', 'missing'], capture_output=True).returncode, 2)

    def test_supervise_produces_correlated_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); events = root / 'events.jsonl'
            command = [sys.executable, str(ROOT / 'scripts/spawn_chair.py'), '--envelope', str(ROOT / 'examples/violin-2.json'),
                       '--supervise', '--jsonl', str(events), '--hall', 'hermes', '--score-id', 'score-test',
                       '--movement-index', '3', '--run-id', 'run-test']
            env = dict(os.environ, MADA_HERMES='/bin/true')
            result = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows, errors = hall.read_events(events)
            self.assertFalse(errors)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['execution_id'], rows[1]['execution_id'])
            self.assertEqual(rows[0]['section'], 'violin_2')
            self.assertEqual(rows[0]['movement_index'], 3)
            self.assertEqual(rows[0]['run_id'], 'run-test')
            for key in ('--score-id', '--movement-index', '--run-id'):
                index = command.index(key)
                bad = command[:index] + command[index+2:]
                self.assertEqual(subprocess.run(bad, capture_output=True, env=env).returncode, 2)
            ticket = root / 'ticket.json'
            ticket.write_text(json.dumps(dict(run_id='another-run', issued_by='conductor',
                expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())))
            self.assertEqual(subprocess.run(command + ['--ticket', str(ticket)], capture_output=True, env=env).returncode, 2)

    def test_full_supervised_flow_to_snapshot(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            path = Path(directory) / 'events.jsonl'
            for movement in self.score['movements']:
                section = movement['lead_section']
                spawn_chair.supervise([sys.executable, '-c', 'pass'], dict(os.environ), hall='test', cap={},
                    audition='pass', timeout_sec=2, jsonl_path=str(path), run_id='run-test', observation={
                        'score_id':'score-test', 'movement_index':movement['index'], 'section':section,
                        'model':'local-bash' if section == 'snare_drum' else 'test-model',
                        'isolation':movement['isolation']})
            rows, errors = hall.read_events(path)
            data = hall.snapshot(self.score, rows, 'run-test', input_errors=errors)
            self.assertTrue(data['ok'], data['errors'])
            self.assertEqual(data['state'], 'complete')
            self.assertIsNone(data['tokens'])
            self.assertIsNone(data['snare']['passed'])
            self.assertEqual(data['movements'][-1]['chairs'][0]['tokens'], 0)

    def test_spawn_failure_closes_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
                spawn_chair.supervise(['/does-not-exist'], {}, hall='test', cap={}, audition='pass',
                                       timeout_sec=1, jsonl_path=str(path), observation={
                    'score_id':'score-test','movement_index':1,'section':'oboe','model':'test-model',
                    'isolation':'shared'}, run_id='run-test')
            rows, _ = hall.read_events(path)
            self.assertEqual(rows[-1]['event'], 'exit')
            self.assertEqual(hall.snapshot(self.score, rows, 'run-test')['state'], 'failed')

unittest.main(verbosity=2)
PY
