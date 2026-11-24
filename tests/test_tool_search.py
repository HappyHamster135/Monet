"""Run native KRunner D-Bus queries and launch only a disposable test receiver."""
from configparser import ConfigParser
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "linux/share/monet/utilities"
NATIVE = all(importlib.util.find_spec(m) for m in ("dbus", "gi", "PySide6"))


@unittest.skipUnless(NATIVE, "requires session D-Bus, GLib and Qt preferences")
class DesktopSearch(unittest.TestCase):
    def test_visible_results_and_activation(self):
        with private_session() as env:
            process = subprocess.run([sys.executable, "-m", "tests.test_tool_search", "--fixture"],
                                     cwd=ROOT, capture_output=True, text=True, env=env, timeout=25)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


def fixture():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    from PySide6.QtCore import QSettings

    sys.path.insert(0, str(MODULES))
    from actions import ACTIONS
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    received = []

    class Target(dbus.service.Object):
        @dbus.service.method("org.monet.Utilities", in_signature="ss")
        def OpenTool(self, key, token):
            if legacy:
                raise dbus.DBusException("old receiver", name="org.freedesktop.DBus.Error.UnknownMethod")
            received.append((str(key), str(token)))

        @dbus.service.method("org.monet.Utilities", in_signature="s")
        def Present(self, payload):
            received.append(tuple(json.loads(payload)))

    legacy = False
    name = dbus.service.BusName("org.monet.Utilities", bus=bus)
    target = Target(name, "/Utilities")
    config = QSettings("Monet", "Utilities")
    config.setValue("favorites", json.dumps(["ports", "shelf", "mic"]))
    config.setValue("hidden", json.dumps(["mic"]))
    config.sync()

    child = subprocess.Popen([sys.executable, str(MODULES / "tool_search.py")])
    try:
        end = time.monotonic() + 5
        while not bus.name_has_owner("org.monet.ToolSearch") and time.monotonic() < end:
            time.sleep(.02)
        def proxy(connection):
            return dbus.Interface(connection.get_object("org.monet.ToolSearch", "/runner"),
                                  "org.kde.krunner1")
        runner = proxy(bus)
        def keys(query):
            return [str(row[0]) for row in runner.Match(query)]
        assert runner.Actions() == []
        assert keys("tools") == ["ports", "shelf"]
        shortcut = ConfigParser(interpolation=None)
        shortcut.read(ROOT / "linux/share/applications/monet-utilities.desktop")
        command = shlex.split(shortcut["Desktop Action Search"]["Exec"])
        # KRunner puts the caret after the initial query when this shortcut opens.
        assert command[:3] == ["krunner", "--runner", "monet-utilities"]
        assert keys(command[3] + "scratchpad")[0] == "notes"
        assert keys("tools listening ports")[0] == "ports"
        assert keys("cleaning mode")[0] == "lock"
        assert keys("codex limits")[0] == "agents"
        assert "mic" not in keys("tools MÎCrophone") and keys("s") == [] and keys(";;;") == []
        assert not received
        # Each named tool is discoverable, including the last entries in the catalog.
        assert all(key in keys("tools " + action.name) for key, action in ACTIONS.items() if key != "mic")
        runner.SetActivationToken("owned-by-first-client")
        second = proxy(dbus.SessionBus(private=True))
        # The test owns the target on this thread, so pump while the provider calls back.
        context = GLib.MainContext.default()
        def run(instance, key, action=""):
            done, errors = [], []
            instance.Run(key, action, reply_handler=lambda: done.append(True), error_handler=errors.append)
            limit = time.monotonic() + 4
            while not done and not errors and time.monotonic() < limit:
                while context.pending():
                    context.iteration(False)
                time.sleep(.005)
            assert done and not errors, errors
        run(second, "notes")
        run(runner, "shelf")
        run(runner, "shelf")
        assert received == [("notes", ""), ("shelf", "owned-by-first-client"), ("shelf", "")]
        assert "sound" in keys("tools MÎCrophone")
        config.setValue("hidden", json.dumps(["ports"]))
        config.sync()
        assert "ports" not in keys("tools listening ports")
        run(runner, "ports")
        run(runner, "../bad")
        run(runner, "shelf", "unknown-action")
        assert len(received) == 3
        config.setValue("favorites", "[]")
        config.sync()
        assert keys("tools") == ["customize"]
        run(runner, "customize")
        assert received[-1] == ("customize", "")
        legacy = True
        run(runner, "shelf")
        assert received[-1] == ("shelf",)
    finally:
        child.terminate()
        child.wait(timeout=3)


if __name__ == "__main__":
    if "--fixture" in sys.argv:
        fixture()
    else:
        unittest.main()
