"""Workbench service/HTTP-handler contracts; no bound socket or paid model."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SERVER = Path(__file__).resolve().parents[1] / 'server.py'
spec = importlib.util.spec_from_file_location('hall_server', SERVER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / 'task'
        shutil.copytree(module.REPO / 'examples/bach-search', self.root)
        self.app = module.Workbench(self.root, self.base / 'state', demo=True)
        self.program = module.read_json(self.root / 'program.json')

    def tearDown(self):
        for proc in self.app.processes.values():
            try:
                proc.wait(timeout=8)
            except module.subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
        self.app.lease.close()
        self.tmp.cleanup()

    def request(self, method, path, body=None, token=True, origin=None, host=None, raw=None):
        handler = module.Handler.__new__(module.Handler)
        handler.server = SimpleNamespace(app=self.app, server_port=8787)
        handler.path = path
        payload = raw if raw is not None else json.dumps(body).encode() if body is not None else b''
        handler.headers = {'Host':host or '127.0.0.1:8787', 'Content-Type':'application/json', 'Content-Length':str(len(payload))}
        if token:
            handler.headers['X-Hall-Token'] = self.app.token
        if origin:
            handler.headers['Origin'] = origin
        handler.rfile = io.BytesIO(payload)
        result = {}
        handler.send = lambda status, value, content_type=None: result.update(status=status, value=value)
        getattr(handler, 'do_' + method)()
        return result

    def wait_run(self, identity):
        end = time.time()+8
        while time.time()<end:
            state = self.app.inspect(identity)
            if state['status'] in ('completed','failed','cancelled'):
                return state
            time.sleep(.05)
        self.fail('run did not terminate')

    def test_queued_pause_survives_initial_coordinator_launch(self):
        with patch.object(self.app,'launch') as pending:
            identity=self.app.start(self.program)['id']
            command=pending.call_args.args[1]
        self.app.control(identity,'pause')
        self.app.launch(identity,command)
        end=time.time()+8
        while time.time()<end:
            status=self.app.inspect(identity)
            if status['status'] in ('paused','completed','failed'):break
            time.sleep(.05)
        self.assertEqual(status['status'],'paused')
        self.assertFalse(any(e['type']=='step_started' for e in status['events']))
        self.app.control(identity,'resume')
        self.assertEqual(self.wait_run(identity)['status'],'completed')

    def test_compile_does_not_execute(self):
        plan = self.app.compile(self.program)
        self.assertTrue(plan['ready'])
        self.assertFalse(plan['admit'])
        self.assertEqual(self.app.runs(), [])
        self.assertFalse((self.root / 'metric.json').exists())

    def test_save_and_load_persists_across_server_restart(self):
        saved = self.app.save(self.program)
        self.assertEqual(self.app.scores()[0]['id'],saved['id'])
        self.app.lease.close()
        self.app = module.Workbench(self.root, self.base/'state')
        self.assertEqual(self.app.scores()[0]['program'], self.program)

    def test_real_run_produces_loop_events(self):
        identity = self.app.start(self.program)['id']
        result = self.wait_run(identity)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([e['decision'] for e in result['events'] if e['type']=='loop_decision'], ['keep','crash','keep','discard'])
        self.assertEqual([e['best_metric'] for e in result['events'] if e['type']=='loop_decision'][-1],11)
        with self.assertRaisesRegex(ValueError,'terminal'):
            self.app.control(identity,'resume')

    def test_missing_ground_cleans_partial_run(self):
        (self.root/'SPEC.py').unlink()
        with self.assertRaises(ValueError):
            self.app.start(self.program)
        self.assertEqual(self.app.runs(), [])

    def test_pause_reservation_prevents_second_run(self):
        with patch.object(self.app,'launch'):
            identity = self.app.start(self.program)['id']
        with self.assertRaisesRegex(ValueError,'unfinished'):
            self.app.start(self.program)
        self.app.control(identity,'pause')
        self.assertEqual(self.app.inspect(identity)['desired'],'pause')

    def test_duplicate_server_state_refused(self):
        with self.assertRaisesRegex(ValueError,'another workbench'):
            module.Workbench(self.root,self.base/'state')

    def test_root_state_separation(self):
        with self.assertRaises(ValueError):
            module.Workbench(self.root,self.root/'state')

    def test_unknown_ids_do_not_create_databases(self):
        for identity in ('../outside','z'*32,'f'*32):
            result = self.request('GET','/api/runs/'+identity)
            self.assertEqual(result['status'],400)
        self.assertEqual(list((self.base/'state/runs').iterdir()),[])

    def test_csrf_origin_and_dns_rebinding_defenses(self):
        for kwargs in ({'token':False},{'origin':'https://evil.test'},{'host':'evil.test:8787'}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.request('POST','/api/runs',{'program':self.program},**kwargs)['status'],403)
        self.assertEqual(self.app.runs(),[])

    def test_http_compile_save_and_errors(self):
        self.assertEqual(self.request('POST','/api/compile',{'program':self.program})['status'],200)
        self.assertEqual(self.request('POST','/api/scores',{'program':self.program})['status'],201)
        self.assertEqual(len(self.request('GET','/api/scores')['value']),1)
        for raw in (b'[]',b'NaN',b'{broken',b'{}'):
            self.assertEqual(self.request('POST','/api/compile',raw=raw)['status'],400)
        self.assertEqual(self.request('GET','/private')['status'],404)

    def test_schema_rejects_unsupported_fields(self):
        self.program['invented_slot']='ribbon'
        self.assertEqual(self.request('POST','/api/compile',{'program':self.program})['status'],400)

    def test_cancel_dead_coordinator_finalizes_run(self):
        with patch.object(self.app,'launch'):
            identity = self.app.start(self.program)['id']
        self.app.control(identity,'cancel')
        self.assertEqual(self.wait_run(identity)['status'],'cancelled')

    def test_unresolved_agent_cannot_start(self):
        p=copy.deepcopy(self.program)
        p['chairs']['snare'].update(executor='agent',section='violin_1',hall='hermes')
        def change(node):
            if node['kind']=='movement':
                node.pop('argv');node['prompt']='Implement'
            elif node['kind']=='loop':
                change(node['baseline']);change(node['body'])
            else:
                for child in node['children']:change(child)
        for chapter in p['score']['chapters']:change(chapter['body'])
        self.assertFalse(self.app.compile(p)['ready'])
        with self.assertRaisesRegex(ValueError,'unresolved'):
            self.app.start(p)

if __name__ == '__main__':
    unittest.main(verbosity=2)
