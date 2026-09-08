"""Build the labelled simulation through the real contract and fixed renderer."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "skills/plan-agent-tasks/assets/dashboard"
EXAMPLE = ROOT / "skills/plan-agent-tasks/examples/progress-panel"
sys.path.insert(0, str(ASSETS))
from panel_core.contract import initial_state, apply_event  # noqa: E402
from panel_core.render import render_html  # noqa: E402


def example_state():
    state = initial_state(json.loads((EXAMPLE / "plan.json").read_text(encoding="utf-8")),
                          "2026-09-08T08:00:00Z")
    for event in json.loads((EXAMPLE / "events.json").read_text(encoding="utf-8")):
        state = apply_event(state, event, event["occurred_at"])
    return state


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(example_state(), ASSETS / "resources"), encoding="utf-8")
    print("Rendered simulated fixture")
