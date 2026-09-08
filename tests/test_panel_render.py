"""Fixed-resource HTML export; fixtures here are deliberately minimal."""

import json
from contextlib import contextmanager
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from panel_fixtures import NOW, make_event, make_state

from panel_core import render, store


TEMPLATE = ('<!doctype html><meta charset="utf-8"><style><!--PANEL_STYLES--></style>'
            '<script id="panel-data" type="application/json"><!--PANEL_DATA--></script>'
            '<script><!--PANEL_SCRIPT--></script>')


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.packet = Path(self.temp.name) / "packet"
        self.resources = self.packet / "dashboard/resources"
        self.resources.mkdir(parents=True)
        (self.resources / "panel-template.html").write_text(TEMPLATE, encoding="utf-8")
        (self.resources / "panel.css").write_text("body { margin: 0; }", encoding="utf-8")
        (self.resources / "panel.js").write_text("window.panelFixture = true;", encoding="utf-8")

    def embedded(self, html):
        return json.loads(re.search(r'type="application/json">(.*?)</script>', html, re.S).group(1))

    def test_embedded_data_cannot_close_script(self):
        state = make_state()
        attack = '</script><script>alert("x")</script>'
        state["tasks"]["DEMO-001"]["title"] = attack + "\u2028\u2029 中文"
        html = render.render_html(state, self.resources)
        self.assertNotIn(attack, html)
        self.assertIn("\\u003c/script", html)
        self.assertNotIn("\u2028", html)
        self.assertNotIn("\u2029", html)
        self.assertEqual(self.embedded(html), state)

    def test_inline_resources_and_data_are_not_template_expressions(self):
        state = make_state()
        state["packet"]["title"] = "{{ unsafe }} <!--PANEL_SCRIPT-->"
        html = render.render_html(state, self.resources)
        self.assertIn("body { margin: 0; }", html)
        self.assertIn("window.panelFixture = true;", html)
        self.assertEqual(self.embedded(html), state)
        self.assertNotIn('src="', html)
        self.assertNotIn('href="', html)

    def test_missing_or_duplicate_markers_fail_without_guessing(self):
        for marker in ("PANEL_DATA", "PANEL_STYLES", "PANEL_SCRIPT"):
            for replacement in ("", ("<!--" + marker + "-->") * 2):
                with self.subTest(marker=marker, replacement=replacement):
                    template = TEMPLATE.replace("<!--" + marker + "-->", replacement)
                    (self.resources / "panel-template.html").write_text(template, encoding="utf-8")
                    with self.assertRaises(render.RenderError):
                        render.render_html(make_state(), self.resources)

    def test_missing_resources_and_invalid_state_are_reported(self):
        (self.resources / "panel.css").unlink()
        with self.assertRaises(render.RenderError):
            render.render_html(make_state(), self.resources)
        state = make_state()
        state["seq"] = float("nan")
        with self.assertRaises(ValueError):
            render.render_html(state, self.resources)

    def test_export_is_offline_snapshot_and_does_not_modify_state(self):
        state = make_state()
        store.import_snapshot(self.packet, state)
        before = (self.packet / "runtime/state.json").read_bytes()
        result = render.export_snapshot(self.packet)
        self.assertEqual(result, self.packet / "dashboard/index.html")
        self.assertEqual(self.embedded(result.read_text(encoding="utf-8")), state)
        self.assertEqual((self.packet / "runtime/state.json").read_bytes(), before)

    def test_export_failure_keeps_published_state_and_prior_html_then_retry_repairs(self):
        store.import_snapshot(self.packet, make_state())
        output = render.export_snapshot(self.packet)
        before = output.read_bytes()
        event = make_event("accepted", 0, [])
        store.publish(self.packet, event, NOW)
        with patch("panel_core.store.os.replace", side_effect=OSError("HTML write failure")):
            with self.assertRaises(render.RenderError):
                render.export_snapshot(self.packet)
        self.assertEqual(store.read_state(self.packet)["seq"], 1)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(list(output.parent.glob("*.tmp")), [])
        self.assertEqual(store.publish(self.packet, event, NOW)["seq"], 1)
        render.export_snapshot(self.packet)
        self.assertEqual(self.embedded(output.read_text(encoding="utf-8"))["seq"], 1)

    def test_post_export_lock_cleanup_failure_reports_updated_snapshot(self):
        store.import_snapshot(self.packet, make_state())
        actual_lock = render._writer_lock
        @contextmanager
        def fail_after_unlock(packet):
            with actual_lock(packet):
                yield
            raise OSError("lock cleanup failed after HTML replacement")
        with patch("panel_core.render._writer_lock", fail_after_unlock):
            with self.assertRaises(render.RenderError) as caught:
                render.export_snapshot(self.packet)
        self.assertTrue(hasattr(caught.exception, "snapshot_updated"), "RenderError lacks commit metadata")
        self.assertTrue(caught.exception.snapshot_updated)
        html = (self.packet / "dashboard/index.html").read_text(encoding="utf-8")
        self.assertEqual(self.embedded(html), caught.exception.state)


if __name__ == "__main__":
    unittest.main()
