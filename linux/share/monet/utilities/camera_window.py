"""Floating view of the same camera mirror offered by the Home Bar."""
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QDialog, QVBoxLayout

from actions import tr


class CameraWindow(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(tr("Camera mirror"))
        self.resize(440, 320)
        self.view = QQuickWidget(self)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        path = Path(__file__).resolve().parents[2] / "plasma/plasmoids/org.monet.notch/contents/ui/CameraMirror.qml"
        self.view.setInitialProperties({"presented": False, "startOnOpen": True})
        self.view.setSource(QUrl.fromLocalFile(str(path)))
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)

    def update_surface(self, visible):
        mirror = self.view.rootObject()
        if mirror:
            mirror.setProperty("presented", visible and not self.isMinimized())

    def showEvent(self, event):
        super().showEvent(event)
        self.update_surface(True)

    def hideEvent(self, event):
        self.update_surface(False)
        super().hideEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self.update_surface(self.isVisible())
