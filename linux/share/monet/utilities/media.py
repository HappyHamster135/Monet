"""User-initiated capture, conversion and player metadata."""
import ctypes
from ctypes.util import find_library
import os
from pathlib import Path
import sys

def read_text(path):
    from PIL import Image
    lib = ctypes.CDLL(find_library("tesseract") or "libtesseract.so")
    # Declare the C API explicitly, including the ownership of its result.
    ptr = ctypes.c_void_p
    string = ctypes.c_char_p
    integer = ctypes.c_int
    for name, result, args in (
        ("TessBaseAPICreate", ptr, []), ("TessBaseAPIInit3", integer, [ptr, string, string]),
        ("TessBaseAPISetImage", None, [ptr, string, integer, integer, integer, integer]),
        ("TessBaseAPIGetUTF8Text", ptr, [ptr]), ("TessDeleteText", None, [ptr]),
        ("TessBaseAPIDelete", None, [ptr])):
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
    with Image.open(path) as source:
        if source.width * source.height > 33_177_600:
            raise ValueError("Select a smaller area.")
        image = source.convert("L")
    data = image.tobytes()
    ctx = lib.TessBaseAPICreate()
    if not ctx:
        raise RuntimeError("Text recognition is unavailable.")
    try:
        import subprocess
        lang = subprocess.run(["kreadconfig6", "--file", "spectaclerc", "--group", "General", "--key", "ocrLanguages"],
                              capture_output=True, text=True, timeout=2).stdout.strip().replace(",", "+") or "eng"
        if lib.TessBaseAPIInit3(ctx, None, lang.encode()) != 0:
            raise RuntimeError("The selected text-recognition language is unavailable.")
        lib.TessBaseAPISetImage(ctx, data, image.width, image.height, 1, image.width)
        result = lib.TessBaseAPIGetUTF8Text(ctx)
        if not result:
            return ""
        try:
            return ctypes.string_at(result).decode().strip()
        finally:
            lib.TessDeleteText(result)
    finally:
        lib.TessBaseAPIDelete(ctx)

def player_info():
    import dbus
    bus = dbus.SessionBus()
    players = []
    for name in bus.list_names():
        if not name.startswith("org.mpris.MediaPlayer2.") or name.endswith(".plasma-browser-integration.instance"):
            continue
        try:
            obj = bus.get_object(name, "/org/mpris/MediaPlayer2", introspect=False)
            prop = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            meta = prop.Get("org.mpris.MediaPlayer2.Player", "Metadata", timeout=1)
            title = str(meta.get("xesam:title", ""))
            status = str(prop.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus", timeout=1))
            chunks = [str(prop.Get("org.mpris.MediaPlayer2", "Identity", timeout=1)), title]
            lyrics = str(meta.get("xesam:asText", "")).strip()
            if lyrics:
                chunks.extend(["", "Lyrics", lyrics])
            try:
                tracks = list(prop.Get("org.mpris.MediaPlayer2.TrackList", "Tracks", timeout=1))
                current = meta.get("mpris:trackid")
                start = tracks.index(current) + 1 if current in tracks else 0
                following = tracks[start:start + 20]
                if following:
                    entries = obj.GetTracksMetadata(dbus.Array(following, signature="o"),
                                                    dbus_interface="org.mpris.MediaPlayer2.TrackList", timeout=2)
                    chunks.extend(["", "Up next", *[str(track.get("xesam:title", "Untitled")) for track in entries]])
            except dbus.DBusException:
                pass
            if len(chunks) == 2:
                chunks.extend(["", "This player hasn’t shared lyrics or a queue."])
            players.append((status != "Playing", "\n".join(chunks)))
        except dbus.DBusException:
            continue
    return "\n\n".join(chunks for _, chunks in sorted(players)) or "No media player is available."

def read_qr(path):
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication, QImage
    from PySide6.QtMultimedia import QVideoFrame, QVideoSink
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    app = QGuiApplication([])
    engine = QQmlEngine()
    comp = QQmlComponent(engine)
    comp.setData(b'''import QtQuick
import org.kde.prison.scanner as S
S.VideoScanner { property string decoded: result.content ? String(result.content) : "" }''', QUrl())
    scanner = comp.create()
    if scanner is None:
        raise RuntimeError(comp.errorString())
    image = QImage(path)
    if image.isNull():
        return ""
    sink = QVideoSink(scanner)
    scanner.setProperty("videoSink", sink)
    scanner.decodedChanged.connect(app.quit)
    sink.setVideoFrame(QVideoFrame(image.convertToFormat(QImage.Format_RGBA8888)))
    QTimer.singleShot(1200, app.quit)
    app.exec()
    return scanner.property("decoded")

if __name__ == "__main__":
    try:
        if sys.argv[1] == "player":
            print(player_info())
        elif sys.argv[1] == "read" and len(sys.argv) == 3:
            qr = read_qr(sys.argv[2])
            text = read_text(sys.argv[2]) if not qr else ""
            print(qr or text or "No text or QR code was recognized.")
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
