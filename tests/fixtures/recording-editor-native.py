"""Exercise the Utilities editor with a generated picture and tone on a private Qt session."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session


def edit_clip():
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
    from window import Window

    app = QApplication([])
    window = Window(ROOT / "linux/libexec")
    window.show()
    window.search.setText("Screen recorder and editor")
    assert window.catalog.count() == 1
    window.open_selected()
    editor = window.pages["recordings"]

    def wait(predicate):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if predicate():
                return
            QTest.qWait(25)
        raise AssertionError((editor.message.text(), editor.player.errorString()))

    def run(*args):
        return subprocess.check_output(args, stderr=subprocess.PIPE, timeout=30)

    folder = Path(os.environ["HOME"])
    source = folder / "Test clip #1.mp4"
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:size=320x180:rate=24:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-vf", "drawbox=x=160:y=0:w=160:h=180:color=blue:t=fill",
        "-threads", "2", "-c:v", "libx264", "-c:a", "aac", source)
    checksum = hashlib.sha256(source.read_bytes()).digest()
    editor.open_file(source)
    wait(lambda: editor.editor.isEnabled() and editor.player.hasAudio())
    editor.play_pause()
    wait(lambda: editor.player.position() > 150)
    editor.begin.setValue(.5)
    editor.end.setValue(2.5)
    editor.rate.setCurrentIndex(3)
    editor.seek.setValue(1200)
    wait(lambda: abs(editor.player.position() - 1200) < 4)
    editor.crop_button.click()
    picture = editor.picture
    rect = picture.sceneRect()
    start = picture.mapFromScene(rect.width() / 2, 0)
    finish = picture.mapFromScene(rect.width() - 1, rect.height() - 1)
    QTest.mousePress(picture.viewport(), Qt.LeftButton, pos=start)
    QTest.mouseMove(picture.viewport(), finish, 20)
    QTest.mouseRelease(picture.viewport(), Qt.LeftButton, pos=finish)
    assert abs(picture.crop[0] - .5) < .02

    def export(path):
        editor.export_to(path)
        wait(lambda: editor.exporter is None)
        assert path.exists(), editor.message.text()
        return json.loads(run("ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path))

    saved = folder / "Cropped.mp4"
    info = export(saved)
    video, audio = info["streams"]
    assert audio["codec_type"] == "audio" and 150 <= video["width"] <= 163
    assert .94 <= float(info["format"]["duration"]) <= 1.12
    rgb = run("ffmpeg", "-v", "error", "-i", saved, "-vframes", "1", "-vf", "scale=1:1",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-")
    assert rgb[2] > 190 and rgb[0] < 60
    editor.export_to(saved)
    assert editor.exporter is None and "new filename" in editor.message.text()
    editor.mute.setChecked(True)
    assert len(export(folder / "Muted.mp4")["streams"]) == 1
    assert export(folder / "Loop.gif")["streams"][0]["codec_name"] == "gif"
    cancelled = folder / "Cancelled.mp4"
    editor.export_to(cancelled)
    editor.cancel_export()
    wait(lambda: editor.exporter is None)
    assert not cancelled.exists() and not list(folder.glob(".monet-recording-*"))
    assert hashlib.sha256(source.read_bytes()).digest() == checksum
    window.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--private"]:
        assert os.environ["HOME"].startswith("/tmp/monet-tests-") and not os.getenv("WAYLAND_DISPLAY")
        edit_clip()
    else:
        with private_session() as env:
            env.update(LANGUAGE="en", QT_FFMPEG_DECODING_HW_DEVICE_TYPES=",")
            subprocess.run([sys.executable, __file__, "--private"], env=env, check=True, timeout=80)
