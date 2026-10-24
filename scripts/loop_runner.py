#!/usr/bin/env python3
"""POSIX durable composite-score runner. SQLite checkpoints; detached job receipts.

Command executors are trusted local programs, not a filesystem sandbox. Never
replay an uncertain launch: resume consumes its receipt or requires reconciliation.
"""
from __future__ import annotations
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from compile_score import digest, safe_path, validate_plan
from score_composer import read_json

class Halt(Exception):
    pass
class StepFailure(Exception):
    pass


def atomic_json(path, value):
    path=Path(path);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('w') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def worker(job_path):
    """Receipt is the sole automatic completion evidence, never PID inference."""
    job_path=Path(job_path);job=read_json(job_path);started=time.time();proc=None
    result=dict(execution_id=job['execution_id'],job_hash=digest(job),status='failed',exit_code=None)
    try:
        env=os.environ.copy();env.update(job['env'])
        with (job_path.parent/'stdout.log').open('wb') as out, (job_path.parent/'stderr.log').open('wb') as err:
            proc=subprocess.Popen(job['argv'],cwd=job['cwd'],env=env,stdout=out,stderr=err,start_new_session=True)
            while proc.poll() is None:
                if (job_path.parent/'cancel').exists():
                    result['status']='cancelled';break
                if time.time()-started >= job['timeout_sec']:
                    result['status']='timeout';break
                time.sleep(.05)
            else:
                result['exit_code']=proc.returncode
                result['status']='succeeded' if proc.returncode==0 else 'failed'
    except Exception as exc:
        result['error']=str(exc)
    finally:
        if proc is not None:
            # Also clean up descendants after a leader exits. Jobs cannot daemonize.
            with contextlib.suppress(ProcessLookupError): os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
        result['elapsed_sec']=time.time()-started
        atomic_json(job_path.parent/'receipt.json',result)
    return 0


class Runner:
    def __init__(self,state):
        self.state=Path(state).resolve()
        self.db=sqlite3.connect(self.state/'journal.sqlite',timeout=30,check_same_thread=False)
        self.db.execute('PRAGMA synchronous=FULL')
        self.lock=threading.RLock()
        self.plan=self.get('plan');validate_plan(self.plan)
        self.root=Path(self.get('root'))
        self.slots=threading.BoundedSemaphore(self.plan['source'].get('parallelism',4))
        self.metric_paths=set()
        def collect(node):
            if node['kind']=='loop':
                self.metric_paths.add(node['metric']['path']);collect(node['baseline']);collect(node['body'])
            else:
                for child in node.get('children',[]): collect(child)
        for chapter in self.plan['chapters']: collect(chapter['body'])

    @classmethod
    def create(cls,plan,root,state):
        validate_plan(plan)
        if not plan['ready']: raise ValueError('draft plans cannot execute')
        root=Path(root).resolve(strict=True);state=Path(state).resolve()
        if not root.is_dir(): raise ValueError('root must be a directory')
        if state==root or root in state.parents:
            raise ValueError('state must be outside the editable task root')
        state.mkdir(parents=True,exist_ok=False,mode=0o700)
        db=sqlite3.connect(state/'journal.sqlite')
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
        db.executescript('CREATE TABLE kv (key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,value TEXT NOT NULL);')
        initial=dict(plan=plan,root=str(root),status='created',desired='run',run_id=uuid.uuid4().hex,created=time.time(),runtime=runtime_digest())
        db.executemany('INSERT INTO kv VALUES (?,?)',[(k,json.dumps(v)) for k,v in initial.items()]);db.commit();db.close()
        r=cls(state)
        try:
            bass=r.snapshot(plan['source']['ground_bass'])
            if any(v is None for v in bass.values()): raise ValueError('ground bass files must exist')
            r.put('ground',bass)
        except Exception:
            r.close();raise
        return r

    def close(self): self.db.close()
    def get(self,key,default=None):
        with self.lock:
            row=self.db.execute('SELECT value FROM kv WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else default
    def put(self,key,value,event=None):
        with self.lock,self.db:
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',(key,json.dumps(value,allow_nan=False)))
            if event: self.db.execute('INSERT INTO events(value) VALUES (?)',(json.dumps(dict(time=time.time(),**event),allow_nan=False),))
    def events(self):
        with self.lock: return [json.loads(r[0]) for r in self.db.execute('SELECT value FROM events ORDER BY seq')]
    def status(self):
        return dict(status=self.get('status'),desired=self.get('desired'),run_id=self.get('run_id'),plan_id=self.plan['plan_id'],error=self.get('error'),admit=False)
    def control(self,action):
        if action not in ('pause','resume','cancel'): raise ValueError('unknown control')
        if action=='resume' and self.get('desired')=='cancel': return
        self.put('desired','run' if action=='resume' else action)
        if action=='cancel':
            for path in self.state.glob('jobs/*/job.json'): (path.parent/'cancel').touch()
    def path(self,name):
        safe_path(name);p=self.root
        for part in Path(name).parts:
            p=p/part
            if p.is_symlink(): raise StepFailure('symlink manifest path: '+name)
        if p.exists() and not p.is_file(): raise StepFailure('manifest must name regular files: '+name)
        return p
    def snapshot(self,paths):
        result={}
        for name in paths:
            p=self.path(name)
            result[name]=dict(data=base64.b64encode(p.read_bytes()).decode(),mode=p.stat().st_mode & 0o777) if p.exists() else None
        return result
    def restore(self,snapshot):
        for name,item in snapshot.items():
            p=self.path(name)
            if item is None:
                p.unlink(missing_ok=True)
            else:
                p.parent.mkdir(parents=True,exist_ok=True)
                tmp=p.with_name(p.name+'.phil-'+uuid.uuid4().hex)
                with tmp.open('wb') as f:
                    f.write(base64.b64decode(item['data']));f.flush();os.fsync(f.fileno())
                os.chmod(tmp,item['mode']);os.replace(tmp,p)
                fd=os.open(p.parent,os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
    def check_ground(self):
        expected=self.get('ground')
        if self.snapshot(expected)!=expected:
            self.restore(expected)
            raise ValueError('ground bass changed; restored protected files')
    def gate(self):
        if self.get('runtime')!=runtime_digest():
            raise ValueError('runner/compiler runtime changed; use pinned runtime')
        desired=self.get('desired')
        if desired!='run':
            raise Halt(desired)
        if time.time() >= self.get('created')+self.plan['source']['budget']['max_wall_sec']:
            raise ValueError('global wall-clock budget exhausted')
    def advance(self):
        with (self.state/'coordinator.lock').open('a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('another coordinator is active')
            if self.get('status') in ('completed','failed','cancelled'): return self.status()
            try:
                if self.get('runtime')!=runtime_digest(): raise ValueError('runner/compiler runtime changed; use pinned runtime')
                self.put('status','running')
                with self.lock:
                    pending=[json.loads(v) for (v,) in self.db.execute("SELECT value FROM kv WHERE key LIKE 'step:%'")]
                if any(x['status']=='launched' and not (self.state/'jobs'/x['execution_id']/'receipt.json').exists() for x in pending):
                    raise Halt('unknown')
                self.gate();self.check_ground()
                for chapter in self.plan['chapters']:
                    self.execute(chapter['body'],chapter['id'],[],None,chapter)
                self.check_ground();self.put('status','completed',dict(type='run_completed'))
            except Halt as exc:
                state={'pause':'paused','cancel':'cancelled','unknown':'needs_reconciliation'}[str(exc)]
                if state=='cancelled': self.restore_active_loops()
                self.put('status',state)
            except Exception as exc:
                self.put('error',str(exc));self.put('status','failed',dict(type='run_failed',error=str(exc)))
                try: self.restore_active_loops()
                except (OSError,StepFailure) as recovery:
                    self.put('error',str(exc)+'; rollback refused: '+str(recovery))
            return self.status()
    def restore_active_loops(self):
        # Outer best wins after all nested scopes; deepest first.
        with self.lock: rows=list(self.db.execute("SELECT key,value FROM kv WHERE key LIKE 'loop:%'"))
        for key,raw in sorted(rows,key=lambda x:len(x[0]),reverse=True):
            data=json.loads(raw)
            if data.get('phase')!='done': self.restore(data['best'])
    def execute(self,node,address,iterations,deadline,chapter):
        self.gate()
        if deadline is not None and time.time()>=deadline: raise StepFailure('loop wall-clock budget exhausted')
        kind=node['kind']
        if kind=='movement':
            self.movement(node,address,iterations,deadline,chapter)
        elif kind=='sequence':
            for child in node['children']: self.execute(child,address+'/'+child['id'],iterations,deadline,chapter)
        elif kind=='parallel':
            with ThreadPoolExecutor(max_workers=min(32,len(node['children']))) as pool:
                jobs=[pool.submit(self.execute,c,address+'/'+c['id'],iterations,deadline,chapter) for c in node['children']]
                failures=[]
                for job in jobs:
                    try: job.result()
                    except Exception as exc: failures.append(exc)
                if failures:
                    # Unknown outranks ordinary failure: never roll back while a detached job may be alive.
                    raise next((e for e in failures if isinstance(e,Halt) and str(e)=='unknown'),failures[0])
        else: self.loop(node,address,iterations,deadline,chapter)
    def movement(self,node,address,iterations,deadline,chapter):
        key='step:'+address
        with self.slots:
            self.gate();self.check_ground()
            previous=self.get(key)
            if previous and previous['status']=='succeeded':
                # Completion receipts attest outputs at that point in the score; later
                # movements may legitimately overwrite the same declared artifacts.
                return
            attempts=previous.get('attempt',0) if previous else 0
            while True:
                if previous and previous['status']=='launched':
                    job_dir=self.state/'jobs'/previous['execution_id'];job=read_json(job_dir/'job.json')
                    receipt_path=job_dir/'receipt.json'
                    if not receipt_path.exists(): raise Halt('unknown')
                    receipt=read_json(receipt_path)
                    if receipt.get('execution_id')!=job['execution_id'] or receipt.get('job_hash')!=digest(job): raise ValueError('receipt identity mismatch')
                elif previous and previous['status']=='succeeded': return
                else:
                    if previous and attempts>=node.get('max_attempts',1): raise StepFailure(previous.get('error','movement failed'))
                    self.gate()
                    for p in node['writes']+node['outputs']: self.path(p)
                    for p in set(node['writes']+node['outputs']) & self.metric_paths:
                        self.path(p).unlink(missing_ok=True)
                    attempts+=1;execution_id=uuid.uuid4().hex;job_dir=self.state/'jobs'/execution_id;job_dir.mkdir(parents=True)
                    env=dict(PHIL_ROOT=str(self.root),PHIL_STATE=str(self.state),PHIL_RUN_ID=self.get('run_id'),PHIL_ITERATION=str(iterations[-1] if iterations else 0),PHIL_ITERATION_PATH=json.dumps(iterations),PHIL_BEST_METRIC=str(self.current_best(address)),MADA_SECTION=self.plan['chairs'][node['chair']]['section'])
                    timeout=min(node['timeout_sec'],self.get('created')+self.plan['source']['budget']['max_wall_sec']-time.time())
                    if deadline: timeout=min(timeout,deadline-time.time())
                    if timeout<=0: raise StepFailure('execution budget exhausted')
                    argv=self.argv(node,job_dir,chapter,env,timeout)
                    job=dict(execution_id=execution_id,argv=argv,cwd=str(self.root),env=env,timeout_sec=timeout)
                    atomic_json(job_dir/'job.json',job)
                    # Commit intent BEFORE launch. A death in this window is unknown, not replayable.
                    previous=dict(status='launched',execution_id=execution_id,attempt=attempts)
                    self.put(key,previous,dict(type='step_started',address=address,execution_id=execution_id))
                    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--job',str(job_dir/'job.json')],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                    worker_deadline=time.time()+timeout+5
                    while not (job_dir/'receipt.json').exists():
                        if child.poll() is not None:
                            child.wait();raise Halt('unknown')
                        if time.time()>worker_deadline:
                            (job_dir/'cancel').touch();raise Halt('unknown')
                        if self.get('desired')=='cancel': (job_dir/'cancel').touch()
                        time.sleep(.05)
                    child.wait()
                    receipt=read_json(job_dir/'receipt.json')
                    if receipt.get('job_hash')!=digest(job): raise ValueError('receipt hash mismatch')
                self.check_ground()
                error=None
                if receipt['status']!='succeeded': error='job '+receipt['status']
                else:
                    outputs=self.snapshot(node['outputs'])
                    if any(v is None for v in outputs.values()): error='missing declared output'
                if error is None:
                    previous.update(status='succeeded',outputs=outputs)
                    self.put(key,previous,dict(type='step_completed',address=address,execution_id=previous['execution_id']))
                    return
                previous.update(status='failed',error=error)
                self.put(key,previous,dict(type='step_failed',address=address,error=error))
                if self.get('desired')=='cancel': raise Halt('cancel')
    def current_best(self,address):
        with self.lock: rows=list(self.db.execute("SELECT key,value FROM kv WHERE key LIKE 'loop:%'"))
        candidates=[(len(k),json.loads(v).get('best_metric')) for k,v in rows if address.startswith(k[5:]+'/')]
        return max(candidates,default=(0,None))[1]
    def argv(self,node,directory,chapter,env,timeout):
        chair=self.plan['chairs'][node['chair']]
        if chair['executor']=='command': return node['argv']
        brief=json.dumps(dict(task=self.plan['source']['task'],chapter={k:v for k,v in chapter.items() if k!='body'},instruction=node['prompt'],root=str(self.root),writes=node['writes'],outputs=node['outputs'],iteration=env['PHIL_ITERATION_PATH'],best_metric=env['PHIL_BEST_METRIC']),ensure_ascii=False)
        envelope=dict(movement=node['id'],sender=dict(section=chair['section'],model=chair['routing']['assigned_model']),cue='VARIATION_REQUESTED',ground_bass_ref=','.join(self.plan['source']['ground_bass']),isolation=chair['isolation'],allowed_toolsets=chair['allowed_toolsets'],tacet_paths=self.plan['source']['ground_bass'],budget=dict(dynamic_mark='ffff' if chair['section']=='heavy_brass' else 'p',timeout_sec=max(1,math.ceil(timeout))),payload=dict(summary=brief))
        atomic_json(directory/'envelope.json',envelope)
        argv=[sys.executable,str(Path(__file__).with_name('spawn_chair.py')),'--envelope',str(directory/'envelope.json'),'--hall',chair['hall'],'--supervise','-q',brief]
        if self.plan['source'].get('brass_cue'): argv.append('--brass-cue')
        return argv
    def metric(self,node):
        try:
            value=read_json(self.path(node['metric']['path']))
        except (ValueError,OSError) as exc:
            raise StepFailure('invalid or missing metric: '+str(exc)) from exc
        for part in node['metric']['key'].split('.'):
            if not isinstance(value,dict) or part not in value: raise StepFailure('metric key missing')
            value=value[part]
        try:
            finite=not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
        except OverflowError: finite=False
        if not finite: raise StepFailure('metric must be a finite number')
        return value
    def loop(self,node,address,iterations,outer_deadline,chapter):
        key='loop:'+address;data=self.get(key)
        if data is None:
            self.path(node['metric']['path']).unlink(missing_ok=True)
            data=dict(phase='baseline',iteration=1,best=self.snapshot(node['edit_paths']),created=time.time(),no_improvement=0,failures=0)
            self.put(key,data)
        if data['phase']=='done': return
        deadline=data['created']+node['limits']['max_wall_sec']
        if outer_deadline: deadline=min(deadline,outer_deadline)
        if data['phase']=='baseline':
            # Baseline executes only once and cannot alter the candidate seed.
            self.execute(node['baseline'],address+'/baseline',iterations,deadline,chapter)
            if self.snapshot(node['edit_paths'])!=data['best']: raise ValueError('baseline modified candidate files')
            data.update(best_metric=self.metric(node),metric_file=self.snapshot([node['metric']['path']]),phase='ready')
            self.put(key,data,dict(type='loop_baseline',address=address,metric=data['best_metric']))
        while data['phase']!='done':
            self.gate()
            if data['phase']=='settle':
                self.restore(data['best']);self.restore(data['metric_file'])
                data.update(phase='ready',iteration=data['iteration']+1)
                self.put(key,data)
            if data['phase']=='ready':
                limits=node['limits'];reason=None
                if data['failures']>=limits.get('max_consecutive_failures',math.inf):
                    raise StepFailure('loop consecutive failure limit')
                if data['iteration']>limits['max_iterations']: reason='max_iterations'
                elif time.time()>=deadline: reason='max_wall_sec'
                elif data['no_improvement']>=limits.get('max_no_improvement',math.inf): reason='max_no_improvement'
                if reason:
                    data.update(phase='done',reason=reason);self.put(key,data,dict(type='loop_completed',address=address,reason=reason,best_metric=data['best_metric']));return
                self.restore(data['best'])
                self.path(node['metric']['path']).unlink(missing_ok=True)
                data['phase']='candidate';self.put(key,data)
            error=None;candidate=None
            try:
                self.execute(node['body'],address+'/iteration-'+str(data['iteration']),iterations+[data['iteration']],deadline,chapter)
                candidate=self.metric(node)
            except (StepFailure,OSError,ValueError) as exc:
                # Ground-bass violations and malformed journals are fatal, never experiments.
                self.check_ground()
                if isinstance(exc,ValueError) and not isinstance(exc,json.JSONDecodeError): raise
                error=str(exc)
            better=candidate is not None and ((candidate<data['best_metric']) if node['metric']['direction']=='min' else (candidate>data['best_metric']))
            decision='crash' if error else 'keep' if better else 'discard'
            if better:
                data.update(best=self.snapshot(node['edit_paths']),best_metric=candidate,metric_file=self.snapshot([node['metric']['path']]),no_improvement=0)
            else: data['no_improvement']+=1
            data['failures']=data['failures']+1 if error else 0
            data['phase']='settle'
            self.put(key,data,dict(type='loop_decision',address=address,iteration=data['iteration'],decision=decision,metric=candidate,best_metric=data['best_metric'],error=error))
    def reconcile(self,address,note,confirm_stopped):
        if not confirm_stopped or not note.strip(): raise ValueError('reconciliation needs --confirm-stopped and a nonempty evidence note')
        with (self.state/'coordinator.lock').open('a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('coordinator is active')
            key='step:'+address;step=self.get(key)
            if not step or step['status']!='launched': raise ValueError('step is not uncertain')
            directory=self.state/'jobs'/step['execution_id']
            if (directory/'receipt.json').exists(): raise ValueError('receipt exists; resume to consume it')
            job=read_json(directory/'job.json')
            atomic_json(directory/'receipt.json',dict(execution_id=step['execution_id'],job_hash=digest(job),status='reconciled_failure',exit_code=None,note=note))
            self.put('status','needs_reconciliation',dict(type='manual_reconciliation',address=address,note=note))


def runtime_digest():
    here=Path(__file__).resolve().parent
    files={p:(here/p).read_text() for p in ('loop_runner.py','compile_score.py','spawn_chair.py','score_composer.py','audition_chair.py','halls.py')}
    files.update({p.name:p.read_text() for p in (here.parent/'templates').glob('*.json')})
    return digest(files)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    w=sub.add_parser('worker');w.add_argument('--job',required=True)
    for command in ('run','resume','status','pause','cancel','reconcile'):
        p=sub.add_parser(command);p.add_argument('--state',required=True)
        if command=='run': p.add_argument('--plan',required=True);p.add_argument('--root',required=True)
        if command=='reconcile': p.add_argument('--address',required=True);p.add_argument('--note',required=True);p.add_argument('--confirm-stopped',action='store_true')
    a=parser.parse_args()
    if a.command=='worker': return worker(a.job)
    r=None
    try:
        r=Runner.create(read_json(a.plan),a.root,a.state) if a.command=='run' else Runner(a.state)
        if a.command in ('run','resume'):
            if a.command=='resume': r.control('resume')
            result=r.advance()
        elif a.command in ('pause','cancel'): r.control(a.command);result=r.status()
        elif a.command=='reconcile': r.reconcile(a.address,a.note,a.confirm_stopped);result=r.status()
        else: result=dict(**r.status(),events=r.events())
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['status']=='completed' or a.command in ('status','pause','cancel','reconcile') else 2
    except (ValueError,OSError,sqlite3.Error) as exc:
        print(str(exc),file=sys.stderr);return 2
    finally:
        if r: r.close()
if __name__=='__main__': sys.exit(main())
