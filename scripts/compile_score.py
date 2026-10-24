#!/usr/bin/env python3
"""Compile a version-2 composite score into a deterministic, sealed execution plan."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import jsonschema
from score_composer import SECTION_TIERS, compose_score, read_json, resolve_score, registry_errors
from spawn_chair import enforce_hall_capabilities, SpawnError, plan as spawn_plan
from halls import resolve_hall
from audition_chair import evaluate

ROOT = Path(__file__).resolve().parent.parent

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def safe_path(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or any(x in ('..', '.git') for x in p.parts) or any(x in value for x in ('\\', '\0', '*', '?', '[')) or str(p) != value or value == '.':
        raise ValueError(f'unsafe manifest path: {value!r}')
    return value

def overlaps(a, b):
    return a == b or a.startswith(b + '/') or b.startswith(a + '/')

def compile_program(program, registry=None, draft=False):
    schema = read_json(ROOT / 'templates/program-schema.json')
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(program), key=lambda e: str(e.path))
    if errors:
        raise ValueError('; '.join(e.message for e in errors))
    registry = copy.deepcopy(registry if registry is not None else {'models': []})
    errors = registry_errors(registry)
    if errors:
        raise ValueError('; '.join(errors))
    source = copy.deepcopy(program)
    contract = read_json(ROOT / 'templates/section-contract.json')
    protected = [safe_path(p) for p in program['ground_bass']]
    chairs = copy.deepcopy(program['chairs'])
    diagnostics = []
    for name, chair in chairs.items():
        section = chair['section']
        tools = chair['allowed_toolsets']
        if not set(tools) <= set(contract['ceilings'][section]):
            raise ValueError(f'{name}: tool ceiling exceeded')
        if section in contract['isolation_lock'] and chair['isolation'] != contract['isolation_lock'][section]:
            raise ValueError(f'{name}: isolation lock violated')
        if chair.get('tier', SECTION_TIERS[section]) != SECTION_TIERS[section]:
            raise ValueError(f'{name}: section tier cannot be escalated')
        if section == 'heavy_brass' and not program.get('brass_cue', '').strip():
            raise ValueError('heavy_brass needs an explicit brass_cue')
        if chair['executor'] == 'command':
            if 'terminal' not in tools or chair['isolation'] != 'shared':
                raise ValueError(f'{name}: trusted command requires terminal and shared isolation')
            if any(k in chair for k in ('model', 'hall', 'tier')):
                raise ValueError('command executors do not bind LLM models/halls/tiers')
            chair['routing'] = {'executor': 'local-command'}
        else:
            if section in ('snare_drum', 'cymbals'):
                raise ValueError('zero-token sections require command executor')
            if 'hall' not in chair:
                raise ValueError(f'{name}: agent requires hall')
            score = compose_score('Resolve chair', score_id='resolve-chair')
            score['movements'] = [score['movements'][0]]
            m = score['movements'][0]
            m.update(lead_section=section, active_sections=[section], tacet_sections=sorted(set(SECTION_TIERS)-{section}), isolation=chair['isolation'])
            score['section_routing'] = {s: {'tier': SECTION_TIERS[s], 'assigned_model': None, 'resolution': 'unresolved', 'resolved_tier': None, 'source': 'none'} for s in {'conductor',section}}
            if program.get('brass_cue'):
                score['brass_cue'] = program['brass_cue']
            inventory = copy.deepcopy(registry)
            if chair.get('model'):
                inventory.setdefault('sections', {})[section] = chair['model']
            resolved, invalid = resolve_score(score, inventory, {}, allow_unresolved=True)
            if invalid:
                raise ValueError('; '.join(invalid))
            route = resolved['section_routing'][section]
            # Validate pin capability even when the inventory is unresolved.
            try:
                enforce_hall_capabilities(resolve_hall(chair['hall']), isolation=chair['isolation'], model=route['assigned_model'] or 'unresolved', tools=tools)
            except SpawnError as exc:
                raise ValueError(str(exc)) from exc
            chair['routing'] = route
            if route['resolution'] == 'unresolved':
                diagnostics.append(f'{name}: unresolved tier {route["tier"]}')
    count = 0
    def walk(node, scope=None, depth=0):
        nonlocal count
        count += 1
        if count > 1024 or depth > 16:
            raise ValueError('program exceeds node/depth limit')
        kind = node['kind']
        paths = set()
        if kind == 'movement':
            if node['chair'] not in chairs:
                raise ValueError('unknown chair ' + node['chair'])
            c = chairs[node['chair']]
            if c['executor'] == 'command':
                if not node.get('argv') or 'prompt' in node:
                    raise ValueError('command movement requires argv only')
            elif not node.get('prompt', '').strip() or 'argv' in node:
                raise ValueError('agent movement requires prompt only')
            if c['executor']=='agent' and c['routing']['assigned_model']:
                envelope=dict(movement=node['id'],sender=dict(section=c['section'],model=c['routing']['assigned_model']),cue='VARIATION_REQUESTED',ground_bass_ref=','.join(protected),isolation=c['isolation'],allowed_toolsets=c['allowed_toolsets'],tacet_paths=protected,budget=dict(dynamic_mark='ffff' if c['section']=='heavy_brass' else 'p',timeout_sec=1),payload=dict(summary=node['prompt']))
                verdict=evaluate(envelope)
                if verdict['audition']!='pass':
                    raise ValueError('; '.join(verdict['reasons']))
                try:
                    spawn_plan(envelope,query=node['prompt'],section_override=None,brass_cue=bool(program.get('brass_cue')),hall_name=c['hall'])
                except SpawnError as exc:
                    raise ValueError(str(exc)) from exc
            if scope is not None and c['isolation'] != 'shared':
                raise ValueError('transactional loops require shared agents with declared file edits')
            paths = set(node['writes'] + node['outputs'])
            if paths and 'file' not in c['allowed_toolsets']:
                raise ValueError('file writes require file toolset')
        elif kind in ('sequence','parallel'):
            ids = [x['id'] for x in node['children']]
            if len(ids) != len(set(ids)):
                raise ValueError('duplicate sibling node id')
            branches = [walk(x, scope, depth+1) for x in node['children']]
            if kind == 'parallel':
                for i, branch in enumerate(branches):
                    if any(overlaps(a,b) for other in branches[:i] for a in branch for b in other):
                        raise ValueError('parallel write manifests overlap')
                for child in node['children']:
                    if shared_agent_writer(child):
                        raise ValueError('parallel shared agent writers require isolated worktrees')
            paths = set().union(*branches)
        else:
            edits = set(node['edit_paths'])
            metric = node['metric']['path']
            if any(overlaps(metric,p) for p in edits):
                raise ValueError('metric must be separate from candidate files')
            if scope is not None and not edits <= scope:
                raise ValueError('nested loop edit_paths must be a subset of parent edit_paths')
            baseline_paths = walk(node['baseline'], edits | {metric}, depth+1)
            body_paths = walk(node['body'], edits | {metric}, depth+1)
            if metric not in baseline_paths or metric not in body_paths:
                raise ValueError('baseline and body must declare metric output')
            paths = edits | {metric} | baseline_paths | body_paths
        for path in paths:
            safe_path(path)
            if any(overlaps(path,p) for p in protected):
                raise ValueError('write overlaps protected ground bass: ' + path)
            if scope is not None and path not in scope:
                raise ValueError('loop write outside edit_paths/metric: ' + path)
        return paths
    def shared_agent_writer(node):
        if node['kind'] == 'movement':
            c = chairs[node['chair']]
            return c['executor'] == 'agent' and c['isolation'] == 'shared' and bool(node['writes'] or node['outputs'])
        if node['kind'] == 'loop':
            return shared_agent_writer(node['body']) or shared_agent_writer(node['baseline'])
        return any(shared_agent_writer(n) for n in node['children'])
    def kinds(node):
        result = {node['kind']}
        children = [node['baseline'],node['body']] if node['kind']=='loop' else node.get('children',[])
        for n in children:
            result |= kinds(n)
        return result
    chapters = program['score']['chapters']
    by_id = {c['id']: c for c in chapters}
    if len(by_id) != len(chapters):
        raise ValueError('duplicate chapter id')
    ordered, visiting, done = [], set(), set()
    def visit(identity):
        if identity not in by_id:
            raise ValueError('missing chapter dependency ' + identity)
        if identity in visiting:
            raise ValueError('chapter dependency cycle')
        if identity in done:
            return
        visiting.add(identity)
        for dep in by_id[identity]['depends_on']:
            visit(dep)
        visiting.remove(identity); done.add(identity); ordered.append(copy.deepcopy(by_id[identity]))
    for c in chapters:
        visit(c['id'])
        walk(c['body'])
        structure = kinds(c['body'])
        if c['form']=='rachmaninoff_climax' and not program.get('brass_cue','').strip():
            raise ValueError('climax form needs an explicit brass_cue')
        if c['form'] not in ('custom','bach_fugue','bach_variation','brahms_variation') and 'sequence' not in structure:
            raise ValueError('this form requires a sequence group')
        if c['form'] == 'bach_fugue' and 'parallel' not in structure:
            raise ValueError('bach_fugue requires a parallel group')
        if c['form'] in ('bach_variation','brahms_variation') and 'loop' not in structure:
            raise ValueError('variation form requires a bounded loop')
    if diagnostics and not draft:
        raise ValueError('; '.join(diagnostics))
    plan = dict(plan_version=1, source=source, registry=registry, chairs=chairs, chapters=ordered,
                ready=not diagnostics, diagnostics=diagnostics, admit=False)
    plan['plan_id'] = digest(plan)
    return plan

def validate_plan(plan):
    try:
        rebuilt = compile_program(plan['source'], plan['registry'], draft=True)
        if rebuilt != plan:
            raise ValueError('compiled plan seal/source mismatch')
    except (KeyError, TypeError) as exc:
        raise ValueError('invalid compiled plan') from exc

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--program', required=True); p.add_argument('--registry'); p.add_argument('--draft',action='store_true'); p.add_argument('--output')
    a=p.parse_args()
    try:
        plan=compile_program(read_json(a.program),read_json(a.registry) if a.registry else None,a.draft)
        data=json.dumps(plan,ensure_ascii=False,indent=2)+'\n'
        if a.output: Path(a.output).write_text(data)
        else: print(data,end='')
        return 0 if plan['ready'] else 2
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc),file=sys.stderr);return 2
if __name__=='__main__':
    sys.exit(main())
