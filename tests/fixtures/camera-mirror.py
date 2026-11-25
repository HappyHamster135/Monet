# Only memory-backed test patterns are visible to this process.
from pathlib import Path
import os
import sys
import time

import dbus
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject
from PySide6.QtCore import QEventLoop, QObject, Qt, QTimer, QUrl
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

Gst.init(None)
registry = Gst.Registry.get()
for factory in Gst.DeviceProviderFactory.list_get_device_providers(Gst.Rank.NONE):
    registry.remove_feature(factory)


class Pattern(Gst.Device):
    sources = []

    def do_create_element(self, name):
        src = Gst.ElementFactory.make("videotestsrc", name)
        src.set_property("is-live", True)
        src.set_property("pattern", 0 if self.get_display_name() == "Colour bars" else 18)
        # GStreamer's create_element vfunc transfers a floating reference.
        self.sources.append(src.weak_ref())
        src._force_floating()
        return src


class Cameras(Gst.DeviceProvider):
    # GI uses this metadata to match the Video/Source device monitor.
    metadata = ('Monet mirror fixture', 'Source/Video', 'In-memory camera inputs', 'Monet')
    active = None

    def do_start(self):
        Cameras.active = self
        self.cameras = []
        for name in ("Colour bars", "Moving ball"):
            self.add(name)
        return True

    def add(self, name):
        caps = Gst.Caps.from_string("video/x-raw,format=I420,width=320,height=240,framerate=15/1")
        props = Gst.Structure.new_empty("props")
        props.set_value("is-default", name == "Colour bars")
        cam = Pattern(**{"display-name": name, "device-class": "Video/Source", "caps": caps, "properties": props})
        self.device_add(cam)
        self.cameras.append(cam)

    def remove(self, index):
        self.device_remove(self.cameras.pop(index))

    def do_stop(self):
        Cameras.active = None


GObject.type_register(Pattern)
GObject.type_register(Cameras)
Cameras.set_static_metadata(*Cameras.metadata)

assert Gst.DeviceProvider.register(None, "monettestcams", Gst.Rank.PRIMARY+2, Cameras)


def pump(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def until(predicate, reason):
    end = time.monotonic() + 5
    while not predicate() and time.monotonic() < end:
        pump(30)
    assert predicate(), reason


def exercise():
    from camera_window import CameraWindow
    from window import Window
    owner = Window(Path("/usr/libexec"), defer_catalog=True)
    owner.Open(["camera"])
    mirror = owner.mirror
    assert isinstance(mirror, CameraWindow)
    owner.Open(["camera"])
    assert owner.mirror is mirror and not owner.isVisible()
    root = mirror.view.rootObject()
    loader = root.findChild(QObject, "cameraFeedLoader")
    until(lambda: loader.property("item") is not None, "mirror should start on explicit launch")

    def feed():
        return loader.property("item")

    def picker_count(page):
        return page.findChild(QQuickItem, "cameraDevicePicker").property("count")

    def frame():
        return feed() and feed().property("gotFrame")

    until(frame, "first camera frame")
    page = feed()
    picker = page.findChild(QQuickItem, "cameraDevicePicker")
    assert picker.property("displayText") == "Colour bars"
    # SMPTE starts with white on the left and blue on the right. Inspect the
    # visible mirror itself, including its letterboxing, with either renderer.
    def mirrored_bars():
        image = mirror.view.grabFramebuffer()
        if image.isNull():
            return False
        y = image.height() // 2
        left = image.pixelColor(int(image.width() * .15), y)
        right = image.pixelColor(int(image.width() * .85), y)
        return left.blue() > 180 and left.red() < 60 and min(right.getRgb()[:3]) > 180
    until(mirrored_bars, "mirrored colour bars on the preview surface")
    picker.forceActiveFocus()
    QTest.keyClick(mirror.view, Qt.Key_Down)
    until(lambda: picker.property("displayText") == "Moving ball" and frame(), "switch camera")
    mirror.close()
    until(lambda: owner.mirror is None, "window released")
    owner.Open(["camera"])
    mirror = owner.mirror
    root = mirror.view.rootObject()
    loader = root.findChild(QObject, "cameraFeedLoader")
    until(frame, "remembered camera")
    page = feed()
    picker = page.findChild(QQuickItem, "cameraDevicePicker")
    assert picker.property("displayText") == "Moving ball"
    Cameras.active.remove(1)
    until(lambda: picker.property("count") == 1 and not feed().property("started"), "unplug during capture")
    assert feed().property("problem")
    retry = page.findChild(QQuickItem, "retryCamera")
    retry.forceActiveFocus()
    QTest.keyClick(mirror.view, Qt.Key_Space)
    until(frame, "start the remaining camera")
    locker = dbus.Interface(dbus.SessionBus().get_object("org.freedesktop.ScreenSaver", "/ScreenSaver"), "org.monet.Test")
    locker.SetActive(True)
    until(lambda: not root.property("available") and feed() is None, "release on lock")
    def released():
        for weak_source in Pattern.sources:
            source = weak_source()
            if source and source.get_state(0).state != Gst.State.NULL:
                return False
        return True
    until(released, "camera pipelines returned to NULL after lock")
    locker.SetActive(False)
    until(lambda: root.property("available"), "unlock")
    assert not loader.property("active")
    start = root.findChild(QQuickItem, "startCamera")
    start.forceActiveFocus()
    QTest.keyClick(mirror.view, Qt.Key_Space)
    until(frame, "restart after unlock")
    Cameras.active.remove(0)
    until(lambda: feed() and not feed().property("started") and picker_count(feed()) == 0, "last camera disconnected")
    Cameras.active.add("Reconnected camera")
    until(lambda: picker_count(feed()) == 1, "camera returns")
    assert not feed().property("started")
    mirror.hide()
    until(lambda: feed() is None, "release on hide")
    mirror.show()
    until(lambda: root.property("available"), "visible after hide")
    assert not loader.property("active")
    mirror.close()
    owner.close()
    pump(30)
    print("Verified preview pixels, launcher reuse, selection, hotplug, locking and release.", flush=True)


def portable_lock(share):
    # The standalone desktop package also runs on KDE without the native activity plugin.
    engine = QQmlEngine()
    source = share / "plasma/plasmoids/org.monet.notch/contents/ui/CameraLock.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(source)))
    gate = component.create()
    assert gate, component.errorString()
    gate.setParent(engine)
    until(lambda: gate.property("active"), "read the portable desktop lock state")
    locker = dbus.Interface(dbus.SessionBus().get_object("org.freedesktop.ScreenSaver", "/ScreenSaver"), "org.monet.Test")
    locker.SetActive(True)
    until(lambda: gate.property("locked") and not gate.property("active"), "portable desktop locks")
    locker.SetActive(False)
    until(lambda: gate.property("active"), "portable desktop unlocks")
    gate.deleteLater()
    pump(20)


if __name__ == "__main__":
    root_path = Path(__file__).resolve().parents[2]
    share = Path(os.environ.get("MONET_CAMERA_TEST_SHARE", root_path / "linux/share"))
    sys.path.insert(0, str(share / "monet/utilities"))
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    inputs = QMediaDevices()
    assert [d.description() for d in inputs.videoInputs()] == ["Colour bars", "Moving ball"]
    portable_lock(share)
    exercise()
