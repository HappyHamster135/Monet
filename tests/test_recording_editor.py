"""Recording edits publish a complete new file and carry the selection into both encoders."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULE))
from recording_export import ExportFile, export_command


class RecordingExport(unittest.TestCase):
    def test_trim_crop_speed_and_sound_use_the_same_edit_for_mp4_and_gif(self):
        source = Path("/example/my take #2.webm")
        for extension in ("mp4", "gif"):
            cmd = export_command(source, Path("out." + extension), 250, 2450, 2, (.25, 0, .5, 1), False)
            self.assertEqual(cmd[cmd.index("-i")+1], str(source))
            self.assertEqual(cmd[cmd.index("-ss")+1], "0.250")
            self.assertEqual(cmd[cmd.index("-t")+1], "2.200")
            graph = cmd[cmd.index("-vf" if extension == "mp4" else "-filter_complex")+1]
            self.assertIn("crop=", graph)
            self.assertIn("setpts=PTS/2", graph)
            if extension == "mp4":
                self.assertIn("atempo=2", cmd)
                self.assertIn("0:a:0?", cmd)
            else:
                self.assertIn("palettegen=stats_mode=single", graph)
                self.assertIn("-an", cmd)

    def test_silent_export_and_invalid_edits(self):
        self.assertIn("-an", export_command(Path("a"), Path("b.mp4"), 0, 1000, 1, None, True))
        for end, speed, crop in [(0, 1, None), (1, 0, None), (1, 1, (.8, .2, .3, .1))]:
            with self.assertRaises(ValueError):
                export_command(Path("a"), Path("b.mp4"), 0, end, speed, crop, False)

    def test_name_claimed_during_export_and_dangling_link_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "my video.mp4")
            output = ExportFile(path)
            output.file.write_bytes(b"encoded")
            path.write_bytes(b"other export")
            with self.assertRaises(FileExistsError):
                output.publish()
            output.close()
            self.assertEqual(path.read_bytes(), b"other export")
            path.unlink()
            path.symlink_to(path.with_name("missing"))
            with self.assertRaises(FileExistsError):
                ExportFile(path)
            self.assertTrue(path.is_symlink())

    def test_cancel_and_publish_never_expose_an_incomplete_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "result.gif")
            cancelled = ExportFile(path)
            cancelled.file.write_bytes(b"partial")
            cancelled.close()
            self.assertEqual(list(path.parent.iterdir()), [])
            complete = ExportFile(path)
            complete.file.write_bytes(b"complete")
            complete.publish()
            complete.close()
            self.assertEqual(path.read_bytes(), b"complete")
