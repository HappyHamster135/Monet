"""Explicit archive extraction ends in app discovery, never downloaded-code execution."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
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
        dialog.show()
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
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

    def worker_script(self, transform):
        folder = self.root / 'worker'; folder.mkdir()
        script = folder / 'monet-files-tools'
        script.write_text(transform(Path(self.tool.__file__).read_text()))
        shutil.copy2(Path(self.tool.__file__).with_name('monet-file-jobs'), folder)
        self.tool.__file__ = str(script)

    def capture(self, dialog, name, **values):
        if not os.environ.get('MONET_ARCHIVE_CAPTURE'): return
        folder=Path(os.environ['MONET_ARCHIVE_CAPTURE']);folder.mkdir(parents=True,exist_ok=True)
        dialog.grab().save(str(folder/(name+'.png')))
        (folder/(name+'.json')).write_text(json.dumps(values,indent=2)+'\n')

    def test_slow_archive_lookup_keeps_the_dialog_and_escape_responsive(self):
        from PySide6.QtCore import QTimer, Qt
        marker = self.root / 'lookup-blocked'
        def inject(source):
            return source.replace("    source = Path(request['source']).resolve(strict=True)",
                "    original_stat = os.stat\n"
                "    def slow_stat(path, *args, **kwargs):\n"
                "        if str(path) == request['source']:\n"
                f"            Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                "            time.sleep(20)\n"
                "        return original_stat(path, *args, **kwargs)\n"
                "    os.stat = slow_stat\n"
                "    source = Path(request['source']).resolve(strict=True)")
        self.worker_script(inject)
        native_stat = os.stat; gui_reads = []
        def record(path, *args, **kwargs):
            if os.fspath(path) == str(self.source):
                gui_reads.append(str(path)); raise AssertionError('Archive stat ran on the GUI thread')
            return native_stat(path, *args, **kwargs)
        with patch.object(os, 'stat', record):
            dialog = self.tool.make_extract_dialog(self.source); self.dialogs.append(dialog); dialog.show()
            ticks=[]; timer=QTimer(dialog); timer.setInterval(20); timer.timeout.connect(lambda: ticks.append(time.monotonic())); timer.start()
            self.wait(marker.exists)
            self.assertNotEqual(int(marker.read_text()), os.getpid())
            self.wait(lambda: len(ticks) >= 6)
            self.assertFalse(dialog.findChild(QPushButton, 'extractApps').isEnabled())
            self.capture(dialog,'slow-lookup',worker_pid=int(marker.read_text()),gui_pid=os.getpid(),
                         heartbeat_count=len(ticks),gui_archive_stats=gui_reads)
            started=time.monotonic(); QTest.keyClick(dialog, Qt.Key_Escape)
            elapsed=time.monotonic()-started
            self.assertLess(elapsed, .25)
            self.capture(dialog,'slow-lookup-cancelled',escape_seconds=elapsed)
            self.wait(lambda: dialog.findChild(QProcess,'archiveExtractor').state() == QProcess.NotRunning)
        self.assertFalse(gui_reads)
        self.assertIsNone(dialog.extracted)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted([self.source.name, 'worker', marker.name]))

    def test_cancel_after_queue_reservation_cannot_launch_a_late_extraction(self):
        from tests.test_files_qol import jobs_module
        from PySide6.QtCore import Qt
        marker=self.root/'submission-blocked'
        def inject(source):
            return source.replace("        try: queue.launch(job['token'])",
                f"        Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                "        time.sleep(20)\n"
                "        try: queue.launch(job['token'])")
        self.worker_script(inject)
        state=self.root/'state'
        with patch.dict(os.environ,XDG_STATE_HOME=str(state)):
            dialog=self.tool.make_extract_dialog(self.source,background=True)
            self.dialogs.append(dialog);dialog.show()
            self.wait(lambda: dialog.findChild(QPushButton,'extractApps').isEnabled())
            self.start(dialog);self.wait(marker.exists)
            self.wait(lambda: dialog.findChild(QPushButton,'showExtracted').isEnabled())
            queue=jobs_module().Queue();job=queue.status()[0]
            self.assertEqual(job['state'],'queued')
            self.capture(dialog,'queued-submission',state=job['state'],token=job['token'])
            started=time.monotonic();QTest.keyClick(dialog,Qt.Key_Escape)
            self.assertLess(time.monotonic()-started,.25)
            self.wait(lambda: queue.read(job['token'])['state']=='cancelled')
            self.assertEqual(list(Path(job['destination']).iterdir()),[])
            self.assertIsNone(dialog.extracted)

    def test_enter_in_the_destination_starts_one_extraction(self):
        from PySide6.QtCore import Qt
        calls=self.root/'calls'
        self.fake_ark(f'from pathlib import Path\nwith Path({str(calls)!r}).open("a") as f:f.write("launch\\n")\nPath("complete").touch()\n')
        for index,key in enumerate((Qt.Key_Return,Qt.Key_Enter),1):
            with self.subTest(key=key):
                dialog=self.dialog();field=dialog.findChild(QLineEdit,'extractDestination');field.setFocus()
                QTest.keyClick(field,key)
                self.wait(lambda: dialog.extracted is not None)
                self.assertEqual(calls.read_text().splitlines(),['launch']*index)
                self.assertTrue((dialog.extracted/'complete').is_file())

    def test_accepted_background_extraction_survives_the_dialog(self):
        from tests.test_files_qol import jobs_module
        self.fake_ark('import time\nfrom pathlib import Path\nPath("partial").write_text("keep")\ntime.sleep(.4)\nPath("complete").write_text("done")\n')
        with patch.dict(os.environ,XDG_STATE_HOME=str(self.root/'state')):
            dialog=self.tool.make_extract_dialog(self.source,background=True)
            self.dialogs.append(dialog);dialog.show()
            self.wait(lambda: dialog.findChild(QPushButton,'extractApps').isEnabled())
            self.start(dialog);self.wait(lambda: dialog.extracted is not None)
            destination=dialog.extracted
            dialog.deleteLater();self.dialogs.remove(dialog);QTest.qWait(20)
            queue=jobs_module().Queue();job=queue.status()[0]
            self.wait(lambda: queue.read(job['token'])['state']=='done')
            self.assertEqual((destination/'complete').read_text(),'done')

    def test_existing_folders_and_broken_links_are_never_overwritten(self):
        suggested = self.tool.archive_destination(self.source)
        suggested.symlink_to(self.root / 'absent')
        alternate = self.tool.archive_destination(self.source)
        self.assertNotEqual(alternate, suggested)
        dialog = self.dialog()
        target = dialog.findChild(QLineEdit, 'extractDestination')
        for path in (self.root, suggested):
            target.setText(str(path)); self.start(dialog)
            self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
            self.assertIn('already exists', dialog.findChild(QLabel, 'extractStatus').text())
            self.assertEqual(dialog.findChild(QProcess, 'archiveExtractor').state(), QProcess.NotRunning)
        self.assertEqual(self.source.read_bytes(), b'fixture')
        self.assertTrue(suggested.is_symlink())

    def test_plain_archive_defaults_to_desktop_and_dropped_folder_extracts_there(self):
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import QFrame
        desktop = self.root / 'Skrivbord'; desktop.mkdir()
        target = self.root / 'A destination å'; target.mkdir()
        self.fake_ark('from pathlib import Path\nPath("readme.txt").write_text("extracted")\n')
        config = self.root / 'config'; config.mkdir()
        (config / 'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="' + str(desktop) + '"\n')
        with patch.dict(os.environ, XDG_CONFIG_HOME=str(config)):
            dialog = self.tool.make_extract_dialog(self.source, find_apps=False)
        self.dialogs.append(dialog); dialog.show()
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
        self.assertEqual(Path(dialog.findChild(QLineEdit, 'extractDestination').text()).parent, desktop)
        drop = dialog.findChild(QFrame, 'extractDropTarget')
        mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(target))])
        enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(drop, enter)
        self.assertTrue(enter.isAccepted())
        event = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(drop, event)
        self.assertTrue(event.isAccepted())
        self.wait(lambda: dialog.extracted is not None)
        self.assertEqual(dialog.extracted.parent, target)
        self.assertEqual((dialog.extracted / 'readme.txt').read_text(), 'extracted')
        self.assertEqual(list(desktop.iterdir()), [])

    def test_drop_rejects_remote_locations_and_checks_files_asynchronously(self):
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import QFrame
        dialog = self.dialog()
        drop = dialog.findChild(QFrame, 'extractDropTarget')
        for urls in ([QUrl('https://example.com/folder')],
                     [QUrl.fromLocalFile(str(self.root)), QUrl.fromLocalFile(str(self.root))]):
            mime = QMimeData(); mime.setUrls(urls)
            event = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
            QApplication.sendEvent(drop, event)
            self.assertFalse(event.isAccepted())
        mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(self.source))])
        enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(drop, enter)
        event = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(drop, event)
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
        self.assertIn('not a file', dialog.findChild(QLabel, 'extractStatus').text())
        self.assertIsNone(dialog.extracted)

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
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
        self.assertIn('already exists', dialog.findChild(QLabel, 'extractStatus').text())
        dialog.reject()
        self.assertEqual((folder / 'partial').read_text(), 'keep')

    def test_replaced_output_is_not_cleaned_up_or_accepted_as_an_extracted_app(self):
        self.fake_ark('from pathlib import Path\n'
                      'folder=Path.cwd(); folder.rename(folder.with_name("retained-output"))\n'
                      'folder.mkdir()\n')
        dialog = self.dialog(); self.start(dialog)
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
        self.assertIsNone(dialog.extracted)
        self.assertIn('folder changed', dialog.findChild(QLabel, 'extractStatus').text())
        folder = Path(dialog.findChild(QLineEdit, 'extractDestination').text())
        self.assertTrue(folder.is_dir())
        self.assertFalse(dialog.findChild(QPushButton, 'showExtracted').isEnabled())

    def test_native_password_cancellation_keeps_partial_output_and_allows_retry(self):
        self.fake_ark('from pathlib import Path\nPath("partial").write_text("keep")\nraise SystemExit(130)\n')
        dialog = self.dialog(); self.start(dialog)
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
        self.assertIsNone(dialog.extracted)
        self.assertIn('cancelled', dialog.findChild(QLabel, 'extractStatus').text())
        folder = Path(dialog.findChild(QLineEdit, 'extractDestination').text())
        self.assertEqual((folder / 'partial').read_text(), 'keep')
        self.start(dialog)
        self.wait(lambda: dialog.findChild(QPushButton, 'extractApps').isEnabled())
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
        self.wait(lambda: dialog.findChild(QProcess, 'archiveExtractor').state() == QProcess.NotRunning)
        self.assertIsNone(dialog.extracted)
        self.assertTrue(folder.exists())
        def stopped():
            try: return Path(f'/proc/{child}/stat').read_text().split()[2] == 'Z'
            except (FileNotFoundError, ProcessLookupError): return True
        self.wait(stopped)

    @unittest.skipUnless(all(shutil.which(tool) for tool in ('ark','7z','Xvfb','xdotool')), 'native encrypted extractor UI')
    def test_worker_preserves_native_encrypted_password_and_cancel_dialogs(self):
        from tests.native_archive_session import desktop,key,run_dialog,text
        with desktop():
            content=self.root/'readme.txt';content.write_text('native encrypted worker')
            self.source=self.root/'encrypted.7z'
            subprocess.run(['7z','a','-pMonet-test-password','-mhe=on',str(self.source),str(content)],
                           check=True,stdout=subprocess.DEVNULL)
            dialog=self.dialog();self.start(dialog)
            def answer(window,title):
                if 'password' in title.lower():text('Monet-test-password');key(window,'Return')
                else:key(window,'Escape')
            titles=run_dialog(dialog,answer)
            self.assertTrue(any('password' in title.lower() for title in titles),titles)
            self.assertIsNotNone(dialog.extracted)
            self.assertEqual((dialog.extracted/'readme.txt').read_text(),content.read_text())
            cancelled=self.dialog();self.start(cancelled)
            titles=run_dialog(cancelled,lambda window,title:key(window,'Escape'))
            self.assertTrue(any('password' in title.lower() for title in titles),titles)
            self.assertIsNone(cancelled.extracted)
            self.assertIn('cancelled',cancelled.findChild(QLabel,'extractStatus').text())

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
