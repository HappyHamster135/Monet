"""Place a native tool inside the visible notch body. Input goes directly to Qt."""
import json
from pathlib import Path
import re

from PySide6.QtCore import QMargins, QPoint, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from actions import ACTIONS, DESKTOP_TOOLS, preferences, tr


class NotchTools(QObject):
    dismissed = Signal(str, bool)

    def __init__(self, receiver):
        super().__init__(receiver)
        self.receiver = receiver
        self.host = None
        self.area = None
        self.token = ""
        self.key = ""
        self.gained_focus = False
        self.engine = self.placement = None
        QApplication.instance().focusWindowChanged.connect(self.focus_changed)

    def build(self):
        from PySide6.QtQml import QQmlComponent, QQmlEngine
        from window import Window
        self.host = Window(self.receiver.window.helpers, defer_catalog=True)
        self.area = QWidget(None, Qt.Tool | Qt.FramelessWindowHint)
        self.area.setAttribute(Qt.WA_QuitOnClose, False)
        palette = QPalette(self.area.palette())
        for role, color in ((QPalette.Window, "#17171b"), (QPalette.Base, "#202024"),
                            (QPalette.AlternateBase, "#29292d"), (QPalette.Button, "#303035"),
                            (QPalette.WindowText, "#f5f5f7"), (QPalette.Text, "#f5f5f7"),
                            (QPalette.ButtonText, "#f5f5f7"), (QPalette.Highlight, "#526d95"),
                            (QPalette.PlaceholderText, "#afb0ba"), (QPalette.HighlightedText, "#ffffff")):
            palette.setColor(role, QColor(color))
        self.area.setPalette(palette)
        layout = QVBoxLayout(self.area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.status.hide()
        layout.addWidget(self.status)
        self.host.status.messageChanged.connect(self.show_status)
        self.area.winId()
        self.engine = QQmlEngine(self)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(Path(__file__).with_name("NotchPlacement.qml"))))
        self.placement = self.component.createWithInitialProperties({"target": self.area.windowHandle()})
        if not self.placement or not self.placement.property("placement"):
            raise RuntimeError("Layer shell unavailable")
        self.placement.setParent(self.engine)
        for sequence in ("Escape", "Alt+Left"):
            QShortcut(QKeySequence(sequence), self.area, activated=self.back)

    def show_status(self, message):
        self.status.setText(message)
        self.status.setVisible(bool(message))

    def back(self):
        if self.token:
            token = self.token
            self.hide()
            self.dismissed.emit(token, True)

    def focus_changed(self, window):
        if not self.token:
            return
        if window is self.area.windowHandle():
            self.gained_focus = True
        elif self.gained_focus and window is None:
            # Menus and native file choosers may transfer focus within this app.
            QTimer.singleShot(140, self, self.check_focus)

    def check_focus(self):
        if self.gained_focus and self.token and not QApplication.focusWindow() and not QApplication.activeModalWidget():
            token = self.token
            self.hide()
            self.dismissed.emit(token, False)

    def hide(self):
        self.token = self.key = ""
        self.gained_focus = False
        if self.area:
            self.area.hide()
            widget = self.scroll.takeWidget()
            if widget:
                widget.hide()
                self.host.stack.addWidget(widget)
            self.receiver.idle.start()

    def busy(self):
        if not self.host:
            return False
        editor = self.host.pages.get("recordings")
        compressor = self.host.pages.get("compress")
        return bool(self.token or self.host.running or (editor and (editor.recorder or editor.exporter))
                    or (compressor and compressor.job))

    def handle(self, payload):
        try:
            if len(payload) > 2048:
                raise ValueError()
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError()
            token = data.get("id", "")
            if data.get("action") == "close":
                if self.token and self.token == token:
                    self.hide()
                return '{"ok":true}'
            key = data.get("key")
            window = self.receiver.window
            window.settings.sync()
            window.favorites, window.hidden = preferences(window.settings)
            if key not in ACTIONS or key in window.hidden:
                raise ValueError()
            if data.get("action") == "run" and key in DESKTOP_TOOLS:
                QTimer.singleShot(0, self, lambda: self.run_action(key))
                return '{"ok":true}'
            if data.get("action") != "show" or key in DESKTOP_TOOLS or not re.fullmatch(r"[0-9.-]{1,64}", token):
                raise ValueError()
            x, y, w, h = (round(data[k]) for k in ("x", "y", "w", "h"))
            screen = next((s for s in QApplication.screens() if data.get("screen") and s.name() == data["screen"]), None)
            if not screen:
                screen = QApplication.screenAt(QPoint(x + w//2, y + h//2))
            if not screen:
                raise ValueError()
            g = screen.geometry()
            if not (40 <= w <= min(g.width(), 800) and 24 <= h <= min(g.height(), 760)
                    and g.left() <= x <= g.right()-w+1 and g.top() <= y <= g.bottom()-h+1):
                raise ValueError()
            if self.token and self.token != token:
                self.back()
            if not self.placement:
                self.build()
            layer = self.placement.property("placement")
            layer.setProperty("screen", screen)
            layer.setProperty("margins", QMargins(x-g.x(), y-g.y(), 0, 0))
            self.area.setFixedSize(w, h)
            if self.token != token or self.key != key:
                self.hide()
                self.host.run_tool(key)
                widget = self.host.pages.get(key)
                if not widget:
                    raise ValueError()
                self.host.stack.removeWidget(widget)
                self.scroll.setWidget(widget)
                self.area.setWindowTitle(ACTIONS[key].name)
                self.token, self.key = token, key
                self.area.show()
                widget.show()
            return '{"ok":true}'
        except (KeyError, ValueError, TypeError, RuntimeError, AttributeError, OverflowError):
            return '{"ok":false}'

    def run_action(self, key):
        window = self.receiver.window
        if key in preferences(window.settings)[1]:
            return
        if key in ("clean", "plain"):
            # The notch currently owns focus. Read the explicitly selected text
            # through Wayland, then reuse the same transform and copy logic.
            window.worker(["wl-paste", "--no-newline", "--type", "text"], lambda value: window.use_clipboard(key, value),
                          lambda _: window.issue(tr("Copy some text first.")))
        elif key == "record":
            from PySide6.QtCore import QProcess
            QProcess.startDetached("spectacle", ["--record", "region"])
        elif key in ("color", "ocr"):
            window.select_from_screen(key)
        elif key == "wheel":
            window.wheel()
        else:
            window.run_tool(key)
