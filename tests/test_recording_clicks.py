"""The recorder groups captured clicks and remembers edits against the original video."""
from pathlib import Path
import os
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
try:
    from recording_clicks import ClickGroups, TakeZooms, suggestions
except ModuleNotFoundError as error:
    if not str(error.name).startswith("PySide6"):
        raise
    raise unittest.SkipTest("Qt for Python is required") from error


class RecordingClicks(unittest.TestCase):
    def test_repeated_clicks_hold_one_focus_and_quick_jumps_do_not_flicker(self):
        groups = ClickGroups()
        for event in ((320, .1, .2), (520, .15, .24), (550, .85, .85),
                      (1700, .9, .9), (1300, .4, .4), (2100, -1, .5)):
            groups.add(*event)
        self.assertEqual(groups.items, [(320, 520, .1, .2), (1700, 1700, .9, .9)])
        first, second = suggestions(groups.items, 3300)
        self.assertEqual((first.start, first.end, second.start, second.end), (0, 1110, 1300, 3300))
        self.assertEqual((second.x, second.y), (.9, .9))

    def test_tray_stop_and_invalid_coordinates_do_not_add_zooms(self):
        groups = ClickGroups()
        groups.add(100, float("nan"), 0)
        groups.add(300, 0, .99)
        groups.add(3890, .7, .99)
        self.assertEqual(len(suggestions(groups.items, 4000)), 1)
        self.assertEqual(suggestions(groups.items, 360), [])

    def test_cleared_edits_follow_renames_and_never_follow_replaced_video(self):
        with TemporaryDirectory() as temp, patch.dict(os.environ, {"XDG_STATE_HOME": temp}):
            video = Path(temp) / "video.webm"
            video.write_bytes(b"first video")
            saved = TakeZooms(video)
            saved.groups = [(410, 700, .25, .75)]
            saved.edited = []
            self.assertTrue(saved.save())
            renamed = video.rename(video.with_name("renamed.webm"))
            again = TakeZooms(renamed)
            self.assertTrue(again.read())
            self.assertEqual(again.edited, [])
            self.assertEqual(suggestions(again.groups, 2400), suggestions(saved.groups, 2400))
            self.assertTrue(again.path.stat().st_mode & 0o077 == 0)
            video.write_bytes(b"other video")
            video.replace(renamed)
            self.assertFalse(TakeZooms(renamed).read())


if __name__ == "__main__":
    unittest.main()
