"""A user-initiated HTTP speed test with bounded transfers and cancellable Qt I/O."""
import statistics
import time
from uuid import uuid4

from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from actions import tr


class SpeedTest(QObject):
    changed = Signal()
    sample_seconds = 5
    max_bytes = 100_000_000
    max_chunk = 16_000_000
    first_chunk = 128_000

    def __init__(self, parent=None, *, origin="https://speed.cloudflare.com"):
        super().__init__(parent)
        self.origin = origin
        self.manager = QNetworkAccessManager(self)
        self.manager.setAutoDeleteReplies(True)
        self.manager.finished.connect(self.finished)
        self.reply = None
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.expired)
        self.phase = "idle"
        self.results = {}
        self.error = ""

    @property
    def running(self):
        return self.phase in ("latency", "download", "upload")

    def start(self):
        if self.running:
            return
        self.manager.clearConnectionCache()
        self.results = {}
        self.error = ""
        self.probes = []
        self.phase = "latency"
        self.request(0)
        self.changed.emit()

    def request(self, size):
        self.size = size
        self.read_bytes = 0
        self.uploaded = 0
        self.snippet = b""
        upload = self.phase == "upload"
        path = "/__up?" if upload else f"/__down?bytes={size}&"
        request = QNetworkRequest(QUrl(self.origin + path + "nonce=" + uuid4().hex))
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.ManualRedirectPolicy)
        request.setAttribute(QNetworkRequest.CookieLoadControlAttribute, QNetworkRequest.Manual)
        request.setAttribute(QNetworkRequest.CookieSaveControlAttribute, QNetworkRequest.Manual)
        request.setRawHeader(b"Cache-Control", b"no-store")
        request.setRawHeader(b"Accept-Encoding", b"identity")
        self.started = time.monotonic()
        if upload:
            request.setRawHeader(b"Content-Type", b"application/octet-stream")
            reply = self.manager.post(request, QByteArray(size, 0))
        else:
            reply = self.manager.get(request)
        self.reply = reply
        reply.setReadBufferSize(256 * 1024)
        if upload:
            reply.uploadProgress.connect(self.upload_progress)
        reply.readyRead.connect(self.ready_read)
        self.timeout.start(15000)

    @Slot("qint64", "qint64")
    def upload_progress(self, sent, total):
        if self.reply is self.sender():
            self.uploaded = max(self.uploaded, sent)

    @Slot()
    def ready_read(self):
        self.read(self.sender())

    def read(self, reply):
        if reply is not self.reply:
            return
        data = reply.readAll()
        self.read_bytes += data.size()
        # A captive portal may return an HTML page with a successful HTTP status.
        if len(self.snippet) < 64:
            self.snippet += bytes(data.first(min(64 - len(self.snippet), data.size())))
        limit = 65536 if self.phase == "upload" else self.size
        if self.read_bytes > limit:
            self.fail(tr("The test server returned an unexpected response."))

    @Slot(QNetworkReply)
    def finished(self, reply):
        if self.reply is not reply:
            return
        self.timeout.stop()
        self.read(reply)
        if self.reply is not reply:
            return
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        ok = reply.error() == QNetworkReply.NoError and status is not None and 200 <= int(status) < 300
        content_type = bytes(reply.rawHeader("Content-Type")).lower()
        html = b"text/html" in content_type or self.snippet.lstrip().lower().startswith((b"<!doctype html", b"<html"))
        self.reply = None
        body_complete = self.uploaded == self.size if self.phase == "upload" else self.read_bytes == self.size
        if not ok or html or not body_complete:
            self.fail(tr("Could not verify the response from the test server. Check the connection and try again."))
            return
        now = time.monotonic()
        elapsed = max(.000001, now - self.started)
        if self.phase == "latency":
            self.probes.append(elapsed * 1000)
            if len(self.probes) < 5:
                self.request(0)
            else:
                # The first request also establishes DNS and TLS.
                self.results["latency"] = statistics.median(self.probes[1:])
                self.begin_transfer("download")
            return

        self.completed += self.size
        duration = max(.000001, now - self.phase_start)
        self.results[self.phase] = self.completed * 8 / duration / 1_000_000
        if duration >= self.sample_seconds or self.completed >= self.max_bytes:
            if self.phase == "download":
                self.begin_transfer("upload")
            else:
                self.phase = "done"
                self.changed.emit()
        else:
            # Aim for a one-second request. Only complete, server-acknowledged
            # requests contribute to the result, including in the upload direction.
            chunk = max(16_000, min(self.size * 8, int(self.size / elapsed), self.max_chunk))
            self.request(min(chunk, self.max_bytes - self.completed))
            self.changed.emit()

    def begin_transfer(self, phase):
        self.phase = phase
        self.completed = 0
        self.phase_start = time.monotonic()
        self.request(min(self.first_chunk, self.max_bytes))
        self.changed.emit()

    def discard_reply(self):
        self.timeout.stop()
        reply, self.reply = self.reply, None
        if reply is not None:
            reply.abort()

    def fail(self, message):
        self.discard_reply()
        self.results.pop(self.phase, None)
        self.phase = "failed"
        self.error = message
        self.changed.emit()

    def expired(self):
        if self.running:
            self.fail(tr("The test server took too long to respond."))

    def cancel(self):
        if self.running:
            self.discard_reply()
            self.results.pop(self.phase, None)
            self.phase = "cancelled"
            self.changed.emit()
