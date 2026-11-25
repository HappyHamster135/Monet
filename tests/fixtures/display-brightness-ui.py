"""Use the Display page with real Plasma controls and two private D-Bus outputs."""
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import dbus
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest

assert os.environ["DBUS_SESSION_BUS_ADDRESS"].startswith("unix:path=/tmp/monet-tests-")
assert os.environ["DBUS_SYSTEM_BUS_ADDRESS"] == "unix:path=/nonexistent"
repo = Path(__file__).resolve().parents[2]
source = repo / "linux/share"
live = "--installed" in sys.argv
if live:
    source = Path("/usr/share")
app = QGuiApplication([])
loader = SourceFileLoader("games", str(Path("/usr/libexec/monet-games") if live else repo / "linux/libexec/monet-games"))
games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(games)
app.setOrganizationName("monet")
app.setApplicationName("settings")


def wait(condition):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        QTest.qWait(20)
    raise AssertionError(f"Timed out at {condition.__code__.co_firstlineno}")


def items(item):
    yield item
    for child in item.childItems():
        yield from items(child)


service = subprocess.Popen([sys.executable, str(Path(__file__).with_name("brightness-native.py")), "display1", "--named"],
                           stdout=subprocess.PIPE, text=True)
try:
    assert service.stdout.readline().strip() == "READY"
    api = dbus.Interface(dbus.SessionBus().get_object("org.monet.BrightnessTest", "/test"), "org.monet.BrightnessTest")
    engine = QQmlApplicationEngine()
    words = games.Words()
    context = engine.rootContext()
    context.setContextObject(words)
    helper = games.Helper(defer_start=True)
    properties = dict(helper=helper, windowActivity=games.WindowActivity(), windowArea=games.WindowArea(),
                      bootClock=games.BootClock(), firstPage="display", blurBehind=False,
                      pictures=QUrl.fromLocalFile(str(source / "monet/settings") + "/").toString(),
                      brush=QUrl.fromLocalFile(str(source / "monet/textures/brush.png")).toString())
    for key, value in properties.items():
        context.setContextProperty(key, value)
    problems = []
    engine.warnings.connect(lambda errors: problems.extend(e.toString() for e in errors))
    engine.load(QUrl.fromLocalFile(str(source / "monet/settings-app/MonetSettings.qml")))
    window, = engine.rootObjects()
    assert isinstance(window, QQuickWindow)
    window.show()

    def row(name):
        return next((i for i in items(window.contentItem()) if i.objectName() == "brightness-" + name), None)

    def slider(name):
        target = row(name)
        return next((i for i in items(target) if i.metaObject().indexOfSignal("moved()") >= 0), None) if target else None

    external = wait(lambda: slider("display0"))
    internal = wait(lambda: slider("display1"))
    assert external.property("value") == 75 and internal.property("value") == 100
    assert json.loads(api.Snapshot())["calls"] == []
    external.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_Left)
    wait(lambda: json.loads(api.Snapshot())["calls"])
    state = json.loads(api.Snapshot())
    assert [c[:3] for c in state["calls"]] == [["display0", 740, 1]], state
    assert state["level"] == 1000 and state["external"] == 740
    api.Change("display1", 0, "hardware-key")
    wait(lambda: internal.property("value") == 0)
    api.SetExternalConnected(False)
    wait(lambda: not row("display0"))
    assert row("display1").property("title") == "Brightness"
    api.SetExternalConnected(True)
    wait(lambda: slider("display0") and slider("display0").property("value") == 74)
    assert slider("display1").property("value") == 0
    assert len(json.loads(api.Snapshot())["calls"]) == 1
    assert not [e for e in problems if "SettingsDisplay" in e or "DisplayBrightness" in e], problems
    print("DISPLAY_BRIGHTNESS_UI_OK")
finally:
    service.terminate()
    service.wait(timeout=5)
