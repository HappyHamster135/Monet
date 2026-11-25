"""A pointer-centered launcher whose painted sectors are native, accessible buttons."""
import math

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon, QPainter, QPainterPath, QPalette, QPen, QRegion
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QLabel

from actions import ACTIONS


class Sector(QAbstractButton):
    def __init__(self, wheel, key, index, count):
        super().__init__(wheel)
        self.wheel = wheel
        self.key = key
        self.setText(ACTIONS[key].name)
        self.setIcon(QIcon.fromTheme(ACTIONS[key].icon))
        self.setAccessibleName(self.text())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setGeometry(wheel.rect())
        bounds = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        center = bounds.center()
        radius = bounds.width() / 2
        inner = radius * .41
        hub = QRectF(center.x()-inner, center.y()-inner, 2*inner, 2*inner)
        sector = 360 / count
        angle = 90 - index * sector
        start = angle + sector / 2
        self.path = QPainterPath()
        self.path.arcMoveTo(bounds, start)
        self.path.arcTo(bounds, start, -sector)
        self.path.arcTo(hub, start-sector, sector)
        self.path.closeSubpath()
        self.setMask(QRegion(self.path.toFillPolygon().toPolygon()))
        radians = math.radians(angle)
        self.anchor = center + QPointF(math.cos(radians), -math.sin(radians)) * (radius * .71)
        self.label_width = min(radius * .54, 2 * radius * .69 * math.sin(math.pi / max(2, count)) - 6)
        self.clicked.connect(lambda: wheel.choose(key))

    def hitButton(self, position):
        return self.path.contains(QPointF(position))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down, Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space):
            self.wheel.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event):
        self.wheel.highlight(self)
        super().enterEvent(event)

    def focusInEvent(self, event):
        self.wheel.highlight(self)
        super().focusInEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        selected = self.wheel.current is self
        fill = palette.color(QPalette.Highlight if selected else QPalette.Button)
        if self.isDown():
            fill = fill.darker(112)
        painter.setBrush(fill)
        painter.setPen(QPen(palette.color(QPalette.Mid), 1))
        painter.drawPath(self.path)
        text_height = self.fontMetrics().height()
        icon_size = max(16, min(34, self.width() // 10))
        center = self.anchor.toPoint()
        x, y = center.x(), center.y() - (icon_size + text_height + 3) // 2
        self.icon().paint(painter, x-icon_size//2, y, icon_size, icon_size)
        width = int(self.label_width)
        label = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, width)
        painter.setPen(palette.color(QPalette.HighlightedText if selected else QPalette.ButtonText))
        painter.drawText(x-width//2, y+icon_size+3, width, text_height, Qt.AlignCenter, label)


class FavoritesWheel(QDialog):
    chosen = Signal(str)
    dismissed = Signal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(ACTIONS["wheel"].name)
        self.setWindowIcon(QIcon.fromTheme("view-more"))
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.buttons = []
        self.current = None

    def present(self, keys, available):
        size = min(max(320, self.fontMetrics().height()*22), max(1, available))
        if size != self.width() or keys != [button.key for button in self.buttons]:
            for button in self.buttons:
                button.hide()
                button.deleteLater()
            self.current = None
            self.buttons.clear()
            self.setFixedSize(size, size)
            self.setMask(QRegion(self.rect(), QRegion.Ellipse))
            span = round(size * .33)
            self.label.setGeometry((size-span)//2, (size-span)//2, span, span)
            for index, key in enumerate(keys):
                button = Sector(self, key, index, len(keys))
                self.buttons.append(button)
                button.show()
            self.label.raise_()
        # Wayland placement comes from the compositor when this surface is mapped.
        if not QApplication.platformName().startswith("wayland"):
            pos = QCursor.pos()
            screen = QApplication.screenAt(pos) or self.screen()
            area = screen.availableGeometry()
            self.move(max(area.left(), min(pos.x()-size//2, area.right()-size+1)),
                      max(area.top(), min(pos.y()-size//2, area.bottom()-size+1)))
        self.show()
        self.raise_()
        self.activateWindow()
        self.buttons[0].setFocus(Qt.ShortcutFocusReason)
        self.highlight(self.buttons[0])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().color(QPalette.Mid), 1))
        painter.setBrush(self.palette().window())
        painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))

    def highlight(self, button):
        previous = self.current
        self.current = button
        self.label.setText(button.text())
        if previous and previous is not button:
            previous.update()
        button.update()

    def choose(self, key):
        if self.isVisible():
            self.hide()
            self.chosen.emit(key)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down):
            step = -1 if key in (Qt.Key_Left, Qt.Key_Up) else 1
            index = (self.buttons.index(self.current) + step) % len(self.buttons)
            self.buttons[index].setFocus(Qt.TabFocusReason)
            self.highlight(self.buttons[index])
        elif key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space):
            if not event.isAutoRepeat():
                self.choose(self.current.key)
        else:
            super().keyPressEvent(event)

    def reject(self):
        self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isVisible() and not self.isActiveWindow():
            QTimer.singleShot(0, self, self.dismiss_if_inactive)

    def dismiss_if_inactive(self):
        if self.isVisible() and not self.isActiveWindow():
            self.hide()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.dismissed.emit()
