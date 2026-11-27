"""Page scrolling never edits a setting; blank surfaces can move native windows."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSlider,
    QAbstractSpinBox, QApplication, QComboBox, QFrame, QGroupBox, QLabel, QLineEdit,
    QScrollArea, QScrollBar, QStyle, QStyleOptionSpinBox, QTabBar, QWidget)
from shiboken6 import isValid


class WindowInteraction(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.candidate = None
        self.forwarding = False

    @staticmethod
    def setting_control(widget):
        while isinstance(widget, QWidget):
            if isinstance(widget, (QAbstractSpinBox, QComboBox, QTabBar)):
                return widget
            if isinstance(widget, QAbstractSlider) and not isinstance(widget, QScrollBar):
                return widget
            if isinstance(widget, QAbstractScrollArea):
                break
            widget = widget.parentWidget()

    @staticmethod
    def over_step_arrow(control, event):
        if not isinstance(control, QAbstractSpinBox):
            return False
        option = QStyleOptionSpinBox()
        control.initStyleOption(option)
        point = control.mapFromGlobal(event.globalPosition().toPoint())
        hit = control.style().hitTestComplexControl(QStyle.CC_SpinBox, option, point, control)
        return hit in (QStyle.SC_SpinBoxUp, QStyle.SC_SpinBoxDown)

    @staticmethod
    def draggable(widget):
        if not isinstance(widget, QWidget) or not widget.isEnabled():
            return False
        window = widget.window()
        if not window.property('monetWindowDrag') or window.isFullScreen():
            return False
        item = widget
        while item:
            if (isinstance(item, (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QLineEdit, QComboBox, QTabBar))
                    or isinstance(item, QAbstractScrollArea) and not isinstance(item, QScrollArea)):
                return False
            if isinstance(item, QLabel) and item.textInteractionFlags() != Qt.NoTextInteraction:
                return False
            if isinstance(item, QGroupBox) and item.isCheckable():
                return False
            item = item.parentWidget()
        # Never steal a video, canvas, quick widget, or other custom control.
        return (type(widget) in (QWidget, QFrame, QLabel, QGroupBox)
                or widget.layout() is not None and widget.focusPolicy() == Qt.NoFocus)

    def start_move(self, window):
        return bool(window and window.startSystemMove())

    def watch(self, widget):
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.ChildPolished:
            child = event.child()
            if isinstance(child,QWidget):self.watch(child)
            return False
        # QML types are not yet complete during their construction events.
        # Inspect only delivered input, never every QObject the engine creates.
        if event.type() not in (QEvent.Wheel, QEvent.MouseButtonPress, QEvent.MouseMove,
                QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick, QEvent.WindowDeactivate):
            return False
        if not isinstance(watched, QWidget):
            return False
        if event.type() == QEvent.Wheel and not self.forwarding:
            control = self.setting_control(watched)
            if control and not self.over_step_arrow(control, event):
                parent = control.parentWidget()
                while parent and not isinstance(parent, QAbstractScrollArea):
                    parent = parent.parentWidget()
                if parent:
                    if not event.pixelDelta().isNull():
                        # Native QScrollArea ignores pixel-only touchpad updates.
                        # Preserve their distance instead of converting them to wheel steps.
                        delta = event.pixelDelta()
                        bar = parent.horizontalScrollBar() if abs(delta.x()) > abs(delta.y()) else parent.verticalScrollBar()
                        bar.setValue(bar.value() - (delta.x() if bar.orientation() == Qt.Horizontal else delta.y()))
                        event.accept()
                        return True
                    viewport = parent.viewport()
                    forwarded = QWheelEvent(viewport.mapFromGlobal(event.globalPosition().toPoint()),
                        event.globalPosition(), event.pixelDelta(), event.angleDelta(), event.buttons(),
                        event.modifiers(), event.phase(), event.inverted(), event.source())
                    self.forwarding = True
                    try: QApplication.sendEvent(viewport, forwarded)
                    finally: self.forwarding = False
                event.accept()
                return True
        if event.type() == QEvent.MouseButtonPress:
            # Qt propagates ignored presses to ancestors; retain the original target.
            if (self.candidate and isValid(self.candidate) and watched.isAncestorOf(self.candidate)
                    and event.globalPosition() == self.origin and event.timestamp() == self.press_time):
                return False
            self.candidate = None
            if (event.button() == Qt.LeftButton and event.modifiers() == Qt.NoModifier
                    and event.source() == Qt.MouseEventNotSynthesized and self.draggable(watched)):
                self.candidate = watched
                self.origin = event.globalPosition()
                self.press_time = event.timestamp()
        elif event.type() == QEvent.MouseMove and self.candidate:
            if (not isValid(self.candidate) or not event.buttons() & Qt.LeftButton
                    or event.modifiers() != Qt.NoModifier):
                self.candidate = None
            elif (event.globalPosition() - self.origin).manhattanLength() >= QApplication.startDragDistance():
                handle = self.candidate.window().windowHandle()
                self.candidate = None
                return self.start_move(handle)
        elif event.type() in (QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick, QEvent.WindowDeactivate):
            self.candidate = None
        return False


def install_interaction(window=None, draggable=True):
    app = QApplication.instance()
    if not hasattr(app, '_monet_interaction'):
        app._monet_interaction = WindowInteraction(app)
    if window is not None:
        window.setProperty('monetWindowDrag', draggable)
        app._monet_interaction.watch(window)
    return app._monet_interaction
