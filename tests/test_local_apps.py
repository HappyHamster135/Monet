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

    def test_explicit_options_are_literal_and_keep_the_original_launcher(self):
        original = self.q.native_shortcut(self.program, "My app", self.apps)
        arguments = '--profile "My profile" "%U" "$(touch NO)" "`echo X`" "$HOME" "" å'
        entry = self.q.native_shortcut(self.program, "My profile", self.apps, arguments=arguments)
        self.assertNotEqual(entry, original)
        self.assertEqual(self.q.native_shortcut(self.program, "My profile", self.apps, arguments=arguments), entry)
        tokens = self.q.desktop_entry(entry.read_text())["Exec"].split()[-2:]
        with patch.object(self.q.subprocess, "Popen") as launch:
            self.assertTrue(self.q.native_run(*tokens))
        launch.assert_called_once_with([str(self.program), '--profile', 'My profile', '%U',
                                       '$(touch NO)', '`echo X`', '$HOME', '', 'å'],
                                      cwd=self.program.parent, start_new_session=True)
        self.assertTrue(original.is_file())
        self.assertFalse((self.root / "NO").exists())

    def test_invalid_options_never_create_a_shortcut_or_start_an_app(self):
        import json
        for arguments in ('"unclosed', 'bad\noption', 'a\x00b', 'å' * 4097, 'a ' * 65):
            with self.assertRaises(ValueError):
                self.q.native_shortcut(self.program, "Invalid", self.apps, arguments=arguments)
        self.assertFalse(self.apps.exists())
        bad = [None, {}, [1], ['a\x00b'], ['x'] * 65, ['å' * 4097]]
        tokens = [json.dumps(value).encode().hex() for value in bad] + ['invalid', 'ff', '00' * 20001]
        with patch.object(self.q.subprocess, "Popen") as launch, patch.object(self.q, "run"):
            for token in tokens:
                self.assertFalse(self.q.native_run(str(self.program).encode().hex(), token))
            launch.assert_not_called()

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
