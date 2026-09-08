"""Export validated state into fixed, self-contained HTML resources."""

import json
from copy import deepcopy
from pathlib import Path
import re

from .contract import validate_state
from .store import SourceError, _atomic_write, _writer_lock, read_state

__all__ = ["RenderError", "render_html", "export_snapshot"]


class RenderError(ValueError):
    """Export failed; metadata distinguishes HTML replacement from later cleanup."""

    def __init__(self, message: str, *, state: dict | None = None):
        super().__init__(message)
        self.snapshot_updated = state is not None
        self.state = deepcopy(state)


def render_html(state: dict, resources_dir: Path) -> str:
    """Inline fixed assets and escaped JSON without evaluating state as templates."""
    validate_state(state)
    resources_dir = Path(resources_dir)
    try:
        template = (resources_dir / "panel-template.html").read_text(encoding="utf-8")
        styles = (resources_dir / "panel.css").read_text(encoding="utf-8")
        script = (resources_dir / "panel.js").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RenderError(f"Cannot read fixed HTML resources: {exc}") from exc
    payload = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    replacements = {"PANEL_DATA": payload, "PANEL_STYLES": styles, "PANEL_SCRIPT": script}
    for name in replacements:
        if template.count("<!--" + name + "-->") != 1:
            raise RenderError(f"Template must contain exactly one {name} marker")
    # One pass over only the template ensures inserted text is never reprocessed.
    return re.sub(r"<!--(PANEL_DATA|PANEL_STYLES|PANEL_SCRIPT)-->",
                  lambda match: replacements[match.group(1)], template)


def export_snapshot(packet_dir: Path) -> Path:
    """Export latest configured state under the writer lock, preserving old HTML on failure."""
    packet_dir = Path(packet_dir)
    exported = None
    try:
        with _writer_lock(packet_dir):
            state = read_state(packet_dir)
            dashboard = packet_dir / "dashboard"
            html = render_html(state, dashboard / "resources")
            target = dashboard / "index.html"
            _atomic_write(target, html)
            exported = state
            return target
    except SourceError:
        raise
    except (OSError, UnicodeError) as exc:
        raise RenderError(f"HTML export encountered an I/O error: {exc}", state=exported) from exc
