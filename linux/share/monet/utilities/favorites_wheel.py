"""A pointer-centered launcher whose painted sectors are native, accessible buttons."""
import math

from html import escape

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPainterPath, QPalette, QPen, QRegion
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QLabel, QMenu, QPushButton, QVBoxLayout

from actions import ACTIONS, tr


class Sector(QAbstractButton):
    def __init__(self, wheel, entry, index, count):
        super().__init__(wheel)
        self.wheel = wheel
        self.entry = entry
        self.setEnabled(entry.kind != 'empty')
        self.key = entry.value
        self.setText(entry.title)
        self.setIcon(QIcon.fromTheme(entry.icon_name))
        self.setAccessibleName(self.text())
        self.setToolTip("" if wheel.active_id == 'radial' else "<span>" + escape(self.text()) + "</span>")
        self.setMouseTracking(True)
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
        if wheel.active_id == 'radial':
            from radial_art import RingGeometry
            geometry = RingGeometry(wheel.rect())
            self.path = geometry.wedge(index, count)
            self.setAttribute(Qt.WA_NoSystemBackground)
            self.pressed.connect(wheel.update)
            self.released.connect(wheel.update)
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

    def mousePressEvent(self, event):
        self.wheel.cancel_gesture()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.wheel.point_at(self, event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self.wheel.pointed is self:
            self.wheel.set_pointed(None)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.wheel.highlight(self)
        super().focusInEvent(event)

    def paintEvent(self, event):
        # Native buttons keep accessible focus and exact hit regions, while
        # the parent paints the whole radial surface without integer clipping.
        if self.wheel.active_id == 'radial':
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        selected = self.wheel.current is self
        fill = palette.color(QPalette.Highlight if selected else QPalette.Button)
        if not self.isEnabled():fill=palette.color(QPalette.Disabled,QPalette.Button)
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
        painter.setPen(palette.color(QPalette.HighlightedText if selected else QPalette.ButtonText)
                       if self.isEnabled() else palette.color(QPalette.Disabled,QPalette.ButtonText))
        painter.drawText(x-width//2, y+icon_size+3, width, text_height, Qt.AlignCenter, label)


class FavoritesWheel(QDialog):
    chosen = Signal(str)
    dismissed = Signal()
    targetChosen = Signal(object)
    profileChosen = Signal(str)
    emojiRequested = Signal()

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
        self.hint.setWordWrap(True)
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
        self.base_palette = QPalette(self.palette())
        self.radial_style = False
        self.emoji_picker = None
        self.picker_selection = None

        self.dismiss_timer = QTimer(self, singleShot=True)
        self.dismiss_timer.timeout.connect(self.dismiss_if_inactive)
        self.bindings = ()
        self.required = Qt.NoModifier
        self.pointed = None
        self.origin = None
        self.mode = "adaptive"

    def prepare_shortcut(self, mode, bindings):
        self.cancel_gesture()
        self.mode = mode
        self.bindings = bindings

    def start_gesture(self):
        if not self.bindings or not self.isVisible() or not self.isActiveWindow():
            return
        # On Wayland the compositor supplies the held modifiers with keyboard
        # focus. Qt's cached keyboardModifiers() can still describe the old window.
        held = QApplication.queryKeyboardModifiers()
        matches = [mods for mods in self.bindings if mods and held & mods == mods]
        bare = Qt.NoModifier in self.bindings
        self.bindings = ()
        if matches:
            self.required = max(matches, key=lambda mods: mods.value.bit_count())
            if self.origin is None:
                self.origin = QCursor.pos()
        elif self.mode == "hold" and not bare:
            self.hide()

    def cancel_gesture(self):
        self.bindings = ()
        self.required = Qt.NoModifier
        self.origin = None
        self.set_pointed(None)

    def set_pointed(self, button):
        if self.pointed is button:
            return
        self.pointed = button
        self.hint.setText(tr("Release to choose") if button else self.hub_hint())

    def hub_hint(self):
        if self.active_id == 'radial':return tr('Edit menu')
        return "‹ " + tr("Back") if self.history else tr("Wheels") + " ▾"

    def enterEvent(self, event):
        if self.bindings and self.origin is None:
            self.origin = event.globalPosition().toPoint()
        super().enterEvent(event)

    def point_at(self, button, position):
        if self.required and self.origin is not None:
            # A clamped wheel can open with a sector already under the pointer.
            if (position - self.origin).manhattanLength() >= QApplication.startDragDistance():
                self.set_pointed(button)
                if self.current is not button:
                    self.highlight(button)
            else:
                self.set_pointed(None)

    def keyReleaseEvent(self, event):
        if self.required and not event.isAutoRepeat() and event.modifiers() & self.required != self.required:
            target = self.pointed
            self.cancel_gesture()
            if target:
                self.choose(target.entry)
            elif self.mode == "hold":
                self.hide()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def contents(self, items, selected=0):
        radial = self.active_id == 'radial'
        if radial != self.radial_style:
            self.radial_style = radial
            palette = QPalette(self.base_palette)
            if radial:
                for role,color in ((QPalette.Window,'#191d21'),(QPalette.WindowText,'#f0f4f2'),
                                   (QPalette.Button,'#191d21'),(QPalette.ButtonText,'#f0f4f2'),
                                   (QPalette.PlaceholderText,'#9ba9ad'),(QPalette.Mid,'#394249')):
                    palette.setColor(role,QColor(color))
            self.setPalette(palette)
            self.hub.setStyleSheet('QPushButton {background:transparent;border:0;} QLabel {color:#eef3f0;background:transparent;}' if radial else '')
            self.drawn = None
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
            span = round((self.width()-16) * .37) if radial else round(self.width() * .39)
            self.hub.setGeometry((self.width()-span)//2, (self.height()-span)//2, span, span)
            self.hub.setMask(QRegion(self.hub.rect(), QRegion.Ellipse))
            inset = max(3, span // 10)
            self.hub_layout.setContentsMargins(inset, 0, inset, 0)
        hint = tr('Edit radial menu') if self.active_id == 'radial' else tr("Back") if self.history else tr("Wheels")
        self.hub.setAccessibleName(hint)
        self.hint.setText(self.hub_hint())
        self.label.setWordWrap(not radial)
        self.hub.raise_()
        enabled = [button for button in self.buttons if button.isEnabled()]
        if enabled:
            button = self.buttons[min(selected, len(self.buttons)-1)]
            if not button.isEnabled():button=enabled[0]
            button.setFocus(Qt.ShortcutFocusReason)
            self.highlight(button)
        else:
            self.hub.setToolTip("")
            self.hub.setAccessibleDescription("")
            self.label.setText(tr("Empty wheel"))
            self.hub.setFocus(Qt.ShortcutFocusReason)
        if radial and enabled:
            self.label.setText(tr('Radial menu'))
        self.update()

    def present(self, items, available):
        self.close_picker(focus=False)
        if items and isinstance(items[0], str):
            from wheel_profiles import Entry
            items = tuple(Entry("tool", key) for key in items)
        size = min(max(320, self.fontMetrics().height()*22), max(1, available))
        self.setFixedSize(size, size)
        if self.active_id == 'radial': self.clearMask()
        else: self.setMask(QRegion(self.rect(), QRegion.Ellipse))
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
            if self.active_id == 'radial':
                # QWindow's input hint is separate from QWidget's raster clip.
                # The painted rim is inset, so even a compositor using this as
                # a visual shape cannot cut into its antialiased pixels.
                self.windowHandle().setMask(QRegion(self.rect(), QRegion.Ellipse))
        finally:
            QApplication.setDesktopFileName(desktop_id)
        self.raise_()
        self.activateWindow()
        if self.current:
            self.current.setFocus(Qt.ShortcutFocusReason)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.emoji_picker and self.emoji_picker.isVisible():
            painter.setPen(QPen(QColor('#414b4b'),1))
            painter.setBrush(QColor('#1e1f22'))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),22,22)
            return
        if self.active_id == 'radial':
            from radial_art import RingGeometry, paint_ring, paint_slot
            geometry=RingGeometry(self.rect())
            selected=self.buttons.index(self.current) if self.current in self.buttons else -1
            paint_ring(painter,geometry,selected,len(self.buttons))
            for index,button in enumerate(self.buttons):
                paint_slot(painter,geometry,button.entry,index,len(self.buttons),button is self.current,button.isDown())
            return
        painter.setPen(QPen(self.palette().color(QPalette.Mid), 1))
        painter.setBrush(self.palette().window())
        painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))

    def highlight(self, button):
        if not button.isEnabled():return
        previous = self.current
        self.current = button
        text = button.text()
        self.hub.setToolTip(button.toolTip())
        self.hub.setAccessibleDescription(text)
        # A long filename without spaces would otherwise extend beyond the hub.
        width = self.hub.width() - 2 * self.hub_layout.contentsMargins().left()
        metrics = self.fontMetrics()
        if self.active_id == 'radial':
            # At most two lines, including a long custom name with no spaces.
            words=text.split();first=''
            while words and metrics.horizontalAdvance((first+' '+words[0]).strip()) <= width:
                first=(first+' '+words.pop(0)).strip()
            remaining=' '.join(words)
            self.label.setText((first+'\n' if first and remaining else first)+metrics.elidedText(remaining,Qt.ElideRight,width))
            self.update()
        else:
            self.label.setText(" ".join(metrics.elidedText(word, Qt.ElideMiddle, width) for word in text.split()))
        if previous and previous is not button:
            previous.update()
        button.update()

    def choose(self, entry):
        self.cancel_gesture()
        if not self.isVisible() or entry.kind == 'empty':
            return
        if self.active_id == 'radial' and entry.kind == 'tool' and entry.value == 'emoji':
            self.emojiRequested.emit()
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

    def open_emoji(self, host):
        from wheel_emoji import WheelEmoji
        self.cancel_gesture()
        self.picker_selection=self.current
        if self.emoji_picker is None:self.emoji_picker=WheelEmoji(self,host)
        for button in self.buttons:button.hide()
        self.hub.hide()
        self.windowHandle().setMask(QRegion())
        self.emoji_picker.setGeometry(self.rect().adjusted(3,3,-3,-3))
        self.emoji_picker.show();self.emoji_picker.raise_();self.emoji_picker.focus_search()
        self.update()

    def close_picker(self, focus=True):
        if not self.emoji_picker or self.emoji_picker.isHidden():return
        selected=self.picker_selection
        self.emoji_picker.hide()
        for button in self.buttons:button.show()
        self.hub.show();self.hub.raise_()
        if self.windowHandle():self.windowHandle().setMask(QRegion(self.rect(),QRegion.Ellipse))
        if selected in self.buttons and selected.isEnabled():
            self.highlight(selected)
            if focus:selected.setFocus(Qt.BacktabFocusReason)
        self.update()

    def open_hub(self):
        self.cancel_gesture()
        if self.active_id == 'radial':
            self.hide();self.chosen.emit('wheel-settings');return
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
        if self.emoji_picker and self.emoji_picker.isVisible():
            super().keyPressEvent(event)
            return
        key = event.key()
        if not event.isAutoRepeat() and key not in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_Shift):
            self.cancel_gesture()
        if key == Qt.Key_Menu or (key == Qt.Key_F10 and event.modifiers() & Qt.ShiftModifier):
            self.open_hub()
        elif key == Qt.Key_Backspace and self.history:
            self.contents(*self.history.pop())
        elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down):
            available = [button for button in self.buttons if button.isEnabled()]
            if not available:
                return
            step = -1 if key in (Qt.Key_Left, Qt.Key_Up) else 1
            index = (available.index(self.current) + step) % len(available) if self.current in available else 0
            available[index].setFocus(Qt.TabFocusReason)
            self.highlight(available[index])
        elif self.active_id == 'radial' and Qt.Key_1 <= key <= Qt.Key_8:
            index=key-Qt.Key_1
            if index<len(self.buttons) and not event.isAutoRepeat():self.choose(self.buttons[index].entry)
        elif key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space):
            if not event.isAutoRepeat():
                if self.hub.hasFocus() or not self.current:
                    self.open_hub()
                else:
                    self.choose(self.current.entry)
        else:
            super().keyPressEvent(event)

    def focusNextPrevChild(self, next):
        self.cancel_gesture()
        return super().focusNextPrevChild(next)

    def reject(self):
        self.cancel_gesture()
        if self.emoji_picker and self.emoji_picker.isVisible():
            self.close_picker()
        elif self.history:
            self.contents(*self.history.pop())
        else:
            self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isVisible():
            if self.isActiveWindow():
                self.start_gesture()
            else:
                self.cancel_gesture()
                self.dismiss_timer.start(0)

    def dismiss_if_inactive(self):
        if self.isVisible() and self.menu is None and not self.isActiveWindow():
            self.hide()

    def hideEvent(self, event):
        self.dismiss_timer.stop()
        self.cancel_gesture()
        if self.menu:
            self.menu.close()
        super().hideEvent(event)
        self.dismissed.emit()
