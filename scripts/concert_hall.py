#!/usr/bin/env python3
"""Read-only Concert Hall state service and ASCII/ANSI terminal board."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time
import unicodedata

from score_composer import read_json, validate_score
from snare_score import score as snare_score


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be a string')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp needs a timezone')
    return result


def read_events(path):
    """A partial append or corrupt line degrades the snapshot, never hides it."""
    events, errors = [], []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('event must be an object')
            events.append(row)
        except ValueError as exc:
            errors.append(f'event line {number}: {exc}')
    return events, errors


def snapshot(score, events, run_id, *, root=None, now=None, input_errors=()):
    """Pure event reduction plus optional target-repo Snare inventory inspection.

    No model calls, commands, graph advancement or admission. Event metadata is
    observational, not a signed audit log or proof of application correctness.
    """
    errors = validate_score(score)
    if errors:
        raise ValueError('; '.join(errors))
    if events and not run_id:
        raise ValueError('events require an explicit run_id')
    now = now or datetime.now(timezone.utc)
    errors = list(input_errors)
    attempts, ignored, unattributed = {}, 0, 0
    identity = ('score_id', 'run_id', 'movement_index', 'section', 'model', 'isolation')
    for number, event in enumerate(events, 1):
        try:
            if not isinstance(event, dict):
                raise ValueError('event must be an object')
            if 'score_id' not in event:
                unattributed += 1
                continue
            if event.get('score_id') != score['score_id'] or event.get('run_id') != run_id:
                ignored += 1
                continue
            if type(event.get('schema_version')) is not int or event['schema_version'] != 1:
                raise ValueError('unsupported event schema_version')
            index = event.get('movement_index')
            if type(index) is not int or not 1 <= index <= len(score['movements']):
                raise ValueError('invalid movement_index')
            movement = score['movements'][index - 1]
            section = event.get('section')
            if section not in movement['active_sections']:
                raise ValueError('event section is Tacet or unknown')
            if event.get('isolation') != movement['isolation']:
                raise ValueError('event isolation differs from score')
            model = event.get('model')
            if not isinstance(model, str) or not model.strip():
                raise ValueError('event model is required')
            if section in {'snare_drum', 'cymbals'} and model != 'local-bash':
                raise ValueError('Snare/Cymbals observation must be local-bash')
            assigned = score['section_routing'][section]['assigned_model']
            if assigned is not None and assigned != model:
                raise ValueError('observed model differs from score assignment')
            key = event.get('execution_id')
            if not isinstance(key, str) or not key.strip():
                raise ValueError('execution_id is required')
            kind = event.get('event')
            if kind not in {'spawn', 'exit'}:
                raise ValueError('unknown event kind')
            at = timestamp(event.get('ts'))
            if at > now:
                raise ValueError('event timestamp is in the future')
            attempt = attempts.setdefault(key, {})
            if kind in attempt:
                if attempt[kind] != event:
                    raise ValueError('conflicting duplicate event')
                continue
            if kind == 'exit':
                start = attempt.get('spawn')
                if start is None:
                    raise ValueError('exit without a matching spawn')
                if any(event.get(field) != start.get(field) for field in identity):
                    raise ValueError('exit metadata differs from spawn')
                if at < timestamp(start['ts']):
                    raise ValueError('exit precedes spawn')
                code, status = event.get('exit_code'), event.get('status')
                if type(code) is not int or status not in {'ok', 'error', 'timeout'}:
                    raise ValueError('exit requires status and integer exit_code')
                if (status == 'ok') != (code == 0) or (status == 'timeout' and code != 124):
                    raise ValueError('exit status conflicts with exit_code')
            attempt[kind] = event
        except (ValueError, TypeError) as exc:
            errors.append(f'event {number}: {exc}')

    seats = {}
    histories = {}
    for execution_id, attempt in attempts.items():
        if 'spawn' not in attempt:
            continue
        start = attempt['spawn']
        key = (start['movement_index'], start['section'])
        histories.setdefault(key, []).append(attempt)
        if key not in seats or timestamp(start['ts']) >= timestamp(seats[key]['spawn']['ts']):
            seats[key] = dict(attempt, execution_id=execution_id)
    for key, history in histories.items():
        history.sort(key=lambda item: timestamp(item['spawn']['ts']))
        for older, newer in zip(history, history[1:]):
            if 'exit' not in older or timestamp(older['exit']['ts']) > timestamp(newer['spawn']['ts']):
                errors.append(f'movement {key[0]} / {key[1]}: overlapping or unclosed execution attempts')

    movements = []
    for movement in score['movements']:
        chairs = []
        dependencies = [movements[d['movement'] - 1] for d in movement['depends_on']]
        waiting = any(d['state'] != 'success' for d in dependencies)
        for section in movement['active_sections']:
            routing = score['section_routing'][section]
            attempt = seats.get((movement['index'], section))
            state = 'waiting' if waiting else 'unresolved' if routing['resolution'] == 'unresolved' else 'pending'
            elapsed, observed_model, execution_id = None, None, None
            if attempt:
                start, end = attempt['spawn'], attempt.get('exit')
                state = {'ok': 'success', 'error': 'failed', 'timeout': 'timeout'}[end['status']] if end else 'playing'
                finished = timestamp(end['ts']) if end else now
                elapsed = round((finished - timestamp(start['ts'])).total_seconds(), 3)
                observed_model, execution_id = start['model'], attempt['execution_id']
                if waiting:
                    errors.append(f'movement {movement["index"]}: execution observed before dependencies succeeded')
                else:
                    for dependency in movement['depends_on']:
                        previous = score['movements'][dependency['movement'] - 1]
                        for previous_section in previous['active_sections']:
                            prior = seats.get((previous['index'], previous_section), {}).get('exit')
                            if prior and timestamp(prior['ts']) > timestamp(start['ts']):
                                errors.append(f'movement {movement["index"]}: dependency finished after execution started')
            chairs.append(dict(section=section, state=state, tier=routing['tier'],
                               assigned_model=routing['assigned_model'], observed_model=observed_model,
                               resolution=routing['resolution'], elapsed_sec=elapsed,
                               execution_id=execution_id, tokens=0 if section in {'snare_drum', 'cymbals'} else None))
        states = {c['state'] for c in chairs}
        state = next((s for s in ('failed', 'timeout', 'playing', 'waiting', 'unresolved', 'pending') if s in states), 'success')
        movements.append(dict(index=movement['index'], name=movement['name'], state=state,
                              lead_section=movement['lead_section'], chairs=chairs,
                              tacet_sections=movement['tacet_sections'], depends_on=movement['depends_on'],
                              isolation=movement['isolation'], max_turns=movement['max_turns'],
                              circuit_breaker=movement['circuit_breaker']))
    observed = any('spawn' in attempt for attempt in attempts.values())
    state = 'planned'
    if observed:
        states = {m['state'] for m in movements}
        state = 'failed' if states & {'failed', 'timeout'} else 'playing' if 'playing' in states else 'complete' if states == {'success'} else 'paused'
    if errors:
        state = 'degraded'
    focus = next((m['index'] for m in movements if m['state'] in {'playing', 'failed', 'timeout'}), None)
    focus = focus or next((m['index'] for m in movements if m['state'] != 'success'), len(movements))
    snare = {'configured': None, 'passed': None, 'rungs': {}, 'errors': []}
    if root is not None:
        snare_errors, rungs = snare_score(Path(root))
        snare.update(configured=sum(command is not None for command in rungs.values()), rungs=rungs, errors=snare_errors)
    return dict(schema_version=1, ok=not errors, admit=False, score_id=score['score_id'],
                run_id=run_id, summary=score['summary'], style=score['style'], state=state,
                focus=focus, movements=movements, tokens=None, snare=snare, errors=errors,
                ignored_events=ignored, unattributed_events=unattributed,
                observed_at=now.isoformat(), section_routing=score['section_routing'])


def clean(value):
    return ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in str(value))


def cell_width(value):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in {'W', 'F'} else 1 for c in value)


def fit(value, width):
    value = clean(value)
    if cell_width(value) <= width:
        return value
    result, used = '', 0
    for char in value:
        size = cell_width(char)
        if used + size > width - 1:
            break
        result += char
        used += size
    return result + '~'


def render(data, *, width=100, collapsed=False, color=False):
    width = max(40, min(240, width))
    focus = data['movements'][data['focus'] - 1]
    style = data['style'].split('_')[0].title()
    ribbon = f'[Hall] {style} | {data["state"].upper()} | {focus["index"]}:{focus["lead_section"]}'
    lines = [fit(ribbon, width)]
    if not collapsed:
        lines += ['-' * width, fit(data['summary'], width), fit(f'Score: {data["score_id"]}  Run: {data["run_id"] or "(plan only)"}  Tokens: unknown', width)]
        marks = {'success': '+', 'playing': '>', 'failed': '!', 'timeout': '!', 'waiting': '.', 'unresolved': '?', 'pending': '-'}
        for movement in data['movements']:
            lines.append(fit(f'{marks[movement["state"]]} {movement["index"]}. {movement["name"]} [{movement["state"]}]', width))
            for dependency in movement['depends_on']:
                lines.append(fit(f'    {dependency["movement"]} --{dependency["cue"]}--> {movement["index"]} : {dependency["artifact"]}', width))
        lines += ['-' * width, fit(f'Chairs / movement {focus["index"]} / {focus["isolation"]} / turns ?/{focus["max_turns"]}', width)]
        for chair in focus['chairs']:
            elapsed = '?' if chair['elapsed_sec'] is None else f'{chair["elapsed_sec"]:.1f}s'
            model = chair['observed_model'] or chair['assigned_model'] or '(unresolved)'
            lines.append(fit(f'{chair["section"]:<13} {chair["state"]:<10} {elapsed:>7} {model}', width))
            lines.append(fit(f'  tier={chair["tier"]} routing={chair["resolution"]} tokens={chair["tokens"] if chair["tokens"] is not None else "?"}', width))
        # The full muted roster wraps at word boundaries to preserve every seat.
        line = 'Tacet: '
        for section in focus['tacet_sections']:
            if cell_width(line + section + ' ') > width:
                lines.append(line.rstrip()); line = '       '
            line += section + ' '
        lines.append(line.rstrip())
        configured = data['snare']['configured']
        lines.append(fit(f'Snare: configured {configured if configured is not None else "?"}/4 | passed ?/4 | breaker {"armed" if focus["circuit_breaker"] else "standby"}', width))
        if data['unattributed_events']:
            lines.append(fit(f'Unattributed legacy events: {data["unattributed_events"]}', width))
        for error in data['errors'] + data['snare']['errors']:
            lines.append(fit(f'! {error}', width))
        lines.append(fit('Playing = start observed; exit not yet observed.', width))
        lines.append(fit('Read-only observation | elapsed != token usage | pass != admit', width))
    if color:
        code = '31' if data['state'] in {'degraded', 'failed'} else '36'
        lines[0] = f'\x1b[{code}m{lines[0]}\x1b[0m'
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--score', required=True)
    parser.add_argument('--events', help='Supervised JSONL log; requires --run-id')
    parser.add_argument('--run-id', help='Filter one execution run; metadata only, not admission')
    parser.add_argument('--root', help='Inspect target AGENTS.md ladder without executing commands')
    parser.add_argument('--json', action='store_true', help='Service snapshot; JSONL during --watch')
    parser.add_argument('--collapsed', action='store_true', help='Single-line Org-Graph ribbon')
    parser.add_argument('--width', type=int, default=shutil.get_terminal_size((100, 24)).columns)
    parser.add_argument('--color', choices=('auto', 'always', 'never'), default='auto')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--frames', type=int, help='Stop watch after this many snapshots')
    args = parser.parse_args(argv)
    if args.events and not args.run_id:
        parser.error('--events requires --run-id')
    if not 0.2 <= args.interval <= 60 or (args.frames is not None and args.frames < 1):
        parser.error('interval must be 0.2..60 seconds and frames must be positive')
    frame, code = 0, 0
    try:
        while True:
            try:
                events, errors = read_events(args.events) if args.events else ([], [])
                data = snapshot(read_json(args.score), events, args.run_id, root=args.root, input_errors=errors)
                code = 0 if data['ok'] else 2
                output = json.dumps(data, ensure_ascii=False, indent=None if args.watch else 2) if args.json else render(
                    data, width=args.width, collapsed=args.collapsed,
                    color=args.color == 'always' or (args.color == 'auto' and sys.stdout.isatty()))
            except (ValueError, OSError) as exc:
                code = 2
                output = json.dumps({'ok': False, 'admit': False, 'errors': [str(exc)]}) if args.json else fit(f'Concert Hall unavailable: {exc}', max(40, min(240, args.width)))
            if args.watch and sys.stdout.isatty() and not args.json:
                sys.stdout.write('\x1b[2J\x1b[H')
            print(output, flush=True)
            frame += 1
            if not args.watch or (args.frames and frame >= args.frames):
                return code
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
