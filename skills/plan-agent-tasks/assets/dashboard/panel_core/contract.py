"""Pure v1 progress operations, independent of files, clocks and hosts."""

from copy import deepcopy

from ._schema import (
    ContractError, DEFINITION_FIELDS, FIELDS, LIFECYCLES, PLAN_FIELDS,
    _event_shape, _exists, _integer, _mapping, _object, _require, _time,
    ensure_done_allowed, validate_state,
)

__all__ = [
    "ContractError", "validate_state", "initial_state", "apply_event",
    "ensure_done_allowed",
]

def initial_state(plan: dict, now: str) -> dict:
    """Construct a planned snapshot without inventing execution observations."""
    _object(plan, PLAN_FIELDS, 'plan')
    state = deepcopy(plan)
    state.update(schema_version=1, tool_version='0.1.0', seq=0, generated_at=now, observed_at=None, events=[], history=[])
    validate_state(state)
    packet, main = state['packet'], state['main']
    _require(packet['lifecycle'] == 'planned' and packet['plan_revision'] == 1 and packet['run_number'] == 1, 'Initialization requires planned run 1, revision 1')
    _require(main['status'] == 'planned' and main['session_id'] is None and main['observed_at'] is None, 'Initialization requires planned Main')
    for task in state['tasks'].values():
        _require(task['status'] == 'pending' and task['round'] == 1 and task['progress_at'] is None and task['blocker'] is None, 'Initialization requires planned tasks')
    for session in state['sessions'].values():
        _require(session['host_status'] == 'planned' and session['round'] == 1 and all(session[key] is None for key in ('actual_name', 'actual_id', 'actual_model', 'observed_at', 'replaces')), 'Initialization requires planned sessions')
    for stage in state['stages'].values():
        _require(stage['status'] == 'pending' and not stage['approved'] and not stage['approval_evidence_ids'], 'Initialization requires planned stages')
    for check in state['checks'].values():
        _require(check['round'] == 1 and (check['result'] == 'UNRUN' or not check['applicable']) and not check['evidence_ids'], 'Initialization requires planned checks')
    _require(not state['evidence'], 'Initialization requires planned evidence')
    return state


def _monotonic(old, new, label):
    old_time, new_time = _time(old, label), _time(new, label)
    _require(old_time is None or (new_time is not None and new_time >= old_time), f'{label} cannot move backwards')


def _older(old, new, label):
    old_time, new_time = _time(old, label), _time(new, label)
    return old_time is not None and new_time is not None and new_time < old_time


def _replace_plan(state, plan):
    # Full snapshots make every retained result inspectable. Executed objects must
    # remain present (tasks may be cancelled) instead of silently disappearing.
    for collection in ('tasks', 'sessions', 'stages', 'checks'):
        _mapping(plan[collection], collection)
        for identity, old in state[collection].items():
            executed = {
                'tasks': lambda: old['status'] not in ('pending', 'ready') or old['round'] > 1 or old['progress_at'] is not None,
                'sessions': lambda: old['actual_id'] is not None or old['observed_at'] is not None or old['host_status'] != 'planned',
                'stages': lambda: old['approved'] or old['status'] != 'pending',
                'checks': lambda: old['result'] not in ('UNRUN', None) or bool(old['evidence_ids']),
            }[collection]()
            _require(not executed or identity in plan[collection], f'Cannot remove executed {collection}: {identity}')
    old_tasks, old_checks = state['tasks'], state['checks']
    candidate = deepcopy(state)
    candidate.update(deepcopy(plan))
    candidate['packet']['plan_revision'] += 1
    # Validate shapes/references before inspecting cross-object definitions.
    for task in candidate['tasks'].values():
        if type(task) is dict and task.get('status') == 'done':
            task['status'] = 'pending'
    validate_state(candidate)
    for identity in set(state['sessions']) & set(plan['sessions']):
        old, new = state['sessions'][identity], plan['sessions'][identity]
        for key in ('task_id', 'role', 'actual_name', 'actual_id', 'host_status', 'observed_at', 'round', 'actual_model', 'replaces'):
            _require(old[key] == new[key], f'plan.replace must preserve session observation: {identity}.{key}')
    for identity in set(old_tasks) & set(plan['tasks']):
        old, new = old_tasks[identity], plan['tasks'][identity]
        _require(new['round'] >= old['round'], f'Task round cannot move backwards: {identity}')
        changed = any(old[key] != new[key] for key in ('required_check_ids', 'stage_id'))
        changed |= [edge for edge in state['dependencies'] if edge['to'] == identity] != [edge for edge in plan['dependencies'] if edge['to'] == identity]
        for check_id in set(old['required_check_ids']) | set(new['required_check_ids']):
            before, after = old_checks.get(check_id), plan['checks'].get(check_id)
            changed |= before is None or after is None or any(before[key] != after[key] for key in ('task_id', 'kind', 'role_id', 'applicable', 'not_applicable_reason'))
        if changed:
            _require(new['round'] > old['round'], f'Changed requirements need a new task round: {identity}')
    for identity in set(old_checks) & set(plan['checks']):
        old, new = old_checks[identity], plan['checks'][identity]
        # Results are observations, not editable plan definitions. Recheck via
        # check.set in a later event after the new plan has been accepted.
        for key in ('round', 'result', 'evidence_ids'):
            _require(old[key] == new[key], f'plan.replace must preserve check result: {identity}.{key}')
    state.update(deepcopy(plan))
    state['packet']['plan_revision'] += 1


def apply_event(state: dict, event: dict, received_at: str) -> dict:
    """Apply an atomic event on a copy; exact retries do not create new work."""
    validate_state(state)
    _event_shape(event)
    _time(received_at, 'received_at', nullable=False)
    for snapshot in [state] + state['history']:
        for record in snapshot['events']:
            if record['event_id'] == event['event_id']:
                _require(record['body'] == event, 'Event id already used with different body')
                return deepcopy(state)
    _require(event['expected_seq'] == state['seq'], 'expected_seq conflict')
    _monotonic(state['observed_at'], event['observed_at'], 'Main observed_at')
    result = deepcopy(state)
    if any(op['type'] == 'run.start' for op in event['ops']):
        _require(len(event['ops']) == 1, 'run.start must be the only operation')
    for op in event['ops']:
        kind = op['type']
        if kind == 'plan.replace':
            _replace_plan(result, op['plan'])
        elif kind == 'run.start':
            _require(result['packet']['lifecycle'] == 'finished' or result['main']['status'] == 'stopped', 'run.start requires a finished or explicitly stopped run')
            plan = deepcopy(op['plan'])
            _object(plan['packet'], FIELDS['packet'], 'run.start.packet')
            _object(plan['source'], FIELDS['source'], 'run.start.source')
            _integer(plan['packet']['run_number'], 'run.start.run_number', 1)
            _require(plan['packet']['id'] == result['packet']['id'], 'run.start cannot change packet identity')
            _require(plan['packet']['run_number'] == result['packet']['run_number'] + 1, 'run.start requires next run_number')
            _require(plan['source']['mode'] == result['source']['mode'] and plan['source']['reference'] == result['source']['reference'], 'run.start cannot change source authority')
            next_run = plan['packet']['run_number']
            plan['packet']['run_number'] = 1
            fresh = initial_state(plan, received_at)
            fresh['packet']['run_number'] = next_run
            archived = {key: deepcopy(value) for key, value in result.items() if key != 'history'}
            fresh['history'] = deepcopy(result['history']) + [archived]
            fresh['seq'] = result['seq']
            result = fresh
        elif kind == 'evidence.put':
            existing = result['evidence'].get(op['id'])
            _require(existing is None or existing == op['evidence'], f'Cannot overwrite evidence: {op["id"]}')
            result['evidence'][op['id']] = deepcopy(op['evidence'])
        else:
            entity = kind.split('.')[0]
            if entity in ('main', 'source'):
                target = result[entity]
            else:
                collection = {'task': 'tasks', 'session': 'sessions', 'stage': 'stages', 'check': 'checks'}[entity]
                _require(op['id'] in result[collection], f'Unknown {entity}: {op["id"]}')
                target = result[collection][op['id']]
            changes = deepcopy(op['changes'])
            if entity == 'task':
                if 'round' in changes:
                    _integer(changes['round'], 'task round', 1)
                    _require(changes['round'] > target['round'], 'Task round must increase')
                    _require(bool(op.get('reason')), 'Task round change requires reason')
                if any(key in changes for key in ('status', 'progress', 'blocker', 'next_action', 'round')):
                    changes.setdefault('progress_at', event['occurred_at'])
                if 'progress_at' in changes:
                    if _older(target['progress_at'], changes['progress_at'], 'Task progress_at'):
                        continue  # Keep the report in events without replacing newer progress.
                    _monotonic(target['progress_at'], changes['progress_at'], 'Task progress_at')
            if entity == 'session':
                if 'round' in changes:
                    _integer(changes['round'], 'session round', 1)
                    _require(changes['round'] >= target['round'], 'Session round cannot move backwards')
                changes.setdefault('observed_at', event['occurred_at'])
                if _older(target['observed_at'], changes['observed_at'], 'Session observed_at'):
                    continue
                _monotonic(target['observed_at'], changes['observed_at'], 'Session observed_at')
            if entity == 'check' and 'round' in changes:
                _integer(changes['round'], 'check round', 1)
                _require(changes['round'] >= target['round'], 'Check round cannot move backwards')
                if changes['round'] > target['round']:
                    _require('result' in changes and 'evidence_ids' in changes, 'New check round requires an explicit result and evidence_ids')
            if entity == 'main' and 'observed_at' in changes:
                _monotonic(target['observed_at'], changes['observed_at'], 'Main observation')
            if entity == 'source' and 'checked_at' in changes:
                _monotonic(target['checked_at'], changes['checked_at'], 'Source checked_at')
            target.update(changes)
            if entity == 'main' and 'status' in changes:
                status = changes['status']
                if status in LIFECYCLES:
                    result['packet']['lifecycle'] = status
                elif status == 'stopped':
                    result['packet']['lifecycle'] = 'blocked'
    result['generated_at'] = received_at
    result['observed_at'] = event['observed_at']
    # Main's explicit observation may be more recent, but cannot be regressed by
    # an implicit heartbeat from an older report.
    if event['observed_at'] is not None:
        _monotonic(result['main']['observed_at'], event['observed_at'], 'Main observation')
        result['main']['observed_at'] = event['observed_at']
    result['seq'] = state['seq'] + 1
    result['events'].append({
        'event_id': event['event_id'], 'seq': result['seq'],
        'occurred_at': event['occurred_at'], 'received_at': received_at,
        'summary': event['summary'], 'body': deepcopy(event),
    })
    validate_state(result)
    return result
