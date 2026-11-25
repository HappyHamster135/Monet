"""Set the focal point and timing for one recording zoom."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QLabel, QVBoxLayout, QWidget)
from actions import tr
from recording_zoom import FULL, Zoom


class Aim(QWidget):
    def __init__(self, frame, crop, zoom):
        super().__init__()
        self.frame = frame
        self.crop = crop or FULL
        self.x, self.y, self.amount = zoom.x, zoom.y, zoom.amount
        self.setMinimumSize(220, 130)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)
        self.setAccessibleName(tr("Zoom focus"))
        self.setAccessibleDescription(tr("Click the picture or use the arrow keys to choose the zoom focus."))

    def picture(self):
        _, _, w, h = self.crop
        scale = min(self.width()/(self.frame.width()*w), self.height()/(self.frame.height()*h))
        width, height = self.frame.width()*w*scale, self.frame.height()*h*scale
        return QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        target = self.picture()
        x, y, w, h = self.crop
        fw, fh = self.frame.width(), self.frame.height()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(target, self.frame, QRectF(x*fw, y*fh, w*fw, h*fh))
        vx, vy, vw, vh = Zoom(0, 3000, self.x, self.y, self.amount).viewport(1500, self.crop)
        view = QRectF(target.x()+(vx-x)*target.width()/w, target.y()+(vy-y)*target.height()/h,
                      target.width()*vw/w, target.height()*vh/h)
        mask = QPainterPath()
        mask.addRect(target)
        mask.addRect(view)
        painter.fillPath(mask, QColor(0, 0, 0, 130))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawRect(view.adjusted(1, 1, -1, -1))
        cx = round(target.x() + (self.x-x)*target.width()/w)
        cy = round(target.y() + (self.y-y)*target.height()/h)
        painter.setClipRect(target)
        for color, width in ((Qt.black, 3), (Qt.white, 1)):
            painter.setPen(QPen(color, width))
            painter.drawLine(cx-7, cy, cx+7, cy)
            painter.drawLine(cx, cy-7, cx, cy+7)
        painter.end()

    def aim(self, x, y):
        left, top, w, h = self.crop
        self.x = max(left, min(left+w, x))
        self.y = max(top, min(top+h, y))
        self.update()

    def aim_at(self, position):
        rect = self.picture()
        x, y, w, h = self.crop
        self.aim(x+w*(position.x()-rect.x())/rect.width(), y+h*(position.y()-rect.y())/rect.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.picture().contains(event.position()):
            self.aim_at(event.position())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.picture().contains(event.position()):
            self.aim_at(event.position())
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        delta = {Qt.Key_Left: (-1,0), Qt.Key_Right: (1,0), Qt.Key_Up: (0,-1), Qt.Key_Down: (0,1)}
        if event.key() in delta:
            dx, dy = delta[event.key()]
            self.aim(self.x + dx*self.crop[2]/100, self.y + dy*self.crop[3]/100)
            event.accept()
        else:
            super().keyPressEvent(event)


class ZoomDialog(QDialog):
    def __init__(self, parent, zoom, frame, crop, earliest, latest, existing):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit zoom") if existing else tr("Add zoom"))
        self.resize(560, 410)
        self.removed = False
        layout = QVBoxLayout(self)
        tip = QLabel(tr("Click the picture or use the arrow keys to choose the zoom focus."))
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self.aim = Aim(frame, crop, zoom)
        layout.addWidget(self.aim, 1)
        form = QFormLayout()
        self.start = self.time_field(zoom.start, earliest, latest-1)
        self.end = self.time_field(zoom.end, earliest+1, latest)
        form.addRow(tr("Start"), self.start)
        form.addRow(tr("End"), self.end)
        self.strength = QDoubleSpinBox()
        self.strength.setRange(1.05, 4)
        self.strength.setSingleStep(.1)
        self.strength.setValue(zoom.amount)
        self.strength.setSuffix("×")
        self.strength.valueChanged.connect(self.amount_changed)
        form.addRow(tr("Magnification"), self.strength)
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.start.valueChanged.connect(self.check)
        self.end.valueChanged.connect(self.check)
        if existing:
            self.buttons.addButton(tr("Remove zoom"), QDialogButtonBox.DestructiveRole).clicked.connect(self.remove)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.aim.setFocus()

    def time_field(self, ms, lo, hi):
        field = QDoubleSpinBox()
        field.setDecimals(3)
        field.setRange(lo/1000, hi/1000)
        field.setSingleStep(.1)
        field.setValue(ms/1000)
        field.setSuffix(tr(" s"))
        return field

    def check(self):
        self.buttons.button(QDialogButtonBox.Save).setEnabled(self.start.value() < self.end.value())

    def amount_changed(self, value):
        self.aim.amount = value
        self.aim.update()

    def remove(self):
        self.removed = True
        self.accept()

    def zoom(self):
        return Zoom(round(self.start.value()*1000), round(self.end.value()*1000),
                    self.aim.x, self.aim.y, self.strength.value())
