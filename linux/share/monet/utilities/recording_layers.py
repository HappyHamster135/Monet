"""Timed artwork on the original video canvas, shared by preview and export."""
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter
from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QImageReader, QPainter

from recording_export import ExportLayer


def pixel_rect(box, size):
    x, y, w, h = box
    width, height = size.width(), size.height()
    left, top = min(width - 1, round(x * width)), min(height - 1, round(y * height))
    return QRect(left, top, max(1, round((x + w) * width) - left),
                 max(1, round((y + h) * height) - top))


def read_image(path):
    if not Path(path).is_file():
        return QImage()
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"webp") or size.isEmpty():
        return QImage()
    if max(size.width(), size.height()) > 2048:
        reader.setScaledSize(size.scaled(2048, 2048, Qt.KeepAspectRatio).expandedTo(QSize(1, 1)))
    return reader.read()


@dataclass(eq=False)
class Layer:
    kind: str
    start: int
    end: int
    box: tuple
    text: str = ""
    color: str = "#ffffff"
    amount: int = 100
    image: QImage = field(default_factory=QImage)
    _tile: QImage = field(default_factory=QImage, init=False, repr=False)

    def stamp(self, size):
        # Keep one bounded tile per annotation. Moving it or playing another
        # frame does not rasterize the same text or logo again.
        if max(size.width(), size.height()) > 2048:
            size = size.scaled(2048, 2048, Qt.KeepAspectRatio).expandedTo(QSize(1, 1))
        if self._tile.size() == size:
            return self._tile
        tile = QImage(size, QImage.Format_ARGB32_Premultiplied)
        tile.fill(Qt.transparent)
        painter = QPainter(tile)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        area = tile.rect()
        if self.kind == "image":
            if self.image.isNull():
                painter.end()
                self._tile = tile
                return tile
            rect = QRect(area.topLeft(), self.image.size().scaled(size, Qt.KeepAspectRatio))
            rect.moveCenter(area.center())
            painter.setOpacity(self.amount / 100)
            painter.drawImage(rect, self.image)
        else:
            # A dark backing keeps captions legible over moving light and dark footage.
            painter.setBrush(QColor(20, 20, 20, 210))
            painter.setPen(Qt.NoPen)
            radius = min(area.width(), area.height()) * .12
            painter.drawRoundedRect(QRectF(area), radius, radius)
            pad = round(radius * .65)
            inner = area.adjusted(pad, pad, -pad, -pad)
            font = QFont("sans-serif")
            font.setBold(True)
            flags = int(Qt.AlignCenter) | int(Qt.TextWordWrap) | int(Qt.TextWrapAnywhere)
            low, high = 1, max(1, inner.height())
            while low < high:
                mid = (low + high + 1) // 2
                font.setPixelSize(mid)
                needed = QFontMetrics(font).boundingRect(inner, flags, self.text)
                if needed.width() <= inner.width() and needed.height() <= inner.height():
                    low = mid
                else:
                    high = mid - 1
            font.setPixelSize(low)
            painter.setFont(font)
            painter.setPen(QColor(self.color))
            painter.drawText(inner, flags, self.text)
        painter.end()
        self._tile = tile
        return tile

    def sigma(self, height):
        return max(1., self.amount * height / 2000)


def paint_stamps(painter, size, layers, source_size):
    for layer in layers:
        rect = pixel_rect(layer.box, size)
        original = pixel_rect(layer.box, source_size)
        painter.drawImage(rect, layer.stamp(original.size()))


def composed(frame, size, layers, source_size):
    """Paint in order, including anything underneath a later blur region."""
    canvas = frame.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    if canvas.isNull():
        return canvas
    for layer in layers:
        if layer.kind == "blur":
            rect = pixel_rect(layer.box, size)
            patch = canvas.copy(rect)
            raw = Image.frombytes("RGBA", (patch.width(), patch.height()), patch.constBits().tobytes())
            blurred = raw.filter(ImageFilter.GaussianBlur(layer.sigma(size.height())))
            buf = blurred.tobytes()
            image = QImage(buf, patch.width(), patch.height(), patch.width() * 4, QImage.Format_RGBA8888)
            painter = QPainter(canvas)
            painter.drawImage(rect.topLeft(), image)
        else:
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            paint_stamps(painter, size, (layer,), source_size)
        painter.end()
    return canvas


def export_layers(layers, source_size, start, end, directory):
    result = []
    for i, layer in enumerate(layers):
        if layer.end <= start or layer.start >= end:
            continue
        path = None
        if layer.kind != "blur":
            # FFmpeg accepts PAM directly. Writing pixels avoids compressing
            # artwork on the UI thread only to decode it again during export.
            path = Path(directory) / f"layer-{i}.pam"
            tile = layer.stamp(pixel_rect(layer.box, source_size).size()).convertToFormat(QImage.Format_RGBA8888)
            if tile.isNull():
                raise ValueError("Empty overlay image")
            with path.open("xb") as stream:
                header = (f"P7\nWIDTH {tile.width()}\nHEIGHT {tile.height()}\nDEPTH 4\n"
                          "MAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n")
                stream.write(header.encode("ascii"))
                stream.write(tile.constBits())
        result.append(ExportLayer(layer.box, layer.start, layer.end, path, layer.sigma(source_size.height())))
    return result
