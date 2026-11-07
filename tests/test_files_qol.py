"""Read-only previews, virtual groups, and durable extraction controls."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet'))
from monet_files import desktop, preview

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QUrl, QMetaObject
    from PySide6.QtGui import QImage, QColor, QPdfWriter, QPainter
    from PySide6.QtQml import QJSEngine
except ImportError:
    QApplication = None


def jobs_module():
    loader = importlib.machinery.SourceFileLoader('file_jobs', str(ROOT / 'linux/libexec/monet-file-jobs'))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader)); loader.exec_module(module)
    return module


@unittest.skipUnless(QApplication, 'Qt preview runtime')
class Previews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_text_image_pdf_and_archive_are_bounded_and_read_only(self):
        text = self.root / 'example.txt'; text.write_text('x' * (preview.TEXT_LIMIT + 100))
        result = preview.data(text)
        self.assertEqual(result['kind'], 'text'); self.assertTrue(result['truncated'])
        self.assertEqual(len(result['text']), preview.TEXT_LIMIT)
        image = self.root / 'photo.png'
        pixels = QImage(1800, 1200, QImage.Format_RGB32); pixels.fill(QColor('red')); pixels.save(str(image))
        self.assertEqual(preview.data(image)['kind'], 'image')
        pdf = self.root / 'report.pdf'; writer = QPdfWriter(str(pdf)); painter = QPainter(writer)
        painter.drawText(50, 100, 'Preview fixture'); painter.end(); del writer
        self.assertEqual(preview.data(pdf)['pages'], 1)
        archive = self.root / 'archive.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('../outside.txt', 'never extract'); out.writestr('$(touch NO).txt', 'never execute')
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        result = preview.data(archive)
        self.assertEqual(result['kind'], 'archive'); self.assertEqual(len(result['entries']), 2)
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, before)
        self.assertFalse((self.root.parent / 'outside.txt').exists())

    def test_special_files_do_not_block_and_archive_lists_are_capped(self):
        if hasattr(os, 'mkfifo'):
            pipe = self.root / 'pipe'; os.mkfifo(pipe)
            self.assertEqual(preview.data(pipe)['kind'], 'message')
        archive = self.root / 'many.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            for index in range(300): out.writestr(str(index), '')
        result = preview.data(archive)
        self.assertEqual(len(result['entries']), preview.ENTRY_LIMIT); self.assertTrue(result['truncated'])

    def test_word_document_is_plain_text_and_gui_worker_renders(self):
        document = self.root / 'notes.docx'
        with zipfile.ZipFile(document, 'w') as out:
            out.writestr('word/document.xml', '<document><p><t>Notes from Stockholm</t></p></document>')
        self.assertEqual(preview.data(document)['text'], 'Notes from Stockholm')
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog, QPlainTextEdit
        original = QDialog.exec
        result = []
        def capture(dialog):
            def check():
                field = dialog.findChild(QPlainTextEdit)
                if field and 'Notes from Stockholm' in field.toPlainText():
                    result.append(True); dialog.grab().save('/tmp/monet-files-preview/document.png'); dialog.reject()
            timer = QTimer(dialog); timer.setInterval(100); timer.timeout.connect(check); timer.start()
            QTimer.singleShot(5000, dialog.reject)
            return original(dialog)
        with patch.object(QDialog, 'exec', capture): preview.show(str(document))
        self.assertTrue(result)

    @unittest.skipUnless(shutil.which('7z'), 'native 7-Zip lister')
    def test_seven_zip_lists_contents_without_extracting(self):
        source = self.root / 'notes.txt'; source.write_text('read only')
        archive = self.root / 'notes.7z'
        subprocess.run(['7z', 'a', str(archive), str(source)], stdout=subprocess.DEVNULL, check=True)
        before = sorted(path.name for path in self.root.iterdir())
        result = preview.data(archive)
        self.assertEqual(result['kind'], 'archive')
        self.assertEqual(result['entries'][0]['name'], 'notes.txt')
        self.assertEqual(before, sorted(path.name for path in self.root.iterdir()))


class Stacks(unittest.TestCase):
    def test_date_groups_and_partial_group_notices(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, days in (('today.txt', 0), ('yesterday.txt', 1), ('recent.txt', 3), ('old.txt', 10)):
                path = root / name; path.touch(); stamp = time.time() - days * 86400
                os.utime(path, (stamp, stamp))
            groups = {group['name']: group for group in desktop.stacks('date', root)['groups']}
            self.assertEqual(groups['Today']['items'][0]['name'], 'today.txt')
            self.assertEqual(groups['Yesterday']['items'][0]['name'], 'yesterday.txt')
            self.assertEqual(groups['Last 7 days']['items'][0]['name'], 'recent.txt')
            self.assertEqual(groups['Older']['items'][0]['name'], 'old.txt')
            self.assertTrue(desktop.stacks(folder=root, visible=1)['limited'])

    def test_groups_do_not_move_files_or_traverse_folders_and_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'photos').mkdir(); (root / 'photos/inside.jpg').write_bytes(b'not enumerated')
            for name in ('photo.jpg', 'report.pdf', 'bundle.tar.gz', 'video.mp4', '.private'):
                (root / name).touch()
            (root / 'link').symlink_to(root / 'photos', target_is_directory=True)
            before = sorted(str(path.relative_to(root)) for path in root.rglob('*'))
            result = desktop.stacks(folder=root)
            groups = {group['name']: group for group in result['groups']}
            self.assertEqual(groups['Folders']['count'], 1)
            self.assertEqual(groups['Archives']['items'][0]['name'], 'bundle.tar.gz')
            self.assertEqual(sum(group['count'] for group in groups.values()), 6)
            self.assertEqual(before, sorted(str(path.relative_to(root)) for path in root.rglob('*')))
            self.assertTrue(desktop.stacks(folder=root, limit=2)['limited'])

    @unittest.skipUnless(QApplication, 'Qt JavaScript runtime')
    def test_toggle_restores_filter_and_keeps_a_newer_user_filter(self):
        app = QApplication.instance() or QApplication([])
        engine = QJSEngine()
        result = engine.evaluate('''var gridUnit=20, config={General:{url:"desktop:/",filterMode:1,filterPattern:"*.png",filterMimeTypes:["image/png"]},MonetStacks:{}}, widgets=[];
var d={type:"org.kde.plasma.folder",currentConfigGroup:["General"],widgets:()=>widgets,
 readConfig:(k,f)=>config[d.currentConfigGroup[0]][k]===undefined?f:config[d.currentConfigGroup[0]][k],
 writeConfig:(k,v)=>config[d.currentConfigGroup[0]][k]=v,reloadConfig:()=>{},
 addWidget:()=>{var w={remove:()=>widgets=[]};widgets.push(w);return w;}};
function desktops(){return[d];}''')
        self.assertFalse(result.isError(), result.toString())
        source = (ROOT / 'linux/share/monet/stacks.js').read_text()
        def run():
            result = engine.evaluate(source); self.assertFalse(result.isError(), result.toString())
            return json.loads(engine.evaluate('JSON.stringify(config.General)').toString())
        self.assertEqual(run()['filterMode'], 2)
        saved = run(); self.assertEqual(saved['filterMode'], 1); self.assertEqual(saved['filterPattern'], '*.png')
        run(); engine.evaluate('config.General.filterPattern="*.pdf";config.General.filterMode=1;')
        self.assertEqual(run()['filterPattern'], '*.pdf')
        # Adding through the gallery enables the existing widget without a toggle
        # removing it. A stale receipt is repaired after native widget removal.
        engine.evaluate('widgets=[{remove:()=>widgets=[]}]; var forceOn=true;')
        self.assertEqual(run()['filterMode'], 2)
        engine.evaluate('forceOn=undefined; widgets=[]; var reconcile=true;')
        self.assertEqual(run()['filterPattern'], '*.pdf')


@unittest.skipUnless(os.name == 'posix', 'POSIX archive worker')
class Transfers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'; self.bin.mkdir()
        self.env = patch.dict(os.environ, XDG_STATE_HOME=str(self.root / 'state'), PATH=str(self.bin) + ':' + os.environ['PATH'])
        self.env.start(); self.addCleanup(self.env.stop)
        self.module = jobs_module(); self.queue = self.module.Queue()
        self.source = self.root / 'An archive $(touch NO).zip'; self.source.write_bytes(b'fixture')
        (self.bin / 'dolphin').write_text('#!/bin/sh\nexit 0\n'); (self.bin / 'dolphin').chmod(0o700)

    def ark(self, code):
        path = self.bin / 'ark'; path.write_text('#!/usr/bin/python3\n' + code); path.chmod(0o700)

    def wait(self, token, state):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            job = self.queue.read(token)
            if job['state'] == state: return job
            time.sleep(.025)
        self.fail((state, job))

    def test_detached_worker_survives_submitter_and_preserves_partial_output_on_retry(self):
        self.ark('from pathlib import Path\nPath("partial").write_text("keep")\nraise SystemExit(1)\n')
        job = self.queue.submit(self.source, self.root / 'extracted')
        self.queue.launch(job['token']); self.wait(job['token'], 'failed')
        self.assertEqual((self.root / 'extracted/partial').read_text(), 'keep')
        self.ark('from pathlib import Path\nPath("complete").write_text("done")\n')
        retry = self.queue.control(job['token'], 'retry'); self.wait(retry['token'], 'done')
        self.assertNotEqual(job['destination'], retry['destination'])
        self.assertEqual((self.root / 'extracted/partial').read_text(), 'keep')
        self.assertEqual((Path(retry['destination']) / 'complete').read_text(), 'done')
        self.assertFalse((self.root / 'NO').exists())

    def test_pause_resume_cancel_and_existing_destination(self):
        self.ark('import time\nfrom pathlib import Path\nPath("started").touch()\ntime.sleep(30)\n')
        job = self.queue.submit(self.source, self.root / 'output')
        with self.assertRaises(FileExistsError): self.queue.submit(self.source, self.root / 'output')
        self.queue.launch(job['token']); self.wait(job['token'], 'running')
        self.addCleanup(lambda: self.queue.control(job['token'], 'cancel') if self.queue.read(job['token'])['state'] in self.module.ACTIVE else None)
        self.queue.control(job['token'], 'pause'); self.wait(job['token'], 'paused')
        self.queue.control(job['token'], 'resume'); self.wait(job['token'], 'running')
        self.queue.control(job['token'], 'cancel'); self.wait(job['token'], 'cancelled')
        self.assertTrue((self.root / 'output').is_dir())

    def test_changed_input_and_lost_worker_never_report_success(self):
        job = self.queue.submit(self.source, self.root / 'output')
        self.source.write_bytes(b'changed input')
        self.queue.run(job['token'], reveal=False)
        self.assertEqual(self.queue.read(job['token'])['state'], 'failed')
        self.queue.change(job['token'], state='running', updated=1)
        stale = self.queue.read(job['token']); stale['updated'] = 1; self.queue.write(stale)
        self.assertEqual(self.queue.status()[0]['state'], 'interrupted')

    def test_preassigned_submission_token_cannot_replace_an_existing_job(self):
        token='b'*32
        job=self.queue.submit(self.source,self.root/'first',token=token)
        original=self.queue.read(token)
        with self.assertRaises(FileExistsError):self.queue.submit(self.source,self.root/'second',token=token)
        self.assertEqual(self.queue.read(token),original)
        self.assertEqual(job['token'],token)
        self.assertFalse((self.root/'second').exists())
        with self.assertRaises(ValueError): self.queue.submit(self.source,self.root/'invalid',token='0'*32)
        self.assertFalse((self.root/'invalid').exists())

    def test_destination_replaced_during_extraction_never_reports_success(self):
        self.ark('from pathlib import Path\n'
                 'folder=Path.cwd(); retained=folder.with_name("retained-partial")\n'
                 'folder.rename(retained); folder.mkdir()\n'
                 '(retained / "partial").write_text("keep")\n')
        job = self.queue.submit(self.source, self.root / 'output')
        self.queue.run(job['token'], reveal=False)
        result = self.queue.read(job['token'])
        self.assertEqual(result['state'], 'failed')
        self.assertIn('folder changed', result['error'])
        self.assertEqual((self.root / 'retained-partial/partial').read_text(), 'keep')
        self.assertEqual(list((self.root / 'output').iterdir()), [])

    def test_destination_disappearing_after_successful_backend_keeps_partial_files(self):
        self.ark('from pathlib import Path\n'
                 'folder=Path.cwd(); (folder / "partial").write_text("keep")\n'
                 'folder.rename(folder.with_name("disconnected-output"))\n')
        job = self.queue.submit(self.source, self.root / 'output')
        self.queue.run(job['token'], reveal=False)
        self.assertEqual(self.queue.read(job['token'])['state'], 'failed')
        self.assertEqual((self.root / 'disconnected-output/partial').read_text(), 'keep')

    @unittest.skipUnless(shutil.which('ark'), 'native Ark backend')
    def test_native_zip_worker_and_destination_url(self):
        with zipfile.ZipFile(self.source, 'w') as archive: archive.writestr('readme.txt', 'native extraction')
        job = self.queue.submit(self.source, self.root / 'output #å')
        self.queue.run(job['token'], reveal=False)
        self.assertEqual(self.queue.read(job['token'])['state'], 'done')
        self.assertEqual((self.root / 'output #å/readme.txt').read_text(), 'native extraction')
        self.assertEqual(self.queue.status()[0]['destinationUrl'], (self.root / 'output #å').as_uri())


@unittest.skipUnless(QApplication and shutil.which('plasmawindowed'), 'native Plasma widget host')
class NativeWidgets(unittest.TestCase):
    def test_stacks_render_with_native_plasma(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/files-qol-native.py'), 'stacks'], check=True, timeout=20)

    def test_transfers_render_with_native_jobs_model(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/files-qol-native.py'), 'transfers'], check=True, timeout=20)
