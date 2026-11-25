"""Exercise per-device click configuration against an isolated KWin D-Bus service."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tools.test import private_session

ROOT = Path(__file__).resolve().parents[1]
IFACE = "org.kde.KWin.InputDevice"
MANAGER = IFACE + "Manager"
PATH = "/org/kde/KWin/InputDevice"
NATIVE = importlib.util.find_spec("dbus") and importlib.util.find_spec("gi")


def serve():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    service = dbus.service.BusName("org.kde.KWin", bus)
    class Manager(dbus.service.Object):
        @dbus.service.method(MANAGER, out_signature="as")
        def ListPointers(self):
            return ["event8", "event9", "event10"]

    class Device(dbus.service.Object):
        def __init__(self, name, fingers):
            super().__init__(service, PATH + "/" + name)
            self.props = {"name": dbus.String(name), "touchpad": dbus.Boolean(fingers > 0),
                          "tapFingerCount": dbus.Int32(fingers), "tapToClick": dbus.Boolean(True),
                          "deviceGroupId": dbus.String(name), "tapAndDrag": dbus.Boolean(False),
                          "supportsLmrTapButtonMap": dbus.Boolean(fingers >= 2), "lmrTapButtonMap": dbus.Boolean(False),
                          "supportsClickMethodAreas": dbus.Boolean(True), "clickMethodAreas": dbus.Boolean(True),
                          "supportsClickMethodClickfinger": dbus.Boolean(fingers >= 3), "clickMethodClickfinger": dbus.Boolean(False)}

        @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, iface):
            assert iface == IFACE
            return self.props

        @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv", out_signature="")
        def Set(self, iface, prop, value):
            assert iface == IFACE and isinstance(value, dbus.Boolean) and prop in self.props
            if prop == "tapAndDrag":
                return  # The driver silently rejected this change.
            if prop.startswith("clickMethod"):
                assert value
                for key in ("clickMethodAreas", "clickMethodClickfinger"):
                    self.props[key] = dbus.Boolean(key == prop)
            else:
                self.props[prop] = value

        @dbus.service.method("org.monet.Test", out_signature="")
        def Replace(self):
            self.props["deviceGroupId"] = dbus.String("reconnected")

    manager = Manager(service, PATH)
    devices = [Device("event8", 3), Device("event9", 1), Device("event10", 0)]
    print("ready", flush=True)
    GLib.MainLoop().run()


@unittest.skipUnless(NATIVE, "requires D-Bus and GLib")
class TouchpadClicks(unittest.TestCase):
    def test_writes_only_supported_choices_to_the_selected_attachment(self):
        with private_session() as env:
            server = subprocess.Popen([sys.executable, "-m", "tests.test_touchpad_clicks", "--service"],
                                      cwd=ROOT, env=env, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(server.stdout.readline().strip(), "ready")
                completed = subprocess.run([sys.executable, "-m", "tests.test_touchpad_clicks", "--exercise"],
                                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            finally:
                server.terminate()
                server.wait(timeout=4)
                server.stdout.close()


def exercise():
    import dbus
    helper = ROOT / "linux/libexec/monet-quick"
    def run(*args, ok=True):
        proc = subprocess.run([sys.executable, helper, *args], capture_output=True, text=True, timeout=5)
        assert (proc.returncode == 0) == ok, (args, proc.stderr, proc.stdout)
        return json.loads(proc.stdout)

    first, second = run("input")["touchpads"]
    assert first["fingers"] == 3 and first["map"] == "secondary"
    assert second["methods"] == ["areas"] and "map" not in second
    def set_choice(key, value, pad=first, ok=True):
        return run("touchpad-click", pad["id"], key, value, ok=ok)
    assert set_choice("method", "fingers")["pads"][0]["method"] == "fingers"
    assert set_choice("map", "middle")["pads"][0]["map"] == "middle"
    assert set_choice("drag", "on", ok=False)["pads"][0]["drag"] is False
    assert not set_choice("method", "fingers", second, False)["ok"]
    off = set_choice("tap", "off")["pads"]
    assert not off[0]["tap"] and off[1] == second
    assert not set_choice("map", "secondary", ok=False)["ok"]
    assert set_choice("tap", "on")["pads"][0]["map"] == "middle"
    bus = dbus.SessionBus()
    bus.get_object("org.kde.KWin", PATH + "/event8").Replace(dbus_interface="org.monet.Test")
    changed = set_choice("method", "areas", ok=False)
    assert changed["problem"] == "gone" and changed["pads"][0]["method"] == "fingers"
    assert changed["pads"][0]["id"] != first["id"]


if __name__ == "__main__":
    if "--service" in sys.argv:
        serve()
    elif "--exercise" in sys.argv:
        exercise()
    else:
        unittest.main()
