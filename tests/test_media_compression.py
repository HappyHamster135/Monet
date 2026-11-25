"""Exercise the media queue, its real encoders, cancellation and atomic publication."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
try:
    from PIL import Image
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from window import Window
    from picture_options import PictureOptions
except ImportError:
    Window = None


@unittest.skipUnless(Window and shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs desktop media tools")
class MediaCompression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.samples = tempfile.TemporaryDirectory()
        root = Path(cls.samples.name)
        cls.video = root / "Take #1.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=20:d=3",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "ffv1", "-threads", "1",
                        "-c:a", "flac", str(cls.video)], check=True)
        cls.picture = root / "Poster 100%.png"
        photo = Image.new("RGBA", (151, 101), (20, 60, 180, 0))
        photo.paste((130, 0, 70, 255), (10, 20, 60, 90))
        photo.save(cls.picture)
        cls.animation = root / "Loop.gif"
        Image.new("RGB", (100, 80), "orange").save(cls.animation, save_all=True, loop=2,
            append_images=[Image.new("RGB", (100, 80), "blue")], duration=[150, 350])

    @classmethod
    def tearDownClass(cls):
        cls.samples.cleanup()

    def setUp(self):
        self.output = tempfile.TemporaryDirectory()
        self.addCleanup(self.output.cleanup)
        self.folder = Path(self.output.name)
        self.window = Window("/usr/libexec")
        self.window.Open(["compress"])
        self.page = self.window.pages["compress"]
        self.addCleanup(self.window.close)
        self.addCleanup(self.page.close_jobs)

    def wait(self, check):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if check():
                return
            QTest.qWait(15)
        self.fail(self.page.message.text() or "Media operation timed out")

    def add_files(self, *paths):
        with patch.object(QFileDialog, "getOpenFileNames", return_value=(list(map(str, paths)), "")):
            self.page.add.click()
        self.wait(lambda: self.page.job is None)

    def save(self, target):
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "")):
            self.page.save.click()
        self.wait(lambda: not self.page.exporting)

    def test_presets_from_menu_survive_a_new_window_and_support_rename_update_delete(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QInputDialog
        from media_presets import defaults
        from actions import tr
        def in_test_store(menu):
            menu.config = QSettings(str(self.folder / "utilities.ini"), QSettings.IniFormat)
            menu.config.beginGroup("mediaPresets")
        def action(menu, label):
            if "“" in label:
                stem, rest = label.split("“", 1)
                name, end = rest.split("”", 1)
                label = tr(stem + "“%1”" + end).replace("%1", name)
            else:
                label = tr(label)
            menu.refresh()
            return next(a for a in menu.actions() if a.text() == label)
        p = self.page
        m = p.menu
        in_test_store(m)
        action(m, "Web picture").trigger()
        self.assertEqual((p.format.currentData(), p.edge.value(), p.name_pattern), (".jpg", 1600, "{name}-web"))
        p.name_pattern = "{name}-{index:03}"
        p.audio.setChecked(False)
        p.limited.setChecked(True)
        p.limit.setValue(1.25)
        p.picture_options.update(size="exact", width=720, height=480, framing="fill", text="Monet", background="black")
        with patch.object(QInputDialog, "getText", return_value=("Daily & photos", True)):
            action(m, "Save as new preset…").trigger()
        uid = m.key
        settings = p.recipe()
        other = Window("/usr/libexec")
        self.addCleanup(other.close)
        other.Open(["compress"])
        page = other.pages["compress"]
        menu = page.menu
        in_test_store(menu)
        self.assertEqual(page.recipe(), defaults())
        action(menu, "Daily && photos").trigger()
        self.assertEqual(page.recipe(), settings)
        self.assertTrue(action(menu, "Daily && photos").isChecked())
        page.edge.setValue(2000)
        self.assertFalse(action(menu, "Daily && photos").isChecked())
        with patch.object(QInputDialog, "getText", return_value=(tr("Web picture"), True)):
            action(menu, "Rename “Daily && photos”…").trigger()
        self.assertEqual(menu.saved()[uid]["name"], "Daily & photos")
        action(menu, "Update “Daily && photos”").trigger()
        self.assertEqual(m.saved()[uid]["settings"]["edge"], 2000)
        with patch.object(QInputDialog, "getText", return_value=("Newsletter", True)):
            action(menu, "Rename “Daily && photos”…").trigger()
        menu.config.setValue("broken", '{"name":"Old","settings":null}')
        self.assertEqual([x["name"] for x in menu.saved().values()], ["Newsletter"])
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            action(menu, "Delete “Newsletter”…").trigger()
        self.assertIn(uid, m.saved())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            action(menu, "Delete “Newsletter”…").trigger()
        self.assertFalse(m.saved())

    def test_names_dialog_shows_the_batch_and_validates_tokens(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from media_names import NameDialog
        self.add_files(self.picture, self.animation)
        def edit(d):
            d.pattern.setText("{index:03}-{name}.{ext}")
            self.assertEqual(d.table.topLevelItem(0).text(1), "001-Poster 100%.webp")
            self.assertEqual(d.table.topLevelItem(1).text(1), "002-Loop.gif")
            d.pattern.setText("{typo}")
            self.assertFalse(d.buttons.button(QDialogButtonBox.Ok).isEnabled())
            d.pattern.setText("release-")
            d.insert_field("index:03")
            self.assertEqual(d.pattern.text(), "release-{index:03}")
            self.assertTrue(d.buttons.button(QDialogButtonBox.Ok).isEnabled())
            return NameDialog.Accepted
        with patch.object(NameDialog, "exec", edit):
            self.page.edit_names()
        self.assertEqual(self.page.name_pattern, "release-{index:03}")

    def test_generated_names_use_final_sizes_and_never_replace_concurrent_files(self):
        from media_names import CopyNames
        noisy = self.folder / "large.png"
        Image.effect_noise((367, 281), 110).save(noisy)
        self.add_files(noisy, self.picture)
        p = self.page
        p.format.setCurrentIndex(p.format.findData(".png"))
        p.limited.setChecked(True)
        p.limit.setValue(.01)
        p.name_pattern = "{counter:03}-{width}x{height}.{format}"
        with patch.object(QFileDialog, "getExistingDirectory", return_value=str(self.folder)):
            p.save.click()
        self.wait(lambda: not p.exporting)
        self.assertEqual(p.saved, 2, p.message.text())
        for seq, entry in enumerate(p.entries.values(), 1):
            with Image.open(entry.output) as img:
                self.assertEqual(entry.output.name, f"{seq:03}-{img.width}x{img.height}.png")
                if seq == 1:
                    self.assertLess(img.width, 367)
            self.assertIn(entry.output.name, entry.row.text(2))
        items = list(p.entries.values())
        p.start_exports([(e, self.folder / "copy.png") for e in items], CopyNames("same"))
        existing = self.folder / "same.png"
        existing.write_bytes(b"another application created this file")
        self.wait(lambda: not p.exporting)
        self.assertEqual(existing.read_bytes(), b"another application created this file")
        self.assertEqual([e.output.name for e in items], ["same (2).png", "same (3).png"])

    def test_busy_destination_yields_to_cancel_before_publishing(self):
        from PySide6.QtCore import QTimer
        from media_names import CopyNames
        from recording_export import ExportFile
        self.add_files(self.picture)
        entry = next(iter(self.page.entries.values()))
        attempts = []
        def taken(output, name=None):
            attempts.append(name)
            if len(attempts) == 1:
                QTimer.singleShot(0, self.page.cancel_export)
            if len(attempts) > 128:
                self.fail("Publication blocked the event loop")
            raise FileExistsError(name)
        with patch.object(ExportFile, "publish", taken):
            self.page.start_exports([(entry, self.folder / "copy.webp")], CopyNames("taken"))
            self.wait(lambda: not self.page.exporting)
        self.assertGreater(len(attempts), 0)
        self.assertLessEqual(len(attempts), 32)
        self.assertIsNone(entry.output)
        self.assertIsNone(self.page.pending_publish)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.save(self.folder / "later.webp")
        self.assertTrue(entry.output.is_file())

    def test_names_are_visible_single_components_and_fit_utf8_file_limits(self):
        from datetime import datetime
        from media_names import CopyNames, copy_base
        now = datetime(2026, 4, 1, 17, 5, 7)
        def base(pattern, name="shot.png"):
            return copy_base(pattern, Path(name), 3, now, (50, 70), ".webp")
        self.assertEqual(base("{{album}}-{name}-{datetime}-{index:04}-{format}", "{time}.png"),
                         "{album}-{time}-20260401-170507-0003-webp")
        self.assertEqual(base("{name}.{ext}"), "shot")
        self.assertEqual(base(""), "shot-small")
        self.assertNotIn("/", base("../folder/{name}"))
        self.assertFalse(base("..").startswith("."))
        for bad in ("{index:08}", "{name.attr}", "{name!s}", "{date", "{width:02}"):
            with self.assertRaises(ValueError):
                base(bad)
        names = CopyNames("")
        self.assertEqual([names.candidate(n, ".png") for n in ("a", "a (2)", "a")], ["a.png", "a (2).png", "a (3).png"])
        choices = [names.candidate("🌷" * 100, ".webp") for _ in range(15)]
        self.assertEqual(len(set(choices)), 15)
        self.assertTrue(all(len(os.fsencode(n)) <= 255 for n in choices))

    def test_sharing_preset_removes_tags_and_file_options_preserve_dates_and_background(self):
        from media_presets import builtins
        picture = self.folder / "tagged.jpg"
        photo = Image.new("RGB", (90, 50), "green")
        exif = Image.Exif()
        exif[315] = "Camera owner"
        exif[274] = 6
        photo.save(picture, exif=exif)
        self.add_files(picture)
        self.page.apply_recipe(builtins()["web"][1])
        self.page.limited.setChecked(True)
        target = self.folder / "web.jpg"
        self.save(target)
        with Image.open(target) as output:
            self.assertEqual(output.size, (50, 90))
            self.assertFalse(output.getexif())
        self.page.picture_options = {"keep_date": True}
        self.save(self.folder / "original.jpg")
        self.assertEqual((self.folder / "original.jpg").read_bytes(), picture.read_bytes())
        self.assertEqual((self.folder / "original.jpg").stat().st_mtime_ns, picture.stat().st_mtime_ns)
        self.page.tree.selectAll()
        self.page.remove.click()
        self.add_files(self.picture)
        self.page.picture_options = {"background": "black"}
        self.page.format.setCurrentIndex(self.page.format.findData(".png"))
        self.save(self.folder / "black.png")
        with Image.open(self.folder / "black.png") as img:
            self.assertEqual(img.getpixel((0, 0)), (0, 0, 0))

    def test_mixed_batch_format_alpha_timing_size_limit_and_audio(self):
        self.add_files(self.picture, self.video, self.animation, self.picture)
        self.assertEqual(self.page.tree.topLevelItemCount(), 3)
        self.assertEqual([e.row.text(2) for e in self.page.entries.values()], ["WEBP", "MP4", "GIF"])
        self.page.edge.setValue(120)
        self.page.limited.setChecked(True)
        self.page.limit.setValue(.10)
        with patch.object(QFileDialog, "getExistingDirectory", return_value=str(self.folder)):
            self.page.save.click()
        self.wait(lambda: not self.page.exporting)
        self.assertEqual(self.page.saved, 3, self.page.message.text())
        for output in self.folder.iterdir():
            self.assertLessEqual(output.stat().st_size, 100000)
        photo, video, animation = [e.output for e in self.page.entries.values()]
        with Image.open(photo) as result:
            self.assertEqual(result.size, (120, 80))
            self.assertEqual(result.getpixel((0, 0))[-1], 0)
        with Image.open(animation) as result:
            self.assertEqual(result.n_frames, 2)
            self.assertEqual(result.info["loop"], 2)
            self.assertEqual(result.info["duration"], 150)
            result.seek(1)
            self.assertEqual(result.info["duration"], 350)
        probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height",
                                         "-of", "json", str(video)], text=True)
        streams = json.loads(probe)["streams"]
        self.assertEqual([s["codec_name"] for s in streams], ["h264", "aac"])
        self.assertEqual(streams[0]["width"], 120)

    def test_generous_limit_keeps_compatible_video_and_honors_mute(self):
        self.add_files(self.video)
        reference = self.folder / "quality.mp4"
        self.save(reference)
        original = reference.read_bytes()
        self.page.limited.setChecked(True)
        self.page.limit.setValue(5)
        converted = self.folder / "capped.mp4"
        self.save(converted)
        # An under-limit lossless input uses the selected quality when converting.
        self.assertEqual(converted.stat().st_size, len(original))
        self.page.tree.selectAll()
        self.page.remove.click()
        self.add_files(reference)
        compatible = self.folder / "unchanged.mp4"
        self.save(compatible)
        self.assertEqual(compatible.read_bytes(), original)
        self.page.audio.setChecked(False)
        muted = self.folder / "muted.mp4"
        self.save(muted)
        self.assertLess(muted.stat().st_size, len(original))
        self.assertEqual(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a",
                         "-show_entries", "stream=index", "-of", "csv=p=0", str(muted)]), b"")
        self.assertEqual(reference.read_bytes(), original)

    def test_exact_size_watermark_preview_and_export_agree(self):
        source = self.folder / "blue.png"
        logo = self.folder / "logo.png"
        Image.new("RGB", (40, 20), "blue").save(source)
        Image.new("RGBA", (7, 7), (255, 0, 0, 255)).save(logo)
        self.add_files(source)
        self.page.format.setCurrentIndex(self.page.format.findData(".png"))
        captured = []
        def edit(dialog):
            dialog.show()
            dialog.size_mode.setCurrentIndex(dialog.size_mode.findData("exact"))
            dialog.width_px.setValue(64)
            dialog.height_px.setValue(64)
            dialog.set_logo(str(logo))
            dialog.position.setCurrentIndex(dialog.position.findData("top-left"))
            dialog.opacity.setValue(100)
            dialog.margin.setValue(1)
            dialog.scale.setValue(10)
            dialog.preview_button.click()
            self.wait(lambda: dialog.job is None)
            rendered = dialog.sample.pixmap().toImage()
            pixel = round(rendered.width() * 3 / 64)
            captured.append(rendered.pixelColor(pixel, pixel).getRgb())
            dialog.accept()
            return dialog.result()
        with patch.object(PictureOptions, "exec", edit):
            self.page.edit_pictures.click()
        self.assertEqual(captured, [(255, 0, 0, 255)])
        self.assertFalse(self.page.edge.isEnabled())
        self.page.limited.setChecked(True)
        self.save(self.folder / "marked.png")
        with Image.open(self.folder / "marked.png") as output:
            self.assertEqual(output.size, (64, 64))
            self.assertEqual(output.getpixel((3, 3)), captured[0])
            self.assertEqual(output.getpixel((60, 3))[-1], 0)
            self.assertEqual(output.getpixel((30, 30)), (0, 0, 255, 255))
        settings = dict(self.page.picture_options)
        def reset_but_cancel(dialog):
            dialog.reset()
            self.assertEqual(dialog.values(), {})
            return PictureOptions.Rejected
        with patch.object(PictureOptions, "exec", reset_but_cancel):
            self.page.edit_pictures.click()
        self.assertEqual(self.page.picture_options, settings)
        self.page.format.setCurrentIndex(self.page.format.findData(".mp4"))
        self.assertTrue(self.page.edit_pictures.isHidden())
        self.assertTrue(self.page.edge.isEnabled())

    def test_svg_logo_with_text_renders_in_the_background_worker(self):
        logo = self.folder / "brand.svg"
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="50" height="20">'
                        '<rect width="50" height="20" fill="red"/><text x="3" y="15">Monet</text></svg>')
        self.add_files(self.picture)
        self.page.picture_options = dict(logo=str(logo), position="top-left", margin=0, opacity=100, scale=40)
        self.page.format.setCurrentIndex(self.page.format.findData(".png"))
        target = self.folder / "branded.png"
        self.save(target)
        self.assertEqual(self.page.saved, 1, self.page.message.text())
        with Image.open(target) as marked:
            self.assertEqual(marked.getpixel((1, 1)), (255, 0, 0, 255))
            self.assertEqual(marked.getpixel((135, 95))[-1], 0)

    def test_fixed_size_does_not_shrink_under_an_impossible_limit(self):
        src = self.folder / "noise.png"
        Image.effect_noise((300, 200), 120).save(src)
        self.add_files(src)
        self.page.picture_options = dict(size="width", width=300)
        self.page.format.setCurrentIndex(self.page.format.findData(".png"))
        self.page.limited.setChecked(True)
        self.page.limit.setValue(.01)
        target = self.folder / "fixed.png"
        self.save(target)
        self.assertEqual(self.page.failed, 1)
        self.assertFalse(target.exists())
        self.page.limited.setChecked(False)
        self.page.picture_options = dict(size="height", height=100, text="Monet", position="center", opacity=90)
        self.save(target)
        with Image.open(target) as output:
            self.assertEqual(output.size, (150, 100))

    def test_crop_stretch_and_text_watermark(self):
        from PIL import ImageChops
        from picture_edit import frame_picture, picture_geometry, watermark
        pic = Image.new("RGB", (60, 20), "blue")
        pic.paste("red", (20, 0, 40, 20))
        cropped = frame_picture(pic, (20, 20), dict(size="exact", framing="fill"))
        stretched = frame_picture(pic, (20, 20), dict(size="exact", framing="stretch"))
        self.assertEqual(cropped.getpixel((2, 2)), (255, 0, 0))
        self.assertEqual(stretched.getpixel((2, 2)), (0, 0, 255))
        blank = Image.new("RGB", (200, 80), "navy")
        marked = watermark(blank, dict(text="Monét", position="bottom-left", margin=3, scale=28, opacity=65), 1)
        box = ImageChops.difference(blank, marked.convert("RGB")).getbbox()
        self.assertIsNotNone(box)
        self.assertGreaterEqual(box[0], 3)
        self.assertLessEqual(box[2], 59)
        self.assertGreater(box[1], 25)
        with self.assertRaises(ValueError):
            picture_geometry((300, 120), dict(size="exact", width=10000, height=10000), 0)

    def test_collision_during_export_preserves_file_and_retry_works(self):
        self.add_files(self.video)
        target = self.folder / "sharing.MP4"
        self.page.audio.setChecked(False)
        entry = next(iter(self.page.entries.values()))
        self.page.start_exports([(entry, target)])
        target.write_bytes(b"another copy won the name")
        self.wait(lambda: not self.page.exporting)
        self.assertEqual(target.read_bytes(), b"another copy won the name")
        self.assertIsNone(entry.output)
        self.assertEqual(self.page.failed, 1)
        self.assertEqual(list(self.folder.iterdir()), [target])
        new_target = self.folder / "retry.MP4"
        self.save(new_target)
        self.assertEqual(entry.output, new_target)
        self.assertEqual(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a",
                         "-show_entries", "stream=index", "-of", "csv=p=0", str(new_target)]), b"")

    def test_copy_names_and_exif_orientation_and_failed_input(self):
        dest = self.folder / "converted"
        dest.mkdir()
        bad = self.folder / "notes.txt"
        bad.write_text("This is not a media file.")
        files = []
        for group in ("one", "two"):
            folder = self.folder / group
            folder.mkdir()
            file = folder / "odd.jpg"
            photo = Image.new("RGB", (201, 133), "green")
            exif = Image.Exif()
            exif[274] = 6
            photo.save(file, exif=exif)
            files.append(file)
        self.add_files(bad, *files)
        self.assertIsNone(self.page.entries[str(bad)].info)
        self.page.format.setCurrentIndex(self.page.format.findData(".png"))
        (dest / "odd-small.png").write_bytes(b"existing")
        with patch.object(QFileDialog, "getExistingDirectory", return_value=str(dest)):
            self.page.save.click()
        self.wait(lambda: not self.page.exporting)
        self.assertEqual((dest / "odd-small.png").read_bytes(), b"existing")
        self.assertEqual({self.page.entries[str(p)].output.name for p in files}, {"odd-small (2).png", "odd-small (3).png"})
        for path in files:
            with Image.open(self.page.entries[str(path)].output) as im:
                self.assertEqual(im.size, (133, 201))

    def test_impossible_video_limit_preserves_original_and_cleans_temporary_output(self):
        self.add_files(self.video)
        self.page.limited.setChecked(True)
        self.page.limit.setValue(.01)
        target = self.folder / "tiny.mp4"
        before = self.video.read_bytes()
        self.save(target)
        self.assertEqual(self.page.failed, 1)
        self.assertIsNone(next(iter(self.page.entries.values())).output)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.video.read_bytes(), before)

    def test_opaque_jpeg_alias_and_single_page_pdf(self):
        self.add_files(self.picture)
        self.page.format.setCurrentIndex(self.page.format.findData(".jpg"))
        target = self.folder / "picture.jpeg"
        self.save(target)
        with Image.open(target) as picture:
            self.assertEqual(picture.size, (151, 101))
            self.assertTrue(all(v > 245 for v in picture.getpixel((0, 0))))
        self.page.format.setCurrentIndex(self.page.format.findData(".pdf"))
        pdf = self.folder / "paper.pdf"
        self.save(pdf)
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
        if shutil.which("pdfinfo"):
            metadata = subprocess.check_output(["pdfinfo", str(pdf)], env=dict(os.environ, LC_ALL="C"), text=True)
            self.assertRegex(metadata, r"Pages:\s+1\b")

    def test_changed_source_is_reinspected_before_retry(self):
        source = self.folder / "download.png"
        shutil.copyfile(self.picture, source)
        self.add_files(source)
        entry = self.page.entries[str(source)]
        self.assertEqual(entry.info["kind"], "image")
        shutil.copyfile(self.animation, source)
        self.save(self.folder / "first.webp")
        self.assertFalse((self.folder / "first.webp").exists())
        self.wait(lambda: entry.inspected and self.page.job is None)
        self.assertEqual(entry.info["kind"], "animation")
        self.save(self.folder / "second.gif")
        with Image.open(entry.output) as result:
            self.assertEqual(result.n_frames, 2)

    def test_cancel_during_encoder_stops_children_and_leaves_no_partial_copy(self):
        self.add_files(self.video, self.picture)
        entries = list(self.page.entries.values())
        target = self.folder / "cancel.mp4"
        self.page.start_exports([(entries[0], target), (entries[1], self.folder / "later.webp")])
        job = self.page.job
        def encoding():
            pid = job.processId()
            children = Path(f"/proc/{pid}/task/{pid}/children")
            if not children.exists():
                return False
            for c in children.read_text().split():
                try:
                    if Path(f"/proc/{c}/comm").read_text().strip() == "ffmpeg":
                        return True
                except FileNotFoundError:
                    pass
            return False
        self.wait(encoding)
        group = job.processId()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            self.assertFalse(self.window.close())
        self.page.cancel.click()
        self.wait(lambda: not self.page.exporting)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertTrue(all(entry.output is None for entry in entries))
        self.assertTrue(self.page.save.isEnabled())
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return
        # A killed encoder may briefly await its parent's or init's reap.
        for proc in Path("/proc").glob("[0-9]*/stat"):
            try:
                rest = proc.read_text().rsplit(")", 1)[1].split()
            except (OSError, IndexError):
                continue
            if int(rest[2]) == group:
                self.assertEqual(rest[0], "Z")
