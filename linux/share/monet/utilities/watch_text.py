"""Look for a user-selected phrase in changed frames, one local OCR job at a time."""
import sys
import time
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QProcess, QProcessEnvironment, QTimer, Signal
from PySide6.QtGui import QImage


def normalized(text):
    return " ".join(text.casefold().split())


class TextAlert(QObject):
    matched = Signal()
    failed = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.phrase = ""
        self.image = QImage()
        self.revision = 0
        self.submitted = 0
        self.generation = 0
        self.next_read = 0
        self.job_generation = -1
        self.job = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("OMP_THREAD_LIMIT", "1")
        self.job.setProcessEnvironment(env)
        self.job.setProgram("nice")
        self.job.setArguments(["-n", "10", sys.executable, str(Path(__file__).with_name("media.py")), "watch-text"])
        self.job.finished.connect(self.finished)
        self.job.errorOccurred.connect(self.error)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.read)

    def target(self, phrase):
        self.phrase = normalized(phrase)
        self.generation += 1
        self.next_read = 0
        self.timer.stop()
        self.image = QImage()
        if self.job.state() != QProcess.NotRunning:
            self.job.kill()

    def observe(self, image):
        if not self.phrase or image.isNull() or self.image == image:
            return
        self.image = image
        self.revision += 1
        if not self.timer.isActive() and self.job.state() == QProcess.NotRunning:
            self.schedule()

    def schedule(self):
        self.timer.start(max(750, int(1000 * (self.next_read - time.monotonic()))))

    def read(self):
        if not self.phrase or self.image.isNull() or self.revision == self.submitted:
            return
        data = QByteArray()
        buffer = QBuffer(data)
        if not buffer.open(QIODevice.WriteOnly) or not self.image.save(buffer, "PPM"):
            self.failed.emit()
            return
        self.submitted = self.revision
        self.next_read = time.monotonic() + 2.5
        self.job_generation = self.generation
        self.job.start()
        self.job.write(data)
        self.job.closeWriteChannel()

    def finished(self, code, status):
        result = bytes(self.job.readAllStandardOutput()).decode(errors="replace")
        self.job.readAllStandardError()
        if self.phrase and self.generation == self.job_generation:
            if code:
                self.failed.emit()
                return
            if self.phrase in normalized(result):
                self.matched.emit()
                return
        if self.phrase and self.revision != self.submitted:
            self.schedule()

    def error(self, error):
        if self.phrase and error == QProcess.FailedToStart:
            self.failed.emit()

    def stop(self):
        self.target("")
        if self.job.state() != QProcess.NotRunning:
            self.job.waitForFinished(500)
