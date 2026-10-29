"""A return preserves the workspace and slow apps don't delay other launches."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_resume import r


@unittest.skipIf(os.name == "nt", "Linux restore lock")
class ConcurrentReturn(unittest.TestCase):
    def test_more_than_twelve_apps_survive_the_checkpoint_and_return_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trip.json"
            apps = [f"app{i}.desktop" for i in range(16)]
            r.atomic_write(path, {"version": 2, "time": 100, "boot": "old", "apps": apps, "done": []})
            launches = []
            def snapshot():
                return [{"app": app, "id": app} for app in launches]
            with patch.object(r, "boot_id", return_value="new"), patch.object(r.time, "time", return_value=110), \
                    patch.object(r.time, "sleep"), patch.object(r, "window_snapshot", side_effect=snapshot):
                self.assertEqual(r.restore(path, path.with_name("off"), lambda: [], lambda _: True, launches.append), apps)
            self.assertEqual(launches, apps)
            report = r.read_state(r.return_path(path))
            self.assertTrue(r.valid_return(report))
            self.assertEqual(set(report["items"]), set(apps))
            self.assertFalse(path.exists())

    def test_late_startup_resize_settles_before_saved_geometry_is_applied(self):
        frame = {"app": "a.desktop", "id": "old", "rect": {"x": 1, "y": 2, "width": 800, "height": 600}}
        small = {"app": "a.desktop", "id": "new", "rect": {"width": 400, "height": 300}}
        large = dict(small, rect={"width": 600, "height": 500})
        with tempfile.TemporaryDirectory() as tmp, patch.object(r, "window_snapshot", side_effect=[[small], [large], [large]]), \
                patch.object(r, "place_windows", return_value=[]) as place:
            job = r.restore_regular("a.desktop", {"windows": [frame]}, Path(tmp)/"off", lambda _: None, set())
            next(job)  # Launch.
            next(job); place.assert_not_called()  # First paint.
            next(job); place.assert_not_called()  # App's startup resize.
            next(job); place.assert_called_once()  # Stable, then Wayland gets a frame.
            with self.assertRaises(StopIteration) as done:
                next(job)
            self.assertTrue(done.exception.value)

    def test_slow_first_app_does_not_delay_launch_or_receipt_for_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trip.json"
            r.atomic_write(path, {"version": 2, "time": 100, "boot": "old",
                                  "apps": ["slow.desktop", "fast.desktop"], "windows": [], "done": []})
            clock = [0.0]; launches = []; receipts = []
            def launch(app):
                launches.append((app, clock[0]))
            def sleep(seconds):
                clock[0] += seconds
                report = r.read_state(path).get("done", [])
                if "fast.desktop" in report:
                    receipts.append(clock[0])
            def snapshot():
                return [{"app": "fast.desktop", "id": "fast"}] if clock[0] else []
            with patch.object(r, "boot_id", return_value="new"), patch.object(r.time, "time", return_value=110), \
                    patch.object(r.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(r.time, "sleep", side_effect=sleep), patch.object(r, "window_snapshot", side_effect=snapshot):
                result = r.restore(path, path.with_name("off"), lambda: [], lambda _: True, launch)
            self.assertEqual(launches, [("slow.desktop", 0.0), ("fast.desktop", 0.0)])
            self.assertEqual(result, ["fast.desktop"])
            self.assertLess(min(receipts), 1)
            self.assertEqual(r.read_state(path)["done"], ["fast.desktop"])

    def test_native_browser_verification_does_not_block_editor_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trip.json"
            r.atomic_write(path, {"version": 2, "time": 100, "boot": "old",
                "apps": [r.BROWSER, "a.desktop"], "browser": {"mode": "native", "profile": "work"}, "done": []})
            browser = r.browser_helper(); events = []
            def ready(*args):
                events.append("verify")
                self.assertIn("editor-start", events)
                return None
            with patch.object(r, "boot_id", return_value="new"), patch.object(r.time, "time", return_value=110), \
                    patch.object(r.time, "sleep"), patch.object(r, "window_snapshot", return_value=[]), \
                    patch.object(browser, "valid", return_value=True), patch.object(browser, "launching", return_value=False), \
                    patch.object(browser, "prepare", return_value={"digest": "expected"}), \
                    patch.object(browser, "process_start", return_value=110), \
                    patch.object(browser, "launch", side_effect=lambda *_: events.append("browser-start") or 42), \
                    patch.object(browser, "ready", side_effect=ready):
                r.restore(path, path.with_name("off"), lambda: [], lambda _: True,
                          lambda _: events.append("editor-start"))
            self.assertEqual(events[:2], ["browser-start", "editor-start"])
            self.assertEqual(events.count("browser-start"), 1)
            self.assertEqual(events.count("editor-start"), 1)


class DesktopPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            raise unittest.SkipTest("Qt JavaScript engine required")
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.Engine = QJSEngine

    def setUp(self):
        self.engine = self.Engine()
        setup = r"""
        var desks = [{id:"work", name:"Work"}, {id:"play", name:"Play"}];
        var frames = ["one", "two"].map((id, i) => ({internalId:id, desktopFileName:"app" + i,
            normalWindow:true, skipTaskbar:false, transient:false, desktops:[desks[0]],
            onAllDesktops:false, keepAbove:false, keepBelow:false, minimized:false,
            frameGeometry:{}, setMaximize:function(h,v) {this.maximized = h && v;}}));
        var raised = [], result;
        var workspace = {desktops:desks, currentDesktop:desks[0], currentActivity:"main",
            cursorPos:{x:10,y:20}, windowList:()=>frames, raiseWindow:w=>raised.push(w.internalId),
            activeWindow:frames[1]};
        function reply(v) {result=v;}
        """
        self.evaluate(setup + r.WINDOWS_JS)
        self.saved = {"scene": {"desktop": {"id": "play", "name": "Play"}},
            "windows": [{"app": "app0.desktop", "id": "old0", "stack": 2, "active": True},
                        {"app": "app1.desktop", "id": "old1", "stack": 1, "active": False}],
            "window_map": [{"old": "old0", "new": "one", "app": "app0.desktop"},
                           {"old": "old1", "new": "two", "app": "app1.desktop"}]}
        self.initial = {"desktop": {"id": "work"}, "activity": "main", "cursor": {"x": 10, "y": 20}}

    def evaluate(self, code):
        result = self.engine.evaluate(code)
        self.assertFalse(result.isError(), result.toString())
        return result

    def script(self, body):
        self.evaluate(body)
        return json.loads(self.evaluate("JSON.stringify(result)").toString())

    def value(self, expression):
        return json.loads(self.evaluate("JSON.stringify(" + expression + ")").toString())

    def test_virtual_desktop_and_above_below_are_restored_without_touching_existing(self):
        area = {"x": 0, "y": 0, "width": 1920, "height": 1080}
        old = {"app": "app0.desktop", "id": "old", "rect": {"x": 70, "y": 90, "width": 800, "height": 600},
               "area": area, "desktops": [{"id": "play", "name": "Play"}], "allDesktops": False,
               "above": True, "below": False}
        current = [{"app": "app0.desktop", "id": "existing", "area": area},
                   {"app": "app0.desktop", "id": "one", "area": area}]
        with patch.object(r, "kwin_script", side_effect=self.script):
            mappings = r.place_windows([old], current, {"existing"})
        self.assertEqual(mappings, [{"old": "old", "new": "one", "app": "app0.desktop"}])
        self.assertEqual(self.value("frames[0].desktops.map(d=>d.id)"), ["play"])
        self.assertTrue(self.value("frames[0].keepAbove"))
        self.assertEqual(self.value("frames[0].frameGeometry"), old["rect"])

    def test_return_restores_desktop_stacking_and_active_window(self):
        self.evaluate("frames[0].desktops=[desks[1]];")
        with patch.object(r, "kwin_script", side_effect=self.script):
            r.finish_desktop(self.saved, [], self.initial)
        self.assertEqual(self.value("raised"), ["two", "one"])
        self.assertEqual(self.value("workspace.currentDesktop.id"), "play")
        self.assertEqual(self.value("workspace.activeWindow.internalId"), "one")

    def test_user_mouse_movement_keeps_their_current_focus_and_order(self):
        self.evaluate("workspace.cursorPos.x=11;")
        with patch.object(r, "kwin_script", side_effect=self.script):
            r.finish_desktop(self.saved, [], self.initial)
        self.assertEqual(self.value("raised"), [])
        self.assertEqual(self.value("workspace.currentDesktop.id"), "work")

    def test_user_opened_another_window_keeps_their_current_focus_and_order(self):
        self.evaluate("frames.push(Object.assign({}, frames[0], {internalId:'user-window'}));")
        with patch.object(r, "kwin_script", side_effect=self.script):
            r.finish_desktop(self.saved, [], self.initial)
        self.assertEqual(self.value("raised"), [])

    def test_existing_desktop_is_never_reshuffled(self):
        with patch.object(r, "kwin_script") as script:
            r.finish_desktop(self.saved, [{"id": "already-open"}], self.initial)
        script.assert_not_called()

    def test_background_minimized_apps_are_left_alone_during_return(self):
        self.evaluate("frames.push(Object.assign({}, frames[0], {internalId:'background', minimized:true}));")
        with patch.object(r, "kwin_script", side_effect=self.script):
            r.finish_desktop(self.saved, [{"id": "background", "minimized": True}], self.initial)
        self.assertEqual(self.value("raised"), ["two", "one"])
        self.assertTrue(self.value("frames[2].minimized"))


if __name__ == "__main__":
    unittest.main()
