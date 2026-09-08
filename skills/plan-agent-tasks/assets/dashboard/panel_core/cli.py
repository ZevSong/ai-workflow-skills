"""One JSON stdout result per command; inputs arrive only through local files."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .contract import ContractError
from .render import RenderError, export_snapshot
from .server import PreviewError, service_status, serve, start_service, stop_service
from .store import ConflictError, SourceError, WriteError, _read_json, initialize, import_snapshot, publish, read_state


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ContractError(message)


def _parser():
    parser = Parser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    for name in ("init", "import", "publish"):
        command = commands.add_parser(name, add_help=False)
        command.add_argument("--input", required=True)
    for name in ("status", "export", "stop"):
        commands.add_parser(name, add_help=False)
    commands.add_parser("start", add_help=False).add_argument("--open", action="store_true")
    commands.add_parser("serve", add_help=False).add_argument("--instance")
    return parser


def _summary(state):
    return {"packet_id": state["packet"]["id"], "tool_version": state["tool_version"],
            "schema_version": state["schema_version"], "seq": state["seq"],
            "generated_at": state["generated_at"], "observed_at": state["observed_at"],
            "source": state["source"]}


def main(argv: list[str] | None = None) -> int:
    packet_dir = Path(__file__).resolve().parents[2]
    state = None
    committed = False
    snapshot_committed = False
    command = None
    code = 0
    try:
        args = _parser().parse_args(argv)
        command = args.command
        if command in ("init", "import", "publish"):
            try:
                value = _read_json(Path(args.input))
            except SourceError as exc:
                raise ContractError(f"Invalid input file: {exc}") from exc
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if command == "init":
                state = initialize(packet_dir, value, now)
            elif command == "import":
                state = import_snapshot(packet_dir, value)
            else:
                state = publish(packet_dir, value, now)
            committed = True
            export_snapshot(packet_dir)
            snapshot_committed = True
            result = {**_summary(state), "state_published": True, "snapshot_updated": True}
        elif command == "export":
            export_snapshot(packet_dir)
            snapshot_committed = True
            result = {**_summary(read_state(packet_dir)), "state_published": False, "snapshot_updated": True}
        elif command == "status":
            state = read_state(packet_dir)
            result = {**_summary(state), "service": service_status(packet_dir),
                      "snapshot_exists": (packet_dir / "dashboard/index.html").is_file()}
        elif command == "start":
            result = start_service(packet_dir, args.open)
        elif command == "stop":
            result = stop_service(packet_dir)
        else:
            result = serve(packet_dir, args.instance)
    except (ContractError, OSError, RenderError, ValueError) as exc:
        if committed:
            code = 6
        elif isinstance(exc, ConflictError):
            code = 3
        elif isinstance(exc, (SourceError, WriteError)):
            code = 4
        elif isinstance(exc, (PreviewError, RenderError)) or isinstance(exc, OSError):
            code = 5
        else:
            code = 2
        known_state = getattr(exc, "state", None)
        if isinstance(exc, WriteError):
            committed = exc.state_published
            state = known_state
        snapshot_updated = snapshot_committed or getattr(exc, "snapshot_updated", False)
        result = {"error": str(exc), "code": code, "state_published": committed,
                  "snapshot_updated": snapshot_updated}
        if state is not None:
            result.update(_summary(state))
        if snapshot_updated and known_state is not None:
            result["snapshot_seq"] = known_state["seq"]
        print(str(exc), file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code
