"""Child of test_laptop_native: only run with an isolated home/config/session bus."""
import os
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QObject, Slot, QUrl, QMetaObject, Qt
from PySide6.QtGui import QPalette, QWindow
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(os.environ["XDG_CONFIG_HOME"])


def theme():
    (CONFIG / "Kvantum").mkdir(exist_ok=True)
    (CONFIG / "Kvantum/kvantum.kvconfig").write_text("[General]\ntheme=Monet\n")
    # Use repository themes so this also works on a KDE test machine without Monet installed.
    import shutil
    for name in ("Monet", "MonetDark"):
        shutil.copytree(ROOT / "linux/share/Kvantum" / name, CONFIG / "Kvantum" / name)
    (CONFIG / "kdeglobals").write_text("[KDE]\nwidgetStyle=kvantum\nLookAndFeelPackage=org.monet.desktop\n"
                                      "[General]\nColorScheme=MonetLight\n")
    (CONFIG / "monet").mkdir(exist_ok=True)
    (CONFIG / "monet/prefs.json").write_text('{"glass": "clear", "hours": false}')
    helper = CONFIG.parent / "monet-light"
    helper.write_text((ROOT / "linux/libexec/monet-light").read_text()
                      .replace("@DATADIR@", str(ROOT / "linux/share"))
                      .replace("@LIBEXECDIR@", str(ROOT / "linux/libexec")))
    app = QApplication([])
    window = QWidget(); window.resize(400, 200); window.show(); QTest.qWait(100)
    states = []
    for mode in ("mist", "smoke", "mist", "smoke"):
        (CONFIG / "monet/light").write_text(mode)
        subprocess.run(["bash", str(helper), "apply"], check=True, timeout=30)
        QTest.qWait(300)
        item = (app.style().name(), app.style().standardPalette().color(QPalette.Window).name())
        states.append(item)
        assert item[0] == ("kvantum-dark" if mode == "smoke" else "kvantum"), item
    assert states[0] == states[2] and states[1] == states[3], states
    assert states[0][1] == "#f3f1ec" and states[1][1] == "#242321", states
    window.close()


def action():
    class Words(QObject):
        @Slot(str, str, result=str)
        def i18nd(self, domain, text): return text
    app = QApplication([])
    engine = QQmlEngine(); words = Words(); engine.rootContext().setContextObject(words)
    marker = CONFIG / "called"
    helper = CONFIG / "monet-quick"
    helper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "' + str(marker) + '"\n')
    helper.chmod(0o700)
    source = (ROOT / "linux/share/monet/widgets/TaskManagerAction.qml").read_text()
    source = source.replace("@LIBEXECDIR@", str(CONFIG))
    component = QQmlComponent(engine)
    component.setData(source.encode(), QUrl.fromLocalFile(str(CONFIG / "TaskManagerAction.qml")))
    item = component.create()
    assert item is not None, [e.toString() for e in component.errors()]
    assert item.property("text") == "Task Manager"
    matches = engine.newQObject(item).property("isTaskManager")
    for app_id, expected in [("org.kde.plasma-systemmonitor.desktop", True), ("org.kde.plasma-systemmonitor", True),
                              ("plasma-systemmonitor.desktop", True), ("org.other.plasma-systemmonitor.desktop", False)]:
        assert matches.call([engine.toScriptValue(app_id)]).toBool() == expected
    assert QMetaObject.invokeMethod(item, "trigger")
    for _ in range(100):
        if marker.exists(): break
        QTest.qWait(20)
    assert marker.read_text() == "search-open\nsystem-monitor\n"
    item.deleteLater(); QTest.qWait(10)


def hardware():
    class Words(QObject):
        @Slot(str, str, result=str)
        @Slot(str, str, "QVariant", result=str)
        @Slot(str, str, "QVariant", "QVariant", result=str)
        def i18nd(self, domain, text, *args):
            for n, value in enumerate(args, 1):
                text = text.replace(f"%{n}", str(value))
            return text
    app = QApplication([])
    engine = QQmlEngine(); words = Words(); engine.rootContext().setContextObject(words)
    folder = ROOT / "linux/share/ksysguard/sensorfaces/org.monet.hardware/contents/ui"
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
import org.kde.ksysguard.sensors as Sensors
HardwareReadings { property int readyState: Sensors.Sensor.Ready }
''', QUrl.fromLocalFile(str(folder / "HardwareFixture.qml")))
    item = component.create()
    assert item is not None, [e.toString() for e in component.errors()]
    reported = engine.newQObject(item).property("reported")
    ready = item.property("readyState")
    # Missing driver telemetry must not be presented as a real 0 degrees or 0 B.
    cases = [
        (ready, 56, "cpu/all/maximumTemperature", 0, True),
        (ready, 0, "cpu/all/maximumTemperature", 0, False),
        (ready, 0, "gpu/gpu0/temperature", 0, False),
        (ready, 45, "gpu/gpu1/temperature", 0, True),
        (ready, 40, "gpu/gpu1/usedVram", 4096, True),
        (ready, 0, "gpu/gpu1/usedVram", 4096, True),
        (ready, 0, "gpu/gpu0/usedVram", 0, False),
        (ready, 0, "lmsensors/thinkpad/fan1", 0, True),
        (ready, float("nan"), "cpu/all/maximumTemperature", 0, False),
        (ready, "56", "cpu/all/maximumTemperature", 0, False),
        (-1, 56, "cpu/all/maximumTemperature", 0, False),
    ]
    for status, value, sensor, capacity, expected in cases:
        result = reported.call([engine.toScriptValue(v) for v in (status, value, sensor, capacity)])
        assert not result.isError() and result.toBool() == expected, (sensor, value, result.toString())
    # No hardware is also a supported state, with an explanation rather than an empty panel.
    assert any(child.property("text") == "No supported hardware sensors were found."
               for child in item.findChildren(QObject))
    item.deleteLater(); QTest.qWait(10)


def performance():
    os.environ["QT_QUICK_BACKEND"] = "software"
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    os.environ.pop("QT_QPA_PLATFORMTHEME", None)
    # The desktop style's threaded QML loader cannot call Python translation
    # slots while the GIL is held. Use Basic for this interaction-only fixture;
    # the real KDE shell and both Monet palettes are checked in native previews.
    class Words(QObject):
        @Slot(str, str, result=str)
        @Slot(str, str, "QVariant", result=str)
        def i18nd(self, domain, text, value=None):
            return text if value is None else text.replace("%1", str(value))
    # Exercise real controls with a private bus. Hardware presence is not needed
    # to verify that navigation selects the right backend, or disables sampling.
    app = QApplication([])
    engine = QQmlEngine(); words = Words(); engine.rootContext().setContextObject(words)
    folder = ROOT / "linux/share/ksysguard/sensorfaces/org.monet.performance/contents/ui"
    source = CONFIG / "PerformanceFixture.qml"
    source.write_text('''import QtQuick
import QtQuick.Controls
import "''' + folder.as_uri() + '''" as Monitor
ApplicationWindow {
    width: 820; height: 680; visible: true
    Monitor.Performance {
        anchors.fill: parent; anchors.margins: 24
        availableSensors: ["cpu/all/maximumTemperature", "gpu/gpu0/usage", "gpu/gpu1/usage", "cpu/cpu0/usage", "cpu/cpu0/frequency", "cpu/cpu1/usage", "cpu/cpu1/frequency"]
    }
}
''')
    # Asynchronous import avoids blocking Qt's QML loader thread on Python's GIL.
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(source)), QQmlComponent.Asynchronous)
    for _ in range(100):
        if not component.isLoading(): break
        QTest.qWait(20)
    assert component.isReady(), [e.toString() for e in component.errors()]
    window = component.create()
    assert window is not None, [e.toString() for e in component.errors()]
    QTest.qWait(100)
    view = window.findChild(QObject, "monetPerformance")
    data = window.findChild(QObject, "performanceData")

    def find(name, item=None):
        item = item or window.contentItem()
        if item.objectName() == name: return item
        for child in item.childItems():
            found = find(name, child)
            if found is not None: return found
        return None

    def click(name):
        item = find(name)
        assert item is not None, name
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                         item.mapToScene(item.boundingRect().center()).toPoint())
        QTest.qWait(30)

    expected = [["cpu/all/usage"], ["memory/physical/usedPercent"], ["gpu/gpu0/usage"],
                ["network/all/download", "network/all/upload"], ["disk/all/read", "disk/all/write"]]
    for section, sensors in enumerate(expected):
        click(f"resourceTab{section}")
        assert view.property("section") == section
        assert data.property("sensors") == sensors, (section, data.property("sensors"))
    original = view.property("availableSensors").toVariant()
    click("resourceTab0")
    # Resource tabs support keyboard navigation as well as pointer clicks.
    find("resourceTab0").forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Right); QTest.qWait(30)
    assert view.property("section") == 1
    view.setProperty("availableSensors", engine.toScriptValue(original)); QTest.qWait(30)
    click("resourceTab2")
    find("graphicsDevice").forceActiveFocus()
    QTest.keyClick(window, Qt.Key_End); QTest.keyClick(window, Qt.Key_Return); QTest.qWait(30)
    assert view.property("gpu") == "gpu/gpu1"
    assert data.property("sensors") == ["gpu/gpu1/usage"]
    click("pausePerformance")
    assert view.property("paused") and not data.property("enabled")
    click("pausePerformance")
    assert not view.property("paused") and data.property("enabled")
    view.setProperty("availableSensors", engine.toScriptValue(["gpu/gpu0/usage"])); QTest.qWait(30)
    assert view.property("graphicsIndex") == 0 and data.property("sensors") == ["gpu/gpu0/usage"]
    # Missing GPU support has an explicit empty state, without an invalid sensor request.
    view.setProperty("availableSensors", engine.toScriptValue([])); QTest.qWait(30)
    assert view.property("gpu") == "" and data.property("sensors") == []
    window.setWidth(540); QTest.qWait(30)
    selector = find("resourceSelector")
    assert selector.isVisible() and not find("resourceTabs").isVisible()
    selector.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_End); QTest.keyClick(window, Qt.Key_Return); QTest.qWait(30)
    assert view.property("section") == 4
    QTest.keyClick(window, Qt.Key_Home); QTest.keyClick(window, Qt.Key_Return); QTest.qWait(30)
    assert data.property("sensors") == ["cpu/all/usage"]
    assert view.property("monitoringActive") and data.property("enabled")
    # Hidden/minimized windows must release sampling; merely unfocused windows
    # still update. This includes GPU names and the Hardware tab readers.
    for section in (0, 2, 4):
        view.setProperty("section", section); QTest.qWait(30)
        window.setVisibility(QWindow.Minimized); QTest.qWait(30)
        assert not view.property("monitoringActive") and not data.property("enabled")
        for sensor in window.findChildren(QObject):
            if sensor.metaObject().indexOfProperty("sensorId") >= 0 and sensor.metaObject().indexOfProperty("enabled") >= 0:
                assert not sensor.property("enabled"), sensor.property("sensorId")
        window.showNormal(); QTest.qWait(30)
        assert view.property("monitoringActive")
    window.close(); window.deleteLater(); QTest.qWait(30)



def system():
    import json
    os.environ["QT_QUICK_BACKEND"] = "software"
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    os.environ.pop("QT_QPA_PLATFORMTHEME", None)
    class Words(QObject):
        @Slot(str, str, result=str)
        @Slot(str, str, "QVariant", result=str)
        def i18nd(self, domain, text, value=None):
            return text if value is None else text.replace("%1", str(value))
    app = QApplication([])
    engine = QQmlEngine(); words = Words(); engine.rootContext().setContextObject(words)
    helper = CONFIG / "snapshot-helper"
    marker = CONFIG / "snapshot-count"
    fixture = dict(version=1, system=dict(os="Monet test", kernel="test kernel"),
                   cpu=dict(models=["Hybrid test CPU"], cores=14, logical=20, topology=[dict(id=0, core=0, package=0, siblings=[0,1])], caches=[]),
                   memory=dict(MemTotal=16*1024**3, SwapTotal=0), graphics=[], networks=[], disks=[])
    helper.write_text("#!/usr/bin/python3\nfrom pathlib import Path\nimport time\np=Path(" + repr(str(marker)) + ")\np.write_text(p.read_text()+'x' if p.exists() else 'x')\ntime.sleep(.1)\nprint(" + repr(json.dumps(fixture)) + ")\n")
    helper.chmod(0o700)
    folder = ROOT / "linux/share/ksysguard/sensorfaces/org.monet.system/contents/ui"
    source = CONFIG / "SystemFixture.qml"
    source.write_text('import QtQuick\nimport QtQuick.Controls\nimport "' + folder.as_uri() + '" as Monitor\n'
        'ApplicationWindow { width: 900; height: 700; visible: true; Monitor.SystemDetails { anchors.fill: parent; anchors.margins: 24; helper: '
        + json.dumps(str(helper)) + '; sensorIds: ["cpu/cpu10/usage", "cpu/cpu2/usage", "cpu/cpu0/usage", "cpu/cpu1/usage", "network/(?!all).*/download", "network/eth0/download", "disk/(?!all).*/read", "disk/nvme0n1/read"] } }')
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(source)), QQmlComponent.Asynchronous)
    for _ in range(100):
        if not component.isLoading(): break
        QTest.qWait(20)
    assert component.isReady(), [e.toString() for e in component.errors()]
    window = component.create()
    assert window is not None, [e.toString() for e in component.errors()]
    view = window.findChild(QObject, "systemDetails")
    for _ in range(100):
        if view.property("snapshot").toVariant().get("version"): break
        QTest.qWait(20)
    assert view.property("snapshot").toVariant()["cpu"]["cores"] == 14
    assert marker.read_text() == "x"
    assert not window.findChild(QObject, "deviceDetails")
    assert any(row.get('value') == 'Hybrid test CPU' for row in view.property('rows').toVariant())
    view.setProperty("section", 1); QTest.qWait(100)
    detail = window.findChild(QObject, "deviceDetails")
    assert detail.property("devices").toVariant() == ["cpu/cpu0", "cpu/cpu1", "cpu/cpu2", "cpu/cpu10"]
    assert not detail.property("showCategorySelector")
    assert detail.property("topology").toVariant()[0]['siblings'] == [0, 1]
    view.setProperty("section", 2); QTest.qWait(50)
    assert detail.property("devices").toVariant() == ["network/eth0"]
    view.setProperty("section", 3); QTest.qWait(50)
    assert detail.property("devices").toVariant() == ["disk/nvme0n1"]
    view.setProperty("sensorIds", engine.toScriptValue(["cpu/cpu10/temperature", "cpu/cpu2/temperature", "cpu/cpu0/temperature"]))
    view.setProperty("section", 4); QTest.qWait(50)
    assert window.findChild(QObject, "hardwareSensorsList").property("model") == [
        "cpu/cpu0/temperature", "cpu/cpu2/temperature", "cpu/cpu10/temperature"]
    # Bounded live work even when a machine exposes hundreds of thermal sensors.
    view.setProperty("sensorIds", engine.toScriptValue([f"lmsensors/test{i}/temperature" for i in range(500)]))
    view.setProperty("section", 4); QTest.qWait(100)
    assert not window.findChild(QObject, "deviceDetails")
    def active_sensors():
        # ListView delegates have a visual parent but need not be QObject-owned
        # by the window. Inspect both trees to exercise actual reader states.
        seen = set()
        pending = [window, window.contentItem()]
        active = []
        while pending:
            obj = pending.pop()
            if obj in seen: continue
            seen.add(obj)
            pending.extend(obj.children())
            if isinstance(obj, QQuickItem): pending.extend(obj.childItems())
            if obj.metaObject().indexOfProperty('sensorId') >= 0 and obj.metaObject().indexOfProperty('enabled') >= 0 and obj.property('enabled'):
                active.append(obj)
        return active
    assert 0 < len(active_sensors()) < 50, len(active_sensors())
    window.setVisibility(QWindow.Minimized); QTest.qWait(50)
    assert not active_sensors()
    window.showNormal(); QTest.qWait(50)
    view.setProperty('section', 0); QTest.qWait(50)
    assert not window.findChild(QObject, 'hardwareSensorsList')
    assert not active_sensors()
    assert marker.read_text() == 'x'  # Navigation never re-runs identification.
    QMetaObject.invokeMethod(view, 'refresh'); QMetaObject.invokeMethod(view, 'refresh')
    for _ in range(100):
        if not view.property('busy'): break
        QTest.qWait(20)
    assert marker.read_text() == 'xx'  # Coalesce double clicks.
    helper.write_text('#!/bin/sh\necho not-json\n')
    QMetaObject.invokeMethod(view, 'refresh')
    for _ in range(100):
        if not view.property('busy'): break
        QTest.qWait(20)
    assert view.property('error')
    assert view.property('snapshot').toVariant()['cpu']['cores'] == 14
    window.close(); window.deleteLater(); QTest.qWait(30)


def tables():
    # Compile against the installed KDE table components, not fixture substitutes.
    # A missing schema or import breaks native actions even if totals still draw.
    import xml.etree.ElementTree as ET
    app = QApplication([])
    engine = QQmlEngine()
    for face in ("applications", "processes"):
        folder = ROOT / f"linux/share/ksysguard/sensorfaces/org.monet.{face}/contents"
        ET.parse(folder / "config/main.xml")
        for filename in ("FullRepresentation.qml", "CompactRepresentation.qml", "Config.qml"):
            c = QQmlComponent(engine, QUrl.fromLocalFile(str(folder / "ui" / filename)), QQmlComponent.Asynchronous)
            for _ in range(200):
                if not c.isLoading(): break
                QTest.qWait(10)
            assert c.isReady(), [e.toString() for e in c.errors()]


def activity():
    app = QApplication([])
    engine = QQmlEngine()
    folder = ROOT / "linux/share/ksysguard/sensorfaces/org.monet.performance/contents/ui"
    component = QQmlComponent(engine)
    component.setData(b"import QtQuick\nWindowActivity { item: Item {} }", QUrl.fromLocalFile(str(folder / "ActivityFixture.qml")))
    activity = component.create()
    assert activity is not None, [e.toString() for e in component.errors()]
    item = activity.property('item')
    window = QQuickWindow()
    window.resize(600, 400)
    # The observer is detached; only its content item is moved into the window.
    item.setParentItem(window.contentItem())
    window.show(); QTest.qWait(30)
    assert activity.property('active')
    activity.setProperty('compositorMinimized', True); QTest.qWait(10)
    assert not activity.property('active')
    activity.setProperty('compositorMinimized', False); QTest.qWait(10)
    assert activity.property('active')
    item.setVisible(False); QTest.qWait(10)
    assert not activity.property('active')
    item.setVisible(True)
    window.setVisibility(QWindow.Minimized); QTest.qWait(30)
    assert not activity.property('windowVisible') and not activity.property('active')
    window.showNormal(); QTest.qWait(30)
    assert activity.property('active')
    window.hide(); QTest.qWait(30)
    assert not activity.property('active')
    window.close(); activity.deleteLater(); QTest.qWait(10)
    c = QQmlComponent(engine)
    c.setData(b"import QtQuick\nQtObject { function hidden(windows) { return MonitorWindows.allMinimized(windows) } }", QUrl.fromLocalFile(str(folder / "WindowsFixture.qml")))
    state = c.create()
    assert state is not None, [e.toString() for e in c.errors()]
    check = engine.newQObject(state).property('hidden')
    def task(app='org.kde.plasma-systemmonitor.desktop', minimized=True):
        return dict(appId=app, isWindow=True, minimized=minimized)
    for windows, expected in [([],False), ([task()],True), ([task('plasma-systemmonitor')],True),
                              ([task(),task(minimized=False)],False), ([task('unrelated')],False)]:
        assert check.call([engine.toScriptValue(windows)]).toBool() == expected
    state.deleteLater(); QTest.qWait(10)


def files():
    sys.path.insert(0, str(ROOT))
    from tests.test_files_tools import files_tools
    from unittest.mock import patch
    from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QTreeWidget, QInputDialog
    app = QApplication([])
    tool = files_tools()
    folder = CONFIG / "Downloads"; folder.mkdir()
    program = folder / "Example"; program.write_text("#!/bin/sh\nexit 0\n"); program.chmod(0o700)
    (folder / "Setup.exe").write_bytes(b"MZexample")
    dialog = tool.make_dialog("apps", folder); dialog.show()
    tree = dialog.findChild(QTreeWidget, "foundApps")
    for _ in range(150):
        if tree.topLevelItemCount(): break
        QTest.qWait(20)
    assert tree.topLevelItemCount() == 2, dialog.findChild(QLabel, "scanStatus").text()
    add = dialog.findChild(QPushButton, "addApp"); show = dialog.findChild(QPushButton, "showApp")
    assert add.isEnabled()
    with patch.object(QInputDialog, "getText", return_value=("Example", True)), patch.object(tool.subprocess, "Popen") as launch:
        QTest.mouseClick(add, Qt.LeftButton); QTest.qWait(50)
        launch.assert_not_called()
    entries = list((CONFIG.parent / "data/applications").glob("monet-local-*.desktop"))
    assert len(entries) == 1 and "Name=Example" in entries[0].read_text()
    tree.setCurrentItem(tree.topLevelItem(1)); QTest.qWait(20)
    assert not add.isEnabled() and show.isEnabled()
    with patch.object(tool.subprocess, "Popen") as reveal:
        QTest.mouseClick(show, Qt.LeftButton)
        reveal.assert_called_once_with(["dolphin", "--select", str(folder / "Setup.exe")], start_new_session=True)
    dialog.findChild(QLineEdit, "filterApps").setText("missing")
    assert not show.isEnabled() and not add.isEnabled()
    dialog.reject(); QTest.qWait(20)
    space = tool.make_dialog("space", folder); space.show()
    assert space.findChild(QLabel, "space_free").text().endswith("GiB")
    program.unlink(); (folder / "Setup.exe").unlink(); folder.rmdir()
    QTest.mouseClick(space.findChild(QPushButton, "refreshSpace"), Qt.LeftButton)
    assert space.findChild(QLabel, "space_free").text() == "—"
    space.reject(); QTest.qWait(20)


{"theme": theme, "action": action, "hardware": hardware, "performance": performance, "files": files, "system": system, "tables": tables, "activity": activity}[sys.argv[1]]()
