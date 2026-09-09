"""Per-packet atomic state storage. Publication never performs HTML export."""

from contextlib import contextmanager
from copy import deepcopy
import errno
import json
import os
from pathlib import Path
import tempfile
import time

from .contract import (
    ContractConflictError, ContractError, apply_event, initial_state, validate_state,
)

__all__ = [
    "ConflictError", "SourceError", "WriteError", "read_state", "initialize",
    "import_snapshot", "publish",
]


class ConflictError(ContractError):
    """Existing identity, sequence, event, or busy writer prevents publication."""


class SourceError(OSError):
    """The configured state/configuration could not be read or validated."""


class WriteError(OSError):
    """Storage failed; metadata distinguishes replacement from later cleanup."""

    def __init__(self, message: str, *, state: dict | None = None):
        super().__init__(message)
        self.state_published = state is not None
        self.state = deepcopy(state)


@contextmanager
def _writer_lock(packet_dir: Path):
    """Use a persistent lock file with an OS lock, never a PID-file lease."""
    runtime = packet_dir / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / ".writer.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            def acquire():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        deadline = time.monotonic() + 10
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise ConflictError("Packet writer is busy; retry later") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            release()


def _atomic_write(target: Path, text: str) -> None:
    """Flush a same-directory temporary file before atomic replacement."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent,
            prefix="." + target.name + ".", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None  # Replacement consumed this path; no post-commit cleanup.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _json_text(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (OSError, ValueError) as exc:
        raise SourceError(f"Cannot read {path.name}: {exc}") from exc


def _config_for(state: dict) -> dict:
    mode = state["source"]["mode"]
    return {
        "packet_id": state["packet"]["id"], "source_mode": mode,
        "reference": deepcopy(state["source"]["reference"]),
        "target": "state.json" if mode == "local" else "view.json",
    }


def _read_config(packet_dir: Path) -> dict:
    config = _read_json(packet_dir / "runtime/panel.json")
    if not isinstance(config, dict) or set(config) != {"packet_id", "source_mode", "reference", "target"}:
        raise SourceError("Invalid panel.json fields")
    mode = config["source_mode"]
    if mode not in ("local", "projection"):
        raise SourceError("Invalid panel.json source_mode")
    target = "state.json" if mode == "local" else "view.json"
    if config["target"] != target:
        raise SourceError("Invalid panel.json target for source_mode")
    if not isinstance(config["packet_id"], str) or not config["packet_id"].strip():
        raise SourceError("Invalid panel.json packet_id")
    if not isinstance(config["reference"], dict):
        raise SourceError("Invalid panel.json reference")
    return config


def read_state(packet_dir: Path) -> dict:
    """Read exactly the configured local snapshot; never fetch external references."""
    packet_dir = Path(packet_dir)
    config = _read_config(packet_dir)
    state = _read_json(packet_dir / "runtime" / config["target"])
    try:
        validate_state(state)
    except ContractError as exc:
        raise SourceError(f"Invalid configured state: {exc}") from exc
    if config != _config_for(state):
        raise SourceError("Configured packet identity or authority differs from state")
    return state


def _create(packet_dir: Path, state: dict) -> dict:
    packet_dir = Path(packet_dir)
    config = _config_for(state)
    accepted = None
    try:
        with _writer_lock(packet_dir):
            runtime = packet_dir / "runtime"
            config_path = runtime / "panel.json"
            target = runtime / config["target"]
            if config_path.exists():
                if _read_config(packet_dir) != config:
                    raise ConflictError("Existing panel configuration has different identity or authority")
            if target.exists():
                raise ConflictError("State target already exists; initialize/import cannot overwrite it")
            # Configuration first makes interrupted initialization recognizable.
            # A retry may fill only a missing target after matching full identity.
            if not config_path.exists():
                _atomic_write(config_path, _json_text(config))
            _atomic_write(target, _json_text(state))
            accepted = state
    except SourceError:
        raise
    except OSError as exc:
        raise WriteError(f"Packet state creation encountered an I/O error: {exc}", state=accepted) from exc
    return deepcopy(state)


def initialize(packet_dir: Path, plan: dict, now: str) -> dict:
    """Create planned state and configuration, refusing an existing target."""
    return _create(packet_dir, initial_state(plan, now))


def import_snapshot(packet_dir: Path, state: dict) -> dict:
    """Create state/configuration from a checked v1 snapshot without resetting it."""
    validate_state(state)
    return _create(packet_dir, state)


def publish(packet_dir: Path, event: dict, now: str) -> dict:
    """Lock, re-read, deduplicate, validate and atomically replace state only."""
    packet_dir = Path(packet_dir)
    accepted = None
    try:
        with _writer_lock(packet_dir):
            state = read_state(packet_dir)
            try:
                updated = apply_event(state, event, now)
            except ContractConflictError as exc:
                raise ConflictError(str(exc)) from exc
            if updated["seq"] != state["seq"]:
                target = packet_dir / "runtime" / _config_for(updated)["target"]
                _atomic_write(target, _json_text(updated))
            accepted = updated
            return updated
    except SourceError:
        raise
    except OSError as exc:
        raise WriteError(f"Packet state publication encountered an I/O error: {exc}", state=accepted) from exc
