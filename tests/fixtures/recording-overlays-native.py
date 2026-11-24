"""Exercise the overlay menus and measure pixels in the encoded MP4 and GIF."""
import faulthandler
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
    from io import BytesIO
    from PIL import Image, ImageStat
    from PySide6.QtCore import QPointF, QSize, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QLineEdit
    modules = Path("/usr/share/monet/utilities") if "--installed" in sys.argv else ROOT / "linux/share/monet/utilities"
    sys.path.insert(0, str(modules))
    from PySide6.QtMultimedia import QVideoFrame, QVideoFrameFormat as F
    from recording_preview import FrameScaler
    from recording_layer_editor import LayerDialog
    from window import Window

    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs)
    app = QApplication([])
    # Check real mapped plane strides, chroma ordering and range conversion.
    # Odd widths and non-integral scaling occur when the editor is resized.
    scaler = FrameScaler()
    for fmt, chroma in ((F.Format_YUV420P, (b"Z", b"\xf0")), (F.Format_YUV422P, (b"Z", b"\xf0")),
                        (F.Format_NV12, (b"Z\xf0",)), (F.Format_NV21, (b"\xf0Z",))):
        for space, range_, rgb in ((F.ColorSpace_BT601, F.ColorRange_Video, (255, 0, 0)),
                                   (F.ColorSpace_BT709, F.ColorRange_Full, (255, 36, 10))):
            desc = F(QSize(63, 36), fmt)
            desc.setColorSpace(space)
            desc.setColorRange(range_)
            frame_ = QVideoFrame(desc)
            assert frame_.map(QVideoFrame.WriteOnly)
            for plane, pattern in enumerate((b"Q", *chroma)):
                data = frame_.bits(plane)
                stride = frame_.bytesPerLine(plane)
                row = (pattern * stride)[:stride]
                for offset in range(0, len(data), stride):
                    data[offset:offset + stride] = row[:len(data[offset:offset + stride])]
            frame_.unmap()
            for size in (QSize(37, 21), QSize(60, 34)):
                sample = scaler.image(frame_, size)
                assert sample.size() == size, (fmt, sample.size())
                for x, y in ((0, 0), (size.width() - 1, size.height() - 1)):
                    pixel = sample.pixelColor(x, y).getRgb()[:3]
                    assert max(abs(c - ref) for c, ref in zip(pixel, rgb)) < 6, (fmt, range_, pixel, rgb)
            frame_.setMirrored(True)
            assert scaler.image(frame_, QSize(37, 21)).isNull()
    scaler.close()

    w = Window("/usr/libexec")
    w.Open(["recordings"])
    page = w.pages["recordings"]
    home = Path(os.environ["HOME"])
    source = home / "check #1.mp4"
    art = home / "Badge # å [1].png"
    logo = Image.new("RGBA", (45, 40), (255, 0, 0, 255))
    logo.paste((0, 0, 0, 0), (0, 0, 8, 8))
    logo.save(art)

    def run(*args):
        return subprocess.check_output(args, stderr=subprocess.PIPE, timeout=25)

    run("ffmpeg", "-v", "error", "-threads", "1", "-filter_threads", "1", "-f", "lavfi", "-i",
        "nullsrc=s=320x180:r=20:d=4,geq=lum='if(lt(mod(X,8),4),36,210)':cb=128:cr=128",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:v", "libx264", "-threads", "2",
        "-c:a", "aac", source)
    original = hashlib.sha256(source.read_bytes()).hexdigest()

    def wait(predicate):
        until = time.monotonic() + 25
        while not predicate() and time.monotonic() < until:
            QTest.qWait(24)
        assert predicate(), (page.message.text(), page.player.errorString())

    page.open_file(source)
    wait(lambda: page.editor.isEnabled() and page.player.hasAudio())
    wait(lambda: page.picture.video.videoSink().videoFrame().isValid())
    page.seek.setValue(1800)
    failures = []

    def edit(which, callback):
        def handle():
            d = QApplication.activeModalWidget()
            try:
                assert isinstance(d, LayerDialog), d
                callback(d)
            except Exception as error:
                failures.append(error)
                if d:
                    d.reject()
        def open_layer():
            items = [a for a in page.layer_menu.actions() if not a.isSeparator()]
            action = items[which]
            page.layer_menu.close()
            QTimer.singleShot(100, handle)
            action.trigger()
        page.overlays.menu().popup(page.overlays.mapToGlobal(page.overlays.rect().bottomLeft()))
        QTest.qWait(60)
        open_layer()
        if failures:
            raise failures.pop()

    def set_range(d):
        d.start.setValue(1)
        d.end.setValue(3)
        assert d.buttons.button(QDialogButtonBox.Ok).isEnabled()

    def text(d):
        assert not d.buttons.button(QDialogButtonBox.Ok).isEnabled()
        d.text.setPlainText("Monet 50%\nO'Brien 标签")
        d.color.setCurrentIndex(1)
        set_range(d)
        box = d.canvas.box()
        QTest.mousePress(d.canvas, Qt.LeftButton, pos=box.center().toPoint())
        QTest.mouseRelease(d.canvas, Qt.LeftButton, pos=(box.center().toPoint() - box.topLeft().toPoint()) + d.canvas.area().topLeft().toPoint())
        x, y, width, height = d.layer.box
        assert y < .05 and x < .05
        corner = d.canvas.box().bottomRight().toPoint()
        QTest.mousePress(d.canvas, Qt.LeftButton, pos=corner)
        QTest.mouseRelease(d.canvas, Qt.LeftButton, pos=corner - (d.canvas.box().center()-d.canvas.box().topLeft()).toPoint()/2)
        assert d.layer.box[2] < width
        QTest.keyClick(d.canvas, Qt.Key_Right)
        QTest.keyClick(d.canvas, Qt.Key_Down, Qt.ShiftModifier)
        if os.environ.get("MONET_RECORDING_OVERLAY_QA"):
            d.grab().save(str(Path(os.environ["MONET_RECORDING_OVERLAY_QA"]) / "dialog.png"))
        d.buttons.button(QDialogButtonBox.Ok).click()
    edit(0, text)
    assert len(page.picture.layers) == 1
    original_caption = page.picture.layers[0].text

    def logo_dialog(d):
        def choose():
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, QFileDialog)
            dialog.setDirectory(str(art.parent))
            entry = dialog.findChild(QLineEdit, "fileNameEdit")
            entry.setText(art.name)
            QTest.keyClick(entry, Qt.Key_Return)
            if dialog.isVisible():
                dialog.reject()
        QTimer.singleShot(120, choose)
        d.pick.click()
        assert d.layer.text == art.name
        d.amount.setValue(86)
        set_range(d)
        d.accept()
    edit(1, logo_dialog)
    art.unlink()  # The editor owns the selected pixels during this edit.

    def blur(d):
        set_range(d)
        d.amount.setValue(100)
        d.accept()
    edit(2, blur)
    assert len(page.picture.layers) == 3
    def send_back(d):
        d.back.click()
        d.back.click()
        assert not d.back.isEnabled()
        d.accept()
    edit(5, send_back)
    assert [layer.kind for layer in page.picture.layers] == ["blur", "text", "image"]
    def bring_front(d):
        d.front.click()
        d.front.click()
        assert not d.front.isEnabled()
        d.accept()
    edit(3, bring_front)
    assert [layer.kind for layer in page.picture.layers] == ["text", "image", "blur"]
    def cancel(d):
        d.text.setPlainText("Cancelled edit")
        d.reject()
    edit(3, cancel)
    assert page.picture.layers[0].text == original_caption
    page.begin.setValue(.5)
    page.end.setValue(3.5)
    page.rate.setCurrentIndex(3)
    page.seek.setValue(1800)
    wait(lambda: abs(page.player.position()-1800) < 10)
    QTest.qWait(150)
    def preview_at(ms, active):
        page.seek.setValue(ms)
        wait(lambda: abs(page.picture.video.frame.startTime() / 1000 - ms) < 55)
        shot = page.picture.viewport().grab().toImage()
        point = page.picture.mapFromScene(255, 40) * shot.devicePixelRatio()
        color = shot.pixelColor(point)
        assert (color.red() - color.blue() > 125) if active else (abs(color.red() - color.blue()) < 12), color
        return shot

    preview_at(800, False)
    preview_at(3150, False)
    preview = preview_at(1800, True)
    target = Path(os.environ["MONET_RECORDING_OVERLAY_QA"]) if os.environ.get("MONET_RECORDING_OVERLAY_QA") else home
    preview.save(str(target / "playback.png"))
    w.grab().save(str(target / "editor.png"))

    def export(path):
        page.export_to(path)
        wait(lambda: page.exporter is None)
        assert path.is_file(), page.message.text()
        return json.loads(run("ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path))

    def frame(path, t):
        return Image.open(BytesIO(run("ffmpeg", "-v", "error", "-threads", "1", "-ss", str(t), "-i",
                                      path, "-frames:v", "1", "-threads", "1", "-c:v", "png", "-f", "image2pipe", "-"))).convert("RGB")

    for ext in ("mp4", "gif"):
        dest = home / ("out #1." + ext)
        info = export(dest)
        assert [(l.start, l.end) for l in page.picture.layers] == [(1000, 3000)] * 3
        assert 1.40 <= float(info["format"]["duration"]) <= 1.62, info
        assert len(info["streams"]) == (2 if ext == "mp4" else 1)
        before, during, after = [frame(dest, t) for t in (.10, .7, 1.4)]
        for k, sample in enumerate((before, during, after)):
            mean = ImageStat.Stat(sample.crop((242, 34, 270, 50))).mean
            sd = ImageStat.Stat(sample.crop((117, 68, 200, 101))).stddev[0]
            rgb = sample.crop((0, 0, 160, 37)).tobytes()
            yellow = sum(r > 130 and g > 120 and b < r * .79 for r, g, b in zip(rgb[::3], rgb[1::3], rgb[2::3]))
            if k == 1:
                assert mean[0] - mean[2] > 125 and sd < 20 and yellow > 15, (ext,k,mean,sd,yellow)
                sample.save(target / ("frame-" + ext + ".png"))
            else:
                assert abs(mean[0] - mean[2]) < 12 and sd > 50 and yellow < 5, (ext,k,mean,sd,yellow)
    # Cropping uses original picture coordinates for artwork and blur.
    page.crop_button.click()
    picture = page.picture
    start = picture.mapFromScene(160, 0)
    end = picture.mapFromScene(319, 179)
    QTest.mousePress(picture.viewport(), Qt.LeftButton, pos=start)
    QTest.mouseRelease(picture.viewport(), Qt.LeftButton, pos=end)
    assert .48 < picture.crop[0] < .52
    clipped = home / "Cropped.mp4"
    info = export(clipped)
    assert 152 <= info["streams"][0]["width"] <= 162
    rgb = frame(clipped, .7).getpixel((95, 40))
    assert rgb[0] - rgb[2] > 125, rgb
    picture.reset_crop()

    # The blur now straddles the logo's edge. Only a layer above the logo
    # should spread its red pixels outside the original image box.
    def overlap(d):
        area = d.canvas.area()
        point = (area.topLeft() + QPointF(.8 * area.width(), .19 * area.height())).toPoint()
        QTest.mouseClick(d.canvas, Qt.LeftButton, pos=point)
        d.accept()
    edit(5, overlap)
    for foreground in (True, False):
        if not foreground:
            edit(5, send_back)
        file = home / ("front.mp4" if foreground else "back.mp4")
        export(file)
        pix = frame(file, .7).getpixel((226, 40))
        preview = picture.viewport().grab().toImage()
        probe = preview.pixelColor(picture.mapFromScene(226, 40) * preview.devicePixelRatio())
        for diff in (pix[0] - pix[2], probe.red() - probe.blue()):
            assert diff > 25 if foreground else abs(diff) < 18, (foreground, pix, probe)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    edit(3, lambda d: d.remove())
    assert [layer.kind for layer in page.picture.layers] == ["text", "image"]
    page.open_file(source)
    wait(lambda: page.editor.isEnabled())
    assert not page.picture.layers
    # A phone clip can carry its orientation as stream metadata. Editing,
    # rendering and exporting it must use the same upright coordinate system.
    portrait = home / "Portrait.mp4"
    run("ffmpeg", "-v", "error", "-display_rotation:v:0", "90", "-i", source, "-c", "copy", portrait)
    page.open_file(portrait)
    wait(lambda: page.editor.isEnabled() and picture.sceneRect().size().toSize() == QSize(180, 320))
    logo.save(art)
    edit(1, logo_dialog)
    page.seek.setValue(1800)
    wait(lambda: abs(picture.video.frame.startTime() / 1000 - 1800) < 55)
    shot = picture.viewport().grab().toImage()
    upright = home / "Upright.mp4"
    info = export(upright)
    assert (info["streams"][0]["width"], info["streams"][0]["height"]) == (180, 320)
    encoded = frame(upright, 1.8)
    assert encoded.size == (180, 320)
    for x, y, on_logo in ((145, 60, True), (60, 60, False), (145, 260, False)):
        pixel = shot.pixelColor(picture.mapFromScene(x, y) * shot.devicePixelRatio())
        red, _, blue = encoded.getpixel((x, y))
        for difference in (pixel.red() - pixel.blue(), red - blue):
            assert difference > 125 if on_logo else abs(difference) < 18, (x, y, pixel, red, blue)
    page.crop_button.click()
    QTest.mousePress(picture.viewport(), Qt.LeftButton, pos=picture.mapFromScene(0, 0))
    QTest.mouseRelease(picture.viewport(), Qt.LeftButton, pos=picture.mapFromScene(179, 159))
    portrait_crop = home / "Portrait cropped.mp4"
    export(portrait_crop)
    top = frame(portrait_crop, 1.8)
    assert top.width >= 176 and 154 <= top.height <= 162
    red, _, blue = top.getpixel((145, 60))
    assert red - blue > 125
    w.close()
    print("Overlay controls, positioning, timing, image transparency and opacity, blur, cancel/remove, MP4/GIF frames, portrait preview and export, color conversion and source integrity passed.")


if __name__ == "__main__":
    if "--private" in sys.argv:
        assert os.environ["HOME"].startswith("/tmp/monet-tests-")
        faulthandler.dump_traceback_later(30)
        exercise()
        faulthandler.cancel_dump_traceback_later()
    else:
        with private_session() as env:
            env.update(LANGUAGE="en", LANG="C.UTF-8", QT_FFMPEG_DECODING_HW_DEVICE_TYPES=",")
            subprocess.run([sys.executable, "-B", __file__, "--private", *sys.argv[1:]], env=env, check=True, timeout=100)
