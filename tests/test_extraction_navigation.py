"""Native extraction controls, long text, scrolling and small-screen geometry."""
import gettext
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_archive_apps as archive
from tests import test_settings_navigation as settings

QT = archive.QApplication is not None
if QT:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QLineEdit, QPushButton, QScrollArea


@unittest.skipUnless(QT, "requires native Qt Widgets")
class ExtractionNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        settings.SettingsNavigation.setUpClass.__func__(cls)

    tearDownClass = classmethod(settings.SettingsNavigation.tearDownClass.__func__)
    wait = archive.ArchiveApps.wait

    def setUp(self):
        archive.ArchiveApps.setUp(self)
        language = os.environ.get("MONET_SETTINGS_TEST_LANGUAGE", "en")
        words = gettext.translation("monet", localedir=str(settings.ROOT / "linux/share/locale"),
                                    languages=[language], fallback=language == "en")
        change = patch.object(self.tool, "WORDS", words); change.start(); self.addCleanup(change.stop)
        self.source = self.root / ("Long archive name with spaces, å and literal $(touch NO) " * 2 + ".zip")
        self.source.write_bytes(b"metadata fixture; never extracted")
        self.screen = min(QGuiApplication.screens(), key=lambda s: s.availableGeometry().height())
        self.area = self.screen.availableGeometry()

    def make(self, find_apps=True):
        dialog = self.tool.make_extract_dialog(self.source, find_apps=find_apps)
        self.dialogs.append(dialog)
        dialog.create(); dialog.windowHandle().setScreen(self.screen)
        dialog.resize(min(620, self.area.width() - 32), min(400, self.area.height() - 48))
        dialog.show()
        dialog.activateWindow(); dialog.raise_()
        self.assertTrue(QTest.qWaitForWindowActive(dialog, 2000), "Extraction dialog did not receive native focus")
        self.wait(lambda: dialog.findChild(QPushButton, "extractApps").isEnabled())
        QTest.qWait(100)
        return dialog

    def capture(self, dialog, name):
        if os.environ.get("MONET_NAV_CAPTURE"):
            folder = Path(os.environ["MONET_NAV_CAPTURE"]); folder.mkdir(parents=True, exist_ok=True)
            self.assertTrue(dialog.grab().save(str(folder / (name + ".png"))))
            rect = lambda value: [value.x(), value.y(), value.width(), value.height()]
            report = dict(screen=self.screen.name(), available=rect(self.area), frame=rect(dialog.frameGeometry()),
                          buttons=[dict(name=button.objectName(), text=button.text(), enabled=button.isEnabled(),
                                        visible=button.isVisible(), rect=rect(button.rect().translated(button.mapTo(dialog, QPoint()))))
                                   for button in dialog.findChildren(QPushButton)])
            (folder / (name + ".json")).write_text(json.dumps(report, indent=2) + "\n")

    def assert_fits(self, dialog):
        frame = dialog.frameGeometry()
        self.assertLessEqual(frame.width(), self.area.width() - 16, str(frame))
        self.assertLessEqual(frame.height(), self.area.height() - 16, str(frame))

    def assert_unclipped(self, widget, dialog):
        parent = widget.parentWidget()
        while parent is not None:
            rectangle = widget.rect().translated(widget.mapTo(parent, QPoint()))
            self.assertTrue(parent.rect().adjusted(-1, -1, 1, 1).contains(rectangle),
                            f"{widget.objectName() or widget.text()} clipped by {parent.metaObject().className()}: {rectangle}")
            if parent is dialog: break
            parent = parent.parentWidget()

    def test_both_extraction_modes_and_buttons_fit_the_small_screen(self):
        for find_apps in (False, True):
            with self.subTest(find_apps=find_apps):
                dialog = self.make(find_apps)
                self.capture(dialog, "extraction-apps" if find_apps else "extraction-plain")
                self.assert_fits(dialog)
                for button in dialog.findChildren(QPushButton):
                    if button.isVisible():
                        if not isinstance(button.parentWidget(), QDialogButtonBox):
                            button.setFocus(Qt.TabFocusReason); QTest.qWait(30)
                        self.assert_unclipped(button, dialog)
                        self.assertGreaterEqual(button.width(), button.sizeHint().width())
                dialog.reject()

    def test_tab_and_shift_tab_keep_enabled_controls_visible(self):
        dialog = self.make()
        field = dialog.findChild(QLineEdit, "extractDestination"); field.setFocus(Qt.TabFocusReason)
        QTest.qWait(30)
        required = {field, *[button for button in dialog.findChildren(QPushButton) if button.isEnabled() and button.isVisible()]}
        seen = set()
        for key, modifiers in ((Qt.Key_Tab, Qt.NoModifier), (Qt.Key_Backtab, Qt.ShiftModifier)):
            for _ in range(len(required) + 3):
                focus = dialog.focusWidget()
                if focus in required:
                    self.assert_unclipped(focus, dialog); seen.add(focus)
                QTest.keyClick(focus or dialog, key, modifiers); QTest.qWait(30)
        self.assertEqual(required - seen, set())

    def test_long_error_stays_scrollable_with_a_visible_escape_action(self):
        dialog = self.make()
        status = dialog.findChild(QLabel, "extractStatus")
        status.setText(("The destination is unavailable. Existing partial files were retained; choose another folder and retry. " * 12).strip())
        QTest.qWait(100)
        self.assert_fits(dialog)
        scroll = dialog.findChild(QScrollArea)
        self.assertIsNotNone(scroll, "Long extraction details need a scrollable area on a small display")
        bar = scroll.verticalScrollBar(); self.assertGreater(bar.maximum(), bar.minimum())
        bar.setValue(bar.minimum())
        viewport = scroll.viewport(); point = QPointF(viewport.width() / 2, viewport.height() / 2)
        for phase, delta in ((Qt.ScrollBegin, 0), (Qt.ScrollUpdate, -80), (Qt.ScrollEnd, 0)):
            event = QWheelEvent(point, QPointF(viewport.mapToGlobal(point.toPoint())), QPoint(0, delta), QPoint(),
                                Qt.NoButton, Qt.NoModifier, phase, False)
            QApplication.sendEvent(viewport, event); QTest.qWait(20)
        self.assertGreater(bar.value(), bar.minimum())
        self.capture(dialog, "extraction-long-error")
        QTest.keyClick(dialog, Qt.Key_Escape); QTest.qWait(30)
        self.assertFalse(dialog.isVisible()); self.assertIsNone(dialog.extracted)


if __name__ == "__main__":
    unittest.main()
