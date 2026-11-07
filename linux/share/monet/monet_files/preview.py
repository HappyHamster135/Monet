"""Bounded, read-only previews. Decoding happens in a disposable worker."""
import base64
import io
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tarfile
import zipfile
from xml.etree import ElementTree

TEXT_LIMIT = 256 * 1024
ENTRY_LIMIT = 250


def archive_entries(path):
    entries = []
    if zipfile.is_zipfile(path):
        # Don't let a huge central directory allocate memory before our list cap.
        with path.open('rb') as stream:
            stream.seek(max(0, path.stat().st_size - 65557))
            tail = stream.read(65557)
        index = tail.rfind(b'PK\x05\x06')
        if index < 0 or len(tail) - index < 22:
            raise ValueError('Archive directory is incomplete.')
        end = struct.unpack('<4s4H2LH', tail[index:index + 22])
        if end[4] > 20000 or end[5] > 8 * 1024 * 1024:
            raise ValueError('This archive is too large to preview. Open it in Archives.')
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist()[:ENTRY_LIMIT]:
                entries.append(dict(name=item.filename, size=item.file_size, folder=item.is_dir()))
            more = len(archive.infolist()) > ENTRY_LIMIT
    else:
        with tarfile.open(path, 'r|*') as archive:
            for item in archive:
                if len(entries) == ENTRY_LIMIT:
                    break
                entries.append(dict(name=item.name, size=item.size, folder=item.isdir()))
            more = len(entries) == ENTRY_LIMIT
    return {'kind': 'archive', 'entries': entries, 'truncated': more}


def image_result(image):
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    if image.isNull():
        raise ValueError('No preview is available.')
    buffer = QBuffer(); buffer.open(QIODevice.WriteOnly)
    image.save(buffer, 'PNG')
    return {'kind': 'image', 'image': base64.b64encode(bytes(buffer.data())).decode()}


def office_text(path):
    # Validate the central directory before opening a document ZIP.
    archive_entries(path)
    names = {'.docx': 'word/document.xml', '.odt': 'content.xml', '.odp': 'content.xml', '.ods': 'content.xml', '.pptx': 'ppt/slides/slide1.xml'}
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(names[path.suffix.lower()])
        if info.file_size > 2 * 1024 * 1024:
            raise ValueError('This document is too large to preview. Open it in its application.')
        tree = ElementTree.fromstring(archive.read(info))
    # Plain text only: document macros, links, images and embedded objects never run.
    text = '\n'.join(part.strip() for part in tree.itertext() if part.strip())
    return dict(kind='text', text=text[:TEXT_LIMIT], truncated=len(text) > TEXT_LIMIT)


def seven_zip_entries(path):
    child = subprocess.Popen(['7z', 'l', '-slt', '--', str(path)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    entries = []; current = None; listing = False; received = 0
    try:
        while True:
            line = child.stdout.readline(8192)
            if not line: break
            received += len(line)
            if received > 1024 * 1024 or len(entries) >= ENTRY_LIMIT: break
            text = line.decode('utf-8', 'replace').rstrip('\r\n')
            if text.startswith('----------'): listing = True
            elif listing and text.startswith('Path = '):
                current = dict(name=text[7:], folder=False); entries.append(current)
            elif current and text.startswith('Size = '):
                try: current['size'] = int(text[7:])
                except ValueError: pass
            elif current and text.startswith('Folder = '): current['folder'] = text.endswith('+')
        if not entries and child.wait(timeout=1) != 0:
            raise ValueError('This archive is locked or cannot be previewed. Open it in Archives.')
        return dict(kind='archive', entries=entries, truncated=len(entries) >= ENTRY_LIMIT or received > 1024 * 1024)
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=1); child.stdout.close()


def data(name):
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QGuiApplication, QImageReader
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QGuiApplication.instance() or QGuiApplication([])
    path = Path(name).resolve(strict=True)
    info = path.stat()
    result = dict(name=path.name, path=str(path), size=info.st_size, modified=info.st_mtime)
    try:
        if stat.S_ISDIR(info.st_mode):
            entries = []
            with os.scandir(path) as iterator:
                for item in iterator:
                    if not item.name.startswith('.'):
                        entries.append(dict(name=item.name, folder=item.is_dir(follow_symlinks=False)))
                    if len(entries) >= ENTRY_LIMIT:
                        break
            result.update(kind='archive', entries=entries, truncated=len(entries) == ENTRY_LIMIT)
        elif not stat.S_ISREG(info.st_mode):
            result.update(kind='message', text='This item cannot be previewed.')
        elif path.suffix.lower() == '.pdf':
            from PySide6.QtPdf import QPdfDocument
            document = QPdfDocument(None)
            if document.load(str(path)) != QPdfDocument.Error.None_:
                raise ValueError('This PDF is locked or cannot be previewed.')
            size = document.pagePointSize(0).toSize().scaled(QSize(1100, 800), Qt.KeepAspectRatio)
            result.update(image_result(document.render(0, size)), pages=document.pageCount())
        elif path.suffix.lower() in {'.docx', '.odt', '.odp', '.ods', '.pptx'}:
            result.update(office_text(path))
        elif path.suffix.lower() in {'.7z', '.rar'}:
            result.update(seven_zip_entries(path))
        elif zipfile.is_zipfile(path) or path.name.lower().endswith(('.tar', '.tgz', '.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst', '.tbz2', '.txz')):
            result.update(archive_entries(path))
        else:
            reader = QImageReader(str(path)); reader.setAutoTransform(True)
            if reader.canRead():
                size = reader.size()
                if size.width() * size.height() > 100_000_000:
                    raise ValueError('This image is too large to preview.')
                reader.setScaledSize(size.scaled(QSize(1100, 800), Qt.KeepAspectRatio))
                result.update(image_result(reader.read()))
            else:
                # Never read a device, FIFO or an entire large file.
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise ValueError('This item cannot be previewed.')
                    raw = stream.read(TEXT_LIMIT + 1)
                if b'\0' in raw:
                    result.update(kind='message', text='No preview for this file type. Open it in its application.')
                else:
                    result.update(kind='text', text=raw[:TEXT_LIMIT].decode('utf-8', 'replace'), truncated=len(raw) > TEXT_LIMIT)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, tarfile.TarError, ElementTree.ParseError) as error:
        result.update(kind='message', text=str(error))
    return result


def show(path):
    from PySide6.QtCore import QProcess, QTimer, Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QPixmap, QShortcut
    from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit,
                                  QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout)
    app = QApplication.instance() or QApplication(sys.argv[:1]); app.setApplicationName('monet-files-preview')
    app.setDesktopFileName('org.kde.dolphin')
    dialog = QDialog(); dialog.setWindowTitle(Path(path).name); dialog.resize(850, 650)
    layout = QVBoxLayout(dialog)
    title = QLabel(Path(path).name); title.setTextFormat(Qt.PlainText); layout.addWidget(title)
    status = QLabel('Loading preview…'); status.setTextFormat(Qt.PlainText); layout.addWidget(status)
    content = QStackedWidget(); layout.addWidget(content, 1)
    picture = QLabel(); picture.setAlignment(Qt.AlignCenter); content.addWidget(picture)
    text = QPlainTextEdit(); text.setReadOnly(True); content.addWidget(text)
    tree = QTreeWidget(); tree.setHeaderLabels(['Name', 'Size']); content.addWidget(tree)
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    opening = buttons.addButton('Open in application', QDialogButtonBox.ActionRole)
    opening.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).absolute()))))
    buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
    for key in ('Space', 'Escape'):
        shortcut = QShortcut(QKeySequence(key), dialog); shortcut.activated.connect(dialog.reject)
    worker = QProcess(dialog)
    executable = Path(__file__).resolve().parents[3] / 'bin/monet-files'
    if not executable.exists():
        executable = Path(__file__).resolve().parents[3] / 'libexec/monet-files'
    worker.setProcessEnvironment(__import__('PySide6.QtCore', fromlist=['QProcessEnvironment']).QProcessEnvironment.systemEnvironment())
    environment = worker.processEnvironment(); environment.insert('QT_QPA_PLATFORM', 'offscreen'); worker.setProcessEnvironment(environment)
    output = bytearray()
    timeout = QTimer(dialog); timeout.setSingleShot(True); timeout.setInterval(6000)
    def stop(message):
        worker.kill(); status.setText(message)
    timeout.timeout.connect(lambda: stop('Preview took too long. Open this file in its application.'))
    def read():
        output.extend(bytes(worker.readAllStandardOutput()))
        if len(output) > 5 * 1024 * 1024:
            stop('Preview is too large. Open this file in its application.')
    worker.readyReadStandardOutput.connect(read)
    worker.readyReadStandardError.connect(worker.readAllStandardError)
    def finished(code, _state):
        timeout.stop(); read()
        if code:
            status.setText('No preview available. Open this file in its application.'); return
        try:
            result = json.loads(output)
            status.setText(f"{result['size']:,} bytes" + (' · Preview shortened' if result.get('truncated') else ''))
            if result.get('pages', 0) > 1:
                status.setText(status.text() + f" · Page 1 of {result['pages']}")
            if result['kind'] == 'image':
                image = QPixmap(); image.loadFromData(base64.b64decode(result['image']))
                picture.setPixmap(image.scaled(content.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)); content.setCurrentWidget(picture)
            elif result['kind'] == 'archive':
                for item in result['entries']:
                    entry = QTreeWidgetItem([item['name'], '' if item.get('folder') else str(item.get('size', ''))])
                    entry.setIcon(0, QIcon.fromTheme('folder' if item.get('folder') else 'text-x-generic')); tree.addTopLevelItem(entry)
                tree.setColumnWidth(0, 600); content.setCurrentWidget(tree)
            else:
                text.setPlainText(result.get('text', '')); content.setCurrentWidget(text)
        except (ValueError, KeyError):
            status.setText('No preview available.')
    worker.finished.connect(finished)
    worker.errorOccurred.connect(lambda _error: status.setText('Could not start the preview.'))
    dialog.finished.connect(lambda _code: worker.kill())
    worker.start(sys.executable, [str(executable), '--preview-data', str(Path(path).absolute())]); timeout.start()
    dialog.exec(); worker.kill(); worker.waitForFinished(1000)
    return 0
