"""Files discovery is bounded, literal and read-only; capacity follows the actual mount."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def files_tools():
    loader = importlib.machinery.SourceFileLoader("monet_files_tools", str(ROOT / "linux/libexec/monet-files-tools"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


class FilesTools(unittest.TestCase):
    def setUp(self):
        self.f = files_tools()
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def executable(self, name, header=b"#!/bin/sh\n", mode=0o700):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(header); path.chmod(mode)
        return path

    def test_extract_launcher_and_desktop_name_without_running_downloads(self):
        wrapper = self.executable("package/usr/lib/app/launcher")
        self.executable("package/usr/lib/app/Example", b"\x7fELF")
        link = self.root / "package/usr/bin/example"; link.parent.mkdir(parents=True)
        link.symlink_to("../lib/app/launcher")
        manifest = self.root / "package/usr/share/applications/example.desktop"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('[Desktop Entry]\nType=Application\nName=Example\nExec=example %U\nMimeType=text/plain;\n')
        with patch.object(self.f.subprocess, "Popen") as execute:
            result = self.f.scan_apps(self.root / "package")
            execute.assert_not_called()
        self.assertEqual(result["items"][0]["path"], str(link))
        self.assertEqual(result["items"][0]["name"], "Example")
        self.assertEqual(sum(item["recommended"] for item in result["items"]), 1)
        self.assertNotIn(str(wrapper), [item["path"] for item in result["items"]])

    def test_links_cannot_escape_or_loop_and_special_files_are_not_read(self):
        self.executable("outside/app")
        folder = self.root / "download"; folder.mkdir()
        (folder / "escape").symlink_to(self.root / "outside/app")
        (folder / "loop").symlink_to(folder, target_is_directory=True)
        os.mkfifo(folder / "pipe"); (folder / "pipe").chmod(0o700)
        (folder / "broken").symlink_to("missing")
        self.assertEqual(self.f.scan_apps(folder)["items"], [])

    def test_windows_and_nonexecutable_appimage_have_explicit_types(self):
        self.executable("Setup.EXE", b"MZexample", 0o600)
        self.executable("Setup.msi", b"\xd0\xcf\x11\xe0example", 0o600)
        self.executable("Paint.AppImage", b"\x7fELF", 0o600)
        self.executable("fake.exe", b"not a program", 0o600)
        items = {Path(item["path"]).name: item["kind"] for item in self.f.scan_apps(self.root)["items"]}
        self.assertEqual(items, {"Setup.EXE": "windows", "Setup.msi": "windows", "Paint.AppImage": "permission"})

    def test_literal_names_are_preserved_and_desktop_commands_are_not_imported(self):
        app = self.executable('An app %U; $(touch NO) `echo X` å')
        (self.root / "evil.desktop").write_text('[Desktop Entry]\nType=Application\nName=Other\nExec=sh -c "touch NO"\n')
        items = self.f.scan_apps(self.root)["items"]
        self.assertEqual(items[0]["path"], str(app))
        self.assertFalse((self.root / "NO").exists())
        self.assertEqual(items[0]["kind"], "native")

    def test_size_depth_and_time_budgets_report_incomplete_search(self):
        for i in range(30): self.executable(f"file{i}")
        self.executable("a/b/deep")
        limited = self.f.scan_apps(self.root, max_entries=8)
        self.assertLessEqual(limited["visited"], 8); self.assertTrue(limited["limited"])
        limited = self.f.scan_apps(self.root, max_depth=0)
        self.assertTrue(limited["limited"])
        self.assertNotIn("deep", [item["name"] for item in limited["items"]])
        self.assertTrue(self.f.scan_apps(self.root, seconds=0)["limited"])

    def test_capacity_uses_available_blocks_and_reports_reserved_space(self):
        # Two live reads race concurrent downloads/builds on the same filesystem.
        # A fixed snapshot also exercises reserved blocks and differing block sizes.
        info = SimpleNamespace(f_blocks=1000, f_bfree=300, f_bavail=250,
                               f_frsize=4096, f_bsize=8192, f_flag=os.ST_RDONLY)
        with patch.object(self.f.os, 'statvfs', return_value=info) as probe:
            result = self.f.drive_space(self.root)
        probe.assert_called_once_with(self.root.resolve())
        self.assertEqual(result["total"], 4096000)
        self.assertEqual(result["free"], 1024000)
        self.assertEqual(result["reserved"], 204800)
        self.assertTrue(result['readonly'])
        self.assertEqual(result["total"], result["used"] + result["free"] + result["reserved"])
        actual = self.f.drive_space(self.root)
        self.assertGreater(actual['total'], 0)
        self.assertEqual(actual['total'], actual['used'] + actual['free'] + actual['reserved'])
        with self.assertRaises(FileNotFoundError): self.f.drive_space(self.root / "gone")


try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLabel, QLineEdit, QPushButton
    from PySide6.QtTest import QTest
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication, "native Qt shortcut dialog")
class ShortcutDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from tests.test_look import quick_helper
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.program = self.root / "Example"; self.program.write_text("#!/bin/sh\nexit 0\n"); self.program.chmod(0o700)
        self.tool = files_tools(); self.quick = quick_helper()
        self.quick.DATA_HOME = self.root / "data"
        with patch.object(self.tool, "quick_helper", return_value=self.quick):
            self.dialog = self.tool.make_shortcut_dialog(self.program)
        self.addCleanup(self.dialog.close)
        self.dialog.show(); QTest.qWait(20)
        self.name = self.dialog.findChild(QLineEdit, "shortcutName")
        self.options = self.dialog.findChild(QLineEdit, "shortcutArguments")
        self.advanced = self.dialog.findChild(QCheckBox, "launchOptions")
        self.save = self.dialog.findChild(QPushButton, "saveShortcut")

    def test_cancel_and_invalid_options_do_not_write_then_keyboard_retry_saves(self):
        self.assertFalse(self.options.isVisible())
        self.advanced.setChecked(True)
        self.assertTrue(self.options.isVisible())
        self.options.setText('"unfinished')
        self.save.click()
        self.assertTrue(self.dialog.isVisible())
        self.assertTrue(self.dialog.findChild(QLabel, "shortcutError").isVisible())
        self.assertFalse(self.quick.DATA_HOME.exists())
        self.name.setText("Example profile")
        self.options.setText('--profile "Personal profile"')
        self.options.setFocus()
        with patch.object(self.quick.subprocess, "Popen") as launch:
            QTest.keyClick(self.options, Qt.Key_Return)
            launch.assert_not_called()
        self.assertEqual(self.dialog.result(), QDialog.Accepted)
        entry, = (self.quick.DATA_HOME / "applications").glob("*.desktop")
        self.assertIn("Name=Example profile", entry.read_text())
        self.assertEqual(self.dialog.saved_name, "Example profile")

    def test_hiding_options_excludes_old_text_and_cancel_creates_nothing(self):
        self.dialog.reject()
        self.assertFalse(self.quick.DATA_HOME.exists())
        self.dialog.show()
        self.advanced.setChecked(True); self.options.setText('"unfinished')
        self.advanced.setChecked(False); self.save.click()
        self.assertEqual(self.dialog.result(), QDialog.Accepted)
        entry, = (self.quick.DATA_HOME / "applications").glob("*.desktop")
        self.assertEqual(self.quick.desktop_entry(entry.read_text())["Exec"].count("native-run"), 1)
        self.assertNotIn('unfinished', entry.read_text())


if __name__ == "__main__": unittest.main()
