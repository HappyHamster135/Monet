"""On-demand screen capture and non-destructive editing of local recordings."""
from datetime import datetime
from pathlib import Path
import subprocess
from uuid import uuid4

from shiboken6 import isValid
from PySide6.QtCore import QProcess, QRectF, QSettings, QSignalBlocker, QSize, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QUndoCommand, QUndoStack
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer, QVideoFrame
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QSizePolicy, QSlider, QStyle, QToolButton, QVBoxLayout, QWidget)

from actions import tr
from recording_export import ExportFile, export_command
from recording_preview import PreviewVideo
from recording_zoom import FULL, Zoom, active_index


def clock(ms):
    seconds, fraction = divmod(max(0, int(ms)), 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02}.{fraction:03}"


class Picture(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.video = PreviewVideo(lambda: any(layer.kind == "blur" for layer in self.active_layers()))
        self.scene().addItem(self.video)
        self.video.nativeSizeChanged.connect(self.fit)
        self.setBackgroundBrush(QBrush(QColor("#171717")))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumSize(160, 100)
        self.origin = None
        self.layers = []
        self.blur_key = None
        self.blur_patches = {}
        self.playhead = 0
        self.crop = None
        self.choosing = False
        self.changed = lambda: None
        self.zooms = []
        self.view = QRectF()
        self.media_clock = lambda: self.playhead
        self.playing = False
        self.motion_timer = QTimer(self)
        self.motion_timer.setInterval(33)
        self.motion_timer.setTimerType(Qt.PreciseTimer)
        self.motion_timer.timeout.connect(self.fit)

    def fit(self, force=False):
        size = self.video.nativeSize()
        if size.isEmpty():
            self.motion_timer.stop()
            return
        bounds = FULL
        self.video.zoom_preview_width = 0
        moving = False
        if self.zooms and not self.choosing:
            bounds = self.crop or FULL
            # A still image can span a long interval in a variable-rate
            # capture. Move on the playback clock, including between frames.
            ms = self.media_clock()
            index = active_index(self.zooms, ms)
            if index is not None:
                zoom = self.zooms[index]
                rise, fall = zoom.ramps()
                moving = self.playing and (ms < zoom.start+rise or ms > zoom.end-fall)
                # Keep one preview scaler through the ramp. Rebuilding it for
                # every fractional change wastes time on high-resolution takes.
                viewport = self.viewport()
                density = min((viewport.width()-4)/(size.width()*bounds[2]),
                              (viewport.height()-4)/(size.height()*bounds[3]))
                self.video.zoom_preview_width = max(1, round(size.width()*density*zoom.amount*viewport.devicePixelRatioF()))
                bounds = zoom.viewport(ms, bounds)
        if moving != self.motion_timer.isActive():
            if moving:
                self.motion_timer.start()
            else:
                self.motion_timer.stop()
        x, y, w, h = bounds
        view = QRectF(x*size.width(), y*size.height(), w*size.width(), h*size.height())
        if force or self.view != view:
            self.view = view
            self.setSceneRect(view)
            self.fitInView(view, Qt.KeepAspectRatio)
            self.centerOn(view.center())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit(True)

    def drawForeground(self, painter, rect):
        if self.layers:
            self.draw_layers(painter)
        if self.zooms and not self.choosing and not self.view.isEmpty():
            # Fit the edited viewport into the same letterbox as the export.
            outside = QPainterPath()
            outside.addRect(rect.united(self.view))
            outside.addRect(self.view)
            painter.fillPath(outside, self.backgroundBrush())
            return
        if not self.crop:
            return
        scene = self.video.boundingRect()
        x, y, width, height = self.crop
        selection = QRectF(x*scene.width(), y*scene.height(), width*scene.width(), height*scene.height())
        mask = QPainterPath()
        mask.addRect(scene)
        mask.addRect(selection)
        painter.fillPath(mask, QColor(0, 0, 0, 155))
        painter.setPen(QPen(Qt.white, 0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(selection)

    def active_layers(self):
        if not self.video.frame.isValid():
            return []
        ms = self.video.frame.startTime() // 1000
        if ms < 0:
            ms = self.playhead
        return [layer for layer in self.layers if layer.start <= ms < layer.end]

    def draw_layers(self, painter):
        from recording_layers import blur_patches, paint_layers
        layers = self.active_layers()
        if not layers:
            return
        size = self.video.nativeSize().toSize()
        if size.isEmpty():
            return
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if any(layer.kind == "blur" for layer in layers):
            limit = self.viewport().size().boundedTo(QSize(1200, 800))
            preview = size.scaled(limit, Qt.KeepAspectRatio).expandedTo(QSize(1, 1))
            key = (self.video.frame_number, size, preview, tuple(layers))
            if key != self.blur_key:
                frame = self.video.image
                if frame.isNull():
                    frame = self.video.snapshot(preview)
                self.blur_patches = blur_patches(frame, preview, layers, size)
                self.blur_key = key
        paint_layers(painter, size, layers, size, self.blur_patches)
        painter.restore()

    def set_layers(self, layers):
        self.layers = layers
        self.blur_key = None
        self.blur_patches = {}
        self.viewport().update()

    def set_zooms(self, zooms):
        self.zooms = sorted(zooms, key=lambda zoom: zoom.start)
        self.fit()
        self.viewport().update()

    def choose(self, on):
        self.choosing = on
        self.fit()
        self.origin = None
        self.viewport().setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)

    def reset_crop(self):
        self.crop = None
        self.choose(False)
        self.viewport().update()
        self.changed()

    def mousePressEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        if self.choosing and event.button() == Qt.LeftButton and self.sceneRect().contains(point):
            self.origin = point
            event.accept()
        else:
            super().mousePressEvent(event)

    def select_to(self, position):
        scene = self.video.boundingRect()
        end = self.mapToScene(position)
        area = QRectF(self.origin, end).normalized().intersected(scene)
        if area.width() >= 2 and area.height() >= 2:
            self.crop = (area.x()/scene.width(), area.y()/scene.height(),
                         area.width()/scene.width(), area.height()/scene.height())
            self.viewport().update()
            return True
        return False

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.select_to(event.position().toPoint())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.origin is not None and event.button() == Qt.LeftButton:
            placed = self.select_to(event.position().toPoint())
            self.choose(not placed)
            self.changed()
        else:
            super().mouseReleaseEvent(event)


class ZoomEdit(QUndoCommand):
    def __init__(self, picture, zooms):
        super().__init__()
        self.picture = picture
        self.before = picture.zooms
        self.after = zooms

    def redo(self):
        self.picture.set_zooms(self.after)

    def undo(self):
        self.picture.set_zooms(self.before)


class Recordings(QWidget):
    def __init__(self, home):
        super().__init__()
        self.home = home
        self.file = None
        self.duration = 0
        self.awaiting_first_frame = False
        self.recorder = None
        self.exporter = None
        self.cancelled = False
        self.close_after_capture = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tools = QHBoxLayout()
        self.record = QToolButton()
        self.record.setText(tr("Record…"))
        self.record.setPopupMode(QToolButton.InstantPopup)
        self.record.setIcon(QIcon.fromTheme("media-record"))
        self.record.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        menu = QMenu(self.record)
        for label, mode in ((tr("Screen region"), "r"), (tr("One window"), "w"), (tr("One screen"), "s")):
            menu.addAction(label, lambda checked=False, mode=mode: self.capture(mode))
        menu.addSeparator()
        self.sound_options = {}
        for key, label in (("videoRecordSystemAudio", tr("Record system sound")),
                           ("videoRecordMicrophone", tr("Record microphone"))):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda on, key=key: self.set_capture_sound(key, on))
            self.sound_options[key] = action
        menu.aboutToShow.connect(self.refresh_capture_sound)
        menu.addSeparator()
        self.auto_edit = menu.addAction(tr("Open editor after recording"))
        self.auto_edit.setCheckable(True)
        self.auto_edit.setChecked(home.settings.value("editAfterRecording", True, type=bool))
        self.auto_edit.toggled.connect(lambda on: home.settings.setValue("editAfterRecording", on))
        self.record.setMenu(menu)
        tools.addWidget(self.record)
        self.browse = QPushButton(tr("Open recording…"), clicked=self.open_dialog)
        tools.addWidget(self.browse)
        self.filename = QLabel()
        self.filename.setTextFormat(Qt.PlainText)
        self.filename.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        tools.addWidget(self.filename, 1)
        layout.addLayout(tools)
        self.picture = Picture()
        self.zoom_history = QUndoStack(self)
        self.zoom_history.setUndoLimit(80)
        self.picture.changed = self.crop_changed
        layout.addWidget(self.picture, 1)
        self.player = QMediaPlayer(self)
        self.picture.media_clock = self.player.position
        self.still_job = None
        self.still_delay = QTimer(self)
        self.still_delay.setSingleShot(True)
        self.still_delay.setInterval(300)
        self.still_delay.timeout.connect(self.load_paused_frame)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoSink(self.picture.video.videoSink())
        self.player.durationChanged.connect(self.set_duration)
        self.player.positionChanged.connect(self.position)
        self.player.mediaStatusChanged.connect(self.state_changed)
        self.picture.video.nativeSizeChanged.connect(self.controls)
        self.player.hasVideoChanged.connect(lambda *_: self.controls())
        self.player.hasAudioChanged.connect(lambda *_: self.controls())
        self.player.errorOccurred.connect(lambda _, why: self.message.setText(why))
        self.editor = QWidget()
        edit = QVBoxLayout(self.editor)
        edit.setContentsMargins(0, 0, 0, 0)
        playback = QHBoxLayout()
        self.play = QToolButton(clicked=self.play_pause)
        self.play.setAccessibleName(tr("Play selection"))
        self.play.setToolTip(tr("Play selection"))
        self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.player.playbackStateChanged.connect(self.playback_changed)
        playback.addWidget(self.play)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setAccessibleName(tr("Recording position"))
        self.seek.valueChanged.connect(self.scrub)
        playback.addWidget(self.seek, 1)
        self.time = QLabel(clock(0))
        playback.addWidget(self.time)
        edit.addLayout(playback)
        trim = QHBoxLayout()
        for start, label, key in ((True, tr("Start"), tr("Set start at playhead")), (False, tr("End"), tr("Set end at playhead"))):
            field = QDoubleSpinBox()
            field.setDecimals(3)
            field.setSingleStep(.1)
            field.setSuffix(tr(" s"))
            field.setKeyboardTracking(False)
            field.setAccessibleName(label)
            if start:
                self.begin = field
            else:
                self.end = field
            trim.addWidget(QLabel(label))
            trim.addWidget(field)
            button = QToolButton()
            button.setIcon(QIcon.fromTheme("go-previous" if start else "go-next",
                                          self.style().standardIcon(QStyle.SP_ArrowLeft if start else QStyle.SP_ArrowRight)))
            button.setToolTip(key)
            button.setAccessibleName(key)
            button.clicked.connect(lambda checked=False, field=field: field.setValue(self.player.position()/1000))
            trim.addWidget(button)
        self.rate = QComboBox()
        self.rate.setAccessibleName(tr("Playback and export speed"))
        for speed in (.5, 1., 1.5, 2.):
            self.rate.addItem(f"{speed:g}×", speed)
        self.rate.setCurrentIndex(1)
        self.rate.currentIndexChanged.connect(lambda _: self.player.setPlaybackRate(self.rate.currentData()))
        trim.addWidget(self.rate)
        trim.addStretch()
        edit.addLayout(trim)
        self.begin.valueChanged.connect(lambda _: self.trim_changed(True))
        self.end.valueChanged.connect(lambda _: self.trim_changed(False))
        options = QHBoxLayout()
        self.crop_button = QPushButton(tr("Crop…"), checkable=True, clicked=self.choose_crop)
        options.addWidget(self.crop_button)
        self.reset = QPushButton(tr("Reset crop"), clicked=self.picture.reset_crop)
        options.addWidget(self.reset)
        self.overlays = QToolButton()
        self.overlays.setText(tr("Overlays"))
        self.overlays.setPopupMode(QToolButton.InstantPopup)
        self.layer_menu = QMenu(self.overlays)
        self.layer_menu.aboutToShow.connect(self.list_layers)
        self.overlays.setMenu(self.layer_menu)
        options.addWidget(self.overlays)
        self.zooms = QToolButton()
        self.zooms.setText(tr("Zooms"))
        self.zooms.setPopupMode(QToolButton.InstantPopup)
        self.zoom_menu = QMenu(self.zooms)
        self.zoom_menu.aboutToShow.connect(self.list_zooms)
        self.zooms.setMenu(self.zoom_menu)
        options.addWidget(self.zooms)
        self.mute = QCheckBox(tr("Mute audio"))
        self.mute.toggled.connect(self.audio.setMuted)
        options.addWidget(self.mute)
        options.addStretch()
        self.save = QPushButton(tr("Export copy…"), clicked=self.save_dialog)
        options.addWidget(self.save)
        edit.addLayout(options)
        layout.addWidget(self.editor)
        status = QHBoxLayout()
        self.message = QLabel(tr("Record your screen or open a recording to edit."))
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        status.addWidget(self.message, 1)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(100)
        self.progress.hide()
        status.addWidget(self.progress)
        self.cancel = QPushButton(tr("Cancel export"), clicked=self.cancel_export)
        self.cancel.hide()
        status.addWidget(self.cancel)
        layout.addLayout(status)
        self.controls()

    def controls(self):
        free = self.recorder is None and self.exporter is None
        self.browse.setEnabled(free)
        self.record.setEnabled(free)
        self.editor.setEnabled(free and self.file is not None and self.duration > 0 and self.player.hasVideo())
        has_picture = not self.picture.video.nativeSize().isEmpty()
        self.crop_button.setEnabled(has_picture)
        self.overlays.setEnabled(has_picture)
        self.zooms.setEnabled(has_picture)
        self.mute.setEnabled(self.player.hasAudio())
        self.reset.setVisible(self.picture.crop is not None)

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Open recording"), QStandardPaths.writableLocation(QStandardPaths.MoviesLocation),
                                              tr("Recordings (*.mp4 *.webm *.mkv *.mov *.m4v)"))
        if path:
            self.open_file(Path(path))

    def open_file(self, path):
        if self.exporter or self.recorder:
            return
        if not path.is_file() or path.suffix.lower() not in (".mp4", ".webm", ".mkv", ".mov", ".m4v"):
            self.message.setText(tr("Choose a local video recording."))
            return
        self.still_delay.stop()
        if self.still_job:
            self.still_job.kill()
        self.player.stop()
        self.player.setSource(QUrl())
        self.file = path.absolute()
        self.filename.setText(self.file.name)
        self.filename.setToolTip(str(self.file))
        self.duration = 0
        self.picture.set_layers([])
        self.zoom_history.clear()
        self.picture.set_zooms([])
        self.picture.reset_crop()
        self.rate.setCurrentIndex(1)
        self.mute.setChecked(False)
        self.awaiting_first_frame = True
        self.message.setText(tr("Opening recording…"))
        self.player.setSource(QUrl.fromLocalFile(str(self.file)))
        self.controls()

    def set_duration(self, ms):
        if ms <= 0:
            return
        old, self.duration = self.duration, ms
        self.seek.setRange(0, min(ms, 2147483647))
        with QSignalBlocker(self.begin), QSignalBlocker(self.end):
            at_end = not old or round(self.end.value()*1000) == old
            self.begin.setRange(0, max(0, ms-1)/1000)
            self.end.setRange(.001, ms/1000)
            if not old:
                self.begin.setValue(0)
            if at_end:
                self.end.setValue(ms/1000)
        self.controls()

    def state_changed(self, state):
        if state == QMediaPlayer.LoadedMedia:
            if self.awaiting_first_frame and self.player.hasVideo():
                self.awaiting_first_frame = False
                QTimer.singleShot(0, self, self.show_first_frame)
            self.message.setText("" if self.player.hasVideo() else tr("This file has no video track."))
        self.controls()

    def show_first_frame(self):
        if self.player.mediaStatus() == QMediaPlayer.LoadedMedia and self.player.playbackState() == QMediaPlayer.StoppedState:
            self.player.pause()
            self.still_delay.start()

    def has_paused_frame(self, ms):
        frame = self.picture.video.frame
        if not frame.isValid():
            return False
        first = frame.startTime() // 1000
        last = frame.endTime() // 1000
        return first < 0 or first <= ms < max(first+1, last)

    def load_paused_frame(self):
        # Sparse H.264 files can buffer several seconds of audio before Qt's
        # paused decoder produces a frame. Fill just the requested still.
        ms = self.player.position()
        if (self.still_job or self.recorder or self.exporter or not self.file or self.player.isPlaying() or not self.isVisible()
                or not self.player.hasVideo() or self.has_paused_frame(ms) or ms >= self.duration):
            return
        source = self.file
        job = self.still_job = QProcess(self)
        def finish(success):
            if not isValid(self) or self.still_job is not job:
                return
            self.still_job = None
            if success and self.file == source and not self.player.isPlaying() and self.player.position() == ms:
                if not self.has_paused_frame(ms):
                    image = QImage.fromData(job.readAllStandardOutput(), "PNG")
                    if not image.isNull():
                        frame = QVideoFrame(image)
                        frame.setStartTime(ms*1000)
                        frame.setEndTime((ms+1)*1000)
                        self.picture.video.present(frame)
            elif self.file != source or self.player.position() != ms:
                self.still_delay.start()
            job.deleteLater()
        job.finished.connect(lambda code, status: finish(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda why: finish(False) if why == QProcess.FailedToStart else None)
        job.start("nice", ["-n", "10", "ffmpeg", "-v", "error", "-nostdin", "-noaccurate_seek",
                           "-ss", f"{ms/1000:.3f}", "-threads", "1", "-protocol_whitelist", "file,pipe",
                           "-i", str(source), "-map", "0:v:0", "-filter_threads", "1",
                           "-vf", "fps=1000:start_time=0", "-frames:v", "1", "-c:v", "png",
                           "-compression_level", "1", "-threads", "1", "-f", "image2pipe", "pipe:1"])

    def trim_changed(self, start):
        a, b = self.bounds()
        if a >= b:
            if start:
                self.end.setValue(min(self.duration, a+1)/1000)
            else:
                self.begin.setValue(max(0, b-1)/1000)
        self.player.pause()
        self.player.setPosition(self.bounds()[0 if start else 1])

    def bounds(self):
        return round(self.begin.value()*1000), round(self.end.value()*1000)

    def play_pause(self):
        if self.player.isPlaying():
            self.player.pause()
        else:
            a, b = self.bounds()
            if not a <= self.player.position() < b:
                self.player.setPosition(a)
            self.player.play()

    def playback_changed(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.picture.playing = playing
        if self.picture.zooms:
            self.picture.fit()
        self.play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause if playing else QStyle.SP_MediaPlay))
        name = tr("Pause") if playing else tr("Play selection")
        self.play.setAccessibleName(name)
        self.play.setToolTip(name)

    def position(self, ms):
        self.picture.playhead = ms
        if not self.player.isPlaying() and self.file and not self.has_paused_frame(ms):
            self.still_delay.start()
        if self.picture.zooms:
            self.picture.fit()
        with QSignalBlocker(self.seek):
            self.seek.setValue(min(ms, 2147483647))
        self.time.setText(clock(ms))
        end = self.bounds()[1]
        if end and ms >= end and self.player.isPlaying():
            self.player.pause()
            self.player.setPosition(end)

    def scrub(self, ms):
        self.player.pause()
        self.player.setPosition(ms)

    def choose_crop(self, on):
        self.player.pause()
        self.picture.choose(on)
        self.message.setText(tr("Drag over the part of the picture to keep.") if on else "")

    def crop_changed(self):
        self.crop_button.setChecked(self.picture.choosing)
        self.reset.setVisible(self.picture.crop is not None)
        self.message.clear()

    def list_zooms(self):
        self.zoom_menu.clear()
        items = self.picture.zooms
        index = active_index(items, self.player.position())
        if index is None:
            self.zoom_menu.addAction(tr("Add zoom at playhead…"), lambda: self.edit_zoom())
        else:
            self.zoom_menu.addAction(tr("Edit zoom at playhead…"), lambda: self.edit_zoom(index))
        if items:
            self.zoom_menu.addSeparator()
        for i, zoom in enumerate(items):
            self.zoom_menu.addAction(f"{clock(zoom.start)} – {clock(zoom.end)}   {zoom.amount:g}×",
                                     lambda checked=False, i=i: self.edit_zoom(i))

        self.zoom_menu.addSeparator()
        self.zoom_menu.addAction(tr("Undo zoom edit"), self.zoom_history.undo).setEnabled(self.zoom_history.canUndo())
        self.zoom_menu.addAction(tr("Redo zoom edit"), self.zoom_history.redo).setEnabled(self.zoom_history.canRedo())

    def zoom_snapshot(self):
        snap = self.picture.video.snapshot(QSize(920, 520))
        layers = self.picture.active_layers()
        if layers and not snap.isNull():
            from recording_layers import composed
            return composed(snap, snap.size(), layers, self.picture.video.nativeSize().toSize())
        return snap

    def edit_zoom(self, index=None):
        from recording_zoom_editor import ZoomDialog
        self.player.pause()
        frame = self.zoom_snapshot()
        if frame.isNull():
            self.message.setText(tr("Play or seek to a frame before adding a zoom."))
            return
        items = list(self.picture.zooms)
        existing = index is not None
        if existing:
            zoom = items[index]
        else:
            start = min(self.player.position(), self.duration-1)
            index = active_index(items, start)
            if index is not None:
                return self.edit_zoom(index)
            index = next((i for i, z in enumerate(items) if z.start > start), len(items))
            limit = items[index].start if index < len(items) else self.duration
            x, y, w, h = self.picture.crop or FULL
            zoom = Zoom(start, min(limit, start+3000), x+w/2, y+h/2)
            items.insert(index, zoom)
        before = items[index-1].end if index else 0
        after = items[index+1].start if index+1 < len(items) else self.duration
        dialog = ZoomDialog(self, zoom, frame, self.picture.crop, before, after, existing)
        seek_preview = existing and not zoom.start <= self.player.position() < zoom.end
        def aim_at_frame(frame):
            if frame.isValid():
                snapshot = self.zoom_snapshot()
                if not snapshot.isNull():
                    dialog.aim.frame = snapshot
                    dialog.aim.update()
        if seek_preview:
            self.picture.video.videoSink().videoFrameChanged.connect(aim_at_frame)
            self.player.setPosition((zoom.start+zoom.end)//2)
        if dialog.exec():
            if dialog.removed:
                del items[index]
            else:
                items[index] = dialog.zoom()
            if items != self.picture.zooms:
                self.zoom_history.push(ZoomEdit(self.picture, items))
            self.message.clear()
        if seek_preview:
            self.picture.video.videoSink().videoFrameChanged.disconnect(aim_at_frame)
        dialog.deleteLater()

    def list_layers(self):
        self.layer_menu.clear()
        for kind, title in (("text", tr("Add caption…")), ("image", tr("Add image…")), ("blur", tr("Blur an area…"))):
            self.layer_menu.addAction(title, lambda checked=False, kind=kind: self.edit_layer(kind))
        if self.picture.layers:
            self.layer_menu.addSeparator()
        for i, layer in enumerate(self.picture.layers):
            name = layer.text.strip().splitlines()[0][:48] if layer.text.strip() else tr("Blur region")
            title = f"{name.replace('&', '&&')}   {clock(layer.start)} – {clock(layer.end)}"
            self.layer_menu.addAction(title, lambda checked=False, i=i: self.edit_layer(index=i))

    def edit_layer(self, kind=None, index=None):
        from recording_layer_editor import LayerDialog
        from recording_layers import Layer
        self.player.pause()
        frame = self.picture.video.snapshot(QSize(920, 500))
        size = self.picture.video.nativeSize().toSize()
        if frame.isNull() or size.isEmpty():
            self.message.setText(tr("Play or seek to a frame before adding an overlay."))
            return
        layers = list(self.picture.layers)
        existing = index is not None
        if not existing:
            a, b = self.bounds()
            start = self.player.position()
            if not a <= start < b:
                start = a
            defaults = {"text": (.15, .76, .70, .15), "image": (.66, .06, .28, .26), "blur": (.30, .34, .40, .28)}
            index = len(layers)
            layers.append(Layer(kind, start, b, defaults[kind], amount=45 if kind == "blur" else 100))
        dialog = LayerDialog(self, layers, index, frame, size, self.player.position(), self.duration, existing)
        if dialog.exec():
            if dialog.removed:
                del dialog.layers[dialog.index]
            self.picture.set_layers(dialog.layers)
            self.message.clear()
        dialog.deleteLater()

    def hideEvent(self, event):
        self.player.pause()
        super().hideEvent(event)

    def save_dialog(self):
        formats = [tr("MP4 video (*.mp4)"), tr("GIF animation (*.gif)")]
        name, selected = QFileDialog.getSaveFileName(self, tr("Export a new copy"), str(self.file.with_name(self.file.stem + "-edited")),
                                                    ";;".join(formats), options=QFileDialog.DontConfirmOverwrite)
        if name:
            target = Path(name)
            suffix = ".gif" if selected == formats[1] else ".mp4"
            if target.suffix.lower() not in (".mp4", ".gif"):
                target = Path(name + suffix)
            self.export_to(target)

    def export_to(self, target):
        if not self.editor.isEnabled() or self.exporter:
            return
        try:
            output = ExportFile(target)
        except FileExistsError:
            self.message.setText(tr("Choose a new filename for the edited copy."))
            return
        except OSError as error:
            self.message.setText(str(error))
            return
        self.player.pause()
        start, end = self.bounds()
        speed = self.rate.currentData()
        layers = []
        try:
            if self.picture.layers:
                from recording_layers import export_layers
                layers = export_layers(self.picture.layers, self.picture.video.nativeSize().toSize(), start, end, output.file.parent)
            size = self.picture.video.nativeSize().toSize()
            fps = self.player.metaData().value(QMediaMetaData.VideoFrameRate) or 0
            command = export_command(self.file, output.file, start, end, speed, self.picture.crop,
                                     self.mute.isChecked(), layers, self.picture.zooms,
                                     (size.width(), size.height()), fps)
            # Large edits can exceed the OS limit on one command argument.
            for option in ("-filter_complex", "-vf"):
                if option in command and len(command[command.index(option)+1]) > 24_000:
                    at = command.index(option)
                    script = output.file.parent / "video-filter.txt"
                    script.write_text(command[at+1], encoding="ascii")
                    command[at:at+2] = ["-/" + option[1:], str(script)]
        except (OSError, ValueError) as error:
            output.close()
            self.message.setText(str(error))
            return
        job = self.exporter = QProcess(self)
        self.cancelled = False
        def progress():
            while job.canReadLine():
                line = bytes(job.readLine()).strip()
                if line.startswith(b"out_time_us="):
                    try:
                        us = int(line.partition(b"=")[2])
                    except ValueError:
                        continue
                    self.progress.setValue(min(99, int(100*us*speed/(1000*(end-start)))))
        job.readyReadStandardOutput.connect(progress)
        def finish(success):
            if not isValid(self) or not isValid(job):
                output.close()
                return
            if self.exporter is not job:
                return
            try:
                if self.cancelled:
                    self.message.setText(tr("Export cancelled."))
                elif success:
                    output.publish()
                    self.message.setText(tr("Saved %1").replace("%1", str(target)))
                else:
                    error = bytes(job.readAllStandardError()).decode(errors="replace").strip()
                    self.message.setText(error[-300:] or tr("Could not export the recording."))
            except FileExistsError:
                self.message.setText(tr("Another file now has that name. Choose a new filename."))
            except OSError as error:
                self.message.setText(str(error))
            finally:
                output.close()
                self.exporter = None
                self.progress.hide()
                self.cancel.hide()
                self.controls()
                job.deleteLater()
        job.finished.connect(lambda code, status: finish(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda why: finish(False) if why == QProcess.FailedToStart else None)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()
        self.cancel.show()
        self.message.setText(tr("Exporting copy…"))
        self.controls()
        job.start(command[0], command[1:])

    def cancel_export(self):
        if self.exporter is not None:
            self.cancelled = True
            self.exporter.kill()

    def capture_settings(self):
        config = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "spectaclerc"
        return QSettings(str(config), QSettings.IniFormat)

    def refresh_capture_sound(self):
        config = self.capture_settings()
        for key, action in self.sound_options.items():
            action.setChecked(config.value("GuiConfig/" + key, False, type=bool))

    def set_capture_sound(self, key, enabled):
        # Use KDE's writer so native settings and their escaping survive an edit.
        try:
            subprocess.run(["kwriteconfig6", "--file", "spectaclerc", "--group", "GuiConfig",
                            "--key", key, "--type", "bool", "true" if enabled else "false"],
                           check=True, timeout=1)
        except (OSError, subprocess.SubprocessError):
            self.refresh_capture_sound()
            self.message.setText(tr("Could not change the recording sound setting."))

    def capture(self, mode):
        if self.recorder or self.exporter or mode not in ("r", "s", "w"):
            return
        config = self.capture_settings()
        directory = QUrl.fromUserInput(str(config.value("VideoSave/videoSaveLocation", "")))
        folder = Path(directory.toLocalFile()) if directory.isLocalFile() else Path(QStandardPaths.writableLocation(QStandardPaths.MoviesLocation))/tr("Screencasts")
        self.player.pause()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.message.setText(str(error))
            return
        preferred = str(config.value("VideoSave/preferredVideoFormat", "WebM_VP9"))
        suffix = ".mp4" if preferred in ("MP4_H264", "2") else ".webm"
        target = folder / (tr("Recording") + datetime.now().strftime(" %Y-%m-%d %H.%M.%S ") + uuid4().hex[:12] + suffix)
        job = self.recorder = QProcess(self)
        self.controls()
        self.message.setText(tr("Click the recording indicator in the system tray to finish."))
        self.home.showMinimized()
        def finish(success):
            if not isValid(self) or not isValid(job) or self.recorder is not job:
                return
            self.recorder = None
            job.deleteLater()
            self.controls()
            if self.close_after_capture and not self.home.isVisible():
                self.home.close()
                return
            self.close_after_capture = False
            try:
                saved = success and target.is_file() and target.stat().st_size > 0
            except OSError:
                saved = False
            if not saved or self.auto_edit.isChecked():
                self.home.setWindowState(self.home.windowState() & ~Qt.WindowMinimized)
            if saved and self.auto_edit.isChecked():
                self.home.Open(["recordings"])
                self.open_file(target)
            else:
                self.message.setText(tr("Saved %1").replace("%1", str(target)) if saved else
                                     tr("Recording cancelled.") if success else tr("Could not record the screen."))
                if not saved:
                    self.home.Open(["recordings"])
        job.finished.connect(lambda code, status: finish(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda why: finish(False) if why == QProcess.FailedToStart else None)
        # A private instance returns when its own take finishes or is cancelled,
        # including when another Spectacle process was already serving screenshots.
        QTimer.singleShot(160, self, lambda: job.start("spectacle", ["--new-instance", "--background", "--nonotify",
                                                                    "--record", mode, "--output", str(target)]))
