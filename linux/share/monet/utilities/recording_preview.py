"""Present SDR decoder buffers directly at the size needed by the recording editor."""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache

from PySide6.QtCore import QRect, QRectF, QSize, QSizeF, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPainter
from PySide6.QtMultimedia import QVideoFrame, QVideoFrameFormat, QVideoSink
from PySide6.QtWidgets import QGraphicsObject


F = QVideoFrameFormat
# Plane subsampling (horizontal, vertical, bytes per sample).
LAYOUTS = {
    F.Format_YUV420P: ("yuv420p", ((1, 1, 1), (2, 2, 1), (2, 2, 1))),
    F.Format_NV12: ("nv12", ((1, 1, 1), (2, 2, 2))),
    F.Format_NV21: ("nv21", ((1, 1, 1), (2, 2, 2))),
    F.Format_YUV422P: ("yuv422p", ((1, 1, 1), (2, 1, 1), (2, 1, 1))),
}
PLANES = C.c_void_p * 4
STRIDES = C.c_int * 4


@lru_cache(maxsize=1)
def libraries():
    """Use the host FFmpeg's public ABI. Qt can present the frame on its own."""
    try:
        path, util = find_library("swscale"), find_library("avutil")
        if not path or not util:
            return None
        sws, av = C.CDLL(path), C.CDLL(util)
        ptr, integer = C.c_void_p, C.c_int
        sws.sws_getContext.argtypes = [integer] * 7 + [ptr, ptr, ptr]
        sws.sws_getContext.restype = ptr
        sws.sws_freeContext.argtypes = [ptr]
        sws.sws_freeContext.restype = None
        sws.sws_getCoefficients.argtypes = [integer]
        sws.sws_getCoefficients.restype = ptr
        sws.sws_setColorspaceDetails.argtypes = [ptr, ptr, integer, ptr, integer, integer, integer, integer]
        sws.sws_setColorspaceDetails.restype = integer
        sws.sws_scale.argtypes = [ptr, PLANES, STRIDES, integer, integer, PLANES, STRIDES]
        sws.sws_scale.restype = integer
        av.av_get_pix_fmt.argtypes = [C.c_char_p]
        av.av_get_pix_fmt.restype = integer
        names = {"rgba", *(name for name, _ in LAYOUTS.values())}
        return sws, {name: av.av_get_pix_fmt(name.encode("ascii")) for name in names}
    except (OSError, AttributeError):
        return None


class FrameScaler:
    def __init__(self):
        self.context = None
        self.params = None
        self.buffers = {}

    def close(self, *_):
        if self.context:
            libraries()[0].sws_freeContext(self.context)
        self.context = self.params = None
        self.buffers.clear()

    def configure(self, fmt, output, name):
        bindings = libraries()
        if not bindings:
            return False
        sws, ids = bindings
        space = fmt.colorSpace()
        # Qt assumes BT.709 for HD and BT.601 for SD when the source omits it.
        hd = space == F.ColorSpace_BT709 or (space == F.ColorSpace_Undefined and fmt.frameHeight() > 576)
        matrix = 1 if hd else 5  # SWS_CS_ITU709 / SWS_CS_ITU601
        full = fmt.colorRange() == F.ColorRange_Full
        params = (fmt.frameWidth(), fmt.frameHeight(), ids[name], output.width(), output.height(), ids["rgba"])
        key = (params, matrix, full)
        if key != self.params:
            self.close()
            self.params = key
            if min(params) < 0:
                return False
            self.context = sws.sws_getContext(*params, 2, None, None, None)  # SWS_BILINEAR
            if self.context:
                table = sws.sws_getCoefficients(matrix)
                if sws.sws_setColorspaceDetails(self.context, table, int(full), table, 1, 0, 1 << 16, 1 << 16) < 0:
                    sws.sws_freeContext(self.context)
                    self.context = None
        return bool(self.context)

    def image(self, frame, output):
        fmt = frame.surfaceFormat()
        layout = LAYOUTS.get(fmt.pixelFormat())
        # Qt handles texture-backed frames, HDR, subtitles and presentation transforms.
        if (not layout or output.isEmpty() or frame.handleType() != QVideoFrame.NoHandle or frame.subtitleText()
                or frame.rotation().value or frame.mirrored() or fmt.rotation().value or fmt.isMirrored()
                or fmt.scanLineDirection() != F.TopToBottom or fmt.viewport() != QRect(0, 0, frame.width(), frame.height())
                or fmt.colorSpace() not in (F.ColorSpace_Undefined, F.ColorSpace_BT601, F.ColorSpace_BT709)
                or fmt.colorTransfer() not in (F.ColorTransfer_Unknown, F.ColorTransfer_BT601, F.ColorTransfer_BT709)):
            return QImage()
        name, planes = layout
        if frame.planeCount() != len(planes) or not self.configure(fmt, output, name) or not frame.map(QVideoFrame.ReadOnly):
            return QImage()
        try:
            src, strides = PLANES(), STRIDES()
            for i, (dx, dy, sample) in enumerate(planes):
                row_bytes = ((frame.width() + dx - 1) // dx) * sample
                rows = (frame.height() + dy - 1) // dy
                stride, data = frame.bytesPerLine(i), frame.bits(i)
                used = stride * (rows - 1) + row_bytes
                if data is None or stride < row_bytes or data.nbytes < used:
                    return QImage()
                # SIMD kernels may read past the final visible sample. Qt can
                # also supply an exactly sized plane without decoder padding.
                if data.readonly or data.nbytes < used + 64:
                    buf = self.buffers.get(i)
                    if buf is None or len(buf) != used + 64:
                        buf = self.buffers[i] = bytearray(used + 64)
                    memoryview(buf)[:used] = data[:used]
                    data = buf
                src[i] = C.addressof(C.c_ubyte.from_buffer(data))
                strides[i] = stride
            # FFmpeg's SIMD scaler benefits from aligned scanlines. Keep the
            # padding outside the visible picture and let Qt own the result.
            width, height = output.width(), output.height()
            padded_width = (width + 15) & ~15
            image = QImage(padded_width, height + 1, QImage.Format_RGBA8888)
            if image.isNull():
                return image
            dest = PLANES(C.addressof(C.c_ubyte.from_buffer(image.bits())))
            count = libraries()[0].sws_scale(self.context, src, strides, 0, frame.height(), dest,
                                               STRIDES(image.bytesPerLine()))
            return image.copy(0, 0, width, height) if count == height else QImage()
        finally:
            frame.unmap()


class PreviewVideo(QGraphicsObject):
    nativeSizeChanged = Signal()

    def __init__(self, needs_image):
        super().__init__()
        self.needs_image = needs_image
        self.scaler = FrameScaler()
        self.destroyed.connect(self.scaler.close)
        self.frame = QVideoFrame()
        self.frame_number = 0
        self.size = QSize()
        self.output = QSize()
        self.image = QImage()
        self.options = QVideoFrame.PaintOptions()
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self.present)

    def videoSink(self):
        return self.sink

    def nativeSize(self):
        return QSizeF(self.size)

    def boundingRect(self):
        return QRectF(0, 0, self.size.width(), self.size.height()) if not self.size.isEmpty() else QRectF()

    @Slot(QVideoFrame)
    def present(self, frame):
        self.frame = QVideoFrame(frame)
        self.frame_number += 1
        self.output = QSize()
        self.image = QImage()
        fmt = frame.surfaceFormat()
        size = fmt.viewport().size()
        if (fmt.rotation().value + frame.rotation().value) % 180 == 90:
            size.transpose()
        if size != self.size:
            self.prepareGeometryChange()
            self.size = size
            self.nativeSizeChanged.emit()
        if not frame.isValid():
            self.scaler.close()
        self.update()

    def snapshot(self, limit):
        if not self.frame.isValid() or self.size.isEmpty() or limit.isEmpty():
            return QImage()
        size = self.size.scaled(limit, Qt.KeepAspectRatio).boundedTo(self.size).expandedTo(QSize(1, 1))
        if size == self.output and not self.image.isNull():
            return self.image
        result = self.scaler.image(self.frame, size)
        return result if not result.isNull() else self.qt_image(size)

    def qt_image(self, size):
        image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        if not image.isNull():
            image.fill(Qt.black)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            self.frame.paint(painter, QRectF(image.rect()), self.options)
            painter.end()
        return image

    def paint(self, painter, option, widget=None):
        if not self.frame.isValid() or self.size.isEmpty():
            return
        rect = self.boundingRect()
        target = painter.deviceTransform().mapRect(rect).size().toSize()
        size = self.size.scaled(target, Qt.KeepAspectRatio).boundedTo(self.size).expandedTo(QSize(1, 1))
        if self.output != size:
            self.output = size
            self.image = self.scaler.image(self.frame, size)
        if self.image.isNull() and self.needs_image():
            self.image = self.qt_image(size)
        if self.image.isNull():
            self.frame.paint(painter, rect, self.options)
        else:
            painter.drawImage(rect, self.image)
