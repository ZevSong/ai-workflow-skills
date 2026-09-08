"""Complete, hand-authored fixtures for the progress-panel state contract."""

from copy import deepcopy
from pathlib import Path
import sys


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "skills" / "plan-agent-tasks" / "assets" / "dashboard"),
)


NOW = "2026-09-08T08:00:00Z"


def _model() -> dict:
    return {
        "provider": "openai",
        "model": "example-model",
        "reasoning_effort": "medium",
        "service_tier": "standard",
    }


def make_state() -> dict:
    """Return a complete valid state with two tasks and a dependency."""
    state = {
        "schema_version": 1,
        "tool_version": "0.1.0",
        "seq": 0,
        "packet": {
            "id": "DEMO",
            "title": "Demo packet",
            "mode": "manual",
            "run_number": 1,
            "plan_revision": 1,
            "lifecycle": "planned",
            "stage_id": None,
            "stop_condition": "All required checks pass",
        },
        "source": {
            "mode": "local",
            "reference": {"repository": "demo", "path": "docs/task-packets/DEMO/packet.md"},
            "available": True,
            "checked_at": NOW,
        },
        "generated_at": NOW,
        "observed_at": None,
        "main": {
            "logical_id": "DEMO-MAIN",
            "session_id": None,
            "status": "planned",
            "observed_at": None,
        },
        "tasks": {
            "DEMO-001": {
                "id": "DEMO-001",
                "title": "Implement the demo",
                "stage_id": None,
                "status": "pending",
                "round": 1,
                "progress": "Not started",
                "progress_at": None,
                "blocker": None,
                "next_action": "Start implementation",
                "session_ids": ["DEMO-001-WORKER", "DEMO-001-REVIEW-A", "DEMO-001-REVIEW-B"],
                "required_check_ids": ["DEMO-001-DELIVERY", "DEMO-001-REVIEW-A", "DEMO-001-REVIEW-B"],
            },
            "DEMO-002": {
                "id": "DEMO-002",
                "title": "Integrate the demo",
                "stage_id": None,
                "status": "pending",
                "round": 1,
                "progress": "Waiting for DEMO-001",
                "progress_at": None,
                "blocker": None,
                "next_action": "Wait for the dependency",
                "session_ids": ["DEMO-002-WORKER"],
                "required_check_ids": ["DEMO-002-DELIVERY"],
            },
        },
        "sessions": {
            "DEMO-001-WORKER": {
                "task_id": "DEMO-001",
                "role": "worker",
                "planned_name": "DEMO-001 Worker",
                "actual_name": None,
                "actual_id": None,
                "host_status": "planned",
                "observed_at": None,
                "round": 1,
                "planned_model": _model(),
                "actual_model": None,
                "replaces": None,
            },
            "DEMO-001-REVIEW-A": {
                "task_id": "DEMO-001",
                "role": "reviewer",
                "planned_name": "DEMO-001 Reviewer A",
                "actual_name": None,
                "actual_id": None,
                "host_status": "planned",
                "observed_at": None,
                "round": 1,
                "planned_model": _model(),
                "actual_model": None,
                "replaces": None,
            },
            "DEMO-001-REVIEW-B": {
                "task_id": "DEMO-001",
                "role": "reviewer",
                "planned_name": "DEMO-001 Reviewer B",
                "actual_name": None,
                "actual_id": None,
                "host_status": "planned",
                "observed_at": None,
                "round": 1,
                "planned_model": _model(),
                "actual_model": None,
                "replaces": None,
            },
            "DEMO-002-WORKER": {
                "task_id": "DEMO-002",
                "role": "worker",
                "planned_name": "DEMO-002 Worker",
                "actual_name": None,
                "actual_id": None,
                "host_status": "planned",
                "observed_at": None,
                "round": 1,
                "planned_model": _model(),
                "actual_model": None,
                "replaces": None,
            },
        },
        "stages": {},
        "checks": {
            "DEMO-001-DELIVERY": {
                "task_id": "DEMO-001",
                "kind": "delivery",
                "role_id": "DEMO-001-WORKER",
                "round": 1,
                "applicable": True,
                "result": "UNRUN",
                "evidence_ids": [],
                "not_applicable_reason": None,
            },
            "DEMO-001-REVIEW-A": {
                "task_id": "DEMO-001",
                "kind": "review",
                "role_id": "DEMO-001-REVIEW-A",
                "round": 1,
                "applicable": True,
                "result": "UNRUN",
                "evidence_ids": [],
                "not_applicable_reason": None,
            },
            "DEMO-001-REVIEW-B": {
                "task_id": "DEMO-001",
                "kind": "review",
                "role_id": "DEMO-001-REVIEW-B",
                "round": 1,
                "applicable": True,
                "result": "UNRUN",
                "evidence_ids": [],
                "not_applicable_reason": None,
            },
            "DEMO-002-DELIVERY": {
                "task_id": "DEMO-002",
                "kind": "delivery",
                "role_id": "DEMO-002-WORKER",
                "round": 1,
                "applicable": True,
                "result": "UNRUN",
                "evidence_ids": [],
                "not_applicable_reason": None,
            },
        },
        "evidence": {},
        "dependencies": [
            {"from": "DEMO-001", "to": "DEMO-002", "required_check_ids": []}
        ],
        "events": [],
        "history": [],
    }
    return deepcopy(state)


def make_event(event_id: str, seq: int, ops: list[dict]) -> dict:
    """Return a deterministic event body for contract tests."""
    return {
        "event_id": event_id,
        "expected_seq": seq,
        "occurred_at": NOW,
        "observed_at": NOW,
        "summary": f"Apply {event_id}",
        "ops": deepcopy(ops),
    }
