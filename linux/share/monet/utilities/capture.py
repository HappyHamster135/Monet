"""A camera mirror and user-selected Wayland window previews. Streams stop on close."""
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QTransform
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QPushButton, QRubberBand, QVBoxLayout

class Selection(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.crop = None
        self.origin = None
        self.band = QRubberBand(QRubberBand.Rectangle, self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap() and not self.crop:
            self.origin = event.position().toPoint()
            self.band.setGeometry(QRect(self.origin, QSize()))
            self.band.show()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if self.origin is None:
            return
        self.band.hide()
        size = self.pixmap().deviceIndependentSize().toSize()
        bounds = QRect(QPoint((self.width()-size.width())//2, (self.height()-size.height())//2), size)
        chosen = self.band.geometry().intersected(bounds)
        if chosen.width() >= 8 and chosen.height() >= 8:
            self.crop = QRectF((chosen.x()-bounds.x())/size.width(), (chosen.y()-bounds.y())/size.height(),
                               chosen.width()/size.width(), chosen.height()/size.height())
        self.origin = None

class Preview(QDialog):
    def __init__(self, parent, camera):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Camera mirror" if camera else "Watch a window")
        self.resize(420, 300)
        self.camera = camera
        self.image = (QLabel if camera else Selection)("Starting camera…" if camera else "Choose a window or screen in the sharing picker.")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(80, 60)
        self.image.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.image, 1)
        self.alert = QCheckBox("Alert when the picture changes")
        self.previous = None
        self.alert.toggled.connect(lambda _: setattr(self, "previous", None))
        self.alert.setVisible(not camera)
        layout.addWidget(self.alert)
        self.stream = None
        self.source = None
        if camera:
            self.session = QMediaCaptureSession(self)
            self.sink = QVideoSink(self)
            self.session.setVideoSink(self.sink)
            self.source = QCamera(QMediaDevices.defaultVideoInput(), self)
            self.session.setCamera(self.source)
            self.source.errorOccurred.connect(lambda *args: self.image.setText(self.source.errorString()))
        else:
            reset = QPushButton("Show full window")
            reset.setToolTip("Drag across the preview to watch a smaller region.")
            reset.clicked.connect(lambda: setattr(self.image, "crop", None))
            layout.addWidget(reset)
            from watch import WindowStream
            self.stream = WindowStream(self.image.setText)
        self.frames = QTimer(self)
        self.frames.setInterval(85 if camera else 200)
        self.frames.timeout.connect(self.draw)
        (self.source or self.stream).start()
        self.frames.start()

    def draw(self):
        if self.stream:
            picture = self.stream.image()
        else:
            frame = self.sink.videoFrame()
            picture = frame.toImage() if frame.isValid() else None
        if picture is None or picture.isNull():
            return
        crop = getattr(self.image, "crop", None)
        if crop:
            picture = picture.copy(round(crop.x()*picture.width()), round(crop.y()*picture.height()),
                max(1,round(crop.width()*picture.width())), max(1,round(crop.height()*picture.height())))
        if self.alert.isChecked():
            sample = picture.scaled(16, 16, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
            pixels = bytes(sample.constBits())
            if self.previous and sum(abs(a-b) for a,b in zip(self.previous, pixels)) > len(pixels) * 14:
                self.alert.setChecked(False)
                from PySide6.QtCore import QProcess
                QProcess.startDetached("notify-send", ["--app-name=Monet Utilities", "Watched window changed"])
            self.previous = pixels
        preview = QPixmap.fromImage(picture).scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image.setPixmap(preview.transformed(QTransform().scale(-1, 1)) if self.camera else preview)

    def closeEvent(self, event):
        self.frames.stop()
        if self.source:
            self.source.stop()
        if self.stream:
            self.stream.close()
        super().closeEvent(event)
