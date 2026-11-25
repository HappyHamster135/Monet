"""An AppImage installed from Downloads survives cleanup and belongs to Settings → Apps."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import runpy
import shlex
import tempfile
import unittest
from unittest.mock import patch

from tests.test_files_tools import QApplication, files_tools, ROOT


class AppImageInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.downloads = self.home / 'Downloads'
        self.downloads.mkdir()
        self.path = self.downloads / 'My %F app.AppImage'
        self.image = b'\x7fELF' + b'\x02\x01\x01\x00AI\x02' + b'payload'
        self.path.write_bytes(self.image)
        self.path.chmod(0o600)
        self.f = files_tools()
        self.q = self.f.quick_helper()
        self.q.DATA_HOME = self.home / 'data'
        self.q.downloads_dir = lambda: self.downloads
        self.management = runpy.run_path(str(ROOT / 'linux/share/monet/monet_runtime/app_management.py'))

    def install(self):
        entry, identity = self.f.install_appimage(self.q, self.path, 'My app')
        fields = self.q.desktop_entry(entry.read_text())
        target = Path(bytes.fromhex(shlex.split(fields['Exec'])[2]).decode())
        return entry, fields, target, identity

    def remove(self, entry, fields, erase):
        plan = self.management['review'](entry, fields, self.home, self.q.DATA_HOME)
        self.assertEqual(plan['kind'], 'portable')
        self.assertTrue(self.management['uninstall'](plan, plan['token'], erase, None)['removed'])

    def test_discovery_install_remove_and_reuse_retained_data(self):
        self.assertEqual(self.f.scan_apps(self.downloads)['items'][0]['kind'], 'appimage')
        settings = self.path.with_name(self.path.name + '.config')
        settings.mkdir()
        (settings / 'prefs').write_text('original settings')
        (settings / 'alias').symlink_to('prefs')
        with patch.object(self.q.subprocess, 'Popen') as launch:
            entry, fields, target, _ = self.install()
            launch.assert_not_called()
        self.assertNotEqual(target.parent, self.downloads)
        self.assertTrue(os.access(target, os.X_OK))
        self.assertFalse(os.access(self.path, os.X_OK))
        saved = target.with_name(settings.name)
        self.assertTrue((saved / 'alias').is_symlink())
        self.assertEqual((saved / 'alias').read_text(), 'original settings')
        (saved / 'prefs').write_text('installed settings')
        self.remove(entry, fields, False)
        self.assertFalse(target.exists())
        self.assertEqual(self.install()[2], target)
        self.assertEqual((saved / 'prefs').read_text(), 'installed settings')
        self.path.rename(self.downloads / 'moved')
        self.assertEqual(target.read_bytes(), self.image)
        self.remove(entry, fields, True)
        self.assertFalse(saved.exists())
        self.assertFalse(entry.exists())
        self.assertEqual((settings / 'prefs').read_text(), 'original settings')

    def test_retry_parallel_install_and_filename_conflict(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = list(pool.map(lambda _: self.install(), range(2)))
        self.assertEqual(a, b)
        entry, _, target, identity = a
        self.path.write_bytes(self.image[:-1] + b'!')
        with self.assertRaisesRegex(FileExistsError, 'different app'):
            self.install()
        self.assertFalse(self.f.trash_installed_download(self.q, self.path, identity))
        self.assertTrue(self.path.exists())
        self.assertEqual(target.read_bytes(), self.image)
        self.assertTrue(entry.exists())

    def test_changed_file_and_cancellation_roll_back_new_data(self):
        checks = []
        def change():
            if not checks:
                checks.append(True)
                self.path.write_bytes(self.image + b'new content')
            return False
        for callback, error in ((change, ValueError), (lambda: True, InterruptedError)):
            with self.assertRaises(error):
                self.f.install_appimage(self.q, self.path, 'My app', interrupted=callback)
            self.assertFalse(any(p.is_file() for p in self.q.DATA_HOME.rglob('*')))
        self.path.write_bytes(b'\x7fELF')
        with self.assertRaisesRegex(ValueError, 'AppImage'):
            self.install()
        self.assertEqual(self.f.scan_apps(self.downloads)['items'][0]['kind'], 'permission')

    def test_personal_launcher_preserved_on_registration_failure(self):
        entry, _, target, _ = self.install()
        target.unlink()
        entry.write_text('personal menu entry')
        with self.assertRaises(FileExistsError):
            self.install()
        self.assertFalse(target.exists())
        self.assertEqual(entry.read_text(), 'personal menu entry')
        self.assertTrue(self.path.exists())

    def test_cleanup_only_applies_to_downloads(self):
        _, _, installed, _ = self.install()
        self.assertTrue(self.f.can_trash_download(self.q, self.path))
        self.assertFalse(self.f.can_trash_download(self.q, installed))
        link = self.downloads / 'link'
        link.symlink_to(self.path)
        self.assertFalse(self.f.can_trash_download(self.q, link))

    @unittest.skipUnless(QApplication, "native Qt installer")
    def test_utilities_picker_cancel_and_appimage_validation(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import sys
        utilities = str(ROOT / 'linux/share/monet/utilities')
        with patch.object(sys, 'path', [utilities, *sys.path]):
            from actions import ACTIONS, find_tools
            self.assertEqual(find_tools('install appimage', [], [])[0][0], 'appimage')
            self.assertEqual(ACTIONS['appimage'].command, ('@monet-files-tools', 'install-appimage'))
        self.path.write_text('#!/bin/sh\n')
        self.path.chmod(0o700)
        with patch.object(self.f, 'quick_helper', return_value=self.q), \
                patch.object(sys, 'argv', ['monet-files-tools', 'install-appimage']), \
                patch('PySide6.QtWidgets.QApplication'), patch.object(QFileDialog, 'getOpenFileName') as pick, \
                patch.object(QMessageBox, 'warning') as warning:
            pick.return_value = '', ''
            self.assertEqual(self.f.main(), 0)
            warning.assert_not_called()
            self.assertEqual(pick.call_args.args[2], str(self.downloads))
            pick.return_value = str(self.path), ''
            self.assertEqual(self.f.main(), 1)
            self.assertIn('AppImage', warning.call_args.args[2])
        self.assertFalse(self.q.DATA_HOME.exists())

    @unittest.skipUnless(QApplication, "native Qt installer")
    def test_dialog_cancel_and_keyboard_install(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLineEdit
        from PySide6.QtTest import QTest
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        app = QApplication.instance() or QApplication([])
        with patch.object(self.f, 'quick_helper', return_value=self.q):
            d = self.f.make_shortcut_dialog(self.path)
        d.show()
        self.assertFalse(d.findChild(QCheckBox, 'trashDownload').isChecked())
        d.reject()
        self.assertFalse(self.q.DATA_HOME.exists())
        d.show()
        field = d.findChild(QLineEdit, 'shortcutName')
        field.setText('Example')
        QTest.keyClick(field, Qt.Key.Key_Return)
        for _ in range(200):
            if d.result() == QDialog.Accepted:
                break
            QTest.qWait(10)
        self.assertEqual(d.result(), QDialog.Accepted)
        self.assertEqual(d.saved_name, 'Example')
        self.assertTrue(self.path.exists())
        self.assertEqual(len(list((self.q.DATA_HOME / 'applications').glob('*.desktop'))), 1)
