#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import copy,json,sys,unittest
from pathlib import Path
root=Path(sys.argv.pop());sys.path.insert(0,str(root/'scripts'))
import compile_score as compiler

def movement(identity='check',chair='local',writes=()):
    return dict(kind='movement',id=identity,chair=chair,argv=['python3','-c','pass'],writes=list(writes),outputs=[],timeout_sec=5)
def program():
    return dict(schema_version=2,task=dict(id='task',summary='test'),score=dict(id='suite',revision='1',chapters=[dict(id='first',name='First',form='custom',depends_on=[],body=movement())]),chairs={'local':dict(section='snare_drum',executor='command',allowed_toolsets=['terminal','file'],isolation='shared')},ground_bass=['SPEC.md'],budget=dict(max_wall_sec=60))

class CompilerTests(unittest.TestCase):
    def test_deterministic_sealed_plan(self):
        a=compiler.compile_program(program());b=compiler.compile_program(program())
        self.assertEqual(a,b);self.assertTrue(a['ready']);self.assertFalse(a['admit']);compiler.validate_plan(a)
    def test_tampered_plan_refused(self):
        p=compiler.compile_program(program());p['chapters'][0]['body']['argv']=['other']
        with self.assertRaises(ValueError):compiler.validate_plan(p)
    def test_unknown_fields_refused(self):
        p=program();p['imaginary']=True
        with self.assertRaises(ValueError):compiler.compile_program(p)
    def test_chapter_sort_and_cycles(self):
        p=program();a=p['score']['chapters'][0];b=copy.deepcopy(a);b.update(id='second',depends_on=['first']);p['score']['chapters']=[b,a]
        self.assertEqual([x['id'] for x in compiler.compile_program(p)['chapters']],['first','second'])
        a['depends_on']=['second']
        with self.assertRaisesRegex(ValueError,'cycle'):compiler.compile_program(p)
    def test_tool_ceiling_and_tacet(self):
        for tools in ([],['delegation']):
            p=program();p['chairs']['local']['allowed_toolsets']=tools
            with self.assertRaises(ValueError):compiler.compile_program(p)
    def test_isolation_lock(self):
        p=program();p['chairs']['local']['isolation']='worktree'
        with self.assertRaises(ValueError):compiler.compile_program(p)
    def test_paths_cannot_escape_or_write_ground(self):
        for path in ('../escape','/absolute','.git/config','SPEC.md'):
            p=program();p['score']['chapters'][0]['body']['writes']=[path]
            with self.assertRaises(ValueError):compiler.compile_program(p)
    def test_parallel_conflicts_and_disjoint_branches(self):
        p=program();p['score']['chapters'][0]['body']=dict(kind='parallel',id='fugue',children=[movement('a',writes=['a.py']),movement('b',writes=['a.py'])])
        with self.assertRaisesRegex(ValueError,'overlap'):compiler.compile_program(p)
        p['score']['chapters'][0]['body']['children'][1]['writes']=['b.py'];compiler.compile_program(p)
    def test_forms_have_structural_meaning(self):
        for form in ('bach_fugue','bach_variation'):
            p=program();p['score']['chapters'][0]['form']=form
            with self.assertRaises(ValueError):compiler.compile_program(p)
    def test_unresolved_agent_is_draft_only(self):
        p=program();p['chairs']['local'].update(executor='agent',section='violin_1',hall='hermes');node=p['score']['chapters'][0]['body'];node.pop('argv');node['prompt']='Implement the task'
        with self.assertRaises(ValueError):compiler.compile_program(p)
        self.assertFalse(compiler.compile_program(p,draft=True)['ready'])
    def test_actual_agent_model_pin_and_hall_capability(self):
        p=program();p['chairs']['local'].update(executor='agent',section='violin_1',hall='hermes');node=p['score']['chapters'][0]['body'];node.pop('argv');node['prompt']='Implement'
        registry={'models':[{'id':'fixture-model','tiers':['heavy-code']}]}
        self.assertEqual(compiler.compile_program(p,registry)['chairs']['local']['routing']['assigned_model'],'fixture-model')
        p['chairs']['local']['hall']='pi'
        with self.assertRaises(ValueError):compiler.compile_program(p,registry)
    def test_two_chairs_share_one_section(self):
        p=program();p['chairs']['other']=copy.deepcopy(p['chairs']['local']);p['score']['chapters'][0]['body']=dict(kind='sequence',id='seq',children=[movement('a'),movement('b','other')]);self.assertEqual(len(compiler.compile_program(p)['chairs']),2)

unittest.main(verbosity=2)
PY
