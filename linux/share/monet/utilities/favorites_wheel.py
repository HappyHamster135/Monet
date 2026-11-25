"""A pointer-centered launcher whose painted sectors are native, accessible buttons."""
import math

from html import escape

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon, QPainter, QPainterPath, QPalette, QPen, QRegion
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QLabel, QMenu, QPushButton, QVBoxLayout

from actions import ACTIONS, tr


class Sector(QAbstractButton):
    def __init__(self, wheel, entry, index, count):
        super().__init__(wheel)
        self.wheel = wheel
        self.entry = entry
        self.key = entry.value
        self.setText(entry.title)
        self.setIcon(QIcon.fromTheme(entry.icon_name))
        self.setAccessibleName(self.text())
        self.setToolTip("<span>" + escape(self.text()) + "</span>")
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
        self.clicked.connect(lambda: wheel.choose(entry))

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
    targetChosen = Signal(object)
    profileChosen = Signal(str)

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(ACTIONS["wheel"].name)
        self.setWindowIcon(QIcon.fromTheme("view-more"))
        self.hub = QPushButton(self)
        self.hub.setFlat(True)
        self.hub.setAutoDefault(False)
        self.hub.clicked.connect(self.open_hub)
        self.hub_layout = QVBoxLayout(self.hub)
        self.hub_layout.setContentsMargins(0, 0, 0, 0)
        self.hub_layout.setSpacing(0)
        self.hub_layout.addStretch()
        self.label = QLabel(self.hub)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hub_layout.addWidget(self.label)
        self.hint = QLabel(self.hub)
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hint.setForegroundRole(QPalette.PlaceholderText)
        self.hub_layout.addWidget(self.hint)
        self.hub_layout.addStretch()
        self.drawn = None
        self.history = []
        self.menu = None
        self.profile_names = {}
        self.active_id = ""
        self.editable = True
        self.buttons = []
        self.current = None

    def contents(self, items, selected=0):
        layout = (self.width(), items)
        if layout != self.drawn:
            self.drawn = layout
            for button in self.buttons:
                button.hide()
                button.deleteLater()
            self.current = None
            self.buttons = [Sector(self, entry, i, len(items)) for i, entry in enumerate(items)]
            for button in self.buttons:
                button.show()
            span = round(self.width() * .39)
            self.hub.setGeometry((self.width()-span)//2, (self.height()-span)//2, span, span)
            self.hub.setMask(QRegion(self.hub.rect(), QRegion.Ellipse))
            inset = max(3, span // 10)
            self.hub_layout.setContentsMargins(inset, 0, inset, 0)
        hint = tr("Back") if self.history else tr("Wheels")
        self.hub.setAccessibleName(hint)
        self.hint.setText("‹ " + hint if self.history else hint + " ▾")
        self.hub.raise_()
        if self.buttons:
            button = self.buttons[min(selected, len(self.buttons)-1)]
            button.setFocus(Qt.ShortcutFocusReason)
            self.highlight(button)
        else:
            self.hub.setToolTip("")
            self.hub.setAccessibleDescription("")
            self.label.setText(tr("Empty wheel"))
            self.hub.setFocus(Qt.ShortcutFocusReason)

    def present(self, items, available):
        if items and isinstance(items[0], str):
            from wheel_profiles import Entry
            items = tuple(Entry("tool", key) for key in items)
        size = min(max(320, self.fontMetrics().height()*22), max(1, available))
        self.setFixedSize(size, size)
        self.setMask(QRegion(self.rect(), QRegion.Ellipse))
        self.history.clear()
        self.contents(items)
        # Wayland placement comes from the compositor when this surface is mapped.
        if not QApplication.platformName().startswith("wayland"):
            pos = QCursor.pos()
            screen = QApplication.screenAt(pos) or self.screen()
            area = screen.availableGeometry()
            self.move(max(area.left(), min(pos.x()-size//2, area.right()-size+1)),
                      max(area.top(), min(pos.y()-size//2, area.bottom()-size+1)))
        # Qt Wayland takes the desktop ID when the surface maps. Use the wheel's
        # own launcher so KWin can place it under the pointer on its first frame.
        desktop_id = QApplication.desktopFileName()
        QApplication.setDesktopFileName("org.monet.FavoritesWheel")
        try:
            self.show()
        finally:
            QApplication.setDesktopFileName(desktop_id)
        self.raise_()
        self.activateWindow()
        if self.buttons:
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
        text = button.text()
        self.hub.setToolTip(button.toolTip())
        self.hub.setAccessibleDescription(text)
        # A long filename without spaces would otherwise extend beyond the hub.
        width = self.hub.width() - 2 * self.hub_layout.contentsMargins().left()
        metrics = self.fontMetrics()
        self.label.setText(" ".join(metrics.elidedText(word, Qt.ElideMiddle, width) for word in text.split()))
        if previous and previous is not button:
            previous.update()
        button.update()

    def choose(self, entry):
        if not self.isVisible():
            return
        if entry.kind == "menu":
            self.history.append((tuple(b.entry for b in self.buttons), self.buttons.index(self.current)))
            self.contents(entry.children)
            return
        self.hide()
        if entry.kind == "tool":
            self.chosen.emit(entry.value)
        else:
            self.targetChosen.emit(entry)

    def open_hub(self):
        if self.history:
            self.contents(*self.history.pop())
            return
        menu = QMenu(self)
        self.menu = menu
        for ident, name in self.profile_names.items():
            action = menu.addAction(name.replace("&", "&&"))
            action.setCheckable(True)
            action.setChecked(ident == self.active_id)
            action.setData(ident)
        edit = None
        if self.editable:
            menu.addSeparator()
            edit = menu.addAction(tr("Customize wheels…"))
        selected = menu.exec(self.hub.mapToGlobal(self.hub.rect().bottomLeft()))
        self.menu = None
        menu.deleteLater()
        if not self.isVisible() or selected is None:
            return
        if selected is edit:
            self.hide()
            self.chosen.emit("wheel-settings")
        else:
            self.profileChosen.emit(selected.data())

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Menu or (key == Qt.Key_F10 and event.modifiers() & Qt.ShiftModifier):
            self.open_hub()
        elif key == Qt.Key_Backspace and self.history:
            self.contents(*self.history.pop())
        elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down):
            if not self.buttons:
                return
            step = -1 if key in (Qt.Key_Left, Qt.Key_Up) else 1
            index = (self.buttons.index(self.current) + step) % len(self.buttons)
            self.buttons[index].setFocus(Qt.TabFocusReason)
            self.highlight(self.buttons[index])
        elif key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space):
            if not event.isAutoRepeat():
                if self.hub.hasFocus() or not self.current:
                    self.open_hub()
                else:
                    self.choose(self.current.entry)
        else:
            super().keyPressEvent(event)

    def reject(self):
        if self.history:
            self.contents(*self.history.pop())
        else:
            self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isVisible() and not self.isActiveWindow():
            QTimer.singleShot(0, self, self.dismiss_if_inactive)

    def dismiss_if_inactive(self):
        if self.isVisible() and self.menu is None and not self.isActiveWindow():
            self.hide()

    def hideEvent(self, event):
        if self.menu:
            self.menu.close()
        super().hideEvent(event)
        self.dismissed.emit()
