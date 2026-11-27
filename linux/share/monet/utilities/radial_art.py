"""One antialiased surface for radial artwork; hit regions never clip its paint."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen


class RingGeometry:
    def __init__(self, rect):
        self.bounds = QRectF(rect).adjusted(8, 8, -8, -8)
        self.center = self.bounds.center()
        self.radius = self.bounds.width() / 2
        self.inner = self.radius * .37
        self.hub = QRectF(self.center.x()-self.inner, self.center.y()-self.inner, 2*self.inner, 2*self.inner)

    def point(self, index, ratio, count=8):
        angle = math.tau * index / count - math.pi / 2
        return self.center + QPointF(math.cos(angle), math.sin(angle)) * (self.radius * ratio)

    def wedge(self, index, count):
        sweep = 360 / count
        start = 90 - index * sweep + sweep / 2
        path = QPainterPath()
        path.arcMoveTo(self.bounds, start)
        path.arcTo(self.bounds, start, -sweep)
        path.arcTo(self.hub, start-sweep, sweep)
        path.closeSubpath()
        return path


def paint_ring(painter, geometry, selected=-1, count=8):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    bounds = geometry.bounds
    # Keep every shadow pixel inside the generous input region. No widget mask
    # touches the painted edge, including at fractional device pixel ratios.
    painter.setPen(Qt.NoPen)
    for spread, alpha in ((6, 5), (4, 7), (2, 10)):
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.drawEllipse(bounds.adjusted(-spread, -spread, spread, spread))
    fill = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
    fill.setColorAt(0, QColor('#282d33')); fill.setColorAt(1, QColor('#20252b'))
    painter.setBrush(fill); painter.drawEllipse(bounds)
    if 0 <= selected < count:
        painter.setBrush(QColor('#2d4941'))
        painter.drawPath(geometry.wedge(selected, count))
    # Each divider and circle is stroked once on this same surface.
    painter.setPen(QPen(QColor('#3a4148'), .8))
    if count > 1:
        for index in range(count):
            painter.drawLine(geometry.point(index+.5, .37, count), geometry.point(index+.5, 1, count))
    painter.setBrush(QColor('#191e23'))
    painter.drawEllipse(geometry.hub)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor('#48525a'), .9)); painter.drawEllipse(bounds)
    painter.restore()


def paint_slot(painter, geometry, item, index, count, selected=False, pressed=False):
    from notch_settings_style import symbol
    painter.save(); painter.setRenderHint(QPainter.Antialiasing)
    center = geometry.point(index, .71, count)
    size = max(32, min(48, geometry.radius * .24))
    chip = QRectF(center.x()-size/2, center.y()-size/2, size, size)
    fill = '#335d51' if pressed else '#3b7363' if selected else '#2e363e'
    painter.setBrush(QColor(fill)); painter.setPen(QPen(QColor('#80c6af' if selected else '#4a555e'), 1))
    painter.drawRoundedRect(chip, 12, 12)
    icon = symbol(item.icon_name or 'list-add', '#f0f5f2' if item.kind != 'empty' else '#728087')
    icon.paint(painter, round(center.x()-13), round(center.y()-13), 26, 26)
    painter.setPen(QColor('#a4b1b7')); font=painter.font(); font.setPixelSize(11); painter.setFont(font)
    point=geometry.point(index, .91, count)
    painter.drawText(QRectF(point.x()-9,point.y()-8,18,16),Qt.AlignCenter,str(index+1))
    painter.restore()
