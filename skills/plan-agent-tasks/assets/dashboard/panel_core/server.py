"""Packet-scoped loopback preview. HTTP never writes, stops, or dispatches."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path, PurePosixPath
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import unquote
import uuid
import webbrowser

from .store import ConflictError, SourceError, _atomic_write, _json_text, _read_config, _read_json, read_state

TOOL_VERSION = "0.1.0"
MAX_EVIDENCE_BYTES = 2 * 1024 * 1024


class PreviewError(OSError):
    """A preview process or endpoint could not be established safely."""


class PacketHTTPServer(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, *args):
        self._clients = set()
        self._clients_lock = threading.Lock()
        super().__init__(*args)

    def get_request(self):
        client, address = super().get_request()
        client.settimeout(2)
        with self._clients_lock:
            self._clients.add(client)
        return client, address

    def close_request(self, request):
        with self._clients_lock:
            self._clients.discard(request)
        super().close_request(request)

    def server_close(self):
        with self._clients_lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        super().server_close()  # Joins non-daemon request threads after waking reads.


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("Instance ID must be a UUID string")
    if str(uuid.UUID(value)) != value:
        raise ValueError("Instance ID must be a canonical UUID")
    return value


def evidence_path(packet_dir: Path, state: dict, evidence_id: str) -> Path | None:
    """Map a canonical local authority anchor without probing repository files."""
    source = state["source"]
    anchor = source["reference"]
    evidence = state["evidence"].get(evidence_id)
    if source["mode"] != "local" or "path" not in anchor or evidence is None:
        return None
    reference = evidence["reference"]
    if reference.get("repository") != anchor["repository"] or "path" not in reference:
        return None
    parts = PurePosixPath(anchor["path"].replace("\\", "/")).parts
    if parts[-2:] != ("runtime", "state.json"):
        return None
    prefix = parts[:-2]
    target = PurePosixPath(reference["path"].replace("\\", "/")).parts
    if target[:len(prefix)] != prefix or len(target) <= len(prefix):
        return None
    root = Path(packet_dir).resolve()
    candidate = root.joinpath(*target[len(prefix):]).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        return None
    return candidate


def make_server(packet_dir: Path, instance_id: str) -> ThreadingHTTPServer:
    """Construct a listener only; the caller owns the loop and socket cleanup."""
    packet_dir = Path(packet_dir).resolve()
    config = _read_config(packet_dir)
    identity = {"packet_id": config["packet_id"], "tool_version": TOOL_VERSION,
                "instance_id": _uuid(instance_id)}
    state_lock = threading.Lock()
    last_good = None

    def load():
        nonlocal last_good
        # Serialize reads so an older successful request cannot replace a newer cache.
        with state_lock:
            try:
                state = read_state(packet_dir)
                if state["packet"]["id"] != identity["packet_id"] or state["tool_version"] != TOOL_VERSION:
                    raise SourceError("Preview identity differs from configured state")
                last_good = state
                return state, None
            except SourceError as exc:
                return last_good, str(exc)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, body, content_type="text/plain; charset=utf-8"):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if status == 405:
                self.send_header("Allow", "GET, HEAD")
            self.end_headers()
            if self.command != "HEAD":
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

        def do_GET(self):
            if self.path == "/api/identity":
                self.respond(200, json.dumps(identity), "application/json")
            elif self.path == "/api/status":
                state, error = load()
                self.respond(200 if state is not None else 503,
                             json.dumps({"state": state, "sync_error": error}, ensure_ascii=False),
                             "application/json; charset=utf-8")
            elif self.path in ("/", "/index.html"):
                try:
                    target = (packet_dir / "dashboard/index.html").resolve()
                    if not target.is_relative_to(packet_dir):
                        raise OSError("Snapshot outside packet")
                    self.respond(200, target.read_bytes(), "text/html; charset=utf-8")
                except OSError:
                    self.respond(503, "Snapshot unavailable; run export locally.")
            elif self.path.startswith("/evidence/") and "?" not in self.path:
                evidence_id = unquote(self.path[len("/evidence/"):])
                if not evidence_id or any(c in evidence_id for c in "/\\\x00") or evidence_id in (".", ".."):
                    self.respond(404, "Evidence unavailable.")
                    return
                state, error = load()
                if error:
                    self.respond(503, "Evidence unavailable while the source cannot be verified.")
                    return
                try:
                    target = evidence_path(packet_dir, state, evidence_id)
                    if target is None:
                        raise OSError("Not packet-local")
                    with target.open("rb") as handle:
                        data = handle.read(MAX_EVIDENCE_BYTES + 1)
                    if len(data) > MAX_EVIDENCE_BYTES or b"\x00" in data:
                        raise ValueError("Not bounded text")
                    text = data.decode("utf-8")
                    self.respond(200, text)
                except (OSError, ValueError):
                    self.respond(404, "Evidence unavailable: missing, outside this packet, or not UTF-8 text (limit 2 MiB).")
            else:
                self.respond(404, "Route unavailable.")

        do_HEAD = do_GET

        def refuse(self):
            self.respond(405, "Read-only preview; use the local CLI for updates.")

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = refuse

    http = PacketHTTPServer(("127.0.0.1", 0), Handler)
    http.identity = identity
    return http


@contextmanager
def _service_lock(packet_dir):
    """A separate, persistent nonblocking OS lock held for the service lifetime."""
    path = Path(packet_dir) / "runtime/.service.lock"
    with path.open("a+b") as handle:
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
        try:
            acquire()
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise ConflictError("Packet preview service is already locked") from exc
            raise
        try:
            yield
        finally:
            release()


def _descriptor(packet_dir):
    path = Path(packet_dir) / "runtime/service.json"
    if not path.exists():
        return None
    try:
        value = _read_json(path)
        config = _read_config(Path(packet_dir))
        if not isinstance(value, dict) or set(value) != {"packet_id", "tool_version", "instance_id", "port"}:
            raise ValueError("Invalid service descriptor fields")
        _uuid(value["instance_id"])
        if value["packet_id"] != config["packet_id"] or value["tool_version"] != TOOL_VERSION:
            raise ValueError("Service descriptor packet/tool identity mismatch")
        if type(value["port"]) is not int or not 1 <= value["port"] <= 65535:
            raise ValueError("Invalid service port")
        return value
    except (SourceError, ValueError, TypeError) as exc:
        raise ConflictError(f"Cannot trust preview descriptor: {exc}") from exc


def _url(descriptor):
    return f"http://127.0.0.1:{descriptor['port']}/"


def _verify(descriptor):
    """Use only a constructed loopback URL; never accept a redirect or proxy."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(_url(descriptor) + "api/identity", timeout=0.35) as response:
            raw = response.read(8193)
            if len(raw) > 8192:
                raise ValueError("Identity response is too large")
            identity = json.loads(raw)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise ConflictError("Endpoint does not provide the expected preview identity") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False
    except ValueError as exc:
        raise ConflictError("Endpoint returned an invalid preview identity") from exc
    expected = {key: descriptor[key] for key in ("packet_id", "tool_version", "instance_id")}
    if identity != expected:
        raise ConflictError("Live preview instance identity differs from its descriptor")
    return True


def service_status(packet_dir: Path) -> dict:
    descriptor = _descriptor(packet_dir)
    if descriptor is None:
        return {"running": False}
    return {**descriptor, "url": _url(descriptor), "running": _verify(descriptor)}


def serve(packet_dir: Path, instance_id: str | None = None) -> dict:
    """Hold the service lock, consume only an exact local stop request, clean up."""
    packet_dir = Path(packet_dir).resolve()
    instance_id = _uuid(instance_id) if instance_id is not None else str(uuid.uuid4())
    runtime = packet_dir / "runtime"
    control = runtime / f"stop-{instance_id}.json"
    with _service_lock(packet_dir):
        http = make_server(packet_dir, instance_id)
        descriptor = {**http.identity, "port": http.server_address[1]}
        published = False
        try:
            _atomic_write(runtime / "service.json", _json_text(descriptor))
            published = True
            http.timeout = 0.1
            while True:
                if control.exists():
                    try:
                        if _read_json(control) == http.identity:
                            break
                    except SourceError:
                        pass
                http.handle_request()
        finally:
            http.server_close()
            control.unlink(missing_ok=True)
            if published:
                # Only delete a descriptor still owned by this instance.
                try:
                    if _read_json(runtime / "service.json") == descriptor:
                        (runtime / "service.json").unlink()
                except SourceError:
                    pass
    return {"stopped": True, "running": False, **http.identity}


def start_service(packet_dir: Path, open_browser: bool = False) -> dict:
    packet_dir = Path(packet_dir).resolve()
    _read_config(packet_dir)
    current = service_status(packet_dir)
    if current["running"]:
        result = {**current, "reused": True}
    else:
        instance_id = str(uuid.uuid4())
        options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                   "stderr": subprocess.DEVNULL, "cwd": str(packet_dir), "close_fds": True}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            options.update(startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            options["start_new_session"] = True
        child = subprocess.Popen([sys.executable, "-X", "utf8", str(packet_dir / "dashboard/panel.py"),
                                  "serve", "--instance", instance_id], **options)
        deadline = time.monotonic() + 9.5
        result = None
        try:
            while time.monotonic() < deadline:
                candidate = service_status(packet_dir)
                if candidate["running"]:
                    result = {**candidate, "reused": candidate["instance_id"] != instance_id}
                    break
                if child.poll() not in (None, 3):
                    raise PreviewError(f"Preview child exited before readiness (exit {child.returncode})")
                time.sleep(0.05)
            if result is None:
                raise PreviewError("Preview did not become identity-ready within 10 seconds")
        finally:
            # Only an owned, unready/losing child may be terminated; never a guessed PID.
            if result is None or result["instance_id"] != instance_id:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=3)
    if open_browser:
        try:
            result["browser_opened"] = bool(webbrowser.open(result["url"]))
        except (OSError, webbrowser.Error) as exc:
            result["browser_opened"] = False
            result["browser_error"] = str(exc)
    return result


def stop_service(packet_dir: Path) -> dict:
    packet_dir = Path(packet_dir).resolve()
    current = service_status(packet_dir)
    if not current["running"]:
        return {**current, "stopped": False}
    identity = {key: current[key] for key in ("packet_id", "tool_version", "instance_id")}
    control = packet_dir / "runtime" / f"stop-{identity['instance_id']}.json"
    _atomic_write(control, _json_text(identity))
    deadline = time.monotonic() + 9.5
    while time.monotonic() < deadline:
        # Descriptor cleanup occurs after socket closure and before lock release.
        if not control.exists() and not _verify(current):
            try:
                with _service_lock(packet_dir):
                    return {**identity, "stopped": True, "running": False}
            except ConflictError:
                # A new service may already hold the lock; it must be a new UUID.
                replacement = _descriptor(packet_dir)
                if replacement and replacement["instance_id"] != identity["instance_id"]:
                    return {**identity, "stopped": True, "running": False}
        time.sleep(0.05)
    raise PreviewError("Verified preview did not stop and release its resources within 10 seconds")
