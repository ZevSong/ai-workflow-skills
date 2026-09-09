"""Real loopback boundaries; every listener and worker is closed by cleanup."""
from copy import deepcopy
import json
import socket
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid

from panel_fixtures import make_state
from panel_core.store import import_snapshot
from panel_core import server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="panel 中文 space ")
        self.addCleanup(self.temp.cleanup)
        self.packet = Path(self.temp.name) / "relocated packet"
        self.state = make_state()
        self.state["source"]["reference"]["path"] = "docs/task-packets/DEMO/runtime/state.json"
        self.state["evidence"] = {
            "GOOD": {"title": "Report", "reference": {"repository": "demo", "path": "docs/task-packets/DEMO/reports/result.md"}},
            "CROSS": {"title": "Other repo", "reference": {"repository": "other", "path": "docs/task-packets/DEMO/reports/result.md"}},
            "OUTSIDE": {"title": "Outside", "reference": {"repository": "demo", "path": "reports/secret.md"}},
            "MISSING": {"title": "Missing", "reference": {"repository": "demo", "path": "docs/task-packets/DEMO/reports/missing.md"}},
        }
        import_snapshot(self.packet, self.state)
        (self.packet / "reports").mkdir()
        (self.packet / "reports/result.md").write_text("中文 <script>alert(1)</script>", encoding="utf-8")
        (self.packet / "dashboard").mkdir()
        (self.packet / "dashboard/index.html").write_text("<html>snapshot</html>", encoding="utf-8")
        self.http, self.base = self.start(self.packet)

    def start(self, packet):
        http = server.make_server(packet, str(uuid.uuid4()))
        thread = threading.Thread(target=http.serve_forever)
        thread.start()
        def close():
            http.shutdown()
            thread.join(3)
            http.server_close()
            self.assertFalse(thread.is_alive())
            self.assertEqual(http.socket.fileno(), -1)
        self.addCleanup(close)
        return http, "http://127.0.0.1:" + str(http.server_address[1])

    def request(self, path, method="GET"):
        req = urllib.request.Request(self.base + path, method=method)
        try:
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as response:
            with response:
                return response.code, response.headers, response.read()

    def test_fixed_routes_identity_head_and_no_writes(self):
        code, headers, body = self.request("/api/identity")
        identity = json.loads(body)
        self.assertEqual(code, 200)
        self.assertEqual(identity["packet_id"], "DEMO")
        self.assertEqual(identity["tool_version"], "0.1.0")
        uuid.UUID(identity["instance_id"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        for path in ("/", "/index.html", "/api/status", "/api/identity", "/evidence/GOOD"):
            with self.subTest(path=path):
                get = self.request(path)
                head = self.request(path, "HEAD")
                self.assertEqual(head[0], 200)
                self.assertEqual(head[2], b"")
                self.assertEqual(head[1]["Content-Length"], str(len(get[2])))
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            self.assertEqual(self.request("/api/status", method)[0], 405)
        for path in ("/runtime/state.json", "/api/stop", "/api/status?path=secret", "/../secret", "/%2e%2e/secret", "/evidence/%2e%2e", "/evidence/GOOD/extra", "/evidence/GOOD%2fextra", "/unknown"):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_relocated_nested_evidence_has_only_packet_scope(self):
        code, headers, body = self.request("/evidence/GOOD")
        self.assertEqual(code, 200)
        self.assertEqual(body.decode("utf-8"), "中文 <script>alert(1)</script>")
        self.assertIn("text/plain", headers["Content-Type"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        for evidence in ("CROSS", "OUTSIDE", "MISSING"):
            code, _, body = self.request("/evidence/" + evidence)
            self.assertEqual(code, 404)
            self.assertIn("unavailable", body.decode())

    def test_failed_source_keeps_last_good_without_refreshing_observation(self):
        first = json.loads(self.request("/api/status")[2])
        self.assertEqual(first, {"state": self.state, "sync_error": None})
        path = self.packet / "runtime/state.json"
        path.write_text("broken", encoding="utf-8")
        stale = json.loads(self.request("/api/status")[2])
        self.assertEqual(stale["state"], self.state)
        self.assertTrue(stale["sync_error"])
        self.assertEqual(self.request("/evidence/GOOD")[0], 503)
        _, other = self.start(self.packet)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(other + "/api/status", timeout=2)
        with error.exception:
            self.assertEqual(error.exception.code, 503)
            self.assertIsNone(json.load(error.exception)["state"])
        path.write_text(json.dumps(self.state), encoding="utf-8")
        self.assertIsNone(json.loads(self.request("/api/status")[2])["sync_error"])

    def test_distinct_packet_ports_and_identities(self):
        second = self.packet.parent / "second"
        state = deepcopy(self.state)
        state["packet"]["id"] = "SECOND"
        import_snapshot(second, state)
        _, base = self.start(second)
        with urllib.request.urlopen(base + "/api/identity", timeout=2) as response:
            identity = json.load(response)
        self.assertNotEqual(base, self.base)
        self.assertEqual(identity["packet_id"], "SECOND")
        self.assertNotEqual(identity["instance_id"], json.loads(self.request("/api/identity")[2])["instance_id"])

    def test_shutdown_closes_preopened_client_socket(self):
        with socket.create_connection(self.http.server_address, timeout=2) as client:
            client.sendall(b"GET /api/status HTTP/1.0\r\n")
            # A complete second request proves the accept loop passed the first socket.
            self.assertEqual(self.request("/api/identity")[0], 200)
            self.http.shutdown()
            self.http.server_close()
            try:
                self.assertEqual(client.recv(1), b"")
            except ConnectionResetError:
                pass
            except TimeoutError:
                self.fail("Preview shutdown left a preopened client socket alive")


if __name__ == "__main__":
    unittest.main()
