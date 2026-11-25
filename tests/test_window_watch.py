"""Region alerts, cold/still frames and OCR cancellation in a private Qt session."""
from ctypes.util import find_library
import importlib.util
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))


@unittest.skipUnless(importlib.util.find_spec("PySide6") and importlib.util.find_spec("gi"), "needs Qt and GStreamer")
class WindowWatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from capture import Preview
        # Leave the system picker and the user's windows alone.
        with patch("watch.WindowStream") as stream:
            self.preview = Preview(None)
            self.stream = stream.return_value
        self.preview.frames.stop()

    def tearDown(self):
        self.preview.close()
        self.app.processEvents()

    def frame(self, color):
        from PySide6.QtGui import QImage
        image = QImage(160, 90, QImage.Format_RGB32)
        image.fill(color)
        self.stream.image.return_value = image
        self.preview.draw()

    def test_change_alert_fires_once_and_a_new_crop_rearms_the_baseline(self):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor
        self.preview.alert.setCurrentIndex(1)
        with patch("PySide6.QtCore.QProcess.startDetached") as notice:
            self.frame(QColor("red"))
            self.preview.image.crop = QRectF(0, 0, 0.5, 1)
            self.preview.crop_changed()
            self.frame(QColor("red"))
            notice.assert_not_called()
            self.frame(QColor("green"))
            self.frame(QColor("red"))
            self.assertEqual(notice.call_count, 1)
            self.assertEqual(self.preview.alert.currentIndex(), 0)

    def test_finished_requires_activity_then_five_seconds_including_without_frames(self):
        from PySide6.QtGui import QColor
        self.preview.alert.setCurrentIndex(2)
        with patch("capture.time.monotonic") as clock, patch("PySide6.QtCore.QProcess.startDetached") as notice:
            clock.return_value = 1
            self.frame(QColor("red"))
            clock.return_value = 20
            self.frame(QColor("red"))
            notice.assert_not_called()
            self.frame(QColor("blue"))
            self.stream.image.return_value = None
            clock.return_value = 24.9
            self.preview.draw()
            notice.assert_not_called()
            clock.return_value = 25.1
            self.preview.draw()
            self.preview.draw()
            self.assertEqual(notice.call_count, 1)

    @unittest.skipUnless(find_library("tesseract"), "needs local OCR")
    def test_local_ocr_reads_only_an_armed_region_and_matches_once(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QImage, QPainter
        from PySide6.QtTest import QTest
        image = QImage(520, 110, QImage.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setFont(QFont("DejaVu Sans", 30))
        painter.drawText(image.rect(), Qt.AlignCenter, "Download complete")
        painter.end()
        self.stream.image.return_value = image
        self.preview.draw()
        alert = self.preview.text_alert
        self.assertFalse(alert.timer.isActive())
        self.preview.words.setText("DOWNload    complete")
        self.preview.alert.setCurrentIndex(3)
        with patch("PySide6.QtCore.QProcess.startDetached") as notice:
            end = time.monotonic() + 8
            while not notice.called and time.monotonic() < end:
                self.app.processEvents()
                QTest.qWait(30)
            self.assertEqual(notice.call_count, 1)
            self.assertIn("The text appeared", notice.call_args.args[1][-1])
            self.preview.draw()
            self.assertFalse(alert.timer.isActive())
            self.assertFalse(alert.phrase)
            self.assertTrue(alert.image.isNull())

    def test_disarming_before_ocr_starts_discards_the_frame(self):
        from PySide6.QtGui import QColor
        self.preview.words.setText("Ready")
        self.preview.alert.setCurrentIndex(3)
        self.frame(QColor("blue"))
        self.assertTrue(self.preview.text_alert.timer.isActive())
        self.preview.alert.setCurrentIndex(0)
        self.assertFalse(self.preview.text_alert.timer.isActive())
        self.assertTrue(self.preview.text_alert.image.isNull())


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "needs Qt D-Bus")
class PinnedWatch(unittest.TestCase):
    def test_only_originating_shell_can_read_and_its_exit_stops_sharing(self):
        from PySide6.QtCore import QObject
        from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher
        from PySide6.QtGui import QImage
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from notch_watch import INTERFACE, NotchWatch
        from tools.test import private_session

        app = QApplication.instance() or QApplication([])
        class Preview(QObject):
            def close(self):
                self.watch.stop()

        def wait(check):
            deadline = time.monotonic() + 4
            while not check() and time.monotonic() < deadline:
                app.processEvents()
                QTest.qWait(5)
            self.assertTrue(check())

        with private_session() as env:
            names = ["watch-producer", "watch-shell", "watch-other"]
            producer, shell, other = [QDBusConnection.connectToBus(env["DBUS_SESSION_BUS_ADDRESS"], n) for n in names]
            try:
                self.assertTrue(shell.registerService("org.kde.plasmashell"))
                preview = Preview()
                preview.picture = QImage(4, 4, QImage.Format_RGB32)
                preview.picture.fill(0xff26ae99)
                with patch("notch_watch.QDBusConnection.sessionBus", return_value=producer):
                    preview.watch = watch = NotchWatch(preview, "37")
                self.assertTrue(watch.start())

                def call(bus, method):
                    msg = QDBusMessage.createMethodCall(watch.service, watch.path, INTERFACE, method)
                    pending = QDBusPendingCallWatcher(bus.asyncCall(msg))
                    wait(pending.isFinished)
                    return pending.reply()

                for method in ("Frame", "Stop", "Edit"):
                    self.assertEqual(call(other, method).errorName(), "org.freedesktop.DBus.Error.AccessDenied")
                self.assertTrue(call(shell, "Frame").arguments()[0].startswith("data:image/jpeg;base64,"))
                self.assertTrue(shell.unregisterService("org.kde.plasmashell"))
                wait(lambda: not watch.active)
                self.assertFalse(producer.interface().isServiceRegistered(watch.service).value())
                self.assertFalse(watch.encoded)
            finally:
                for n in names:
                    QDBusConnection.disconnectFromBus(n)
