#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import sys,tempfile,unittest,json,copy,subprocess,time,os,signal,threading
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv.pop())/'scripts'))
from compile_score import compile_program
from loop_runner import Runner,Halt
import loop_runner

def move(name,code,writes=(),outputs=()):
    return dict(kind='movement',id=name,chair='local',argv=[sys.executable,'-c',code],writes=list(writes),outputs=list(outputs),timeout_sec=3)
def program(body):
    return dict(schema_version=2,task=dict(id='test',summary='Progressive improvement'),score=dict(id='suite',revision='1',chapters=[dict(id='chapter',name='Bach',form='custom',depends_on=[],body=body)]),chairs={'local':dict(section='snare_drum',executor='command',allowed_toolsets=['terminal','file'],isolation='shared')},ground_bass=['SPEC.md'],budget=dict(max_wall_sec=30))
def loop(code=None):
    return dict(kind='loop',id='variations',edit_paths=['candidate.txt'],metric=dict(path='metric.json',key='loss',direction='min'),limits=dict(max_iterations=3,max_wall_sec=20),baseline=move('baseline',"import json;from pathlib import Path;Path('metric.json').write_text(json.dumps({'loss':float(Path('candidate.txt').read_text())}))",outputs=['metric.json']),body=move('vary',code or "import os,json;from pathlib import Path;i=int(os.environ['PHIL_ITERATION']);v=[8,12,6][i-1];Path('candidate.txt').write_text(str(v));Path('metric.json').write_text(json.dumps({'loss':v}))",writes=['candidate.txt'],outputs=['metric.json']))
class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'repo';self.root.mkdir();(self.root/'SPEC.md').write_text('locked');(self.root/'candidate.txt').write_text('10')
    def tearDown(self): self.tmp.cleanup()
    def run_program(self,p):
        runner=Runner.create(compile_program(p),self.root,self.base/'state');runner.advance();return runner
    def test_keep_discard_and_best_restoration(self):
        r=self.run_program(program(loop()));self.assertEqual(r.status()['status'],'completed');self.assertEqual((self.root/'candidate.txt').read_text(),'6');self.assertEqual([e['decision'] for e in r.events() if e['type']=='loop_decision'],['keep','discard','keep'])
    def test_completed_steps_are_not_replayed(self):
        n=move('once',"from pathlib import Path;p=Path('count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')",writes=['count'],outputs=['count']);r=self.run_program(program(n));r.close();r=Runner(self.base/'state');r.advance();self.assertEqual((self.root/'count').read_text(),'1')
    def test_invalid_metric_is_crash_not_win(self):
        n=loop("from pathlib import Path;Path('candidate.txt').write_text('0');Path('metric.json').write_text('{\"loss\":true}')");r=self.run_program(program(n));self.assertEqual((self.root/'candidate.txt').read_text(),'10');self.assertEqual([e['decision'] for e in r.events() if e['type']=='loop_decision'],['crash']*3)
    def test_failed_candidate_does_not_reuse_metric(self):
        r=self.run_program(program(loop('raise SystemExit(1)')));self.assertEqual((self.root/'candidate.txt').read_text(),'10');self.assertEqual(len([e for e in r.events() if e.get('decision')=='crash']),3)
    def test_ground_bass_tamper_is_fatal_and_restored(self):
        r=self.run_program(program(move('bad',"from pathlib import Path;Path('SPEC.md').write_text('bad')")));self.assertEqual(r.status()['status'],'failed');self.assertEqual((self.root/'SPEC.md').read_text(),'locked')
    def test_pause_before_dispatch_and_resume(self):
        r=Runner.create(compile_program(program(move('ok','pass'))),self.root,self.base/'state');r.control('pause');r.advance();self.assertEqual(r.status()['status'],'paused');r.control('resume');r.advance();self.assertEqual(r.status()['status'],'completed')
    def test_missing_output_fails(self):
        r=self.run_program(program(move('missing','pass',outputs=['missing'])));self.assertEqual(r.status()['status'],'failed')
    def test_symlink_manifest_refused(self):
        (self.root/'link').symlink_to(self.base/'outside');r=self.run_program(program(move('link','pass',writes=['link'])));self.assertEqual(r.status()['status'],'failed')
    def test_draft_refused(self):
        p=compile_program(program(move('ok','pass')));p['ready']=False
        with self.assertRaises(ValueError):Runner.create(p,self.root,self.base/'state')
    def test_no_improvement_limit(self):
        n=loop();n['limits']['max_no_improvement']=1;n['body']['argv']=[sys.executable,'-c',"from pathlib import Path;Path('metric.json').write_text('{\"loss\":10}')"]
        r=self.run_program(program(n));self.assertEqual(len([e for e in r.events() if e['type']=='loop_decision']),1)
    def test_parallel_and_sequence(self):
        n=dict(kind='parallel',id='duet',children=[move('a',"from pathlib import Path;Path('a').write_text('a')",outputs=['a']),move('b',"from pathlib import Path;Path('b').write_text('b')",outputs=['b'])]);r=self.run_program(program(n));self.assertEqual(r.status()['status'],'completed')
    def test_decision_checkpoint_restores_without_rejudging(self):
        r=Runner.create(compile_program(program(loop())),self.root,self.base/'state');original=r.put;stopped=[False]
        def interrupted(key,value,event=None):
            original(key,value,event)
            if event and event['type']=='loop_decision' and not stopped[0]:
                stopped[0]=True;raise Halt('pause')
        r.put=interrupted;r.advance();self.assertEqual(r.status()['status'],'paused');r.put=original;r.control('resume');r.advance()
        self.assertEqual((self.root/'candidate.txt').read_text(),'6');self.assertEqual(len([e for e in r.events() if e['type']=='loop_decision']),3)
    def test_killed_coordinator_recovers_receipt_without_replay(self):
        n=move('slow',"import time;from pathlib import Path;p=Path('count');p.write_text('1' if not p.exists() else 'duplicate');time.sleep(.6);Path('done').write_text('ok')",writes=['count'],outputs=['done'])
        r=Runner.create(compile_program(program(n)),self.root,self.base/'state');r.close()
        proc=subprocess.Popen([sys.executable,loop_runner.__file__,'resume','--state',str(self.base/'state')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        end=time.time()+5
        while not (self.root/'count').exists() and time.time()<end: time.sleep(.02)
        self.assertTrue((self.root/'count').exists());proc.kill();proc.wait()
        r=Runner(self.base/'state');r.advance();self.assertEqual(r.status()['status'],'needs_reconciliation')
        end=time.time()+5
        while not list((self.base/'state').glob('jobs/*/receipt.json')) and time.time()<end: time.sleep(.02)
        r.advance();self.assertEqual(r.status()['status'],'completed');self.assertEqual((self.root/'count').read_text(),'1');r.close()
    def test_launch_intent_without_receipt_requires_manual_evidence(self):
        r=Runner.create(compile_program(program(move('once','pass'))),self.root,self.base/'state')
        d=r.state/'jobs'/'uncertain';d.mkdir(parents=True);loop_runner.atomic_json(d/'job.json',{'execution_id':'uncertain'})
        r.put('step:chapter',dict(status='launched',execution_id='uncertain',attempt=1));r.advance();self.assertEqual(r.status()['status'],'needs_reconciliation')
        with self.assertRaises(ValueError):r.reconcile('chapter','',False)
        r.reconcile('chapter','operator verified launch never occurred',True);r.advance();self.assertEqual(r.status()['status'],'failed')
    def test_baseline_cannot_reuse_old_metric(self):
        (self.root/'metric.json').write_text('{"loss":0}');n=loop();n['baseline']['argv']=[sys.executable,'-c','pass']
        r=self.run_program(program(n));self.assertEqual(r.status()['status'],'failed')
    def test_missing_nan_and_infinite_metrics_are_crashes(self):
        for text in ('{}','{"loss":NaN}','{"loss":1e999}'):
            with self.subTest(text=text):
                n=loop("from pathlib import Path;Path('metric.json').write_text("+repr(text)+")");n['limits']['max_iterations']=1
                state=self.base/('state'+str(len(list(self.base.iterdir()))));r=Runner.create(compile_program(program(n)),self.root,state);r.advance()
                self.assertEqual([e['decision'] for e in r.events() if e['type']=='loop_decision'],['crash']);r.close()
    def test_timeout_and_explicit_retry_bound(self):
        n=move('timeout','import time;time.sleep(2)');n['timeout_sec']=.1;n['max_attempts']=2
        r=self.run_program(program(n));self.assertEqual(r.status()['status'],'failed');self.assertEqual(len([e for e in r.events() if e['type']=='step_started']),2)
    def test_nested_loop_addresses_and_outer_rollback(self):
        inner=loop();inner['limits']['max_iterations']=1
        outer=dict(kind='loop',id='outer',edit_paths=['candidate.txt','metric.json'],metric=dict(path='outer.json',key='loss',direction='min'),limits=dict(max_iterations=2,max_wall_sec=20),baseline=move('base',"from pathlib import Path;Path('outer.json').write_text('{\"loss\":10}')",outputs=['outer.json']),body=dict(kind='sequence',id='body',children=[inner,move('judge',"from pathlib import Path;Path('outer.json').write_text('{\"loss\":9}')",outputs=['outer.json'])]))
        r=self.run_program(program(outer));self.assertEqual(r.status()['status'],'completed');self.assertEqual(len([e for e in r.events() if e['type']=='loop_baseline']),3)
    def test_consecutive_crash_limit_fails_even_on_last_iteration(self):
        n=loop('raise SystemExit(1)');n['limits'].update(max_iterations=1,max_consecutive_failures=1)
        r=self.run_program(program(n));self.assertEqual(r.status()['status'],'failed');self.assertEqual((self.root/'candidate.txt').read_text(),'10')
    def test_global_budget_and_cancellation_are_terminal(self):
        r=Runner.create(compile_program(program(move('ok','pass'))),self.root,self.base/'state');r.put('created',time.time()-100);r.advance();self.assertEqual(r.status()['status'],'failed');r.close()
        r=Runner.create(compile_program(program(move('ok','pass'))),self.root,self.base/'cancel-state');r.control('cancel');r.control('resume');r.advance();self.assertEqual(r.status()['status'],'cancelled');r.close()
    def test_agent_uses_actual_spawn_adapter_and_pinned_model(self):
        fake=self.base/'hermes';fake.write_text('#!'+sys.executable+'\nimport sys,os,json\nfrom pathlib import Path\nPath("agent.json").write_text(json.dumps({"argv":sys.argv[1:],"section":os.environ["MADA_SECTION"]}))\n');fake.chmod(0o755)
        n=move('agent','pass',outputs=['agent.json']);n.pop('argv');n['prompt']='Implement this task'
        p=program(n);p['chairs']['local'].update(section='violin_1',executor='agent',hall='hermes');old=os.environ.get('MADA_HERMES');os.environ['MADA_HERMES']=str(fake)
        try:
            r=Runner.create(compile_program(p,{'models':[{'id':'fixture-model','tiers':['heavy-code']}]}),self.root,self.base/'state');r.advance();self.assertEqual(r.status()['status'],'completed')
            result=json.loads((self.root/'agent.json').read_text());self.assertEqual(result['section'],'violin_1');self.assertIn('fixture-model',result['argv']);self.assertIn('terminal,file',result['argv']);r.close()
        finally:
            if old is None:os.environ.pop('MADA_HERMES',None)
            else:os.environ['MADA_HERMES']=old
    def test_dead_worker_without_receipt_is_uncertain(self):
        class DeadWorker:
            def poll(self): return 1
            def wait(self): return 1
        r=Runner.create(compile_program(program(move('ok','pass'))),self.root,self.base/'state')
        with patch.object(loop_runner.subprocess,'Popen',return_value=DeadWorker()): r.advance()
        self.assertEqual(r.status()['status'],'needs_reconciliation')
    def test_cancel_inflight_candidate_restores_best(self):
        n=loop("import time;from pathlib import Path;Path('candidate.txt').write_text('0');Path('started').write_text('yes');time.sleep(3)")
        n['edit_paths'].append('started');n['body']['writes'].append('started')
        r=Runner.create(compile_program(program(n)),self.root,self.base/'state');thread=threading.Thread(target=r.advance);thread.start()
        end=time.time()+5
        while not (self.root/'started').exists() and time.time()<end:time.sleep(.02)
        self.assertTrue((self.root/'started').exists());r.control('cancel');thread.join(5);self.assertFalse(thread.is_alive());self.assertEqual(r.status()['status'],'cancelled');self.assertEqual((self.root/'candidate.txt').read_text(),'10');self.assertFalse((self.root/'started').exists())
    def test_failed_retry_cannot_reuse_its_metric(self):
        code="import os;from pathlib import Path;p=Path(os.environ['PHIL_STATE'])/'retry-marker';first=not p.exists();p.touch();Path('metric.json').write_text('{\"loss\":0}') if first else None;raise SystemExit(1 if first else 0)"
        n=loop(code);n['body']['max_attempts']=2;n['limits']['max_iterations']=1
        r=self.run_program(program(n));self.assertEqual([e['decision'] for e in r.events() if e['type']=='loop_decision'],['crash']);self.assertEqual((self.root/'candidate.txt').read_text(),'10')
unittest.main(verbosity=2)
PY
