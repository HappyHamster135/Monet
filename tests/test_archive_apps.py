"""Explicit archive extraction ends in app discovery, never downloaded-code execution."""
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tests.test_files_tools import files_tools

try:
    from PySide6.QtCore import QProcess
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication, 'native archive extraction dialog')
class ArchiveApps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.tool = files_tools()
        self.source = self.root / 'An app $(touch NO); %U å.tar.gz'
        self.source.write_bytes(b'fixture')
        self.dialogs = []
        self.addCleanup(lambda: [d.reject() for d in self.dialogs])

    def dialog(self):
        dialog = self.tool.make_extract_dialog(self.source); self.dialogs.append(dialog)
        dialog.show(); QTest.qWait(10)
        return dialog

    def start(self, dialog):
        dialog.findChild(QPushButton, 'extractApps').click()

    def wait(self, condition, seconds=5):
        for _ in range(int(seconds * 100)):
            if condition(): return
            QTest.qWait(10)
        self.fail('Archive fixture did not finish: ' + '\n'.join(
            d.findChild(QLabel, 'extractStatus').text() for d in self.dialogs))

    def fake_ark(self, script):
        folder = self.root / 'bin'; folder.mkdir()
        executable = folder / 'ark'
        executable.write_text('#!/usr/bin/python3\n' + script); executable.chmod(0o700)
        env = patch.dict(os.environ, PATH=str(folder) + os.pathsep + os.environ['PATH'])
        env.start(); self.addCleanup(env.stop)

    def test_existing_folders_and_broken_links_are_never_overwritten(self):
        suggested = self.tool.archive_destination(self.source)
        suggested.symlink_to(self.root / 'absent')
        alternate = self.tool.archive_destination(self.source)
        self.assertNotEqual(alternate, suggested)
        dialog = self.dialog()
        target = dialog.findChild(QLineEdit, 'extractDestination')
        for path in (self.root, suggested):
            target.setText(str(path)); self.start(dialog)
            self.assertIn('already exists', dialog.findChild(QLabel, 'extractStatus').text())
            self.assertEqual(dialog.findChild(QProcess, 'archiveExtractor').state(), QProcess.NotRunning)
        self.assertEqual(self.source.read_bytes(), b'fixture')
        self.assertTrue(suggested.is_symlink())

    def test_success_uses_literal_paths_and_preserves_execute_permissions(self):
        self.fake_ark('import json,sys\nfrom pathlib import Path\n'
                      'Path("arguments.json").write_text(json.dumps(sys.argv[1:]))\n'
                      'Path("app").write_bytes(b"#!/bin/sh\\ntouch SHOULD_NOT_RUN\\n")\n'
                      'Path("app").chmod(0o700)\n')
        dialog = self.dialog(); self.start(dialog)
        self.wait(lambda: dialog.extracted is not None)
        self.assertEqual(dialog.result(), QDialog.Accepted)
        folder = dialog.extracted
        self.assertEqual(json.loads((folder / 'arguments.json').read_text()),
                         ['--batch', '--destination', str(folder), str(self.source)])
        self.assertEqual(self.tool.scan_apps(folder)['items'][0]['path'], str(folder / 'app'))
        self.assertFalse((folder / 'SHOULD_NOT_RUN').exists())
        self.assertFalse((self.root / 'NO').exists())

    def test_partial_failure_is_retained_and_retry_requires_another_folder(self):
        self.fake_ark('from pathlib import Path\nPath("partial").write_text("keep")\nraise SystemExit(1)\n')
        dialog = self.dialog(); self.start(dialog)
        worker = dialog.findChild(QProcess, 'archiveExtractor')
        self.wait(lambda: worker.state() == QProcess.NotRunning)
        self.assertIsNone(dialog.extracted)
        folder = Path(dialog.findChild(QLineEdit, 'extractDestination').text())
        self.assertEqual((folder / 'partial').read_text(), 'keep')
        self.start(dialog)
        self.assertIn('already exists', dialog.findChild(QLabel, 'extractStatus').text())
        dialog.reject()
        self.assertEqual((folder / 'partial').read_text(), 'keep')

    def test_missing_ark_removes_only_the_empty_reserved_folder(self):
        dialog = self.dialog()
        empty_path = self.root / 'empty-path'; empty_path.mkdir()
        with patch.dict(os.environ, PATH=str(empty_path)):
            self.start(dialog)
            self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
        self.assertIsNone(dialog.extracted)
        self.assertFalse(Path(dialog.findChild(QLineEdit, 'extractDestination').text()).exists())
        self.assertIn('did not finish', dialog.findChild(QLabel, 'extractStatus').text())

    def test_cancellation_stops_extractor_and_descendants_but_keeps_partial_files(self):
        self.fake_ark('import subprocess,sys,time\nfrom pathlib import Path\n'
                      'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\n'
                      'Path("child").write_text(str(child.pid))\ntime.sleep(60)\n')
        dialog = self.dialog(); self.start(dialog)
        folder = Path(dialog.findChild(QLineEdit, 'extractDestination').text())
        self.wait(lambda: (folder / 'child').exists())
        child = int((folder / 'child').read_text())
        dialog.reject()
        self.assertEqual(dialog.findChild(QProcess, 'archiveExtractor').state(), QProcess.NotRunning)
        self.assertIsNone(dialog.extracted)
        self.assertTrue(folder.exists())
        def stopped():
            try: return Path(f'/proc/{child}/stat').read_text().split()[2] == 'Z'
            except FileNotFoundError: return True
        self.wait(stopped)

    @unittest.skipUnless(shutil.which('ark'), 'native Ark extraction backend')
    def test_real_zip_and_tar_extract_then_scan_without_running_any_app(self):
        for kind in ('zip', 'tar.gz'):
            with self.subTest(kind=kind):
                self.source = self.root / ('Download %U; å.' + kind)
                content = b'#!/bin/sh\ntouch SHOULD_NOT_RUN\n'
                if kind == 'zip':
                    with zipfile.ZipFile(self.source, 'w') as archive:
                        info = zipfile.ZipInfo('package/bin/example'); info.create_system = 3
                        info.external_attr = 0o100755 << 16
                        archive.writestr(info, content)
                else:
                    with tarfile.open(self.source, 'w:gz') as archive:
                        info = tarfile.TarInfo('package/bin/example'); info.mode = 0o755; info.size = len(content)
                        archive.addfile(info, io.BytesIO(content))
                before = self.source.read_bytes()
                dialog = self.dialog(); self.start(dialog)
                self.wait(lambda: dialog.extracted is not None, seconds=20)
                folder = dialog.extracted
                self.assertEqual((folder / 'package/bin/example').read_bytes(), content)
                self.assertEqual(self.source.read_bytes(), before)
                self.assertEqual(self.tool.scan_apps(folder)['items'][0]['kind'], 'native')
                self.assertFalse((folder / 'SHOULD_NOT_RUN').exists())


if __name__ == '__main__':
    unittest.main()
