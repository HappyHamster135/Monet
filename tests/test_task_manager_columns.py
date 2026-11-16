"""Task Manager's Graphics column (0.9.8-6) also reaches the pages someone already had their own
copy of: KDE's Task Manager keeps a page of its own once anything on it changes, and from then
on never reads Monet's page with the new column."""
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]

OLD = """[page]
Title=Applications

[Face-1][FaceConfig][General]
sortedColumns=appName,usage,vmPSS,netInbound,netOutbound
columnWidths=0.4,0.15,0.15,0.15,0.15
columnDisplay={"appName":"text","usage":"lineScaled","vmPSS":"text","netInbound":"text","netOutbound":"text"}
sortColumn=vmPSS
"""


class GraphicsColumn(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.q = quick_helper()

    def group(self, name):
        lines = (self.folder / name).read_text().splitlines()
        return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("Title"))

    def test_an_old_copy_gets_graphics_after_memory_and_keeps_the_rest(self):
        (self.folder / "monet-applications.page").write_text(OLD)
        self.assertEqual(self.q.task_manager_graphics(self.folder), ["monet-applications.page"])
        page = self.group("monet-applications.page")
        self.assertEqual(page["sortedColumns"].split(","), ["appName", "usage", "vmPSS", "monetGraphics", "netInbound", "netOutbound"])
        widths = [float(w) for w in page["columnWidths"].split(",")]
        self.assertEqual(len(widths), 6)
        self.assertAlmostEqual(sum(widths), 1.0, places=2)   # the same room, shared
        self.assertGreater(widths[0], widths[1])             # names stay the widest
        self.assertEqual(json.loads(page["columnDisplay"])["monetGraphics"], "text")
        self.assertEqual(page["sortColumn"], "vmPSS")         # their own choices stay
        self.assertTrue((self.folder / "monet-applications.page").read_text().startswith("[page]\nTitle=Applications\n"))
        # Done once: nothing more the second time.
        self.assertEqual(self.q.task_manager_graphics(self.folder), [])

    def test_copies_with_it_or_without_a_memory_column_and_other_pages_stay_as_they_are(self):
        has = OLD.replace("vmPSS,", "vmPSS,monetGraphics,")
        (self.folder / "monet-processes.page").write_text(has)
        (self.folder / "monet-applications.page").write_text(OLD.replace("vmPSS", "memory"))
        (self.folder / "overview.page").write_text(OLD)
        self.assertEqual(self.q.task_manager_graphics(self.folder), [])
        self.assertEqual((self.folder / "monet-processes.page").read_text(), has)
        self.assertEqual((self.folder / "overview.page").read_text(), OLD)

    def test_a_missing_folder_or_odd_values_are_fine(self):
        self.assertEqual(self.q.task_manager_graphics(self.folder / "absent"), [])
        odd = OLD.replace("columnWidths=0.4,0.15,0.15,0.15,0.15", "columnWidths=wide").replace(
            'columnDisplay={"appName"', "columnDisplay=not json{")
        (self.folder / "monet-processes.page").write_text(odd)
        self.assertEqual(self.q.task_manager_graphics(self.folder), ["monet-processes.page"])
        page = self.group("monet-processes.page")
        self.assertIn("monetGraphics", page["sortedColumns"])
        self.assertEqual(page["columnWidths"], "wide")

    def test_monet_look_runs_it_once_and_monets_own_pages_have_it(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('graphics_column="$CONFIG/monet/task-manager-graphics-v1"', look)
        self.assertIn('"$LIBEXECDIR/monet-quick" task-manager-graphics', look)
        for name in ("monet-applications.page", "monet-processes.page"):
            self.assertIn("monetGraphics", (ROOT / "linux/share/plasma-systemmonitor" / name).read_text())


if __name__ == "__main__":
    unittest.main()
