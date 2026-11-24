"""A single, user-selected Wayland window, read through its portal PipeWire FD."""
import os
import uuid
from PySide6.QtGui import QImage
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gio, GLib, Gst, GstVideo

PORTAL = "org.freedesktop.portal.Desktop"
DESKTOP = "/org/freedesktop/portal/desktop"
CAST = "org.freedesktop.portal.ScreenCast"

class WindowStream:
    def __init__(self, error):
        self.error = error
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.sender = self.bus.get_unique_name()[1:].replace(".", "_")
        self.handle = None
        self.pending = None
        self.signal = 0
        self.session_signal = 0
        self.fd = -1
        self.pipeline = None
        self.sink = None
        self.closed = False

    def start(self):
        session = "monet" + uuid.uuid4().hex
        self.handle = DESKTOP + "/session/" + self.sender + "/" + session
        self.request("CreateSession", (), {"session_handle_token": GLib.Variant("s", session)}, self.select)

    def request(self, method, args, options, done):
        token = "monet" + uuid.uuid4().hex
        options["handle_token"] = GLib.Variant("s", token)
        self.pending = DESKTOP + "/request/" + self.sender + "/" + token
        def response(conn, sender, path, iface, signal, parameters):
            self.cancel_signal()
            self.pending = None
            code, result = parameters.unpack()
            if self.closed:
                return
            if code:
                self.fail("Window sharing was canceled." if code == 1 else "Window sharing was unavailable.")
                return
            try:
                done(result)
            except (GLib.Error, KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
                self.fail(str(exc))
        self.signal = self.bus.signal_subscribe(PORTAL, "org.freedesktop.portal.Request", "Response",
                                                self.pending, None, Gio.DBusSignalFlags.NONE, response)
        types = {"CreateSession": "(a{sv})", "SelectSources": "(oa{sv})", "Start": "(osa{sv})"}
        params = GLib.Variant(types[method], (*args, options))
        pending = self.pending
        def acknowledged(connection, result):
            try:
                connection.call_finish(result)
            except GLib.Error as exc:
                if self.pending == pending:
                    self.fail(str(exc))
        self.bus.call(PORTAL, DESKTOP, CAST, method, params, GLib.VariantType.new("(o)"),
                      Gio.DBusCallFlags.NONE, 30000, None, acknowledged)

    def select(self, result):
        self.handle = result["session_handle"]
        self.session_signal = self.bus.signal_subscribe(PORTAL, "org.freedesktop.portal.Session", "Closed",
            self.handle, None, Gio.DBusSignalFlags.NONE, lambda *_: self.fail("Window sharing ended."))
        self.request("SelectSources", (self.handle,), {"types": GLib.Variant("u", 2),
                     "multiple": GLib.Variant("b", False)}, lambda _: self.request("Start", (self.handle, ""), {}, self.connected))

    def connected(self, result):
        node = int(result["streams"][0][0])
        def opened(connection, result):
            try:
                value, fds = connection.call_with_unix_fd_list_finish(result)
                if not self.closed:
                    self.fd = fds.get(value.unpack()[0])
                    self.play(node)
            except (GLib.Error, RuntimeError, ValueError) as exc:
                self.fail(str(exc))
        self.bus.call_with_unix_fd_list(PORTAL, DESKTOP, CAST, "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (self.handle, {})), GLib.VariantType.new("(h)"),
            Gio.DBusCallFlags.NONE, 30000, None, None, opened)

    def play(self, node):
        Gst.init(None)
        self.pipeline = Gst.parse_launch("pipewiresrc name=capture ! video/x-raw,pixel-aspect-ratio=1/1 ! queue max-size-buffers=1 leaky=downstream ! "
            "videorate drop-only=true max-rate=5 ! videoconvertscale ! "
            "video/x-raw,format=RGBA,width=(int)[1,960],height=(int)[1,720],pixel-aspect-ratio=1/1 ! "
            "appsink name=frames sync=false max-buffers=1 drop=true")
        source = self.pipeline.get_by_name("capture")
        source.set_property("fd", self.fd)
        source.set_property("path", str(node))
        self.sink = self.pipeline.get_by_name("frames")
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self.fail("Could not start the window preview.")

    def image(self):
        if not self.sink:
            return None
        bus = self.pipeline.get_bus()
        event = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if event:
            self.fail("The shared window closed." if event.type == Gst.MessageType.EOS else event.parse_error()[0].message)
            return None
        frame = self.sink.emit("try-pull-sample", 0)
        if frame is None:
            return None
        fmt = frame.get_caps().get_structure(0)
        width, height = fmt.get_value("width"), fmt.get_value("height")
        buffer = frame.get_buffer()
        layout = GstVideo.buffer_get_video_meta(buffer)
        offset = layout.offset[0] if layout else 0
        stride = layout.stride[0] if layout else width * 4
        good, info = buffer.map(Gst.MapFlags.READ)
        if not good:
            return None
        try:
            if stride < width * 4 or offset + (height - 1) * stride + width * 4 > info.size:
                return None
            return QImage(memoryview(info.data)[offset:], width, height, stride, QImage.Format_RGBA8888).copy()
        finally:
            buffer.unmap(info)

    def cancel_signal(self):
        if self.signal:
            self.bus.signal_unsubscribe(self.signal)
            self.signal = 0

    def fail(self, message):
        if not self.closed:
            self.close()
            self.error(message)

    def close(self):
        self.closed = True
        self.cancel_signal()
        if self.session_signal:
            self.bus.signal_unsubscribe(self.session_signal)
            self.session_signal = 0
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = self.sink = None
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        for kind, path in (("Request", self.pending), ("Session", self.handle)):
            if path:
                self.bus.call(PORTAL, path, "org.freedesktop.portal." + kind, "Close", None, None,
                              Gio.DBusCallFlags.NONE, 1000, None, None)
        self.pending = self.handle = None
