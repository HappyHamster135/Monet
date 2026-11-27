"""Capture setup and a trim/export editor that stay in their host surface."""
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QProcess, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QLabel, QSlider, QVBoxLayout)
from actions import tr
from notch_pages import Page, label, button, row
from screen_selection import ScreenSelection


class ScreenshotPage(ScreenSelection):
    def __init__(self, host, dismiss):
        super().__init__(host, 'screenshot')
        self.inline_dismiss = dismiss
        saved = host.settings.value('notchLastScreenshot','')
        self.file = Path(saved) if isinstance(saved,str) and saved and Path(saved).is_file() else None
        self.box = QVBoxLayout(self)
        self.mode = QComboBox()
        for name, flag in [('Region', '--region'), ('Window', '--activewindow'), ('Whole desktop', '--fullscreen')]:
            self.mode.addItem(tr(name), flag)
        self.mode.setCurrentIndex(max(0,self.mode.findData(host.settings.value('notchScreenshotArea','--region'))))
        self.box.addWidget(label(tr('Capture area'), True)); self.box.addWidget(self.mode)
        self.pointer = QCheckBox(tr('Include pointer')); self.box.addWidget(self.pointer)
        self.pointer.setChecked(host.settings.value('notchScreenshotPointer',False,type=bool))
        self.mode.activated.connect(lambda _:self.save_options())
        self.pointer.clicked.connect(self.save_options)
        self.folder_button=button(tr('Choose save folder…'),self.choose_folder); self.box.addWidget(self.folder_button)
        self.preview = QLabel(); self.preview.setAlignment(Qt.AlignCenter); self.preview.setFixedHeight(140)
        self.preview.hide(); self.box.addWidget(self.preview)
        self.message = label(tr('The notch hides while selecting. Return here to copy your capture.'), True)
        self.box.addWidget(self.message)
        self.box.addWidget(button(tr('Take screenshot'), lambda: self.pick(True), True))
        self.copy = button(tr('Copy image'), self.copy_image); self.copy.setEnabled(False); self.box.addWidget(self.copy)
        self.box.addStretch()
        if self.file:
            self.copy.setEnabled(True); self.preview.show(); self.update_preview()
            self.message.setText(tr('Saved: ')+self.file.name)

    def save_options(self, *_):
        self.owner.settings.setValue('notchScreenshotArea',self.mode.currentData())
        self.owner.settings.setValue('notchScreenshotPointer',self.pointer.isChecked())
        self.owner.settings.sync()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self,tr('Save screenshots in'),self.owner.settings.value('notchScreenshotFolder',''))
        if folder:
            self.owner.settings.setValue('notchScreenshotFolder',folder)
            self.owner.settings.sync()
            self.message.setText(tr('Save folder: ')+folder)

    def capture(self):
        folder = Path(self.owner.settings.value('notchScreenshotFolder', '') or
                      Path(QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)) / 'Screenshots')
        try: folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.finish(tr('Could not create the screenshot folder.')); return
        target = folder / ('Screenshot '+datetime.now().strftime('%Y-%m-%d %H.%M.%S ')+uuid4().hex[:8]+'.png')
        args = ['spectacle','--new-instance','--background','--nonotify','--output',str(target),self.mode.currentData()]
        if self.pointer.isChecked(): args += ['--pointer']
        def done(_):
            if target.is_file():
                self.file = target; self.copy.setEnabled(True); self.preview.show(); self.update_preview()
                self.owner.settings.setValue('notchLastScreenshot',str(target)); self.owner.settings.sync()
                self.message.setText(tr('Saved: ')+target.name)
                self.finish(tr('Screenshot saved.'))
            else: self.finish(tr('Screenshot cancelled.'))
        self.owner.worker(args, done, lambda _: self.finish(tr('Could not capture the screen.')))

    def update_preview(self):
        if self.file:
            pixmap = QPixmap(str(self.file))
            self.preview.setPixmap(pixmap.scaled(max(32,self.width()-24),140,Qt.KeepAspectRatio,Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event); self.update_preview()

    def copy_image(self):
        if self.file:
            image = QImage(str(self.file))
            if not image.isNull(): QApplication.clipboard().setImage(image); self.message.setText(tr('Image copied.'))


class ClipEditor(Page):
    """Non-destructive trim/export. The source recording is never overwritten."""
    def __init__(self, host, back):
        super().__init__(host)
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.file, self.job, self.export_file = None, None, None
        self.player = QMediaPlayer(self); self.audio = QAudioOutput(self); self.player.setAudioOutput(self.audio)
        self.preview = QVideoWidget(); self.preview.setMinimumWidth(0); self.preview.setFixedHeight(140)
        self.player.setVideoOutput(self.preview)
        row(self.layout_box, button(tr('Back to recording'), back), button(tr('Choose video…'), self.choose))
        self.name = label(tr('Choose a local recording to trim.'), True); self.layout_box.addWidget(self.name)
        self.layout_box.addWidget(self.preview)
        self.play = button(tr('Play / pause'), self.toggle); self.layout_box.addWidget(self.play)
        self.seek = QSlider(Qt.Horizontal); self.seek.setAccessibleName(tr('Video position')); self.layout_box.addWidget(self.seek)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(lambda n: self.seek.setValue(n) if not self.seek.isSliderDown() else None)
        self.starts, self.ends = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, title in [(self.starts,'Start (seconds)'),(self.ends,'End (seconds)')]:
            spin.setDecimals(2); spin.setRange(0,86400); spin.setAccessibleName(tr(title))
            self.layout_box.addWidget(label(tr(title),True)); self.layout_box.addWidget(spin)
        self.format = QComboBox(); self.format.addItem('MP4','.mp4'); self.format.addItem('GIF','.gif')
        self.layout_box.addWidget(label(tr('Export format'),True)); self.layout_box.addWidget(self.format)
        self.mute = QCheckBox(tr('Remove audio')); self.layout_box.addWidget(self.mute)
        self.save = button(tr('Export trimmed copy…'), self.export, True); self.layout_box.addWidget(self.save)
        self.cancel = button(tr('Cancel export'), self.cancel_export); self.cancel.hide(); self.layout_box.addWidget(self.cancel)
        self.message = label('',True); self.layout_box.addWidget(self.message)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.errorOccurred.connect(lambda *_: self.message.setText(tr('Could not play this video. Choose another recording.')))
        self.save.setEnabled(False)

    def choose(self):
        if self.job: return
        name, _ = QFileDialog.getOpenFileName(self, tr('Choose recording'), '', tr('Video (*.mp4 *.webm *.mkv *.mov *.m4v)'))
        if name: self.open_file(Path(name))

    def open_file(self, path):
        if self.job or not path.is_file(): return
        self.file = path; self.name.setText(path.name); self.player.stop(); self.starts.setValue(0)
        self.save.setEnabled(False); self.player.setSource(QUrl.fromLocalFile(str(path)))

    def duration_changed(self, ms):
        self.seek.setRange(0,ms); self.starts.setMaximum(ms/1000); self.ends.setMaximum(ms/1000)
        self.ends.setValue(ms/1000); self.save.setEnabled(ms > 0 and not self.job)

    def toggle(self):
        from PySide6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() == QMediaPlayer.PlayingState: self.player.pause()
        else: self.player.play()

    def hideEvent(self, event):
        self.player.pause(); super().hideEvent(event)

    def export(self):
        if self.job or not self.file: return
        start, end = round(self.starts.value()*1000), round(self.ends.value()*1000)
        if not 0 <= start < end <= self.player.duration():
            self.message.setText(tr('End must be after start and within the recording.')); return
        suffix = self.format.currentData()
        name, _ = QFileDialog.getSaveFileName(self,tr('Export trimmed copy'),str(self.file.with_name(self.file.stem+' trimmed'+suffix)), '*'+suffix,
                                             options=QFileDialog.DontConfirmOverwrite)
        if not name: return
        target = Path(name)
        if target.suffix.lower() != suffix: target = Path(str(target)+suffix)
        from recording_export import ExportFile, export_command
        try:
            output = ExportFile(target)
            command = export_command(self.file, output.file, start, end, 1, None, self.mute.isChecked())
        except (OSError,ValueError):
            self.message.setText(tr('Choose a new filename in a writable folder. Existing files are kept.')); return
        self.export_file = output
        job = self.job = QProcess(self); self.save.setEnabled(False); self.cancel.show()
        self.message.setText(tr('Exporting…')); self.cancelled = False
        job.readyReadStandardOutput.connect(lambda: job.readAllStandardOutput())
        job.readyReadStandardError.connect(lambda: job.readAllStandardError())
        def done(ok):
            if self.job is not job: return
            self.job = None; self.cancel.hide(); self.save.setEnabled(True)
            try:
                if not ok or self.cancelled: raise ValueError()
                output.publish(); self.message.setText(tr('Saved: ')+target.name)
            except (OSError,ValueError): self.message.setText(tr('Export cancelled.') if self.cancelled else tr('Could not export. Your original recording is unchanged.'))
            finally: output.close(); self.export_file = None; job.deleteLater()
        job.finished.connect(lambda code,status: done(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda error: done(False) if error == QProcess.FailedToStart else None)
        job.start(command[0],command[1:])

    def cancel_export(self):
        if self.job: self.cancelled = True; self.job.kill()
