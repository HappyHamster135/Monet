"""User-selected Wayland window previews. Streams stop on close."""
import time

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRubberBand, QSizePolicy, QVBoxLayout

class Selection(QLabel):
    cropChanged = Signal()

    def __init__(self, text):
        super().__init__(text)
        self.crop = None
        self.origin = None
        self.band = QRubberBand(QRubberBand.Rectangle, self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.pixmap().isNull() and not self.crop:
            self.origin = event.position().toPoint()
            self.band.setGeometry(QRect(self.origin, QSize()))
            self.band.show()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if self.origin is None or event.button() != Qt.LeftButton:
            return
        self.band.hide()
        size = self.pixmap().deviceIndependentSize().toSize()
        bounds = QRect(QPoint((self.width()-size.width())//2, (self.height()-size.height())//2), size)
        chosen = self.band.geometry().intersected(bounds)
        if chosen.width() >= 8 and chosen.height() >= 8:
            self.crop = QRectF((chosen.x()-bounds.x())/size.width(), (chosen.y()-bounds.y())/size.height(),
                               chosen.width()/size.width(), chosen.height()/size.height())
            self.cropChanged.emit()
        self.origin = None

class Preview(QDialog):
    def __init__(self, parent, widget_id=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Watch a window")
        self.resize(420, 300)
        self.bridge = None
        self.text_alert = None
        self.picture = QImage()
        self.full_picture = QImage()
        self.baseline = None
        self.changed_at = None
        self.image = Selection("Choose a window in the sharing picker.")
        self.image.setTextFormat(Qt.PlainText)
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(80, 60)
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.image, 1)
        self.stream = None
        from watch_text import TextAlert
        self.text_alert = TextAlert(self)
        self.text_alert.matched.connect(lambda: self.notify("The text appeared in the watched region"))
        self.text_alert.failed.connect(lambda: self.notify("Text recognition is unavailable"))
        self.words = QLineEdit()
        self.words.setAccessibleName("Text to watch for")
        self.words.setPlaceholderText("Text to watch for…")
        self.words.setMaxLength(180)
        self.words.hide()
        self.words.textChanged.connect(self.reset_alert)
        self.alert = QComboBox()
        self.alert.addItems(["Alerts off", "Alert when the picture changes", "Alert when changes stop", "Alert when text appears"])
        self.alert.setAccessibleName("Window alert")
        self.alert.setToolTip("Changes stop after five seconds without visible movement.")
        self.alert.currentIndexChanged.connect(self.reset_alert)
        layout.addWidget(self.alert)
        layout.addWidget(self.words)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        choose = QPushButton("Choose window…")
        choose.clicked.connect(self.choose_window)
        actions.addWidget(choose)
        self.reset = QPushButton("Show full window")
        self.reset.setToolTip("Drag across the preview to watch a smaller region.")
        self.reset.clicked.connect(self.clear_crop)
        self.reset.setEnabled(False)
        actions.addWidget(self.reset)
        actions.addStretch()
        self.image.cropChanged.connect(self.crop_changed)
        if widget_id:
            from notch_watch import NotchWatch
            self.bridge = NotchWatch(self, widget_id)
            self.pin = QPushButton("Show in notch")
            self.pin.setEnabled(False)
            self.pin.clicked.connect(self.pin_watch)
            actions.addWidget(self.pin)
        from watch import WindowStream
        self.stream = WindowStream(self.capture_failed)
        self.frames = QTimer(self)
        self.frames.setInterval(200)
        self.frames.timeout.connect(self.draw)
        self.frames.start()
        self.stream.start()

    def choose_window(self):
        from watch import WindowStream
        if self.bridge:
            self.bridge.stop()
            self.pin.setEnabled(False)
        self.stream.close()
        self.full_picture = self.picture = QImage()
        self.image.crop = None
        self.reset.setEnabled(False)
        self.alert.setCurrentIndex(0)
        self.image.setText("Choose a window in the sharing picker.")
        self.stream = WindowStream(self.capture_failed)
        self.frames.start()
        self.stream.start()

    def clear_crop(self):
        self.image.crop = None
        self.crop_changed()

    def crop_changed(self):
        self.reset.setEnabled(self.image.crop is not None)
        self.render_watch()
        self.reset_alert()

    def reset_alert(self):
        use_text = self.alert.currentIndex() == 3
        self.words.setVisible(use_text)
        self.text_alert.target(self.words.text() if use_text else "")
        if use_text:
            self.text_alert.observe(self.picture)
        self.baseline = None
        self.changed_at = None

    def watch_alert(self):
        mode = self.alert.currentIndex()
        if not mode or self.picture.isNull():
            return
        if mode == 3:
            self.text_alert.observe(self.picture)
            return
        sample = self.picture.scaled(32, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
        values = bytes(sample.constBits())
        if self.baseline is None:
            self.baseline = values
            return
        # Compare with the last significant change so gradual progress counts too.
        moved = sum(abs(a-b) > 28 for a, b in zip(values, self.baseline)) >= 24
        now = time.monotonic()
        if moved:
            self.baseline = values
            self.changed_at = now
        settled = self.changed_at is not None and now - self.changed_at >= 5
        if (mode == 1 and moved) or (mode == 2 and settled):
            self.notify("Watched window changed" if mode == 1 else "Watched region stopped changing")

    def notify(self, text):
        from PySide6.QtCore import QProcess
        self.alert.setCurrentIndex(0)
        QProcess.startDetached("notify-send", ["--app-name=Monet Utilities", text])

    def pin_watch(self):
        if self.bridge.start():
            self.hide()
        else:
            self.pin.setText("Notch unavailable · Try again")

    def edit(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.render_watch()

    def capture_failed(self, message):
        self.frames.stop()
        self.full_picture = self.picture = QImage()
        self.text_alert.stop()
        if self.bridge:
            was_pinned = self.bridge.active
            self.bridge.stop()
            self.pin.setEnabled(False)
            if was_pinned and not self.isVisible():
                self.notify("Window sharing ended")
                self.close()
                return
        self.image.setText(message)

    def render_watch(self):
        if self.full_picture.isNull():
            return
        crop = self.image.crop
        picture = self.full_picture
        if crop:
            picture = picture.copy(round(crop.x()*picture.width()), round(crop.y()*picture.height()),
                max(1,round(crop.width()*picture.width())), max(1,round(crop.height()*picture.height())))
        changed = self.picture != picture
        self.picture = picture
        if self.bridge:
            self.pin.setEnabled(True)
            if changed:
                self.bridge.changed()
        if self.isVisible():
            self.image.setPixmap(QPixmap.fromImage(picture).scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


    def draw(self):
        frame = self.stream.image()
        if frame is not None and not frame.isNull():
            self.full_picture = frame
            self.render_watch()
            self.watch_alert()
        elif self.changed_at is not None and self.alert.currentIndex() == 2:
            # Some players send no new frames at all once a progress display settles.
            if time.monotonic() - self.changed_at >= 5:
                self.watch_alert()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.stream and not self.full_picture.isNull():
            self.render_watch()

    def closeEvent(self, event):
        self.frames.stop()
        if self.bridge:
            self.bridge.stop()
        if self.text_alert:
            self.text_alert.stop()
        if self.stream:
            self.stream.close()
        super().closeEvent(event)
