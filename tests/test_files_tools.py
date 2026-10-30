"""Files discovery is bounded, literal and read-only; capacity follows the actual mount."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
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
        info = os.statvfs(self.root)
        result = self.f.drive_space(self.root)
        self.assertEqual(result["total"], info.f_blocks * info.f_frsize)
        self.assertEqual(result["free"], info.f_bavail * info.f_frsize)
        self.assertEqual(result["total"], result["used"] + result["free"] + result["reserved"])
        with self.assertRaises(FileNotFoundError): self.f.drive_space(self.root / "gone")


if __name__ == "__main__": unittest.main()
