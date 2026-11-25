"""A media queue with one low-priority conversion running at a time."""
from collections import deque
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import sys

from PySide6.QtCore import QLocale, QProcess, Qt
from PySide6.QtGui import QImageWriter
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton,
                               QSpinBox, QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from actions import tr
from recording_export import ExportFile
from media_compress import output_suffix, source_signature

WORKER = Path(__file__).with_name("media_compress.py")


@dataclass
class Entry:
    path: Path
    row: QTreeWidgetItem
    info: dict | None = None
    output: Path | None = None
    inspected: bool = False


def display_size(size):
    return QLocale().formattedDataSize(size, 1, QLocale.DataSizeSIFormat)


def unused_name(source, folder, suffix, reserved):
    base = folder / (source.stem + "-small")
    name = Path(str(base) + suffix)
    count = 1
    while name in reserved or os.path.lexists(name):
        count += 1
        name = Path(f"{base} ({count}){suffix}")
    return name


class CompressPage(QWidget):
    def __init__(self):
        super().__init__()
        self.entries = {}
        self.job = None
        self.plans = deque()
        self.exporting = False
        self.cancelled = False
        self.closing = False
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self.add = QPushButton(tr("Add files…"))
        self.add.clicked.connect(self.choose_files)
        buttons.addWidget(self.add)
        self.remove = QPushButton(tr("Remove"))
        self.remove.clicked.connect(self.remove_selected)
        buttons.addWidget(self.remove)
        buttons.addStretch()
        self.reveal = QPushButton(tr("Show in Files"))
        self.reveal.clicked.connect(self.reveal_copy)
        buttons.addWidget(self.reveal)
        self.tree = QTreeWidget()
        self.tree.setAccessibleName(tr("Media files"))
        self.tree.setHeaderLabels([tr("File"), tr("Original"), tr("Compressed copy")])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setMinimumHeight(75)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2):
            self.tree.header().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self.selection_changed)
        self.tree.setAcceptDrops(False)
        self.stack = QStackedWidget()
        empty = QLabel(tr("Drop photos, videos or GIFs here."))
        empty.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(empty)
        self.stack.addWidget(self.tree)
        layout.addWidget(self.stack, 1)
        self.options = QWidget()
        form = QFormLayout(self.options)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.format = QComboBox()
        for key, label in (("", tr("Automatic")), (".mp4", tr("MP4 video")), (".gif", tr("GIF animation")),
                           (".webp", tr("WebP image")), (".jpg", tr("JPEG image")), (".png", tr("PNG image"))):
            self.format.addItem(label, key)
        if b"heic" in QImageWriter.supportedImageFormats():
            self.format.addItem(tr("HEIC image"), ".heic")
        self.format.addItem(tr("PDF document"), ".pdf")
        form.addRow(tr("Save as"), self.format)
        self.quality = QComboBox()
        self.quality.addItems([tr("Smaller file"), tr("Balanced"), tr("Higher quality")])
        self.quality.setCurrentIndex(1)
        form.addRow(tr("Quality"), self.quality)
        self.edge = QSpinBox()
        self.edge.setRange(0, 32768)
        self.edge.setSpecialValueText(tr("Automatic"))
        self.edge.setSuffix(" px")
        form.addRow(tr("Longest edge"), self.edge)
        self.limited = QCheckBox(tr("Maximum file size"))
        self.limit = QDoubleSpinBox()
        self.limit.setAccessibleName(self.limited.text())
        self.limit.setRange(.01, 64000)
        self.limit.setValue(10)
        self.limit.setSuffix(" MB")
        self.limit.setEnabled(False)
        self.limited.toggled.connect(self.limit.setEnabled)
        form.addRow(self.limited, self.limit)
        self.fit_note = QLabel(tr("Pictures and GIFs can be resized to fit."))
        self.fit_note.setWordWrap(True)
        form.addRow(self.fit_note)
        self.audio = QCheckBox(tr("Keep video sound"))
        self.audio.setChecked(True)
        form.addRow(self.audio)
        layout.addWidget(self.options)
        self.progress = QProgressBar()
        self.progress.setAccessibleName(tr("Compression progress"))
        layout.addWidget(self.progress)
        footer = QHBoxLayout()
        layout.addLayout(footer)
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        footer.addWidget(self.message, 1)
        self.cancel = QPushButton(tr("Cancel"))
        self.cancel.clicked.connect(self.cancel_export)
        footer.addWidget(self.cancel)
        self.save = QPushButton(tr("Save copy…"))
        self.save.clicked.connect(self.choose_output)
        footer.addWidget(self.save)
        self.format.currentIndexChanged.connect(self.format_changed)
        self.limit.valueChanged.connect(self.update_controls)
        self.limited.toggled.connect(self.update_controls)
        self.update_controls()

    def suffix(self, entry):
        return self.format.currentData() or {"image": ".webp", "animation": ".gif", "video": ".mp4"}[entry.info["kind"]]

    def format_changed(self):
        for e in self.entries.values():
            if e.info and not e.output and not self.exporting:
                e.row.setText(2, self.suffix(e)[1:].upper())
                e.row.setToolTip(2, "")
        self.update_controls()

    def update_controls(self):
        ready = [e for e in self.entries.values() if e.info]
        formats = {self.suffix(e) for e in ready}
        self.stack.setCurrentIndex(int(bool(self.entries)))
        selected = self.tree.selectedItems()
        self.remove.setEnabled(bool(selected) and not self.exporting)
        self.add.setEnabled(not self.exporting)
        self.options.setVisible(bool(ready))
        self.options.setEnabled(not self.exporting)
        self.fit_note.setVisible(self.limited.isChecked() and bool(formats - {".mp4"}))
        self.audio.setVisible(any(e.info["audio"] and self.suffix(e) == ".mp4" for e in ready))
        # For videos above the cap, the byte budget sets the bitrate.
        limit = round(self.limit.value() * 1000000) if self.limited.isChecked() else 0
        self.quality.setEnabled(any(self.suffix(e) != ".png" and
                                    (self.suffix(e) != ".mp4" or not limit or e.info["size"] <= limit)
                                    for e in ready))
        entry = self.entries.get(selected[0].data(0, Qt.UserRole)) if len(selected) == 1 else None
        self.reveal.setVisible(bool(entry and entry.output))
        self.save.setText(tr("Save copies…") if len(ready) > 1 else tr("Save copy…"))
        self.save.setVisible(not self.exporting)
        self.save.setEnabled(bool(ready) and not self.job)
        self.cancel.setVisible(self.exporting)
        self.progress.setVisible(self.exporting)

    def selection_changed(self):
        self.update_controls()
        selected = self.tree.selectedItems()
        if len(selected) == 1 and selected[0].text(2) == tr("Failed") and not self.exporting:
            self.message.setText(selected[0].toolTip(2))

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("Add media files"))
        self.add_paths(files)

    def add_paths(self, paths):
        if self.exporting:
            return
        for path in paths:
            path = Path(path).absolute()
            key = str(path)
            if key in self.entries:
                continue
            row = QTreeWidgetItem([path.name, "", tr("Reading…")])
            row.setData(0, Qt.UserRole, key)
            row.setToolTip(0, key)
            self.entries[key] = Entry(path, row)
            self.tree.addTopLevelItem(row)
            if self.tree.currentItem() is None:
                self.tree.setCurrentItem(row)
        self.update_controls()
        self.inspect_next()

    def dragEnterEvent(self, event):
        if not self.exporting and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.exporting:
            self.add_paths(url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile())
            event.acceptProposedAction()

    def remove_selected(self):
        if self.exporting:
            return
        for row in self.tree.selectedItems():
            self.entries.pop(row.data(0, Qt.UserRole), None)
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(row))
        if not self.entries:
            self.message.clear()
            self.stop_job()
        self.update_controls()

    def reveal_copy(self):
        selected = self.tree.selectedItems()
        if len(selected) == 1:
            entry = self.entries[selected[0].data(0, Qt.UserRole)]
            if entry.output:
                if not QProcess.startDetached("dolphin", ["--select", str(entry.output)])[0]:
                    self.message.setText(tr("Couldn’t open Files."))

    def worker(self, args, finished, *, line_received=None, input_data=None):
        job = QProcess(self)
        self.job = job
        job.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        def report():
            while job.canReadLine():
                line_received(bytes(job.readLine()))
        if line_received:
            job.readyReadStandardOutput.connect(report)
        def end(ok):
            if self.job is not job:
                return
            if line_received:
                report()
            self.job = None
            error = bytes(job.readAllStandardError()).decode(errors="replace").strip()
            job.deleteLater()
            finished(ok, error)
        job.finished.connect(lambda code, status: end(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda error: end(False) if error == QProcess.FailedToStart else None)
        job.start("nice", ["-n", "12", sys.executable, str(WORKER), *map(str, args)])
        if input_data is not None:
            job.write(input_data)
            job.closeWriteChannel()

    def inspect_next(self):
        if self.job or self.closing or self.exporting:
            return
        batch = [item for item in self.entries.values() if not item.inspected]
        if not batch:
            self.update_controls()
            return
        def received(line):
            key, info, reason = json.loads(line)
            entry = self.entries.get(key)
            if self.closing or entry is None or batch_entries.get(key) is not entry:
                return
            entry.inspected = True
            entry.info = info
            if info is None:
                self.row_error(entry, reason)
            else:
                entry.row.setText(1, display_size(info["size"]))
                entry.row.setText(2, self.suffix(entry)[1:].upper())
        def finished(ok, error):
            if not self.closing:
                for entry in batch:
                    if not entry.inspected and self.entries.get(str(entry.path)) is entry:
                        entry.inspected = True
                        self.row_error(entry, error or tr("Couldn’t read this file."))
                self.inspect_next()
        batch_entries = {str(e.path): e for e in batch}
        self.worker(["inspect"], finished, line_received=received,
                    input_data=json.dumps(list(batch_entries)).encode())
        self.update_controls()

    def choose_output(self):
        ready = [e for e in self.entries.values() if e.info]
        if not ready or self.job or self.exporting:
            return
        if len(ready) == 1:
            e = ready[0]
            suffix = self.suffix(e)
            name, _ = QFileDialog.getSaveFileName(self, tr("Save compressed copy"),
                       str(unused_name(e.path, e.path.parent, suffix, set())), "*" + suffix,
                       options=QFileDialog.DontConfirmOverwrite)
            if not name:
                return
            target = Path(name)
            if output_suffix(target) != suffix:
                target = Path(name + suffix)
            targets = [(e, target)]
        else:
            folder = QFileDialog.getExistingDirectory(self, tr("Save compressed copies in"), str(ready[0].path.parent))
            if not folder:
                return
            reserved = set()
            targets = []
            for e in ready:
                target = unused_name(e.path, Path(folder), self.suffix(e), reserved)
                reserved.add(target)
                targets.append((e, target))
        self.start_exports(targets)

    def start_exports(self, targets):
        if self.exporting or self.job or not targets:
            return
        self.plans = deque(targets)
        for entry, _ in targets:
            entry.output = None
            entry.row.setText(2, tr("Queued"))
            entry.row.setToolTip(2, "")
        self.exporting = True
        self.cancelled = False
        self.total = len(targets)
        self.saved = self.failed = 0
        self.update_controls()
        self.export_next()

    def row_error(self, entry, reason):
        entry.row.setText(2, tr("Failed"))
        entry.row.setToolTip(2, reason)
        self.message.setText(reason)

    def export_next(self):
        while self.plans and not self.cancelled:
            entry, target = self.plans.popleft()
            try:
                output = ExportFile(target)
            except OSError as error:
                self.failed += 1
                self.row_error(entry, tr("Choose a new filename for the copy.") if isinstance(error, FileExistsError) else str(error))
                continue
            self.message.setText(tr("Saving %1").replace("%1", entry.path.name))
            entry.row.setText(2, tr("Saving…"))
            self.progress.setRange(0, 0)
            limit = round(self.limit.value() * 1000000) if self.limited.isChecked() else 0
            def progress(line):
                value = line.strip()
                if value.isdigit():
                    self.progress.setRange(0, 100)
                    self.progress.setValue(int(value))
            def saved(ok, error):
                try:
                    if self.cancelled:
                        entry.row.setText(2, tr("Cancelled"))
                    elif not ok:
                        raise ValueError(error or tr("The media encoder could not finish."))
                    else:
                        size = output.file.stat().st_size
                        if size == 0 or (limit and size > limit):
                            raise ValueError(tr("The output did not meet the requested size."))
                        if source_signature(entry.path) != entry.info["signature"]:
                            raise ValueError(tr("The source changed. Review the file and save again."))
                        output.publish()
                        entry.output = target
                        entry.row.setText(2, target.suffix[1:].upper() + " · " + display_size(size))
                        entry.row.setToolTip(2, str(target))
                        self.saved += 1
                        if self.total == 1:
                            difference = size - entry.info["size"]
                            summary = tr("Copy saved. %1 smaller.") if difference < 0 else tr("Copy saved. %1 larger.")
                            self.message.setText(summary.replace("%1", display_size(abs(difference)))
                                                 if difference else tr("Copy saved at the original size."))
                except (ValueError, OSError) as problem:
                    try:
                        changed = source_signature(entry.path) != entry.info["signature"]
                    except OSError:
                        changed = True
                    if changed:
                        entry.info = None
                        entry.inspected = False
                    self.failed += 1
                    self.row_error(entry, str(problem))
                finally:
                    output.close()
                self.export_next()
            self.worker(["encode", entry.path, output.file, self.quality.currentIndex(), self.edge.value(),
                         limit, int(self.audio.isChecked()), "--source-info"], saved, line_received=progress,
                        input_data=json.dumps(entry.info).encode())
            return
        self.exporting = False
        if self.cancelled:
            self.message.setText(tr("Cancelled. %1 of %2 copies saved.").replace("%1", str(self.saved)).replace("%2", str(self.total)))
        elif self.total > 1:
            self.message.setText(tr("Saved %1 of %2 copies.").replace("%1", str(self.saved)).replace("%2", str(self.total)))
        self.update_controls()
        self.inspect_next()

    def stop_job(self):
        if self.job:
            pid = self.job.processId()
            if pid > 0:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    self.job.kill()
            else:
                self.job.kill()

    def cancel_export(self):
        if self.exporting:
            self.cancelled = True
            while self.plans:
                entry, _ = self.plans.popleft()
                entry.row.setText(2, tr("Cancelled"))
            self.stop_job()

    def close_jobs(self):
        self.closing = True
        job = self.job
        if self.exporting:
            self.cancel_export()
        else:
            self.stop_job()
        if job:
            job.waitForFinished(2500)
