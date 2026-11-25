"""Exercise zoom editing through Utilities and compare the preview with encoded frames."""
from io import BytesIO
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


def exercise():
    from PIL import Image, ImageDraw, ImageStat
    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    sys.path.insert(0, str(Path("/usr/share/monet/utilities") if "--installed" in sys.argv else ROOT/"linux/share/monet/utilities"))
    from recording_zoom import Zoom
    from recording_zoom_editor import ZoomDialog
    from window import Window

    app = QApplication([])
    home = Path.home()
    window = Window("/usr/libexec")
    window.Open(["recordings"])
    page = window.pages["recordings"]
    picture = page.picture
    def wait(check):
        limit = time.monotonic() + 15
        while time.monotonic() < limit:
            if check():
                return
            QTest.qWait(20)
        raise AssertionError((page.message.text(), page.player.mediaStatus(), page.player.playbackState(),
                              page.player.hasVideo(), page.duration, page.awaiting_first_frame, picture.video.frame.isValid()))
    def run(*args):
        return subprocess.check_output(args, stderr=subprocess.PIPE, timeout=30)
    pattern = Image.new("RGB", (320, 180))
    pen = ImageDraw.Draw(pattern)
    for col in range(8):
        for row in range(6):
            pen.rectangle((40*col, 30*row, 40*col+39, 30*row+29),
                          fill=(24 + 27*col, 24 + 37*row, 190 if (col+row)%2 else 40))
    pattern.save(home/"pattern.png")
    source = home/"take.mp4"
    run("ffmpeg", "-v", "error", "-loop", "1", "-framerate", "24", "-i", home/"pattern.png",
        "-f", "lavfi", "-i", "sine=duration=5", "-t", "5", "-threads", "2",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-c:a", "aac", source)
    original = hashlib.sha256(source.read_bytes()).digest()
    page.open_file(source)
    wait(lambda: page.editor.isEnabled() and picture.video.frame.isValid())
    def seek(ms):
        page.scrub(ms)
        wait(lambda: abs(picture.video.frame.startTime()/1000-ms) < 50)
    def menu_action(text):
        page.list_zooms()
        return next(a for a in page.zoom_menu.actions() if a.text().startswith(text))
    def dialog(text, fn):
        errors = []
        def apply():
            widget = QApplication.activeModalWidget()
            try:
                assert isinstance(widget, ZoomDialog), widget
                fn(widget)
            except Exception as exc:
                errors.append(exc)
                if widget:
                    widget.reject()
        QTimer.singleShot(50, apply)
        menu_action(text).trigger()
        if errors:
            raise errors[0]
    def first(d):
        d.start.setValue(.5)
        d.end.setValue(2.5)
        d.strength.setValue(2.)
        box = d.aim.picture()
        x = int(box.left()+box.width()*.82)
        QTest.mouseClick(d.aim, Qt.LeftButton, pos=QPoint(x, int(box.center().y())))
        QTest.keyClick(d.aim, Qt.Key_Up)
        assert d.aim.x > .80 and d.aim.y < .50
        d.buttons.button(QDialogButtonBox.Save).click()
    seek(600)
    dialog("Add zoom", first)
    assert len(picture.zooms) == 1
    seek(3200)
    def second(d):
        assert d.start.minimum() == 2.5
        d.end.setValue(4.7)
        d.strength.setValue(2.)
        d.aim.aim(.05, .80)
        d.accept()
    dialog("Add zoom", second)
    assert len(picture.zooms) == 2
    dialog("Edit zoom", lambda d: (d.strength.setValue(3), d.reject()))
    assert picture.zooms[-1].amount == 2
    dialog("Edit zoom", lambda d: d.remove())
    assert len(picture.zooms) == 1
    menu_action("Undo zoom").trigger()
    assert len(picture.zooms) == 2
    menu_action("Redo zoom").trigger()
    assert len(picture.zooms) == 1
    menu_action("Undo zoom").trigger()

    def compare(image, expected, size, title):
        checked = 0
        for fx in (.11, .27, .41, .59, .73, .91):
            for fy in (.12, .32, .52, .78, .88):
                sx, sy = expected(fx, fy)
                if min(sx%40, 40-sx%40, sy%30, 30-sy%30) < 4:
                    continue
                wanted = pattern.getpixel((min(319,int(sx)), min(179,int(sy))))
                measured = image(int(size[0]*fx), int(size[1]*fy))
                assert max(abs(a-b) for a,b in zip(wanted, measured)) < 28, (title, fx,fy,wanted,measured)
                checked += 1
        assert checked >= 8, (title, checked)

    def preview(ms, expected):
        seek(ms)
        QTest.qWait(70)
        shot = picture.viewport().grab().toImage()
        # The viewport centers the full edited aspect ratio within its margins.
        w, h = shot.width()-4, shot.height()-4
        aspect = 320/180
        w, h = min(w, round(h*aspect)), min(h, round(w/aspect))
        ox, oy = (shot.width()-w)//2, (shot.height()-h)//2
        compare(lambda x,y: shot.pixelColor(ox+x,oy+y).getRgb()[:3], expected, (w,h), "preview")
    mid_y = picture.zooms[0].y*180-45
    full = lambda x,y: (320*x,180*y)
    right = lambda x,y: (160+160*x,mid_y+90*y)
    left = lambda x,y: (160*x,90+90*y)
    def first_ramp(ms):
        u = (ms - 500)/420
        fraction = 1 / (1 + u*u*(3-2*u))
        y_travel = mid_y / 90
        return lambda x,y: (320*((1-fraction)+x*fraction), 180*(y_travel*(1-fraction)+y*fraction))
    preview(750, first_ramp(750))
    preview(1500, right)
    preview(2850, full)
    preview(3800, left)
    def encoded(target, sec, expected):
        if target.suffix == ".gif":
            elapsed = 0
            with Image.open(target) as gif:
                for index in range(gif.n_frames):
                    gif.seek(index)
                    elapsed += gif.info["duration"]
                    if elapsed > sec*1000:
                        image = gif.convert("RGB")
                        break
        else:
            data = run("ffmpeg", "-v", "error", "-i", target, "-ss", str(sec), "-frames:v", "1",
                       "-threads", "1", "-c:v", "png", "-f", "image2pipe", "-")
            image = Image.open(BytesIO(data)).convert("RGB")
        # Sample a small tile: GIF expresses some flat colours by dithering.
        def sample(x, y):
            return ImageStat.Stat(image.crop((x-2, y-2, x+3, y+3))).mean
        compare(sample, expected, image.size, (target.name, sec))
    # The start trim cuts into the ramp. Measure both holds and the unzoomed
    # gap after the speed change, and check the audio stream and duration.
    page.begin.setValue(.7)
    page.end.setValue(4.7)
    page.rate.setCurrentIndex(page.rate.findData(2.))
    for ext in ("mp4","gif"):
        dest = home/("zoomed."+ext)
        page.export_to(dest)
        wait(lambda: page.exporter is None)
        assert dest.is_file(), page.message.text()
        if os.environ.get("MONET_ZOOM_QA"):
            import shutil
            shutil.copy2(dest, Path(os.environ["MONET_ZOOM_QA"]) / dest.name)
        info = json.loads(run("ffprobe","-v","error","-show_streams","-show_format","-of","json",dest))
        assert abs(float(info["format"]["duration"])-2) < .13
        assert len(info["streams"]) == (2 if ext=="mp4" else 1)
        if ext == "mp4":
            encoded(dest,0,first_ramp(700))
        encoded(dest,.40,right)
        encoded(dest,1.05,full)
        encoded(dest,1.55,left)

    picture.crop = (.25, 0, .5, 1)
    picture.fit()
    cropped = home/"cropped.mp4"
    page.export_to(cropped)
    wait(lambda: page.exporter is None)
    encoded(cropped, .40, lambda x,y: (160+80*x, mid_y+90*y))
    encoded(cropped, 1.05, lambda x,y: (80+160*x,180*y))
    assert hashlib.sha256(source.read_bytes()).digest() == original
    page.open_file(source)
    assert not picture.zooms and not page.zoom_history.canUndo()
    # At 0.5 fps the whole selection fits inside the first red frame.
    # The camera still moves and the next blue frame must stay out of view.
    sparse = home/"sparse.mp4"
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:size=320x180:duration=6:rate=1/2",
        "-f", "lavfi", "-i", "sine=duration=6", "-vf", "drawbox=w=iw:h=ih:t=fill:color=blue:enable='gte(t,2)'",
        "-threads", "1", "-c:v", "libx264", "-c:a", "aac", sparse)
    page.open_file(sparse)
    wait(lambda: page.editor.isEnabled() and picture.video.frame.isValid())
    picture.set_zooms([Zoom(0, 3000, .83, .36, 2)])
    page.player.setPosition(0)
    page.player.play()
    widths = set()
    frame_times = set()
    for _ in range(16):
        QTest.qWait(25)
        widths.add(round(picture.view.width(), 1))
        frame_times.add(picture.video.frame.startTime())
    page.player.pause()
    assert len(widths) >= 4 and len(frame_times) == 1, (widths, frame_times)
    assert not picture.motion_timer.isActive()
    page.begin.setValue(.5)
    page.end.setValue(1.3)
    dest = home/"still-trim.mp4"
    page.export_to(dest)
    wait(lambda: page.exporter is None)
    info = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-of", "json", dest))
    assert len(info["streams"]) == 2
    assert all(abs(float(stream["duration"])-.8) < .04 for stream in info["streams"])
    data = run("ffmpeg", "-v", "error", "-ss", "0.4", "-i", dest, "-frames:v", "1",
               "-vf", "scale=1:1", "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-")
    assert data[0] > 210 and data[2] < 40, data
    window.close()
    print("Zoom menu, aiming, timing, cancel, undo/redo, preview and decoded MP4/GIF frames passed.")


if __name__ == "__main__":
    if "--private" in sys.argv:
        assert os.environ["HOME"].startswith("/tmp/monet-tests-")
        exercise()
    else:
        with private_session() as env:
            env.update(LANGUAGE="en", LANG="C.UTF-8", QT_FFMPEG_DECODING_HW_DEVICE_TYPES=",", LP_NUM_THREADS="1")
            subprocess.run([sys.executable, "-B", __file__, "--private", *sys.argv[1:]], env=env, check=True, timeout=100)
