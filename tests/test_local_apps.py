"""Local app shortcuts never execute downloads while registering or interpret file names."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_look import ROOT, quick_helper


class LocalApps(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.apps = self.root / "applications"
        self.program = self.root / 'App %U; $(touch NO) `echo X` å'
        self.program.write_text('#!/bin/sh\nprintf done\n')
        self.program.chmod(0o700)

    def test_registers_literal_path_without_running_or_claiming_file_types(self):
        with patch.object(self.q.subprocess, "Popen") as launch:
            entry = self.q.native_shortcut(self.program, "My app", self.apps)
            launch.assert_not_called()
        data = self.q.desktop_entry(entry.read_text())
        token = data["Exec"].split()[-1]
        self.assertEqual(bytes.fromhex(token).decode(), str(self.program))
        self.assertNotIn("MimeType", data)
        self.assertNotIn("DBusActivatable", data)
        with patch.object(self.q.subprocess, "Popen") as launch:
            self.assertTrue(self.q.native_run(token))
            launch.assert_called_once_with([str(self.program)], cwd=self.program.parent, start_new_session=True)

    def test_repeat_is_idempotent_and_personal_edits_are_kept(self):
        entry = self.q.native_shortcut(self.program, "My app", self.apps)
        self.assertEqual(self.q.native_shortcut(self.program, "My app", self.apps), entry)
        entry.write_text("personal launcher")
        with self.assertRaises(FileExistsError):
            self.q.native_shortcut(self.program, "My app", self.apps)
        self.assertEqual(entry.read_text(), "personal launcher")

    def package_icon(self, icon="demo", contents=None):
        program = self.root / "package/usr/bin/demo"
        program.parent.mkdir(parents=True)
        program.write_text("#!/bin/sh\nexit 0\n"); program.chmod(0o700)
        share = program.parent.parent / "share"
        (share / "applications").mkdir(parents=True)
        (share / "applications/demo.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=Demo\nExec=demo %U\nIcon={icon}\n")
        (share / "pixmaps").mkdir()
        image = share / "pixmaps/demo.svg"
        image.write_text(contents or '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30"/></svg>')
        return program, image

    def test_packaged_icon_is_named_copied_and_framed_without_launch(self):
        program, image = self.package_icon()
        with patch.object(self.q.subprocess, "Popen") as launch:
            entry = self.q.native_shortcut(program, "Demo", self.apps)
            launch.assert_not_called()
        icon = self.q.desktop_entry(entry.read_text())["Icon"]
        self.assertEqual(icon, entry.stem)
        copy = self.root / f"icons/hicolor/scalable/apps/{icon}.svg"
        self.assertEqual(copy.read_text(), image.read_text())
        with patch.object(self.q, "data_dirs", return_value=[self.root]), \
                patch.object(self.q, "DATADIR", str(ROOT / "linux/share")), patch.object(self.q, "run"):
            self.assertEqual(self.q.frames(), [icon])
            frame = self.root / f"icons/Monet/apps/scalable/{icon}.svg"
            self.assertIn("Monet frame:", frame.read_text())
            self.assertEqual(frame.read_text().count("data:image/png;base64,"), 2)

    def test_packaged_absolute_icon_and_compressed_svg(self):
        import gzip
        program, image = self.package_icon()
        compressed = image.with_suffix(".svgz")
        compressed.write_bytes(gzip.compress(image.read_bytes())); image.unlink()
        desktop = program.parent.parent / "share/applications/demo.desktop"
        desktop.write_text(desktop.read_text().replace("Icon=demo", f"Icon={compressed}"))
        entry = self.q.native_shortcut(program, "Demo", self.apps)
        icon = self.q.desktop_entry(entry.read_text())["Icon"]
        self.assertTrue((self.root / f"icons/hicolor/scalable/apps/{icon}.svg").is_file())

    def test_packaged_icon_does_not_follow_links_outside_package(self):
        program, image = self.package_icon()
        outside = self.root / "outside.svg"; outside.write_bytes(image.read_bytes())
        image.unlink(); image.symlink_to(outside)
        entry = self.q.native_shortcut(program, "Demo", self.apps)
        self.assertEqual(self.q.desktop_entry(entry.read_text())["Icon"], "application-x-executable")

    def test_painted_icon_wins_and_broken_compression_is_ignored(self):
        program, image = self.package_icon()
        theme = self.root / "icons/Monet/apps/scalable"; theme.mkdir(parents=True)
        (theme / "demo.svg").write_text(image.read_text())
        with patch.object(self.q, "data_dirs", return_value=[self.root]):
            entry = self.q.native_shortcut(program, "Demo", self.apps)
        self.assertEqual(self.q.desktop_entry(entry.read_text())["Icon"], "demo")
        broken = self.root / "bad.svgz"; broken.write_bytes(b"not gzip")
        self.assertEqual(self.q.icon_data(broken), b"")

    def test_bad_names_missing_nonexecutable_and_windows_files_are_rejected(self):
        for name in ("", "Bad\nExec=evil", "Bad\x00", "a" * 129):
            with self.assertRaises(ValueError):
                self.q.native_shortcut(self.program, name, self.apps)
        self.program.chmod(0o600)
        with self.assertRaises(ValueError):
            self.q.native_shortcut(self.program, "App", self.apps)
        self.program.chmod(0o700)
        self.program.write_bytes(b'MZwindows')
        with self.assertRaises(ValueError):
            self.q.native_shortcut(self.program, "App", self.apps)
        self.program.unlink()
        with self.assertRaises(ValueError):
            self.q.native_shortcut(self.program, "App", self.apps)
        self.assertFalse(self.apps.exists())

    def test_cancel_writes_nothing_and_moved_app_reports_failure(self):
        with patch.object(self.q, "run", return_value=None), patch.object(self.q, "native_shortcut") as save:
            self.assertFalse(self.q.native_shortcut_dialog(str(self.program)))
            save.assert_not_called()
        token = str(self.program).encode().hex()
        self.program.unlink()
        with patch.object(self.q, "run") as dialog, patch.object(self.q.subprocess, "Popen") as launch:
            self.assertFalse(self.q.native_run(token))
            launch.assert_not_called()
            self.assertEqual(dialog.call_args.args[0], "kdialog")
