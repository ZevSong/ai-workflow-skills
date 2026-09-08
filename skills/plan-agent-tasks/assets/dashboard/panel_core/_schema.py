"""Pure v1 progress state contract, independent of files, clocks and hosts."""

from datetime import datetime, timedelta
import re
from urllib.parse import urlsplit


class ContractError(ValueError):
    """The supplied state or event violates the v1 contract."""


PLAN_FIELDS = 'packet source main tasks sessions stages checks evidence dependencies'.split()
DEFINITION_FIELDS = 'tasks sessions stages checks dependencies'.split()
STATE_FIELDS = PLAN_FIELDS + 'schema_version tool_version seq generated_at observed_at events history'.split()
TASK_STATUSES = 'pending ready implementing fixing validating awaiting_review reviewing waiting_approval blocked failed done cancelled'.split()
LIFECYCLES = 'planned running waiting_user blocked finished'.split()
HOST_STATUSES = 'planned running idle waiting_user blocked completed failed stopped unknown'.split()
FIELDS = {
    'packet': 'id title mode run_number plan_revision lifecycle stage_id stop_condition'.split(),
    'source': 'mode reference available checked_at'.split(),
    'main': 'logical_id session_id status observed_at'.split(),
    'task': 'id title stage_id status round progress progress_at blocker next_action session_ids required_check_ids'.split(),
    'session': 'task_id role planned_name actual_name actual_id host_status observed_at round planned_model actual_model replaces'.split(),
    'stage': 'title task_ids status approved approval_evidence_ids'.split(),
    'check': 'task_id kind role_id round applicable result evidence_ids not_applicable_reason'.split(),
    'evidence': 'title reference'.split(),
    'dependency': 'from to required_check_ids'.split(),
    'event': 'event_id expected_seq occurred_at observed_at summary ops'.split(),
    'record': 'event_id seq occurred_at received_at summary body'.split(),
}


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _object(value, fields, label, *, partial=False):
    _require(type(value) is dict, f'{label}: expected object')
    _require(all(type(key) is str for key in value), f'{label}: keys must be strings')
    unknown = set(value) - set(fields)
    _require(not unknown, f'Unknown field in {label}: {sorted(unknown)}')
    if not partial:
        _require(set(fields) <= set(value), f'Missing field in {label}: {sorted(set(fields) - set(value))}')


def _text(value, label, *, nullable=False, empty=False):
    if nullable and value is None:
        return
    _require(type(value) is str and (empty or bool(value.strip())), f'{label}: expected nonempty string')


def _integer(value, label, minimum=0):
    _require(type(value) is int and value >= minimum, f'{label}: expected integer >= {minimum}')


def _boolean(value, label):
    _require(type(value) is bool, f'{label}: expected boolean')


def _enum(value, choices, label):
    _text(value, label)
    _require(value in choices, f'{label}: invalid value {value!r}')


def _time(value, label, *, nullable=True):
    if nullable and value is None:
        return None
    _text(value, label)
    _require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)', value)), f'{label}: expected ISO 8601 UTC time')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ContractError(f'{label}: invalid time') from exc
    _require(result.utcoffset() == timedelta(0), f'{label}: expected UTC')
    return result


def _ids(value, label, *, nonempty=False):
    _require(type(value) is list, f'{label}: expected list')
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), f'{label}: duplicate identity')
    _require(not nonempty or bool(value), f'{label}: cannot be empty')


def _mapping(value, label):
    _require(type(value) is dict, f'{label}: expected object')
    for key in value:
        _text(key, f'{label} key')


def _reference(value, label):
    _require(type(value) is dict, f'{label}: expected reference object')
    if set(value) == {'url'}:
        _text(value['url'], label)
        try:
            url = urlsplit(value['url'])
            valid = url.scheme in ('http', 'https') and bool(url.hostname) and not url.username and not url.password
            url.port
        except ValueError as exc:
            raise ContractError(f'{label}: invalid URL') from exc
        _require(valid and not any(c.isspace() for c in value['url']), f'{label}: expected HTTP(S) URL without credentials')
    else:
        _object(value, ('repository', 'path'), label)
        _text(value['repository'], label)
        _text(value['path'], label)
        path = value['path'].replace('\\', '/')
        _require(not path.startswith('/') and ':' not in path and all(part not in ('', '.', '..') for part in path.split('/')), f'{label}: expected repository-relative path')


def _model(value, label):
    if value is None:
        return
    _object(value, ('provider', 'model', 'reasoning_effort', 'service_tier'), label)
    for key, item in value.items():
        _text(item, f'{label}.{key}', nullable=True)


def _exists(identity, collection, label, *, nullable=False):
    if nullable and identity is None:
        return
    _text(identity, label)
    _require(identity in collection, f'{label}: unknown reference {identity}')


def _check_complete(state, check_id, task_id):
    _exists(check_id, state['checks'], 'check')
    check = state['checks'][check_id]
    _require(check['task_id'] == task_id, f'Wrong task for check: {check_id}')
    if not check['applicable']:
        _require(bool(check['not_applicable_reason']), f'Missing exemption reason: {check_id}')
        return
    _require(check['round'] == state['tasks'][task_id]['round'] and check['result'] == 'PASS', f'Incomplete current-round check: {check_id}')
    _require(bool(check['evidence_ids']), f'Missing evidence: {check_id}')
    for evidence_id in check['evidence_ids']:
        _exists(evidence_id, state['evidence'], 'evidence')


def ensure_done_allowed(state: dict, task_id: str) -> None:
    """Validate every declared completion dimension; do not infer review results."""
    _exists(task_id, state['tasks'], 'task')
    task = state['tasks'][task_id]
    _ids(task['required_check_ids'], 'required_check_ids', nonempty=True)
    for check_id in task['required_check_ids']:
        _check_complete(state, check_id, task_id)


def validate_state(state: dict) -> None:
    """Validate the complete v1 snapshot, including references and archived runs."""
    _object(state, STATE_FIELDS, 'state')
    _integer(state['schema_version'], 'schema_version')
    _require(state['schema_version'] == 1, 'Unsupported schema_version')
    _require(state['tool_version'] == '0.1.0', 'Unsupported tool_version')
    _integer(state['seq'], 'seq')
    _time(state['generated_at'], 'generated_at', nullable=False)
    _time(state['observed_at'], 'observed_at')
    for name in ('packet', 'source', 'main'):
        _object(state[name], FIELDS[name], name)
    packet, source, main = state['packet'], state['source'], state['main']
    for key in ('id', 'title', 'stop_condition'):
        _text(packet[key], f'packet.{key}')
    _enum(packet['mode'], ('auto', 'semi-auto', 'manual'), 'packet.mode')
    _enum(packet['lifecycle'], LIFECYCLES, 'packet.lifecycle')
    for key in ('run_number', 'plan_revision'):
        _integer(packet[key], f'packet.{key}', 1)
    _enum(source['mode'], ('local', 'projection'), 'source.mode')
    _reference(source['reference'], 'source.reference')
    _boolean(source['available'], 'source.available')
    _time(source['checked_at'], 'source.checked_at')
    _text(main['logical_id'], 'main.logical_id')
    _text(main['session_id'], 'main.session_id', nullable=True)
    _enum(main['status'], LIFECYCLES + ['stopped', 'unknown'], 'main.status')
    _time(main['observed_at'], 'main.observed_at')
    for name in ('tasks', 'sessions', 'stages', 'checks', 'evidence'):
        _mapping(state[name], name)
        singular = {'tasks': 'task', 'sessions': 'session', 'stages': 'stage', 'checks': 'check', 'evidence': 'evidence'}[name]
        for identity, value in state[name].items():
            _object(value, FIELDS[singular], f'{name}.{identity}')
    tasks, sessions, stages, checks = (state[k] for k in ('tasks', 'sessions', 'stages', 'checks'))
    _require(main['logical_id'] not in sessions, 'Duplicate Main logical identity')
    _exists(packet['stage_id'], stages, 'packet.stage_id', nullable=True)
    for identity, item in state['evidence'].items():
        _text(item['title'], f'evidence.{identity}.title')
        _reference(item['reference'], f'evidence.{identity}.reference')
    for identity, task in tasks.items():
        _require(task['id'] == identity, f'Task id must match key: {identity}')
        _text(task['title'], f'{identity}.title')
        _enum(task['status'], TASK_STATUSES, f'{identity}.status')
        _integer(task['round'], f'{identity}.round', 1)
        _exists(task['stage_id'], stages, 'task.stage_id', nullable=True)
        for key in ('progress', 'next_action'):
            _text(task[key], f'{identity}.{key}', empty=True)
        _text(task['blocker'], f'{identity}.blocker', nullable=True)
        _require(task['status'] != 'blocked' or bool(task['blocker']), f'Missing blocker: {identity}')
        _time(task['progress_at'], f'{identity}.progress_at')
        _ids(task['session_ids'], f'{identity}.session_ids')
        _ids(task['required_check_ids'], f'{identity}.required_check_ids', nonempty=True)
        for role_id in task['session_ids']:
            _exists(role_id, sessions, 'task.session_ids')
            _require(sessions[role_id]['task_id'] == identity, f'Wrong task for role: {role_id}')
        for check_id in task['required_check_ids']:
            _exists(check_id, checks, 'task.required_check_ids')
            _require(checks[check_id]['task_id'] == identity, f'Wrong task for check: {check_id}')
    actual_ids = {main['session_id']} if main['session_id'] is not None else set()
    for identity, session in sessions.items():
        _exists(session['task_id'], tasks, 'session.task_id')
        _require(identity in tasks[session['task_id']]['session_ids'], f'Role missing from task.session_ids: {identity}')
        _enum(session['role'], ('worker', 'reviewer'), f'{identity}.role')
        _text(session['planned_name'], f'{identity}.planned_name')
        for key in ('actual_name', 'actual_id'):
            _text(session[key], f'{identity}.{key}', nullable=True)
        if session['actual_id'] is not None:
            _require(session['actual_id'] not in actual_ids, f'Duplicate actual_id: {identity}')
            actual_ids.add(session['actual_id'])
        _enum(session['host_status'], HOST_STATUSES, f'{identity}.host_status')
        _time(session['observed_at'], f'{identity}.observed_at')
        _integer(session['round'], f'{identity}.round', 1)
        _require(session['round'] <= tasks[session['task_id']]['round'], f'Future session round: {identity}')
        for key in ('planned_model', 'actual_model'):
            _model(session[key], f'{identity}.{key}')
        _exists(session['replaces'], sessions, 'session.replaces', nullable=True)
        if session['replaces'] is not None:
            replaced = sessions[session['replaces']]
            _require(session['replaces'] != identity and replaced['task_id'] == session['task_id'] and replaced['role'] == session['role'], f'Invalid replacement role: {identity}')
    for identity in sessions:
        seen, current = set(), identity
        while current is not None:
            _require(current not in seen, 'Session replacement cycle')
            seen.add(current)
            current = sessions[current]['replaces']
    for identity, stage in stages.items():
        _text(stage['title'], f'{identity}.title')
        _enum(stage['status'], ('pending', 'active', 'waiting_approval', 'blocked', 'done', 'cancelled'), f'{identity}.status')
        _boolean(stage['approved'], f'{identity}.approved')
        _ids(stage['task_ids'], f'{identity}.task_ids')
        _ids(stage['approval_evidence_ids'], f'{identity}.approval_evidence_ids')
        _require(not stage['approved'] or bool(stage['approval_evidence_ids']), f'Missing approval evidence: {identity}')
        for evidence_id in stage['approval_evidence_ids']:
            _exists(evidence_id, state['evidence'], 'stage.approval_evidence_ids')
        for task_id in stage['task_ids']:
            _exists(task_id, tasks, 'stage.task_ids')
            _require(tasks[task_id]['stage_id'] == identity, f'Inconsistent stage membership: {task_id}')
    for identity, task in tasks.items():
        if task['stage_id'] is not None:
            _require(identity in stages[task['stage_id']]['task_ids'], f'Task missing from stage: {identity}')
    for identity, check in checks.items():
        _exists(check['task_id'], tasks, 'check.task_id')
        _enum(check['kind'], ('delivery', 'review', 'approval', 'test', 'integration', 'acceptance'), f'{identity}.kind')
        _exists(check['role_id'], {**sessions, main['logical_id']: main}, 'check.role_id')
        if check['role_id'] in sessions:
            role = sessions[check['role_id']]
            _require(role['task_id'] == check['task_id'], f'Wrong task for check role: {identity}')
        if check['kind'] == 'review':
            _require(check['role_id'] in sessions and sessions[check['role_id']]['role'] == 'reviewer', f'Review requires an independent reviewer: {identity}')
        _integer(check['round'], f'{identity}.round', 1)
        _require(check['round'] <= tasks[check['task_id']]['round'], f'Future check round: {identity}')
        _boolean(check['applicable'], f'{identity}.applicable')
        _text(check['not_applicable_reason'], f'{identity}.not_applicable_reason', nullable=True)
        if check['applicable']:
            _enum(check['result'], ('PASS', 'FAIL', 'UNRUN', 'BLOCKED'), f'{identity}.result')
            _require(check['not_applicable_reason'] is None, f'Applicable check has exemption reason: {identity}')
        else:
            _require(bool(check['not_applicable_reason']), f'Missing exemption reason: {identity}')
            _require(check['result'] is None, f'Non-applicable result must be null: {identity}')
        _ids(check['evidence_ids'], f'{identity}.evidence_ids')
        for evidence_id in check['evidence_ids']:
            _exists(evidence_id, state['evidence'], 'check.evidence_ids')
        if check['kind'] == 'approval' and check['result'] == 'PASS':
            _require(bool(check['evidence_ids']), f'Missing approval evidence: {identity}')
    _require(type(state['dependencies']) is list, 'dependencies: expected list')
    edges, graph = set(), {identity: [] for identity in tasks}
    for edge in state['dependencies']:
        _object(edge, FIELDS['dependency'], 'dependency')
        for key in ('from', 'to'):
            _exists(edge[key], tasks, f'dependency.{key}')
        pair = (edge['from'], edge['to'])
        _require(pair not in edges, 'Duplicate dependency')
        edges.add(pair)
        graph[edge['from']].append(edge['to'])
        _ids(edge['required_check_ids'], 'dependency.required_check_ids')
        for check_id in edge['required_check_ids']:
            _exists(check_id, checks, 'dependency check')
            _require(checks[check_id]['task_id'] == edge['from'], f'Dependency check must belong to predecessor: {check_id}')
    indegrees = dict.fromkeys(tasks, 0)
    for children in graph.values():
        for child in children:
            indegrees[child] += 1
    queue = [key for key, degree in indegrees.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in graph[current]:
            indegrees[child] -= 1
            if indegrees[child] == 0:
                queue.append(child)
    _require(visited == len(tasks), 'Dependency cycle')
    for identity, task in tasks.items():
        if task['status'] == 'done':
            ensure_done_allowed(state, identity)
    _validate_records(state)
    _require(type(state['history']) is list, 'history: expected list')
    previous_run = 0
    for archived in state['history']:
        _object(archived, [key for key in STATE_FIELDS if key != 'history'], 'archived state')
        validate_state({**archived, 'history': []})
        _require(archived['packet']['id'] == packet['id'], 'Archived packet identity mismatch')
        run = archived['packet']['run_number']
        _integer(run, 'archived run_number', 1)
        _require(previous_run < run < packet['run_number'], 'Invalid archived run order')
        previous_run = run


def _event_shape(event):
    _object(event, FIELDS['event'], 'event')
    _text(event['event_id'], 'event_id')
    _integer(event['expected_seq'], 'expected_seq')
    _time(event['occurred_at'], 'occurred_at', nullable=False)
    _time(event['observed_at'], 'observed_at')
    _text(event['summary'], 'summary')
    _require(type(event['ops']) is list, 'ops: expected list')
    for op in event['ops']:
        _require(type(op) is dict and type(op.get('type')) is str, 'Invalid operation')
        kind = op['type']
        if kind in ('plan.replace', 'run.start'):
            _object(op, ('type', 'plan'), kind)
            _object(op['plan'], DEFINITION_FIELDS if kind == 'plan.replace' else PLAN_FIELDS, kind + '.plan')
        elif kind == 'evidence.put':
            _object(op, ('type', 'id', 'evidence'), kind)
            _text(op['id'], kind + '.id')
            _object(op['evidence'], FIELDS['evidence'], kind)
        elif kind in ('task.set', 'session.set', 'stage.set', 'check.set', 'main.set', 'source.set'):
            fields = ['type', 'changes'] + ([] if kind in ('main.set', 'source.set') else ['id'])
            _object(op, fields + (['reason'] if kind == 'task.set' else []), kind, partial=True)
            _require(set(fields) <= set(op), f'Missing operation field: {kind}')
            if 'id' in op:
                _text(op['id'], kind + '.id')
            if 'reason' in op:
                _text(op['reason'], 'reason')
            entity = kind.split('.')[0]
            immutable = {
                'task': {'id', 'stage_id', 'session_ids', 'required_check_ids'},
                'session': {'task_id', 'role', 'replaces'},
                'stage': {'task_ids'},
                'check': {'task_id', 'kind', 'role_id'},
                'main': {'logical_id'},
                'source': {'mode', 'reference'},
            }[entity]
            _object(op['changes'], set(FIELDS[entity]) - immutable, kind + '.changes', partial=True)
        else:
            raise ContractError(f'Unknown operation: {kind}')


def _validate_records(state):
    _require(type(state['events']) is list, 'events: expected list')
    seen, previous = set(), 0
    for record in state['events']:
        _object(record, FIELDS['record'], 'event record')
        _event_shape(record['body'])
        _integer(record['seq'], 'event seq', 1)
        _require(previous < record['seq'] <= state['seq'], 'Invalid event sequence')
        previous = record['seq']
        _require(record['body']['expected_seq'] == record['seq'] - 1, 'Event sequence/body mismatch')
        for key in ('event_id', 'occurred_at', 'summary'):
            _require(record[key] == record['body'][key], f'Event record/body mismatch: {key}')
        _time(record['received_at'], 'received_at', nullable=False)
        _require(record['event_id'] not in seen, 'Duplicate event_id')
        seen.add(record['event_id'])


