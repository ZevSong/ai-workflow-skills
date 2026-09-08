"""CLI/process integration against copied packets, including Windows Unicode paths."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

from panel_fixtures import make_state, make_event

ASSETS = Path(__file__).resolve().parents[1] / "skills/plan-agent-tasks/assets/dashboard"


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ASSETS / "panel.py").exists(), "The copied packet CLI is not implemented")
        self.temp = tempfile.TemporaryDirectory(prefix="CLI 中文 space ")
        self.addCleanup(self.temp.cleanup)
        self.packet = Path(self.temp.name) / "docs/task-packets/演示 packet"
        shutil.copytree(ASSETS, self.packet / "dashboard", ignore=shutil.ignore_patterns("__pycache__"))
        self.entry = self.packet / "dashboard/panel.py"
        self.state = make_state()
        self.state["source"]["reference"]["path"] = "docs/task-packets/DEMO/runtime/state.json"

    def input(self, value, name="input 中文.json"):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def command(self, *args, code=0):
        completed = subprocess.run([sys.executable, "-X", "utf8", str(self.entry), *args],
                                   cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(completed.returncode, code, completed.stderr + completed.stdout)
        result = json.loads(completed.stdout)
        self.assertIsInstance(result, dict)
        return result

    def init(self):
        plan = {key: deepcopy(self.state[key]) for key in ("packet", "source", "main", "tasks", "sessions", "stages", "checks", "evidence", "dependencies")}
        return self.command("init", "--input", self.input(plan))

    def test_copied_cli_init_export_status_and_input_errors(self):
        self.assertEqual(self.init()["seq"], 0)
        status = self.command("status")
        self.assertEqual(status["packet_id"], "DEMO")
        self.assertEqual(status["service"]["running"], False)
        self.assertTrue(status["snapshot_exists"])
        before = (self.packet / "runtime/state.json").read_bytes()
        self.command("export")
        self.assertEqual((self.packet / "runtime/state.json").read_bytes(), before)
        self.command("init", "--input", self.input({}), code=2)
        self.command("publish", "--unknown", code=2)
        self.command("publish", "--input", "missing.json", code=2)
        self.command("export", "--input", "unneeded.json", code=2)
        (self.packet / "runtime/state.json").write_text("broken")
        self.command("status", code=4)

    def test_legacy_redirected_stdout_preserves_committed_json_and_error_flags(self):
        self.state["source"]["reference"] = {
            "repository": "演示仓库🚀", "path": "docs/task-packets/演示🚀/runtime/state.json",
        }
        plan = {key: deepcopy(self.state[key]) for key in ("packet", "source", "main", "tasks", "sessions", "stages", "checks", "evidence", "dependencies")}
        environment = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252:strict"}
        # No -X utf8: capture raw redirected bytes from the actual copied entrypoint.
        def run(*args):
            return subprocess.run([sys.executable, str(self.entry), *args], cwd=self.temp.name,
                                  capture_output=True, env=environment, timeout=15)
        initialized = run("init", "--input", self.input(plan))
        disk = json.loads((self.packet / "runtime/state.json").read_text(encoding="utf-8"))
        self.assertEqual(disk["source"]["reference"], self.state["source"]["reference"])
        self.assertTrue((self.packet / "dashboard/index.html").is_file())
        self.assertEqual(initialized.returncode, 0, initialized.stderr.decode("cp1252"))
        result = json.loads(initialized.stdout.decode("ascii"))
        self.assertEqual(result["source"]["reference"], self.state["source"]["reference"])
        self.assertTrue(result["state_published"])
        self.assertTrue(result["snapshot_updated"])
        event = make_event("LEGACY-1", 0, [{"type": "task.set", "id": "DEMO-001", "changes": {"status": "implementing", "progress": "进展🚀"}}])
        (self.packet / "dashboard/resources/panel.css").unlink()
        failed = run("publish", "--input", self.input(event))
        self.assertEqual(failed.returncode, 6, failed.stderr.decode("cp1252"))
        self.assertTrue(failed.stderr, "A restrictive code page must also retain diagnostics")
        result = json.loads(failed.stdout.decode("ascii"))
        self.assertTrue(result["state_published"])
        self.assertFalse(result["snapshot_updated"])
        self.assertEqual(result["seq"], 1)
        self.assertEqual(result["source"]["reference"], self.state["source"]["reference"])
        disk = json.loads((self.packet / "runtime/state.json").read_text(encoding="utf-8"))
        self.assertEqual(disk["tasks"]["DEMO-001"]["progress"], "进展🚀")

    def test_publish_partial_export_failure_retry_and_conflict(self):
        self.init()
        event = make_event("EVENT-1", 0, [{"type": "task.set", "id": "DEMO-001", "changes": {"status": "implementing"}}])
        event_file = self.input(event)
        resource = self.packet / "dashboard/resources/panel.css"
        contents = resource.read_bytes()
        resource.unlink()
        failed = self.command("publish", "--input", event_file, code=6)
        self.assertTrue(failed["state_published"])
        self.assertFalse(failed["snapshot_updated"])
        self.assertEqual(failed["seq"], 1)
        resource.write_bytes(contents)
        self.command("export")
        repeated = self.command("publish", "--input", event_file)
        self.assertEqual(repeated["seq"], 1)
        state = json.loads((self.packet / "runtime/state.json").read_text(encoding="utf-8"))
        self.assertEqual(len(state["events"]), 1)
        event["event_id"] = "EVENT-2"
        self.command("publish", "--input", self.input(event), code=3)

    def test_import_preserves_done_rounds_and_history_and_refuses_overwrite(self):
        state = self.state
        state["tasks"]["DEMO-001"]["round"] = 2
        state["tasks"]["DEMO-001"]["status"] = "done"
        state["evidence"]["RESULT"] = {"title": "Actual retained evidence", "reference": {"repository": "demo", "path": "reports/checked.md"}}
        for cid in state["tasks"]["DEMO-001"]["required_check_ids"]:
            state["checks"][cid].update(round=2, result="PASS", evidence_ids=["RESULT"])
        state["packet"]["run_number"] = 2
        old = make_state()
        old["packet"]["lifecycle"] = "finished"
        old.pop("history")
        state["history"] = [old]
        snapshot = self.input(state)
        self.command("import", "--input", snapshot)
        self.assertEqual(json.loads((self.packet / "runtime/state.json").read_text(encoding="utf-8")), state)
        self.command("import", "--input", snapshot, code=3)
        (self.packet / "runtime/state.json").unlink()
        state["packet"]["id"] = "OTHER"
        state["history"][0]["packet"]["id"] = "OTHER"
        self.command("import", "--input", self.input(state), code=3)

    def test_storage_and_render_commit_metadata_in_real_child(self):
        self.init()
        event = make_event("METADATA-1", 0, [{"type": "task.set", "id": "DEMO-001", "changes": {"status": "implementing"}}])
        event_file = self.input(event)
        # Inject only OS-lock cleanup faults around real replacement and export.
        bootstrap = '''
import contextlib, json, sys
sys.path.insert(0, sys.argv[1])
from panel_core import cli, store, render
mode = sys.argv[2]
original = store._writer_lock
@contextlib.contextmanager
def broken_lock(packet):
    if mode == 'before':
        raise OSError('injected pre-publication storage error')
    with original(packet):
        yield
    raise OSError('injected post-replacement cleanup error')
if mode == 'render':
    render._writer_lock = broken_lock
else:
    store._writer_lock = broken_lock
raise SystemExit(cli.main(['publish', '--input', sys.argv[3]]))
'''
        for mode, code, published, snapshot in (("before", 4, False, False), ("after", 4, True, False), ("render", 6, True, True)):
            with self.subTest(mode=mode):
                completed = subprocess.run([sys.executable, "-X", "utf8", "-c", bootstrap, str(self.entry.parent), mode, event_file], capture_output=True, text=True, encoding="utf-8", timeout=15)
                self.assertEqual(completed.returncode, code, completed.stderr)
                result = json.loads(completed.stdout)
                self.assertEqual(result["state_published"], published)
                self.assertEqual(result["snapshot_updated"], snapshot)
                if published:
                    self.assertEqual(result["seq"], 1)
                    disk = json.loads((self.packet / "runtime/state.json").read_text(encoding="utf-8"))
                    self.assertEqual(len(disk["events"]), 1)
                else:
                    self.assertNotIn("seq", result)
                if snapshot:
                    self.assertEqual(result["snapshot_seq"], 1)
                    self.assertIn('"seq":1', (self.packet / "dashboard/index.html").read_text(encoding="utf-8"))

    def test_unready_child_is_cleaned_up_and_lock_can_be_reacquired(self):
        self.init()
        original = self.entry.read_text(encoding="utf-8")
        # Real child acquires service lock but never publishes readiness.
        self.entry.write_text("import pathlib,time\nfrom panel_core.server import _service_lock\nwith _service_lock(pathlib.Path(__file__).resolve().parent.parent):\n    time.sleep(60)\n", encoding="utf-8")
        bootstrap = "import sys;sys.path.insert(0,sys.argv[1]);from panel_core.cli import main;raise SystemExit(main(['start']))"
        completed = subprocess.run([sys.executable, "-X", "utf8", "-c", bootstrap, str(self.entry.parent)], capture_output=True, text=True, encoding="utf-8", timeout=14)
        self.assertEqual(completed.returncode, 5, completed.stderr)
        self.assertFalse(json.loads(completed.stdout)["state_published"])
        self.entry.write_text(original, encoding="utf-8")
        self.addCleanup(lambda: self.command("stop"))
        self.assertTrue(self.command("start")["running"])
        self.assertTrue(self.command("stop")["stopped"])

    def test_export_summary_read_failure_keeps_snapshot_commit_flag(self):
        self.init()
        bootstrap = "import sys;sys.path.insert(0,sys.argv[1]);from panel_core import cli;from panel_core.store import SourceError;cli.read_state=lambda packet: (_ for _ in ()).throw(SourceError('injected summary read failure'));raise SystemExit(cli.main(['export']))"
        completed = subprocess.run([sys.executable, "-X", "utf8", "-c", bootstrap, str(self.entry.parent)], capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(completed.returncode, 4)
        result = json.loads(completed.stdout)
        self.assertFalse(result["state_published"])
        self.assertTrue(result["snapshot_updated"], "Successful export followed by a summary-read failure must retain its commit flag")

    def test_real_start_reuse_status_stop_and_lock_release(self):
        self.init()
        if sys.platform == "win32":
            # Observe the actual background child's console, not just Popen arguments.
            self.entry.write_text("import sys,ctypes,pathlib\nif 'serve' in sys.argv:\n    pathlib.Path(__file__).resolve().parent.parent.joinpath('runtime/console.txt').write_text(str(ctypes.windll.kernel32.GetConsoleWindow()))\n" + self.entry.read_text(encoding="utf-8"), encoding="utf-8")
        self.addCleanup(lambda: self.command("stop"))
        first = self.command("start")
        self.assertTrue(first["running"])
        self.assertFalse(first["reused"])
        if sys.platform == "win32":
            self.assertEqual((self.packet / "runtime/console.txt").read_text(), "0")
        reused = self.command("start")
        self.assertTrue(reused["reused"])
        self.assertEqual(first["instance_id"], reused["instance_id"])
        self.assertEqual(self.command("status")["service"]["instance_id"], first["instance_id"])
        with urllib.request.urlopen(first["url"] + "api/status", timeout=2) as response:
            self.assertEqual(json.load(response)["state"]["seq"], 0)
        stopped = self.command("stop")
        self.assertTrue(stopped["stopped"])
        self.assertFalse(self.command("status")["service"]["running"])
        self.assertFalse((self.packet / "runtime/service.json").exists())
        self.assertEqual(list((self.packet / "runtime").glob("stop-*.json")), [])
        with self.assertRaises((urllib.error.URLError, OSError)):
            urllib.request.urlopen(first["url"] + "api/identity", timeout=1)
        again = self.command("start")
        self.assertNotEqual(first["instance_id"], again["instance_id"])
        self.assertTrue(self.command("stop")["stopped"])

    def test_concurrent_starts_share_one_instance(self):
        self.init()
        self.addCleanup(lambda: self.command("stop"))
        children = [subprocess.Popen([sys.executable, "-X", "utf8", str(self.entry), "start"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8") for _ in range(2)]
        results = []
        try:
            for child in children:
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, out + err)
                results.append(json.loads(out))
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
                child.stdout.close()
                child.stderr.close()
        self.assertEqual(results[0]["instance_id"], results[1]["instance_id"])
        self.assertTrue(self.command("stop")["stopped"])

    def test_stop_rejects_mismatched_instance_without_control_file(self):
        self.init()
        self.addCleanup(lambda: self.command("stop"))
        first = self.command("start")
        path = self.packet / "runtime/service.json"
        good = path.read_text(encoding="utf-8")
        descriptor = json.loads(good)
        try:
            for key, bad in (("instance_id", "00000000-0000-0000-0000-000000000000"), ("packet_id", "OTHER"), ("tool_version", "9.9"), ("port", True)):
                malformed = {**descriptor, key: bad}
                path.write_text(json.dumps(malformed), encoding="utf-8")
                self.command("stop", code=3)
                self.assertEqual(list(path.parent.glob("stop-*.json")), [])
                with urllib.request.urlopen(first["url"] + "api/identity", timeout=2) as response:
                    self.assertEqual(json.load(response)["instance_id"], first["instance_id"])
        finally:
            path.write_text(good, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
