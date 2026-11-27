"""Use the real inline pages on a disposable desktop; never touch the user's clipboard."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))

from PySide6.QtCore import QPoint, QProcess, QSettings, Qt
from PySide6.QtGui import QColor, QImage, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QTabWidget, QLabel, QWidget
from actions import DESKTOP_TOOLS, NOTCH_PAGES, stored
from notch_tools import NotchTools
from window import Receiver, Window


class CompactTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = Window("/usr/libexec", defer_catalog=True)
        self.window.settings = QSettings(self.temp.name + "/prefs.ini", QSettings.IniFormat)
        self.receiver = Receiver(self.window)
        self.tools = NotchTools(self.receiver)
        self.generation = 0

    def tearDown(self):
        self.tools.hide()
        if self.tools.area: self.tools.area.deleteLater()
        if self.tools.host: self.tools.host.deleteLater()
        self.window.deleteLater()
        self.receiver.deleteLater()
        QTest.qWait(15)
        self.temp.cleanup()

    def show(self, key, width=414, height=350):
        self.generation += 1
        area = self.app.primaryScreen().geometry()
        reply = json.loads(self.tools.handle(json.dumps(dict(action="show", key=key, id=f"19.{self.generation}",
            screen="", x=area.x()+5, y=area.y()+5, w=width, h=height))))
        self.assertTrue(reply["ok"], key)
        QTest.qWait(80)
        return self.tools.scroll.widget()

    def test_common_tools_route_inline_and_fit(self):
        self.assertFalse(NOTCH_PAGES & DESKTOP_TOOLS)
        for width in (288, 414):
            for key in ("snippets", "emoji", "record", "recordings", "plain", "clean", "lock"):
                with self.subTest(key=key, width=width):
                    page = self.show(key, width)
                    if key == "snippets":
                        page.add()
                    QTest.qWait(20)
                    self.assertLessEqual(page.width(), self.tools.scroll.viewport().width())
                    self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(), 0)
                    for control in page.findChildren(QWidget):
                        if not isinstance(control, (QPushButton, QLineEdit, QComboBox)):
                            continue
                        if control.isVisibleTo(page):
                            x = control.mapTo(page, control.rect().topLeft()).x()
                            self.assertGreaterEqual(x, 0)
                            self.assertLessEqual(x + control.width(), page.width(), control.text() if hasattr(control, "text") else key)

    def test_plain_and_clean_copy_the_result_and_report_errors(self):
        copies = []
        def copy(owner, text, done):
            copies.append(text)
            done(True)
        with patch("notch_pages.copy_text", side_effect=copy):
            page = self.show("plain")
            page.edit.setPlainText("hello\nworld")
            page.apply.click()
            self.assertEqual(copies[-1], "hello\nworld")
            self.assertEqual(self.tools.status.text(), "Plain text copied.")
            page = self.show("clean")
            page.edit.setPlainText("https://example.com/page?utm_source=news&q=cat")
            page.apply.click()
            self.assertEqual(copies[-1], "https://example.com/page?q=cat")
            self.assertIn("utm_source", page.detail.text())
            page.apply.click()
            self.assertEqual(self.tools.status.text(), "Link already clean. Copied.")
            before = len(copies)
            page.edit.setPlainText("this is not a URL")
            page.apply.click()
            self.assertEqual(len(copies), before)
            self.assertIn("http", self.tools.status.text())
        with patch("notch_pages.copy_text", side_effect=lambda owner, text, done: done(False)):
            page.edit.setPlainText("https://example.com")
            page.apply.click()
            self.assertIn("Couldn’t copy", self.tools.status.text())

    def test_cleaning_setup_stays_inline_and_only_starts_on_explicit_click(self):
        with patch.object(self.window, "worker") as worker, patch.object(self.window, "start_desktop_cleaning") as native:
            page = self.show("lock", width=288)
            self.assertIsNone(self.app.activeModalWidget())
            worker.assert_not_called(); native.assert_not_called()
            page.duration.setCurrentIndex(page.duration.findData(120))
            page.start.click()
            QTest.qWait(260)
            self.assertFalse(self.tools.area.isVisible())
            self.assertTrue(self.tools.busy())
            self.assertEqual(worker.call_args.args[0][-1], "120")
            self.assertTrue(str(worker.call_args.args[0][-2]).endswith("cleaning.py"))
            native.assert_not_called()
            page.cleaning.stop()

    def test_cleaning_visible_mode_uses_the_existing_compositor_input_pause(self):
        with patch.object(self.window, "start_desktop_cleaning") as native:
            page = self.show("lock")
            if page.display.findData("visible") < 0:
                page.display.addItem("Keep desktop visible", "visible")
            page.display.setCurrentIndex(page.display.findData("visible"))
            page.duration.setCurrentIndex(page.duration.findData(30))
            page.start.click(); QTest.qWait(260)
            native.assert_called_once_with(30, False)
            self.assertTrue(self.tools.busy())
            page.cleaning.stop()

    def test_reused_pages_repaint_the_canvas_between_controls(self):
        # A reused Wayland buffer may still contain the previous page. Transparent
        # labels do not erase those pixels, so test painting into a dirty image.
        for key in ("plain", "snippets", "record", "emoji", "snippets", "compress", "record"):
            page = self.show(key)
            # Do not let QWidget.render's automatic background pass mask the
            # missing paint handler, as it did in the earlier offscreen checks.
            page.setAutoFillBackground(False)
            page.setAttribute(Qt.WA_StyledBackground, False)
            frame = QImage(page.size(), QImage.Format_ARGB32)
            frame.fill(QColor("magenta"))
            page.render(frame, QPoint(), QRegion(), QWidget.DrawChildren)
            self.assertEqual(frame.pixelColor(1, 1).name(), "#101011", key)
            if key == "record":
                self.assertEqual(frame.pixelColor(20, 180).name(), "#101011")
            if key == "snippets":
                self.assertFalse(page.names.isVisible())
                self.assertTrue(page.empty.isVisible())

    def test_clipboard_read_is_passive_and_repeated_visits_keep_draft(self):
        self.app.clipboard().setText("test clipboard")
        with patch("notch_pages.copy_text") as copy:
            page = self.show("plain")
            self.assertEqual(page.edit.toPlainText(), "test clipboard")
            copy.assert_not_called()
        page = self.show("snippets")
        page.add()
        page.name.setText("Draft")
        page.edit.setPlainText("Unsaved content")
        self.show("emoji")
        self.assertIs(self.show("snippets"), page)
        self.assertEqual(page.edit.toPlainText(), "Unsaved content")

    def test_snippet_save_rename_expand_and_confirm_delete(self):
        page = self.show("snippets")
        page.add()
        page.name.setText("Greeting")
        page.edit.setPlainText("Hello {{date}}")
        page.shortcut.setText("hello")
        page.expand.setChecked(True)
        self.assertTrue(page.save())
        self.assertEqual(stored(self.window.settings, "snippets", {})["Greeting"], "Hello {{date}}")
        page.name.setText("Welcome")
        self.assertTrue(page.save())
        self.assertNotIn("Greeting", stored(self.window.settings, "snippets", {}))
        copied = []
        with patch("notch_pages.copy_text", side_effect=lambda owner, text, done: (copied.append(text), done(True))):
            page.copy_snippet()
        self.assertNotIn("{{date}}", copied[-1])
        page.remove()
        self.assertIn("Welcome", stored(self.window.settings, "snippets", {}))
        page.remove()
        for key in ("snippets", "snippetShortcuts", "snippetVariables"):
            self.assertNotIn("Welcome", stored(self.window.settings, key, {}))

    def test_snippet_duplicate_does_not_overwrite_another_entry(self):
        self.window.settings.setValue("snippets", json.dumps({"Saved": "keep me"}))
        page = self.show("snippets")
        page.add()
        page.name.setText("Saved")
        page.edit.setPlainText("changed")
        self.assertFalse(page.save())
        self.assertEqual(stored(self.window.settings, "snippets", {}), {"Saved": "keep me"})

    def test_emoji_search_categories_copy_and_recents(self):
        page = self.show("emoji")
        self.assertGreater(page.grid.count(), 30)
        page.search.setText("rocket")
        QTest.qWait(120)
        self.assertGreater(page.grid.count(), 0)
        item = page.grid.item(0)
        copies = []
        with patch("notch_pages.copy_text", side_effect=lambda owner, text, done: (copies.append(text), done(True))):
            page.choose(item)
        self.assertEqual(copies, ["🚀"])
        self.assertEqual(stored(self.window.settings, "notchRecentEmoji", []), ["🚀"])
        page.search.clear()
        page.category.setCurrentIndex(next(i for i in range(page.category.count()) if page.category.tabData(i) == 5))
        page.fill()
        self.assertTrue(all(page.categories[page.grid.item(i).data(Qt.UserRole)] == 5 for i in range(page.grid.count())))
        page.category.setCurrentIndex(next(i for i in range(page.category.count()) if page.category.tabData(i) == "recent"))
        page.fill()
        self.assertEqual(page.grid.count(), 1)

    def test_recording_keeps_controls_inline_and_handles_launch_failure(self):
        page = self.show("record")
        self.assertIs(page, self.show("recordings"))
        self.assertFalse(self.window.isVisible())
        with patch("subprocess.run"), patch.object(QProcess, "start") as start:
            page.capture()
            job = page.recorder
            self.assertTrue(self.tools.busy())
            self.assertFalse(self.tools.area.isVisible())
            self.assertFalse(page.start.isEnabled())
            QTest.qWait(250)
            argv = start.call_args.args
            self.assertEqual(argv[0], "spectacle")
            self.assertIn("--background", argv[1])
            self.assertIn("--new-instance", argv[1])
            self.assertFalse(self.window.isVisible())
            job.errorOccurred.emit(QProcess.FailedToStart)
            self.assertIsNone(page.recorder)
            self.assertTrue(page.start.isEnabled())
            self.assertIn("Couldn’t record", page.message.text())

    def test_desktop_pages_reflow_instead_of_horizontal_scrolling(self):
        for width in (288, 414):
            for key in ("compress", "link-settings", "clipboard-expiry", "media-keys", "wheel-scrolling", "extra-clicks", "quit-protection", "scripts",
                        "quit-on-close", "wallpaper", "window-switcher", "process-control", "ports", "network", "monitor-alerts", "fans", "devices", "wheel-settings"):
                with self.subTest(key=key, width=width):
                    page = self.show(key, width)
                    self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(), 0)
                    self.assertLessEqual(page.width(), self.tools.scroll.viewport().width())
                    tabs = page.findChildren(QTabWidget)
                    for tab in tabs:
                        tab.setCurrentIndex(tab.count()-1)
                    QTest.qWait(40)
                    for control in page.findChildren(QWidget):
                        if not control.isVisibleTo(page):
                            continue
                        if isinstance(control, (QLabel, QComboBox, QLineEdit, QPushButton)):
                            at = control.mapTo(page, control.rect().topLeft())
                            self.assertGreaterEqual(at.x(), 0)
                            self.assertLessEqual(at.x()+control.width(), page.width(), type(control).__name__)
                        if isinstance(control, QLabel) and control.wordWrap():
                            self.assertGreaterEqual(control.height(), control.heightForWidth(control.width()), control.text())
                    self.tools.scroll.verticalScrollBar().setValue(self.tools.scroll.verticalScrollBar().maximum())
                    self.assertEqual(self.tools.scroll.horizontalScrollBar().maximum(), 0)

    def test_long_checkbox_labels_wrap_and_keep_their_state(self):
        page = self.show("quit-on-close", width=288)
        self.assertIn("\n", page.fallback.text())
        checked = page.fallback.isChecked()
        self.show("quit-on-close", width=414)
        self.assertEqual(page.fallback.isChecked(), checked)

    def test_layout_updates_settle_and_reflow_changed_help_text(self):
        from notch_style import ResponsiveTool
        calls = []
        fit = ResponsiveTool.fit
        def counted_fit(layout):
            calls.append(layout)
            fit(layout)
        with patch.object(ResponsiveTool, "fit", counted_fit):
            page = self.show("scripts", width=288)
            QTest.qWait(100)
            calls.clear()
            QTest.qWait(100)
            self.assertEqual(calls, [], "An idle page must not continuously recalculate its layout")
            label = page.notch_layout.labels[0]
            label.setText("Long updated help text that needs to wrap within the notch. " * 6)
            QTest.qWait(100)
            self.assertTrue(calls, "Updated text must still trigger a layout pass")
            self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
            calls.clear()
            QTest.qWait(100)
            self.assertEqual(calls, [])

    def test_closing_a_compression_page_does_not_end_a_running_operation(self):
        page = self.show("compress")
        page.job = object()
        self.tools.hide()
        self.assertTrue(self.tools.busy())
        page.job = None
        self.assertFalse(self.tools.busy())


if __name__ == "__main__":
    unittest.main()
