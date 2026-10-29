"""All running clocks follow the saved format without restarting the desktop."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from tests.test_settings_feedback import QT

if QT:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest


@unittest.skipUnless(QT, "requires PySide6 in the Monet VM")
class ClockFormat(unittest.TestCase):
    def test_live_change_region_fallback_and_restart(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QGuiApplication.instance() or QGuiApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "plasma-localerc"
            config.write_text("[Formats]\nLANG=en_US.UTF-8\n")
            widgets = (Path(__file__).resolve().parents[1] / "linux/share/monet/widgets").as_uri()
            fixture = Path(folder) / "ClockTest.qml"
            fixture.write_text('import QtQuick\nimport "' + widgets + '"\nQtObject {\n'
                'property ClockFormat first: ClockFormat { configFolder: ' + json.dumps(Path(folder).as_uri()) + ' }\n'
                'property ClockFormat second: ClockFormat { configFolder: first.configFolder }\n'
                'property string desktop: first.time(new Date(2026, 9, 28, 18, 20))\n'
                'property string panel: second.time(new Date(2026, 9, 28, 18, 20))\n}')
            engines = []

            def load():
                engine = QQmlApplicationEngine()
                engines.append(engine)
                errors = []
                engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
                engine.load(QUrl.fromLocalFile(str(fixture)))
                QTest.qWait(100)
                self.assertTrue(engine.rootObjects(), errors)
                return engine.rootObjects()[0]

            def expect(root, text):
                for _ in range(100):
                    if all(text in root.property(p) for p in ("desktop", "panel")):
                        return
                    QTest.qWait(30)
                self.fail((root.property("desktop"), root.property("panel"), text))

            def write(key, value):
                subprocess.run(["kwriteconfig6", "--file", str(config), "--group", "Formats", "--key", key,
                                *(["--delete"] if value is None else [value])], check=True)

            try:
                root = load()
                expect(root, "PM")
                write("LC_TIME", "en_GB.UTF-8")
                expect(root, "18:20")
                expect(load(), "18:20")
                write("LC_TIME", "en_US.UTF-8")
                expect(root, "PM")
                write("LANG", "en_GB.UTF-8")
                expect(root, "PM")  # Explicit time preference still wins.
                write("LC_TIME", None)
                expect(root, "18:20")
                self.assertNotIn("LC_TIME", config.read_text())
            finally:
                for engine in engines:
                    engine.deleteLater()
                QTest.qWait(1)
