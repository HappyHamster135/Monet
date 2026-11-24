"""Task Manager's Graphics column (0.9.8-6) also reaches the pages someone already had their own
copy of: KDE's Task Manager keeps a page of its own once anything on it changes, and from then
on never reads Monet's page with the new column."""
import json
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree
import tempfile
import unittest

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]

OLD = """[page]
Title=Applications

[Face-1][org.monet.applications][General]
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

    def test_current_memory_id_and_unrelated_faces(self):
        active = OLD.replace("vmPSS", "memory")
        ignored = OLD.replace("[org.monet.applications]", "[FaceConfig]")
        page = self.folder / "monet-applications.page"
        page.write_text(ignored + active)
        self.assertEqual(self.q.task_manager_graphics(self.folder), [page.name])
        self.assertTrue(page.read_text().startswith(ignored))
        self.assertIn("usage,memory,monetGraphics,netInbound", page.read_text()[len(ignored):])
        self.assertEqual(self.q.task_manager_graphics(self.folder), [])

    def test_widths_only_keep_the_resized_columns_aligned(self):
        page = self.folder / "monet-applications.page"
        page.write_text("[Face-1][org.monet.applications][General]\ncolumnWidths=0.40,0.10,0.1,0.1,0.1,0.1,0.1\n")
        self.assertEqual(self.q.task_manager_graphics(self.folder), [page.name])
        values = self.group(page.name)
        self.assertNotIn("sortedColumns", values)
        widths = [float(w) for w in values["columnWidths"].split(",")]
        self.assertEqual(len(widths), 8)
        self.assertAlmostEqual(widths[2], widths[3])
        self.assertAlmostEqual(widths[0] / widths[1], 4, places=1)
        self.assertEqual(self.q.task_manager_graphics(self.folder), [])

    def test_a_missing_folder_or_odd_values_are_fine(self):
        self.assertEqual(self.q.task_manager_graphics(self.folder / "absent"), [])
        odd = OLD.replace("columnWidths=0.4,0.15,0.15,0.15,0.15", "columnWidths=wide").replace(
            'columnDisplay={"appName"', "columnDisplay=not json{")
        (self.folder / "monet-processes.page").write_text(odd)
        self.assertEqual(self.q.task_manager_graphics(self.folder), ["monet-processes.page"])
        page = self.group("monet-processes.page")
        self.assertIn("monetGraphics", page["sortedColumns"])
        self.assertEqual(page["columnWidths"], "wide")

    def test_page_and_face_defaults_match_the_group_kde_loads(self):
        for name in ("applications", "processes"):
            face = f"org.monet.{name}"
            share = ROOT / "linux/share"
            page = (share / "plasma-systemmonitor" / f"monet-{name}.page").read_text()
            group = page.split(f"][{face}][General]\n", 1)[1].split("\n[", 1)[0]
            values = dict(line.split("=", 1) for line in group.splitlines() if "=" in line)
            xml = ElementTree.parse(share / "ksysguard/sensorfaces" / face / "contents/config/main.xml")
            defaults = {e.get("name"): e.findtext("{*}default") for e in xml.findall(".//{*}entry")}
            self.assertEqual(values["sortedColumns"].split(",")[1:4], ["usage", "memory", "monetGraphics"])
            self.assertEqual(values["sortedColumns"], defaults["sortedColumns"])
            self.assertEqual(values["columnWidths"], defaults["columnWidths"])
            self.assertEqual(json.loads(values["columnDisplay"]), json.loads(defaults["columnDisplay"]))

    def test_upgrade_hides_the_shortcut_once_and_keeps_a_custom_dashboard(self):
        settings = {"hiddenPages": "my.page", "startPage": "monet-graphics.page",
                    "lastVisitedPage": "monet-graphics.page", "pageOrder": "my.page,monet-processes.page"}
        def write(file, group, key, value):
            settings[key] = value
            return True
        with patch.object(self.q, "CONFIG", self.folder / "config"), patch.object(self.q, "DATA_HOME", self.folder), \
             patch.object(self.q, "task_manager_reset", return_value={"ok": True}), \
             patch.object(self.q, "kread", side_effect=lambda file, group, key: settings.get(key, "")), \
             patch.object(self.q, "kwrite", side_effect=write):
            self.assertTrue(self.q.prepare_task_manager()["ok"])
            self.assertEqual(settings["hiddenPages"], "my.page,monet-graphics.page")
            self.assertEqual(settings["startPage"], "monet-processes.page")
            self.assertEqual(settings["lastVisitedPage"], "monet-processes.page")
            settings["hiddenPages"] = "my.page"
            self.q.prepare_task_manager()
            self.assertEqual(settings["hiddenPages"], "my.page")
            (self.q.CONFIG / "monet/task-manager-graphics-v2").unlink()
            pages = self.folder / "plasma-systemmonitor"
            pages.mkdir()
            (pages / "monet-graphics.page").touch()
            self.q.prepare_task_manager()
            self.assertEqual(settings["hiddenPages"], "my.page")


if __name__ == "__main__":
    unittest.main()
