"""Real filesystem and process tests for per-packet state publication."""

from copy import deepcopy
from contextlib import contextmanager
import json
import multiprocessing
from pathlib import Path
from queue import Empty
import tempfile
import unittest
from unittest.mock import patch

from panel_fixtures import NOW, make_event, make_state
from panel_core.contract import ContractError

from panel_core import store


def plan():
    state = make_state()
    return {key: deepcopy(state[key]) for key in (
        "packet", "source", "main", "tasks", "sessions", "stages",
        "checks", "evidence", "dependencies",
    )}


def concurrent_publish(packet, event_id, ready, go, results):
    ready.put(event_id)
    if not go.wait(10):
        results.put("timeout")
        return
    try:
        store.publish(Path(packet), make_event(event_id, 0, []), NOW)
        results.put("accepted")
    except store.ConflictError:
        results.put("conflict")
    except Exception as exc:
        results.put(type(exc).__name__ + ": " + str(exc))


def hold_writer_lock(packet, ready):
    with store._writer_lock(Path(packet)):
        ready.set()
        # The parent terminates this actual lock holder to exercise OS cleanup.
        multiprocessing.Event().wait(30)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.packet = Path(self.temp.name) / "packet"

    def init(self, value=None):
        return store.initialize(self.packet, value or plan(), NOW)

    def test_initialize_explicit_config_and_read_preserve_state(self):
        state = self.init()
        self.assertEqual(store.read_state(self.packet), state)
        config = json.loads((self.packet / "runtime/panel.json").read_text())
        self.assertEqual(config, {
            "packet_id": "DEMO", "source_mode": "local", "reference": plan()["source"]["reference"],
            "target": "state.json",
        })
        self.assertEqual(state["seq"], 0)
        self.assertIsNone(state["observed_at"])

    def test_existing_state_is_never_overwritten_by_initialize_or_import(self):
        self.init()
        store.publish(self.packet, make_event("first", 0, []), NOW)
        old = (self.packet / "runtime/state.json").read_bytes()
        for action in (lambda: self.init(), lambda: store.import_snapshot(self.packet, make_state())):
            with self.assertRaises(store.ConflictError):
                action()
            self.assertEqual((self.packet / "runtime/state.json").read_bytes(), old)

    def test_import_preserves_run_events_and_observation(self):
        from panel_core.contract import apply_event
        state = apply_event(make_state(), make_event("imported", 0, []), NOW)
        self.assertEqual(store.import_snapshot(self.packet, state), state)
        self.assertEqual(store.read_state(self.packet), state)

    def test_invalid_input_cannot_create_configuration(self):
        value = plan()
        value["source"]["mode"] = "guessed"
        with self.assertRaises(ContractError):
            self.init(value)
        self.assertFalse((self.packet / "runtime/panel.json").exists())

    def test_seq_conflict_does_not_write(self):
        self.init()
        with self.assertRaises(store.ConflictError):
            store.publish(self.packet, make_event("wrong", 7, []), NOW)
        self.assertEqual(store.read_state(self.packet)["seq"], 0)

    def test_retry_after_later_event_returns_current_state_without_rewriting(self):
        self.init()
        first = make_event("first", 0, [])
        accepted = store.publish(self.packet, first, NOW)
        later = store.publish(self.packet, make_event("later", 1, []), "2026-09-08T08:01:00Z")
        target = self.packet / "runtime/state.json"
        before = target.stat().st_mtime_ns
        result = store.publish(self.packet, first, "2026-09-08T08:02:00Z")
        self.assertEqual(result, later)
        self.assertEqual(result["events"][0], accepted["events"][0])
        self.assertEqual(target.stat().st_mtime_ns, before)
        self.assertEqual(store.read_state(self.packet)["seq"], 2)

    def test_event_id_cannot_be_reused_with_changed_body(self):
        self.init()
        event = make_event("same", 0, [])
        store.publish(self.packet, event, NOW)
        event["summary"] = "changed"
        with self.assertRaises(store.ConflictError):
            store.publish(self.packet, event, NOW)
        self.assertEqual(store.read_state(self.packet)["seq"], 1)

    def test_all_operations_rejected_together_and_lock_released(self):
        self.init()
        event = make_event("invalid", 0, [
            {"type": "task.set", "id": "DEMO-001", "changes": {"status": "implementing"}},
            {"type": "task.set", "id": "typo", "changes": {"status": "implementing"}},
        ])
        with self.assertRaises(ContractError):
            store.publish(self.packet, event, NOW)
        self.assertEqual(store.read_state(self.packet)["tasks"]["DEMO-001"]["status"], "pending")
        self.assertEqual(store.publish(self.packet, make_event("valid", 0, []), NOW)["seq"], 1)

    def test_failed_replace_preserves_old_complete_file_and_releases_lock(self):
        self.init()
        target = self.packet / "runtime/state.json"
        before = target.read_bytes()
        with patch("panel_core.store.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(store.WriteError) as caught:
                store.publish(self.packet, make_event("failed", 0, []), NOW)
        self.assertTrue(hasattr(caught.exception, "state_published"), "WriteError lacks commit metadata")
        self.assertFalse(caught.exception.state_published)
        self.assertIsNone(caught.exception.state)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(target.parent.glob("*.tmp")), [])
        self.assertEqual(store.publish(self.packet, make_event("retry", 0, []), NOW)["seq"], 1)

    def test_post_commit_lock_cleanup_failure_reports_accepted_state(self):
        self.init()
        actual_lock = store._writer_lock
        @contextmanager
        def fail_after_unlock(packet):
            with actual_lock(packet):
                yield
            raise OSError("lock cleanup failed after publication")
        with patch("panel_core.store._writer_lock", fail_after_unlock):
            with self.assertRaises(store.WriteError) as caught:
                store.publish(self.packet, make_event("accepted-before-error", 0, []), NOW)
        self.assertTrue(hasattr(caught.exception, "state_published"), "WriteError lacks commit metadata")
        self.assertTrue(caught.exception.state_published)
        self.assertEqual(caught.exception.state["seq"], 1)
        self.assertEqual(store.read_state(self.packet), caught.exception.state)

    def test_failed_state_creation_recovers_matching_config_without_overwrite(self):
        original_replace = store.os.replace
        def fail_state(source, destination):
            if Path(destination).name == "state.json":
                raise OSError("state creation failed")
            return original_replace(source, destination)
        with patch("panel_core.store.os.replace", side_effect=fail_state):
            with self.assertRaises(OSError):
                self.init()
        self.assertTrue((self.packet / "runtime/panel.json").exists())
        self.assertFalse((self.packet / "runtime/state.json").exists())
        changed = plan()
        changed["packet"]["id"] = "OTHER"
        with self.assertRaises(store.ConflictError):
            self.init(changed)
        self.assertEqual(self.init()["packet"]["id"], "DEMO")

    def test_existing_target_without_config_is_not_adopted_or_overwritten(self):
        runtime = self.packet / "runtime"
        runtime.mkdir(parents=True)
        (runtime / "state.json").write_text("legacy data")
        with self.assertRaises(store.ConflictError):
            self.init()
        self.assertEqual((runtime / "state.json").read_text(), "legacy data")
        self.assertFalse((runtime / "panel.json").exists())

    def test_projection_writes_view_and_never_touches_original_source(self):
        runtime = self.packet / "runtime"
        runtime.mkdir(parents=True)
        source = runtime / "state.json"
        source.write_text("original unknown source format")
        value = plan()
        value["source"]["mode"] = "projection"
        value["source"]["reference"] = {"url": "https://example.com/main.json"}
        self.init(value)
        store.publish(self.packet, make_event("projection", 0, []), NOW)
        self.assertEqual(source.read_text(), "original unknown source format")
        self.assertEqual(store.read_state(self.packet)["seq"], 1)
        self.assertEqual(json.loads((runtime / "panel.json").read_text())["target"], "view.json")

    def test_read_never_guesses_authority_from_existing_files(self):
        self.init()
        runtime = self.packet / "runtime"
        (runtime / "view.json").write_text("{}")
        self.assertEqual(store.read_state(self.packet)["packet"]["id"], "DEMO")
        (runtime / "panel.json").unlink()
        with self.assertRaises(store.SourceError):
            store.read_state(self.packet)

    def test_config_rejects_target_escape_mode_mismatch_and_identity_mismatch(self):
        self.init()
        config_file = self.packet / "runtime/panel.json"
        original = json.loads(config_file.read_text())
        for changes in ({"target": "../outside.json"}, {"target": "view.json"},
                        {"source_mode": "unknown"}, {"packet_id": "OTHER"},
                        {"reference": {"url": "https://example.com/different"}}, {"extra": True}):
            with self.subTest(changes=changes):
                config_file.write_text(json.dumps(original | changes))
                with self.assertRaises(store.SourceError):
                    store.read_state(self.packet)

    def test_invalid_or_missing_source_never_creates_an_alternate_state(self):
        self.init()
        target = self.packet / "runtime/state.json"
        for data in ("{", "{}", '{"schema_version": NaN}'):
            target.write_text(data)
            with self.assertRaises(store.SourceError):
                store.read_state(self.packet)
            with self.assertRaises(store.SourceError):
                store.publish(self.packet, make_event("invalid-source", 0, []), NOW)
        target.unlink()
        with self.assertRaises(store.SourceError):
            store.read_state(self.packet)
        self.assertFalse((target.parent / "view.json").exists())

    def test_two_packets_have_independent_sequences(self):
        self.init()
        other = self.packet.parent / "other"
        store.initialize(other, plan(), NOW)
        store.publish(self.packet, make_event("first", 0, []), NOW)
        self.assertEqual(store.read_state(other)["seq"], 0)

    def test_two_real_processes_with_same_seq_accept_exactly_one(self):
        self.init()
        context = multiprocessing.get_context("spawn")
        ready, results, go = context.Queue(), context.Queue(), context.Event()
        processes = [context.Process(target=concurrent_publish, args=(str(self.packet), identity, ready, go, results))
                     for identity in ("process-a", "process-b")]
        for process in processes:
            process.start()
            self.addCleanup(lambda p=process: p.is_alive() and p.terminate())
        for _ in processes:
            ready.get(timeout=10)
        go.set()
        self.assertCountEqual([results.get(timeout=15) for _ in processes], ["accepted", "conflict"])
        for process in processes:
            process.join(10)
            self.assertEqual(process.exitcode, 0)
        state = store.read_state(self.packet)
        self.assertEqual(state["seq"], 1)
        self.assertEqual(len(state["events"]), 1)

    def test_process_exit_releases_os_lock_without_deleting_lock_file(self):
        self.init()
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        process = context.Process(target=hold_writer_lock, args=(str(self.packet), ready))
        process.start()
        self.addCleanup(lambda: process.is_alive() and process.terminate())
        self.assertTrue(ready.wait(10))
        waiting, results, go = context.Queue(), context.Queue(), context.Event()
        writer = context.Process(target=concurrent_publish,
                                 args=(str(self.packet), "after-exit", waiting, go, results))
        writer.start()
        self.addCleanup(lambda: writer.is_alive() and writer.terminate())
        waiting.get(timeout=10)
        go.set()
        with self.assertRaises(Empty):
            results.get(timeout=0.3)
        self.assertEqual(store.read_state(self.packet)["seq"], 0)
        process.terminate()
        process.join(10)
        self.assertTrue((self.packet / "runtime/.writer.lock").exists())
        self.assertEqual(results.get(timeout=10), "accepted")
        writer.join(10)
        self.assertEqual(writer.exitcode, 0)
        self.assertEqual(store.read_state(self.packet)["seq"], 1)


if __name__ == "__main__":
    unittest.main()
