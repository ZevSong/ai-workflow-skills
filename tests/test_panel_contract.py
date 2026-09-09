"""Behavior tests for the progress-panel state contract."""

from copy import deepcopy
import unittest

from panel_fixtures import NOW, make_event, make_state
from panel_core.contract import ContractError, apply_event, ensure_done_allowed, initial_state, validate_state


def evidence(reference: dict | None = None) -> dict:
    return {
        "title": "Checked result",
        "reference": reference or {"repository": "demo", "path": "reports/result.md"},
    }


def pass_required_ops(state: dict, task_id: str, *, omit: str | None = None) -> list[dict]:
    ops = []
    for check_id in state["tasks"][task_id]["required_check_ids"]:
        if check_id == omit:
            continue
        evidence_id = f"E-{check_id}"
        ops.extend(
            [
                {"type": "evidence.put", "id": evidence_id, "evidence": evidence()},
                {
                    "type": "check.set",
                    "id": check_id,
                    "changes": {"result": "PASS", "evidence_ids": [evidence_id]},
                },
            ]
        )
    return ops


def initial_plan() -> dict:
    state = make_state()
    return {key: deepcopy(state[key]) for key in (
        "packet", "source", "main", "tasks", "sessions", "stages", "checks", "evidence", "dependencies"
    )}


class ContractTests(unittest.TestCase):
    def test_conflicts_have_a_distinct_type_from_malformed_input(self):
        from panel_core import contract
        self.assertTrue(hasattr(contract, "ContractConflictError"), "Typed conflict exception missing")
        state = make_state()
        with self.assertRaises(contract.ContractConflictError):
            apply_event(state, make_event("stale", 9, []), NOW)
        event = make_event("first", 0, [])
        state = apply_event(state, event, NOW)
        changed = deepcopy(event)
        changed["summary"] = "different body"
        with self.assertRaises(contract.ContractConflictError):
            apply_event(state, changed, NOW)
        malformed = deepcopy(changed)
        malformed["ops"] = "not operations"
        with self.assertRaises(ContractError) as caught:
            apply_event(state, malformed, NOW)
        self.assertNotIsInstance(caught.exception, contract.ContractConflictError)
        self.assertEqual(apply_event(state, event, NOW), state)

    def test_delivery_cannot_imply_done(self):
        state = make_state()
        event = make_event("premature-done", 0, [
            {"type": "task.set", "id": "DEMO-001", "changes": {"status": "done"}}
        ])
        with self.assertRaises(ContractError):
            apply_event(state, event, NOW)
        self.assertEqual(state["seq"], 0)
        self.assertEqual(state["tasks"]["DEMO-001"]["status"], "pending")

    def test_all_independent_reviewers_are_required(self):
        state = make_state()
        ops = pass_required_ops(state, "DEMO-001", omit="DEMO-001-REVIEW-B")
        ops.append({"type": "task.set", "id": "DEMO-001", "changes": {"status": "done"}})
        with self.assertRaisesRegex(ContractError, "DEMO-001-REVIEW-B"):
            apply_event(state, make_event("one-review-missing", 0, ops), NOW)

    def test_current_round_passes_with_evidence_allow_done(self):
        state = make_state()
        ops = pass_required_ops(state, "DEMO-001")
        ops.append({"type": "task.set", "id": "DEMO-001", "changes": {"status": "done"}})
        updated = apply_event(state, make_event("complete-task", 0, ops), NOW)
        self.assertEqual(updated["tasks"]["DEMO-001"]["status"], "done")
        self.assertEqual(updated["seq"], 1)
        self.assertEqual(state["seq"], 0)

    def test_round_change_requires_a_reason_and_invalidates_old_results(self):
        state = make_state()
        completed = apply_event(
            state,
            make_event("passes", 0, pass_required_ops(state, "DEMO-001")),
            NOW,
        )
        with self.assertRaisesRegex(ContractError, "reason"):
            apply_event(completed, make_event("round-without-reason", 1, [
                {"type": "task.set", "id": "DEMO-001", "changes": {"round": 2}}
            ]), NOW)
        changed = apply_event(completed, make_event("new-round", 1, [
            {
                "type": "task.set",
                "id": "DEMO-001",
                "reason": "Review requested changes",
                "changes": {"round": 2, "status": "fixing"},
            }
        ]), NOW)
        with self.assertRaisesRegex(ContractError, "current-round"):
            ensure_done_allowed(changed, "DEMO-001")

    def test_non_applicable_check_requires_reason(self):
        state = make_state()
        check = state["checks"]["DEMO-001-REVIEW-B"]
        check.update({"applicable": False, "result": None, "not_applicable_reason": None})
        with self.assertRaisesRegex(ContractError, "exemption reason"):
            validate_state(state)

    def test_reasoned_non_applicable_check_can_satisfy_requirement(self):
        state = make_state()
        ops = pass_required_ops(state, "DEMO-001", omit="DEMO-001-REVIEW-B")
        ops.extend([
            {
                "type": "check.set",
                "id": "DEMO-001-REVIEW-B",
                "changes": {
                    "applicable": False,
                    "result": None,
                    "not_applicable_reason": "The approved profile requires one reviewer",
                },
            },
            {"type": "task.set", "id": "DEMO-001", "changes": {"status": "done"}},
        ])
        updated = apply_event(state, make_event("approved-exemption", 0, ops), NOW)
        self.assertEqual(updated["tasks"]["DEMO-001"]["status"], "done")

    def test_task_and_check_enums_cannot_be_confused(self):
        state = make_state()
        state["tasks"]["DEMO-001"]["status"] = "PASS"
        with self.assertRaises(ContractError):
            validate_state(state)
        state = make_state()
        state["checks"]["DEMO-001-DELIVERY"]["result"] = "done"
        with self.assertRaises(ContractError):
            validate_state(state)

    def test_unknown_schema_and_unknown_fields_are_rejected(self):
        state = make_state()
        state["schema_version"] = 2
        with self.assertRaisesRegex(ContractError, "schema_version"):
            validate_state(state)
        state = make_state()
        state["packet"]["surprise"] = True
        with self.assertRaisesRegex(ContractError, "Unknown field"):
            validate_state(state)

    def test_bad_time_and_non_utc_time_are_rejected(self):
        for timestamp in ("yesterday", "2026-09-08T08:00:00+08:00", "2026-09-08"):
            with self.subTest(timestamp=timestamp):
                state = make_state()
                state["generated_at"] = timestamp
                with self.assertRaises(ContractError):
                    validate_state(state)

    def test_reference_shape_and_missing_evidence_reference_are_rejected(self):
        state = make_state()
        state["source"]["reference"] = {"repository": "demo", "path": "/private/report.md"}
        with self.assertRaises(ContractError):
            validate_state(state)
        state = make_state()
        state["checks"]["DEMO-001-DELIVERY"]["evidence_ids"] = ["E-MISSING"]
        with self.assertRaisesRegex(ContractError, "E-MISSING"):
            validate_state(state)

    def test_http_reference_must_be_http_or_https(self):
        state = make_state()
        state["source"]["reference"] = {"url": "file:///private/report.md"}
        with self.assertRaises(ContractError):
            validate_state(state)

    def test_dependency_must_be_a_dag(self):
        state = make_state()
        state["dependencies"].append(
            {"from": "DEMO-002", "to": "DEMO-001", "required_check_ids": []}
        )
        with self.assertRaisesRegex(ContractError, "cycle"):
            validate_state(state)

    def test_dependency_check_must_belong_to_predecessor(self):
        state = make_state()
        state["dependencies"][0]["required_check_ids"] = ["DEMO-002-DELIVERY"]
        with self.assertRaisesRegex(ContractError, "predecessor"):
            validate_state(state)

    def test_stage_approval_requires_existing_evidence(self):
        state = make_state()
        state["packet"]["stage_id"] = "S1"
        state["tasks"]["DEMO-001"]["stage_id"] = "S1"
        state["stages"]["S1"] = {
            "title": "Implementation",
            "task_ids": ["DEMO-001"],
            "status": "active",
            "approved": True,
            "approval_evidence_ids": [],
        }
        with self.assertRaisesRegex(ContractError, "approval evidence"):
            validate_state(state)

    def test_identity_is_not_inferred_from_titles(self):
        state = make_state()
        state["tasks"]["DEMO-001"]["id"] = "A title is not an id"
        with self.assertRaisesRegex(ContractError, "key"):
            validate_state(state)

    def test_duplicate_actual_session_identity_is_rejected(self):
        state = make_state()
        state["sessions"]["DEMO-001-WORKER"]["actual_id"] = "session-1"
        state["sessions"]["DEMO-001-REVIEW-A"]["actual_id"] = "session-1"
        with self.assertRaisesRegex(ContractError, "actual_id"):
            validate_state(state)

    def test_event_is_atomic_when_a_later_operation_fails(self):
        state = make_state()
        event = make_event("atomic", 0, [
            {"type": "task.set", "id": "DEMO-001", "changes": {"progress": "Changed"}},
            {"type": "task.set", "id": "TYPO", "changes": {"progress": "Bad"}},
        ])
        with self.assertRaises(ContractError):
            apply_event(state, event, NOW)
        self.assertEqual(state["tasks"]["DEMO-001"]["progress"], "Not started")
        self.assertEqual(state["events"], [])

    def test_unknown_objects_cannot_be_created_by_set(self):
        with self.assertRaisesRegex(ContractError, "Unknown task"):
            apply_event(make_state(), make_event("typo", 0, [
                {"type": "task.set", "id": "DEMO-OO1", "changes": {"status": "ready"}}
            ]), NOW)

    def test_retry_is_idempotent_before_sequence_check(self):
        state = make_state()
        event = make_event("retry", 0, [
            {"type": "task.set", "id": "DEMO-001", "changes": {"status": "ready"}}
        ])
        first = apply_event(state, event, NOW)
        retried = apply_event(first, event, "2026-09-08T08:00:05Z")
        self.assertEqual(retried, first)
        self.assertEqual(len(retried["events"]), 1)
        conflicting = deepcopy(event)
        conflicting["summary"] = "Different body"
        with self.assertRaisesRegex(ContractError, "different body"):
            apply_event(first, conflicting, NOW)

    def test_stale_sequence_is_rejected(self):
        state = apply_event(make_state(), make_event("first", 0, [
            {"type": "task.set", "id": "DEMO-001", "changes": {"status": "ready"}}
        ]), NOW)
        with self.assertRaisesRegex(ContractError, "expected_seq"):
            apply_event(state, make_event("stale", 0, []), NOW)

    def test_event_cannot_write_sequence(self):
        event = make_event("client-seq", 0, [])
        event["seq"] = 99
        with self.assertRaisesRegex(ContractError, "Unknown field"):
            apply_event(make_state(), event, NOW)

    def test_main_observation_cannot_move_backwards(self):
        state = make_state()
        state["main"]["observed_at"] = "2026-09-08T08:00:10Z"
        with self.assertRaisesRegex(ContractError, "backwards"):
            apply_event(state, make_event("old-main", 0, [
                {
                    "type": "main.set",
                    "changes": {"observed_at": "2026-09-08T08:00:05Z"},
                }
            ]), "2026-09-08T08:00:11Z")

    def test_source_set_cannot_change_authority(self):
        with self.assertRaises(ContractError):
            apply_event(make_state(), make_event("source-mode", 0, [
                {"type": "source.set", "changes": {"mode": "projection"}}
            ]), NOW)

    def test_initial_state_adds_contract_metadata_and_rejects_execution_claims(self):
        plan = initial_plan()
        created = initial_state(plan, NOW)
        self.assertEqual(created["schema_version"], 1)
        self.assertEqual(created["tool_version"], "0.1.0")
        self.assertEqual(created["seq"], 0)
        self.assertEqual(created["generated_at"], NOW)
        self.assertEqual(created["events"], [])
        plan["tasks"]["DEMO-001"]["status"] = "implementing"
        with self.assertRaisesRegex(ContractError, "planned"):
            initial_state(plan, NOW)

    def test_plan_replace_increments_revision_and_preserves_evidence(self):
        state = make_state()
        state = apply_event(state, make_event("evidence", 0, [
            {"type": "evidence.put", "id": "E-OLD", "evidence": evidence()}
        ]), NOW)
        replacement = {key: deepcopy(state[key]) for key in (
            "tasks", "sessions", "stages", "checks", "dependencies"
        )}
        updated = apply_event(state, make_event("replace", 1, [
            {"type": "plan.replace", "plan": replacement}
        ]), NOW)
        self.assertEqual(updated["packet"]["plan_revision"], 2)
        self.assertIn("E-OLD", updated["evidence"])

    def test_run_start_archives_without_nested_history(self):
        state = make_state()
        state["packet"]["lifecycle"] = "finished"
        plan = initial_plan()
        plan["packet"]["run_number"] = 2
        updated = apply_event(state, make_event("new-run", 0, [
            {"type": "run.start", "plan": plan}
        ]), NOW)
        self.assertEqual(updated["packet"]["run_number"], 2)
        self.assertEqual(updated["seq"], 1)
        self.assertEqual(len(updated["history"]), 1)
        self.assertNotIn("history", updated["history"][0])

class ContractEdgeTests(unittest.TestCase):
    def test_delivery_does_not_satisfy_test_integration_or_acceptance(self):
        for kind in ('test', 'integration', 'acceptance', 'approval'):
            with self.subTest(kind=kind):
                state = make_state()
                extra = deepcopy(state['checks']['DEMO-001-DELIVERY'])
                extra.update(kind=kind, role_id=state['main']['logical_id'])
                state['checks']['EXTRA'] = extra
                state['tasks']['DEMO-001']['required_check_ids'].append('EXTRA')
                ops = pass_required_ops(state, 'DEMO-001', omit='EXTRA')
                ops.append({'type': 'task.set', 'id': 'DEMO-001', 'changes': {'status': 'done'}})
                with self.assertRaisesRegex(ContractError, 'EXTRA'):
                    apply_event(state, make_event('missing-dimension', 0, ops), NOW)

    def test_bad_nested_field_types_raise_contract_error(self):
        mutations = [
            ('packet', 'run_number', True),
            ('source', 'available', 1),
            ('main', 'status', []),
            ('task', 'round', '1'),
            ('task', 'required_check_ids', []),
            ('task', 'session_ids', ['DEMO-001-WORKER', 'DEMO-001-WORKER']),
            ('check', 'applicable', 'false'),
            ('check', 'round', 2),
            ('session', 'planned_model', {'surprise': 'value'}),
        ]
        for entity, key, value in mutations:
            with self.subTest(entity=entity, key=key):
                state = make_state()
                target = {'task': state['tasks']['DEMO-001'], 'check': state['checks']['DEMO-001-DELIVERY'], 'session': state['sessions']['DEMO-001-WORKER']}.get(entity, state.get(entity))
                target[key] = value
                with self.assertRaises(ContractError):
                    validate_state(state)

    def test_invalid_repository_references_and_credential_urls(self):
        references = [
            {'repository': 'demo', 'path': '../outside.md'},
            {'repository': 'demo', 'path': 'C:/private.md'},
            {'repository': 'demo', 'path': 'reports/../../private.md'},
            {'repository': 'demo', 'path': 'reports/a.md', 'url': 'https://example.com'},
            {'url': 'https://user:password@example.com/report'},
        ]
        for reference in references:
            with self.subTest(reference=reference):
                state = make_state()
                state['source']['reference'] = reference
                with self.assertRaises(ContractError):
                    validate_state(state)

    def test_valid_utc_offset_http_reference_and_nonapplicable_result(self):
        state = make_state()
        state['generated_at'] = '2026-09-08T08:00:00+00:00'
        state['evidence']['E'] = evidence({'url': 'https://example.com/report'})
        validate_state(state)
        state['checks']['DEMO-001-REVIEW-B'].update(applicable=False, result='PASS', not_applicable_reason='Exempt')
        with self.assertRaises(ContractError):
            validate_state(state)

    def test_old_session_report_is_recorded_without_overwriting_new_observation(self):
        state = make_state()
        state['sessions']['DEMO-001-WORKER'].update(host_status='running', observed_at='2026-09-08T08:00:10Z')
        event = make_event('old-report', 0, [{'type': 'session.set', 'id': 'DEMO-001-WORKER', 'changes': {'host_status': 'idle', 'observed_at': '2026-09-08T08:00:05Z'}}])
        event['occurred_at'] = '2026-09-08T08:00:05Z'
        event['observed_at'] = '2026-09-08T08:00:12Z'
        updated = apply_event(state, event, '2026-09-08T08:00:12Z')
        self.assertEqual(updated['sessions']['DEMO-001-WORKER']['host_status'], 'running')
        self.assertEqual(updated['events'][0]['body'], event)
        self.assertEqual(updated['seq'], 1)

    def test_old_task_report_preserves_current_progress_and_round(self):
        state = make_state()
        state['tasks']['DEMO-001'].update(status='fixing', round=2, progress='New fix', progress_at='2026-09-08T08:00:10Z')
        event = make_event('old-task', 0, [{'type': 'task.set', 'id': 'DEMO-001', 'changes': {'progress': 'Old implementation'}}])
        event['observed_at'] = '2026-09-08T08:00:12Z'
        updated = apply_event(state, event, '2026-09-08T08:00:12Z')
        self.assertEqual(updated['tasks']['DEMO-001']['progress'], 'New fix')
        self.assertEqual(updated['tasks']['DEMO-001']['round'], 2)

    def test_plan_replace_cannot_remove_an_executed_task(self):
        state = make_state()
        state['tasks']['DEMO-001']['status'] = 'implementing'
        plan = {key: deepcopy(state[key]) for key in ('tasks', 'sessions', 'stages', 'checks', 'dependencies')}
        del plan['tasks']['DEMO-001']
        with self.assertRaisesRegex(ContractError, 'executed'):
            apply_event(state, make_event('remove-task', 0, [{'type': 'plan.replace', 'plan': plan}]), NOW)

    def test_changed_requirements_require_a_new_round_and_preserve_old_results(self):
        state = make_state()
        state = apply_event(state, make_event('pass', 0, pass_required_ops(state, 'DEMO-001')), NOW)
        plan = {key: deepcopy(state[key]) for key in ('tasks', 'sessions', 'stages', 'checks', 'dependencies')}
        plan['tasks']['DEMO-001']['required_check_ids'].remove('DEMO-001-REVIEW-B')
        with self.assertRaisesRegex(ContractError, 'new task round'):
            apply_event(state, make_event('requirements', 1, [{'type': 'plan.replace', 'plan': plan}]), NOW)
        plan['tasks']['DEMO-001'].update(round=2, status='fixing')
        updated = apply_event(state, make_event('requirements-2', 1, [{'type': 'plan.replace', 'plan': plan}]), NOW)
        self.assertEqual(updated['checks']['DEMO-001-DELIVERY']['result'], 'PASS')
        self.assertEqual(updated['checks']['DEMO-001-DELIVERY']['round'], 1)
        with self.assertRaisesRegex(ContractError, 'current-round'):
            ensure_done_allowed(updated, 'DEMO-001')

    def test_plan_replace_cannot_regress_session_observation(self):
        state = make_state()
        state['sessions']['DEMO-001-WORKER'].update(actual_id='worker-session', observed_at='2026-09-08T08:00:10Z', host_status='running')
        plan = {key: deepcopy(state[key]) for key in ('tasks', 'sessions', 'stages', 'checks', 'dependencies')}
        plan['sessions']['DEMO-001-WORKER'].update(actual_id=None, observed_at=None, host_status='planned')
        with self.assertRaises(ContractError):
            apply_event(state, make_event('forget-session', 0, [{'type': 'plan.replace', 'plan': plan}]), NOW)

    def test_plan_replace_cannot_erase_existing_check_evidence(self):
        state = make_state()
        state = apply_event(state, make_event('passes', 0, pass_required_ops(state, 'DEMO-001')), NOW)
        plan = {key: deepcopy(state[key]) for key in ('tasks', 'sessions', 'stages', 'checks', 'dependencies')}
        plan['checks']['DEMO-001-DELIVERY'].update(result='UNRUN', evidence_ids=[])
        with self.assertRaisesRegex(ContractError, 'preserve check result'):
            apply_event(state, make_event('erase-result', 1, [{'type': 'plan.replace', 'plan': plan}]), NOW)

    def test_task_set_cannot_change_completion_requirements_or_move_round_backwards(self):
        for changes in ({'required_check_ids': ['DEMO-001-DELIVERY']}, {'round': 0}, {'id': 'OTHER'}):
            with self.subTest(changes=changes):
                with self.assertRaises(ContractError):
                    apply_event(make_state(), make_event('bad-task', 0, [{'type': 'task.set', 'id': 'DEMO-001', 'reason': 'Bad edit', 'changes': changes}]), NOW)

    def test_main_stop_allows_new_run_and_live_run_cannot_restart(self):
        plan = initial_plan()
        plan['packet']['run_number'] = 2
        with self.assertRaisesRegex(ContractError, 'finished or explicitly stopped'):
            apply_event(make_state(), make_event('restart', 0, [{'type': 'run.start', 'plan': plan}]), NOW)
        stopped = apply_event(make_state(), make_event('stop', 0, [{'type': 'main.set', 'changes': {'status': 'stopped'}}]), NOW)
        restarted = apply_event(stopped, make_event('restart', 1, [{'type': 'run.start', 'plan': plan}]), NOW)
        self.assertEqual(restarted['packet']['lifecycle'], 'planned')
        self.assertEqual(restarted['packet']['run_number'], 2)
        self.assertEqual(restarted['history'][0]['main']['status'], 'stopped')

    def test_retry_after_another_event_preserves_latest_state(self):
        event = make_event('first', 0, [])
        state = apply_event(make_state(), event, NOW)
        state = apply_event(state, make_event('second', 1, []), NOW)
        self.assertEqual(apply_event(state, event, NOW), state)

    def test_history_keeps_evidence_and_deduplicates_prior_run_events(self):
        first = make_event('first', 0, pass_required_ops(make_state(), 'DEMO-001'))
        state = apply_event(make_state(), first, NOW)
        state = apply_event(state, make_event('finish', 1, [{'type': 'main.set', 'changes': {'status': 'finished'}}]), NOW)
        plan = initial_plan()
        plan['packet']['run_number'] = 2
        state = apply_event(state, make_event('restart', 2, [{'type': 'run.start', 'plan': plan}]), NOW)
        self.assertEqual(state['history'][0]['checks']['DEMO-001-DELIVERY']['result'], 'PASS')
        self.assertTrue(state['history'][0]['evidence'])
        self.assertNotIn('history', state['history'][0])
        self.assertEqual(apply_event(state, first, NOW), state)
        validate_state(state)

    def test_unknown_operation_and_wrong_stage_membership_are_rejected(self):
        with self.assertRaises(ContractError):
            apply_event(make_state(), make_event('unknown', 0, [{'type': 'unknown.set', 'changes': {}}]), NOW)
        state = make_state()
        state['tasks']['DEMO-001']['stage_id'] = 'MISSING'
        with self.assertRaises(ContractError):
            validate_state(state)

    def test_initial_state_rejects_actual_model_and_executed_checks(self):
        plan = initial_plan()
        plan['sessions']['DEMO-001-WORKER']['actual_model'] = deepcopy(plan['sessions']['DEMO-001-WORKER']['planned_model'])
        with self.assertRaises(ContractError):
            initial_state(plan, NOW)
        plan = initial_plan()
        plan['checks']['DEMO-001-DELIVERY']['result'] = 'FAIL'
        with self.assertRaises(ContractError):
            initial_state(plan, NOW)

    def test_malformed_run_start_and_history_raise_contract_error(self):
        state = make_state()
        state['packet']['lifecycle'] = 'finished'
        plan = initial_plan()
        plan['packet'] = None
        with self.assertRaises(ContractError):
            apply_event(state, make_event('bad-run', 0, [{'type': 'run.start', 'plan': plan}]), NOW)
        state = make_state()
        archive = {key: deepcopy(value) for key, value in state.items() if key != 'history'}
        archive['packet'] = None
        state['history'].append(archive)
        with self.assertRaises(ContractError):
            validate_state(state)


class PlanReplacementReviewTests(unittest.TestCase):
    def test_changed_check_moved_to_new_owner_requires_round_above_retained_result(self):
        state = make_state()
        state['evidence']['EXTRA-EVIDENCE'] = evidence()
        extra = deepcopy(state['checks']['DEMO-001-DELIVERY'])
        extra.update(kind='test', result='PASS', evidence_ids=['EXTRA-EVIDENCE'])
        state['checks']['EXTRA'] = extra
        state['dependencies'][0]['required_check_ids'] = ['EXTRA']
        validate_state(state)
        plan = {key: deepcopy(state[key]) for key in (
            'tasks', 'sessions', 'stages', 'checks', 'dependencies'
        )}
        new_owner = deepcopy(state['tasks']['DEMO-002'])
        new_owner.update(id='DEMO-003', session_ids=[], required_check_ids=['EXTRA'])
        plan['tasks']['DEMO-003'] = new_owner
        plan['tasks']['DEMO-001']['round'] = 2
        plan['tasks']['DEMO-002']['round'] = 2
        plan['checks']['EXTRA'].update(
            task_id='DEMO-003', kind='acceptance', role_id=state['main']['logical_id']
        )
        plan['dependencies'][0]['from'] = 'DEMO-003'
        with self.assertRaisesRegex(ContractError, 'new task round: DEMO-003'):
            apply_event(state, make_event('new-owner-old-round', 0, [
                {'type': 'plan.replace', 'plan': plan}
            ]), NOW)
        plan['tasks']['DEMO-003']['round'] = 2
        updated = apply_event(state, make_event('new-owner-new-round', 0, [
            {'type': 'plan.replace', 'plan': plan}
        ]), NOW)
        self.assertEqual(updated['checks']['EXTRA']['round'], 1)
        self.assertEqual(updated['checks']['EXTRA']['result'], 'PASS')
        self.assertEqual(updated['tasks']['DEMO-003']['round'], 2)
        with self.assertRaisesRegex(ContractError, 'current-round'):
            ensure_done_allowed(updated, 'DEMO-003')
        self.assertEqual(state['checks']['EXTRA']['task_id'], 'DEMO-001')

    def test_dependency_only_check_semantic_change_requires_owner_new_round(self):
        state = make_state()
        state['evidence']['EXTRA-EVIDENCE'] = evidence()
        extra = deepcopy(state['checks']['DEMO-001-DELIVERY'])
        extra.update(kind='test', result='PASS', evidence_ids=['EXTRA-EVIDENCE'])
        state['checks']['EXTRA'] = extra
        state['dependencies'][0]['required_check_ids'] = ['EXTRA']
        validate_state(state)
        plan = {key: deepcopy(state[key]) for key in (
            'tasks', 'sessions', 'stages', 'checks', 'dependencies'
        )}
        plan['checks']['EXTRA']['kind'] = 'acceptance'
        with self.assertRaisesRegex(ContractError, 'new task round: DEMO-001'):
            apply_event(state, make_event('changed-gate', 0, [
                {'type': 'plan.replace', 'plan': plan}
            ]), NOW)
        plan['tasks']['DEMO-001']['round'] = 2
        updated = apply_event(state, make_event('changed-gate-new-round', 0, [
            {'type': 'plan.replace', 'plan': plan}
        ]), NOW)
        self.assertEqual(updated['checks']['EXTRA']['result'], 'PASS')
        self.assertEqual(updated['checks']['EXTRA']['round'], 1)
        self.assertEqual(updated['tasks']['DEMO-001']['round'], 2)
        self.assertEqual(state['checks']['EXTRA']['kind'], 'test')

    def test_plan_replacement_and_evidence_put_accept_both_atomic_orders(self):
        state = make_state()
        plan = {key: deepcopy(state[key]) for key in (
            'tasks', 'sessions', 'stages', 'checks', 'dependencies'
        )}
        extra = deepcopy(state['checks']['DEMO-001-DELIVERY'])
        extra.update(kind='test', result='PASS', evidence_ids=['LATER'])
        plan['checks']['EXTRA'] = extra
        replacement = {'type': 'plan.replace', 'plan': plan}
        put = {'type': 'evidence.put', 'id': 'LATER', 'evidence': evidence()}
        outcomes = []
        for ops in ([replacement, put], [put, replacement]):
            with self.subTest(first=ops[0]['type']):
                try:
                    updated = apply_event(state, make_event('atomic-plan', 0, ops), NOW)
                except ContractError as exc:
                    self.fail(f'Valid complete transaction was rejected: {exc}')
                self.assertEqual(updated['events'][0]['body']['ops'], ops)
                outcomes.append({key: value for key, value in updated.items() if key != 'events'})
        self.assertEqual(len(outcomes), 2, 'Both operation orders must be accepted')
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(outcomes[0]['checks']['EXTRA']['evidence_ids'], ['LATER'])
        self.assertEqual(state['evidence'], {})


class PacketStageTests(unittest.TestCase):
    def setUp(self):
        self.state = make_state()
        self.state['stages'] = {
            identity: {'title': identity, 'task_ids': [], 'status': 'pending',
                       'approved': False, 'approval_evidence_ids': []}
            for identity in ('S1', 'S2')
        }
        self.state['packet']['stage_id'] = 'S1'

    def test_packet_set_transitions_between_registered_stages_without_approval(self):
        try:
            updated = apply_event(self.state, make_event('stage-transition', 0, [
                {'type': 'packet.set', 'changes': {'stage_id': 'S2'}}
            ]), NOW)
        except ContractError as exc:
            self.fail(f'Registered stage transition was rejected: {exc}')
        self.assertEqual(updated['packet']['stage_id'], 'S2')
        self.assertEqual(updated['stages'], self.state['stages'])
        self.assertEqual(updated['packet']['lifecycle'], 'planned')
        self.assertEqual(self.state['packet']['stage_id'], 'S1')

    def test_packet_set_clears_current_stage(self):
        try:
            updated = apply_event(self.state, make_event('clear-stage', 0, [
                {'type': 'packet.set', 'changes': {'stage_id': None}}
            ]), NOW)
        except ContractError as exc:
            self.fail(f'Clearing stage was rejected: {exc}')
        self.assertIsNone(updated['packet']['stage_id'])

    def test_invalid_stage_rejects_entire_event(self):
        original = deepcopy(self.state)
        with self.assertRaisesRegex(ContractError, 'unknown reference MISSING'):
            apply_event(self.state, make_event('invalid-stage', 0, [
                {'type': 'task.set', 'id': 'DEMO-001', 'changes': {'progress': 'Changed'}},
                {'type': 'packet.set', 'changes': {'stage_id': 'MISSING'}},
            ]), NOW)
        self.assertEqual(self.state, original)

    def test_packet_set_cannot_change_metadata_or_authority(self):
        for field, value in {
            'id': 'OTHER', 'title': 'Other title', 'mode': 'auto',
            'lifecycle': 'finished', 'run_number': 2, 'plan_revision': 2,
            'stop_condition': 'Other condition', 'source': {},
        }.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(ContractError, 'Unknown field'):
                    apply_event(self.state, make_event('immutable', 0, [
                        {'type': 'packet.set', 'changes': {field: value}}
                    ]), NOW)


if __name__ == "__main__":
    unittest.main()
