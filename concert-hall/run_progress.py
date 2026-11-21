"""Read-only projection of a saved plan and its ordered runner events."""
import re

STEP_STATES = {'step_started': 'running', 'step_completed': 'passed', 'step_failed': 'failed'}
TERMINAL = {'completed', 'failed', 'cancelled'}


def plan_steps(plan):
    def walk(node, chapter, address, key):
        kind = node['kind']
        if kind == 'movement':
            chair = node['chair']
            yield re.compile(address), dict(
                key=key, chapter=chapter['id'], name=node['id'], chair=chair,
                section=plan['chairs'][chair]['section'], rung=node.get('verify_rung'),
            )
        elif kind == 'loop':
            yield from walk(node['baseline'], chapter, address + '/baseline', key + '/baseline')
            yield from walk(node['body'], chapter, address + r'/iteration-(\d+)', key + '/body')
        else:
            for child in node['children']:
                yield from walk(child, chapter, address + '/' + re.escape(child['id']), key + '/' + child['id'])

    for chapter in plan['chapters']:
        yield from walk(chapter['body'], chapter, re.escape(chapter['id']), chapter['id'])


def project_run(plan, events, status):
    patterns = list(plan_steps(plan))
    matches = {}
    current = {}
    timeline = []
    last_chapter = None
    for index, event in enumerate(events):
        kind = event.get('type')
        address = event.get('address')
        if kind == 'manual_reconciliation' and address in current:
            current[address] = {**current[address], 'status': 'reconciled', 'evidence': event.get('note')}
        if kind not in STEP_STATES or not isinstance(address, str):
            continue
        step = dict(index=index, address=address, status=STEP_STATES[kind], error=event.get('error'),
                    execution_id=event.get('execution_id'))
        if address not in matches:
            matches[address] = {}
            for pattern, metadata in patterns:
                if match := pattern.fullmatch(address):
                    matches[address] = dict(**metadata, iterations=[int(n) for n in match.groups()])
                    break
        step.update(matches[address])
        last_chapter = step.get('chapter', last_chapter)
        prior = current.get(address)
        # Older failure events omit execution_id. Match only the current attempt
        # at the exact address, never a different iteration or parallel branch.
        if kind != 'step_started' and prior and prior['status'] == 'running':
            if step['execution_id'] and prior['execution_id'] and step['execution_id'] != prior['execution_id']:
                continue
            step['execution_id'] = step['execution_id'] or prior['execution_id']
        current[address] = step
        timeline.append(step)

    for address, step in current.items():
        if step['status'] != 'running':
            continue
        if status == 'needs_reconciliation':
            current[address] = {**step, 'status': 'pending_receipt'}
        elif status != 'running':
            current[address] = {**step, 'status': 'unknown'}
    active = [step for step in current.values() if step['status'] in ('running', 'pending_receipt')]
    chapter_id = next((step['chapter'] for step in active if 'chapter' in step), last_chapter)
    chapter_name = next((chapter['name'] for chapter in plan['chapters'] if chapter['id'] == chapter_id), None)
    return dict(chapter=chapter_name, chapter_id=chapter_id, active=len(active), steps=list(current.values()), timeline=timeline)
