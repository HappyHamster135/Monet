"""Exercise the real notch observer and timer against a private session bus."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tools.test import private_session, stop

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"
NATIVE = (all(importlib.util.find_spec(name) for name in ("PySide6", "gi", "dbus"))
          and any(Path("/usr").glob("lib*/qt6/qml/org/kde/plasma/workspace/dbus/qmldir")))


@unittest.skipUnless(NATIVE, "requires Plasma QML and the desktop bus")
class NotchAwake(unittest.TestCase):
    def test_shared_timer_and_local_end_times(self):
        with private_session() as env:
            env.update(MONET_KEEP_AWAKE_PRIVATE_BUS="1", TZ="Europe/Stockholm", XDG_SESSION_ID="test-notch-awake")
            child = subprocess.run([sys.executable, "-m", "tests.test_notch_awake", "--fixture"],
                                   cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)


def fixture():
    import datetime
    import time

    import dbus
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest

    app = QGuiApplication([])
    home = Path.home()
    bus = dbus.SessionBus()
    manager = dbus.Interface(bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"), "org.freedesktop.DBus")
    name, path = "org.monet.KeepAwake", "/org/monet/KeepAwake"
    services = home / "services"
    services.mkdir()
    (services / (name + ".service")).write_text(
        f"[D-BUS Service]\nName={name}\nExec={sys.executable} {ROOT}/linux/libexec/monet-keep-awake\n")
    config = home.parent / "bus.conf"
    config.write_text(config.read_text().replace("</busconfig>", f"<servicedir>{services}</servicedir></busconfig>"))
    manager.ReloadConfig()
    manager.UpdateActivationEnvironment({k: v for k, v in os.environ.items() if k.startswith(("DBUS_", "XDG_")) or k == "HOME"})
    fake = subprocess.Popen([sys.executable, str(ROOT / "tests/fixtures/keep-awake-native.py"), "fake"],
                            stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        assert fake.stdout.readline().strip() == "READY"
        scene = home / "Scene.qml"
        scene.write_text(f'import QtQuick\nimport "{UI.as_uri()}" as Monet\n' + '''
Item {
    function i18n(t, a) { return a === undefined ? t : t.replace("%1", a) }
    Monet.NotchAwake { id: wake; objectName: "first" }
    Monet.NotchAwake { objectName: "second" }
    Monet.AwakeControls { objectName: "controls"; width: 300; height: 270; awake: wake }
}
''')
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
        engine.load(QUrl.fromLocalFile(str(scene)))
        root, = engine.rootObjects()
        one, two, controls = [root.findChild(QObject, key) for key in ("first", "second", "controls")]

        def wait(condition):
            until = time.monotonic() + 4
            while time.monotonic() < until:
                if condition():
                    return
                QTest.qWait(20)
            raise AssertionError((one.property("statusText"), two.property("statusText"), warnings))

        def state():
            return two.property("state").toVariant()

        QTest.qWait(140)
        assert not bus.name_has_owner(name)
        one.setDuration(1800)
        wait(lambda: one.property("active") and state().get("duration") == 1800)
        assert two.property("compactText") == "30 min"
        deadline = state()["end"]
        # The fixture owns an isolated bus. Re-activate its killed worker
        # without a new SetDuration and check both existing notch observers.
        import signal
        pid = manager.GetConnectionUnixProcessID(name)
        os.kill(pid, signal.SIGKILL)
        wait(lambda: not bus.name_has_owner(name) and not two.property("active"))
        manager.StartServiceByName(name, 0)
        wait(lambda: one.property("active") and state().get("end") == deadline)
        assert two.property("compactText") == "30 min"
        two.setDuration(-1)
        wait(lambda: one.property("statusText") == "Until turned off or you sign out")
        peer = dbus.Interface(bus.get_object(name, path), name)
        peer.SetDuration(dbus.Int32(61))
        wait(lambda: two.property("minutes") == 2)
        wait(lambda: two.property("minutes") == 1)
        peer.SetDuration(dbus.Int32(1))
        wait(lambda: not one.property("active") and not two.property("active"))
        wait(lambda: not bus.name_has_owner(name))
        one.setDuration(3600)
        wait(lambda: state().get("duration") == 3600)
        two.setDuration(0)
        wait(lambda: not bus.name_has_owner(name) and not one.property("active"))

        def ms(text):
            return datetime.datetime.fromisoformat(text).timestamp() * 1000
        def end(start, hour, minute):
            return controls.nextEnd(ms(start), hour, minute)
        assert end("2026-11-25T23:59:40+01:00", 0, 0) == ms("2026-11-26T00:00:00+01:00")
        assert end("2026-10-25T02:50:00+02:00", 2, 15) == ms("2026-10-25T02:15:00+01:00")
        assert end("2026-03-29T01:59:40+01:00", 2, 30) == ms("2026-03-30T02:30:00+02:00")
        assert not warnings, warnings
    finally:
        stop(fake)


if __name__ == "__main__":
    fixture() if "--fixture" in sys.argv else unittest.main()
