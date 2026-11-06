"""Persistent owner-Host JSONL bridge; never accepts browser filesystem paths."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('philharmonie_workbench', ROOT / 'concert-hall/server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class Bridge:
    def __init__(self, config):
        self.config = config
        state = Path(config['state']).resolve()
        if config.get('demo'):
            state.mkdir(parents=True, exist_ok=True, mode=0o700)
            root = state / 'demo-task'
            if not root.exists():
                shutil.copytree(ROOT / 'examples/bach-search', root)
        else:
            root = Path(config['root'])
        self.base_registry = server.read_json(config['registry']) if config.get('registry') else {'models': []}
        self.app = server.Workbench(root, state, self.base_registry, config.get('demo', False))
        self.bindings_path = state / 'dsh-bindings.json'

    def bindings(self):
        return server.read_json(self.bindings_path) if self.bindings_path.exists() else {}

    def session(self, identity):
        binding = self.bindings().get(identity)
        runs = [r for r in self.app.runs() if binding and r['task']['id'] == binding['program']['task']['id']]
        return dict(sessionId=identity, binding=binding, run=runs[-1] if runs else None)

    def request(self, request):
        session = request.get('sessionId')
        method, path, body = request.get('method'), request.get('path'), request.get('body') or {}
        registry = copy.deepcopy(self.base_registry)
        available = set(request.get('available', []))
        for model in registry['models']:
            model['enabled'] = model.get('enabled', True) and model['id'] in available
        self.app.registry = registry
        if method == 'GET':
            if path == 'config':
                return dict(**self.app.config(), embedded=True, **self.session(session))
            if path == 'session':
                return self.session(session)
            if path == 'example':
                return server.read_json(ROOT / 'examples/bach-search/program.json')
            if path == 'scores':
                return self.app.scores()
            if path == 'runs':
                return self.app.runs()
            if path.startswith('runs/'):
                return self.app.inspect(path.split('/')[1])
        elif method == 'POST':
            if path == 'binding':
                if not session:
                    raise ValueError('open Concert Hall from a DSH Session before binding')
                program = body['program']
                self.app.compile(program)
                bindings = self.bindings()
                bindings[session] = dict(program=program)
                server.atomic_json(self.bindings_path, bindings)
                return self.session(session)
            if path == 'compile':
                return self.app.compile(body['program'])
            if path == 'scores':
                return self.app.save(body['program'])
            if path == 'runs':
                return self.app.start(body['program'])
            if path.startswith('runs/'):
                return self.app.control(path.split('/')[1], body['action'])
        raise ValueError('unsupported bridge operation')


def main():
    bridge = None
    for raw in sys.stdin:
        identity = None
        try:
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('bridge message too large')
            message = json.loads(raw)
            identity = message['id']
            if message.get('operation') == 'init':
                if bridge is not None:
                    raise ValueError('already initialized')
                bridge = Bridge(message['config'])
                value = {'ready': True}
            else:
                if bridge is None:
                    raise ValueError('bridge is not initialized')
                value = bridge.request(message)
            result = dict(id=identity, value=value)
        except Exception as exc:
            result = dict(id=identity, error=str(exc))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
    if bridge:
        bridge.app.lease.close()

if __name__ == '__main__':
    main()
