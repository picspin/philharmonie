#!/usr/bin/env python3
"""Loopback Concert Hall workbench. A local trusted-user interface, not hosting."""
from __future__ import annotations
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
import fcntl
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'scripts'))
from compile_score import compile_program
from score_composer import read_json, SECTION_TIERS, registry_errors
from loop_runner import Runner, atomic_json

ID = re.compile(r'^[a-f0-9]{32}$')

class Workbench:
    def __init__(self, root, state, registry=None, demo=False):
        self.root = Path(root).resolve(strict=True)
        self.state = Path(state).resolve()
        if self.state == self.root or self.root in self.state.parents:
            raise ValueError('state must be outside the editable task root')
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lease = (self.state / 'workbench.lock').open('a')
        try:
            fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lease.close()
            raise ValueError('another workbench owns this state directory')
        self.registry = registry or {'models': []}
        errors = registry_errors(self.registry)
        if errors:
            raise ValueError('; '.join(errors))
        self.demo = demo
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.processes = {}
        (self.state / 'scores').mkdir(exist_ok=True)
        (self.state / 'runs').mkdir(exist_ok=True)

    def resource(self, kind, identity):
        if not ID.fullmatch(identity):
            raise ValueError('invalid resource id')
        return self.state / kind / identity

    def config(self):
        return dict(root=str(self.root), demo=self.demo, registry=self.registry,
                    tiers=SECTION_TIERS, admit=False)

    def compile(self, program):
        return compile_program(program, self.registry, draft=True)

    def save(self, program):
        plan = self.compile(program)
        identity = secrets.token_hex(16)
        atomic_json(self.resource('scores', identity), program)
        return dict(id=identity, plan=plan)

    def scores(self):
        return [dict(id=p.name, program=read_json(p)) for p in
                sorted((self.state / 'scores').iterdir()) if ID.fullmatch(p.name)]

    def runs(self):
        result = []
        for p in sorted((self.state / 'runs').iterdir()):
            if ID.fullmatch(p.name):
                result.append(dict(id=p.name, **self.inspect(p.name, events=False)))
        return result

    def inspect(self, identity, events=True):
        path = self.resource('runs', identity)
        if not (path / 'journal.sqlite').is_file():
            raise ValueError('run not found')
        r = Runner(path)
        try:
            result = dict(**r.status(), task=r.plan['source']['task'],
                          chapters=r.plan['chapters'])
            if events:
                result['events'] = r.events()
            return result
        finally:
            r.close()

    def launch(self, identity, command):
        existing = self.processes.get(identity)
        if existing is not None and existing.poll() is None:
            raise ValueError('run coordinator is already active')
        directory = self.resource('runs', identity)
        with (directory / 'coordinator.log').open('ab') as log:
            self.processes[identity] = subprocess.Popen(
                [sys.executable, str(REPO / 'scripts/loop_runner.py'), command,
                 '--state', str(directory)], stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, start_new_session=True)

    def start(self, program):
        with self.lock:
            if any(r['status'] in ('created', 'running', 'paused', 'needs_reconciliation')
                   for r in self.runs()):
                raise ValueError('this task root has an unfinished run; resume or cancel it first')
            plan = self.compile(program)
            if not plan['ready']:
                raise ValueError('unresolved capability tiers; configure the host registry first')
            identity = secrets.token_hex(16)
            directory = self.resource('runs', identity)
            try:
                r = Runner.create(plan, self.root, directory)
            except Exception:
                if directory.exists():
                    shutil.rmtree(directory)
                raise
            r.close()
            try:
                self.launch(identity, 'resume')
            except OSError as exc:
                r = Runner(directory)
                r.put('error', str(exc))
                r.put('status', 'failed')
                r.close()
                raise
            return dict(id=identity)

    def control(self, identity, action):
        with self.lock:
            if action not in ('pause', 'resume', 'cancel'):
                raise ValueError('unsupported action')
            if self.inspect(identity, events=False)['status'] in ('completed', 'failed', 'cancelled'):
                raise ValueError('terminal runs cannot be controlled; start a new run')
            r = Runner(self.resource('runs', identity))
            try:
                r.control(action)
            finally:
                r.close()
            # A live coordinator consumes pause/cancel; a dead coordinator needs
            # one recovery pass to settle receipts and honor cancellation.
            p = self.processes.get(identity)
            if (p is None or p.poll() is not None) and action in ('resume', 'cancel'):
                self.launch(identity, 'resume')
            return self.inspect(identity)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log request bodies or the local bearer token.

    def send(self, status, body, content_type='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        host = self.headers.get('Host')
        expected = f'127.0.0.1:{self.server.server_port}'
        if host != expected:
            self.send(403, dict(error='use the exact loopback URL printed by the server'))
            return False
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + expected:
            self.send(403, dict(error='cross-origin requests are refused'))
            return False
        if self.path.startswith('/api/') and not secrets.compare_digest(
                self.headers.get('X-Hall-Token', ''), self.server.app.token):
            self.send(403, dict(error='invalid local session token'))
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        app = self.server.app
        path = urlsplit(self.path).path
        try:
            if path == '/':
                data = (REPO / 'concert-hall/web/index.html').read_text().replace('__TOKEN__', app.token)
                return self.send(200, data.encode(), 'text/html; charset=utf-8')
            assets = {'/app.mjs': 'text/javascript', '/composer.mjs': 'text/javascript', '/styles.css': 'text/css'}
            if path in assets:
                return self.send(200, (REPO / 'concert-hall/web' / path[1:]).read_bytes(), assets[path])
            if path == '/api/config':
                return self.send(200, app.config())
            if path == '/api/example':
                return self.send(200, read_json(REPO / 'examples/bach-search/program.json'))
            if path == '/api/scores':
                return self.send(200, app.scores())
            if path == '/api/runs':
                return self.send(200, app.runs())
            if path.startswith('/api/runs/'):
                return self.send(200, app.inspect(path.split('/')[-1]))
            self.send(404, dict(error='not found'))
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.send(400, dict(error=str(exc)))

    def do_POST(self):
        if not self.authorized():
            return
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, dict(error='JSON required'))
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 1024 * 1024:
                return self.send(413, dict(error='request size must be 1 byte to 1 MiB'))
            body = json.loads(self.rfile.read(size), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('non-finite JSON constant: '+x)))
            if not isinstance(body, dict):
                raise ValueError('request must be an object')
            app = self.server.app
            if self.path == '/api/compile':
                return self.send(200, app.compile(body['program']))
            if self.path == '/api/scores':
                return self.send(201, app.save(body['program']))
            if self.path == '/api/runs':
                return self.send(201, app.start(body['program']))
            if self.path.startswith('/api/runs/'):
                return self.send(200, app.control(self.path.split('/')[-1], body['action']))
            self.send(404, dict(error='not found'))
        except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
            self.send(400, dict(error=str(exc)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root');p.add_argument('--demo', action='store_true')
    p.add_argument('--state', required=True);p.add_argument('--registry')
    p.add_argument('--port', type=int, default=8787)
    a = p.parse_args()
    if bool(a.root) == a.demo:
        p.error('choose exactly one of --root or --demo')
    state = Path(a.state).resolve()
    if a.demo:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        root = state / 'demo-task'
        if not root.exists():
            shutil.copytree(REPO / 'examples/bach-search', root)
    else:
        root = Path(a.root)
    app = Workbench(root, state, read_json(a.registry) if a.registry else None, a.demo)
    server = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    server.app = app
    print(f'Concert Hall: http://127.0.0.1:{server.server_port}', flush=True)
    print(f'Task root: {app.root} | State: {app.state}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
