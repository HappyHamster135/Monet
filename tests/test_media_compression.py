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
