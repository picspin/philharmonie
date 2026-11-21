import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_progress import project_run


class RunProgressTest(unittest.TestCase):
    def test_parallel_nested_attempts_and_uncertain_receipt(self):
        example = json.loads((ROOT / 'examples/bach-search/program.json').read_text())
        loop = example['score']['chapters'][0]['body']
        move, verify = loop['body']['children']
        loop['body'] = {'kind': 'parallel', 'children': [move, dict(loop, body=verify)]}
        plan = {'chapters': example['score']['chapters'], 'chairs': example['chairs']}
        a = 'variations/iteration-2/mutate'
        b = 'variations/iteration-2/progressive-search/iteration-1'
        events = [
            {'type': 'step_started', 'address': a, 'execution_id': 'old'},
            {'type': 'step_failed', 'address': a, 'error': 'job failed'},
            {'type': 'step_started', 'address': a, 'execution_id': 'new'},
            {'type': 'step_started', 'address': b, 'execution_id': 'nested'},
        ]
        current = project_run(plan, events, 'running')
        self.assertEqual(current['active'], 2)
        self.assertEqual(current['steps'][1]['iterations'], [2, 1])
        self.assertEqual(current['steps'][1]['rung'], 'unit')
        self.assertEqual(current['timeline'][1]['execution_id'], 'old')
        self.assertIsNone(current['steps'][0]['rung'])
        events.append({'type': 'step_completed', 'address': a, 'execution_id': 'new'})
        uncertain = project_run(plan, events, 'needs_reconciliation')
        self.assertEqual([s['status'] for s in uncertain['steps']], ['passed', 'pending_receipt'])
        events.append({'type': 'manual_reconciliation', 'address': b, 'note': 'worker exited'})
        reconciled = project_run(plan, events, 'needs_reconciliation')
        self.assertEqual(reconciled['steps'][1]['evidence'], 'worker exited')
        self.assertEqual(reconciled['active'], 0)

    def test_old_unknown_step_remains_visible(self):
        run = project_run({'chapters': [], 'chairs': {}}, [{'type': 'step_failed', 'address': 'old'}], 'failed')
        self.assertEqual(run['timeline'][0]['address'], 'old')
        self.assertNotIn('rung', run['timeline'][0])
