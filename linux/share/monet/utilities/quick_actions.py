"""Run desktop actions without opening the catalog or blocking its input thread."""
from collections import defaultdict, deque
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from actions import ACTIONS, tr


class QuickActions:
    def __init__(self, window):
        self.window = window
        self.queues = defaultdict(deque)
        self.busy = set()
        self.prompt = None
        self.error = None

    def trigger(self, key):
        if key in self.window.hidden:
            return
        if key == "empty-trash":
            if self.prompt:
                self.prompt.raise_()
                self.prompt.activateWindow()
                return
            if key in self.busy:
                return
            parent = self.window if self.window.isVisible() else None
            self.prompt = QMessageBox(parent)
            # KDE's native dialog adapter loses the default button when a custom
            # destructive button is present. Keep Enter bound to Cancel.
            self.prompt.setOption(QMessageBox.Option.DontUseNativeDialog, True)
            self.prompt.setIcon(QMessageBox.Warning)
            self.prompt.setWindowTitle(tr("Empty Trash"))
            self.prompt.setText(tr("Permanently delete all items in Trash?"))
            self.prompt.setInformativeText(tr("Items in Trash on connected drives will also be deleted."))
            self.prompt.addButton(QMessageBox.Cancel)
            empty = self.prompt.addButton(tr("Empty Trash"), QMessageBox.DestructiveRole)
            self.prompt.setDefaultButton(QMessageBox.Cancel)
            self.prompt.setEscapeButton(QMessageBox.Cancel)
            self.prompt.setAttribute(Qt.WA_QuitOnClose, False)

            def decided(_):
                prompt, self.prompt = self.prompt, None
                confirmed = prompt.clickedButton() is empty
                prompt.deleteLater()
                if confirmed:
                    self.enqueue(key)
                self.window.panelDismissed.emit()
            self.prompt.finished.connect(decided)
            self.prompt.open()
            self.prompt.raise_()
            self.prompt.activateWindow()
        else:
            self.enqueue(key)

    def enqueue(self, key):
        group = "appearance" if key in ("switch-appearance", "automatic-appearance") else key
        if group in self.busy and key in ("empty-trash", "lock-screen", "display-off"):
            return
        self.queues[group].append(key)
        if group not in self.busy:
            self.next_action(group)

    def next_action(self, group):
        queue = self.queues[group]
        while queue:
            key = queue.popleft()
            if key in self.window.hidden:
                continue
            self.busy.add(group)
            args = ["empty-trash"] if key == "empty-trash" else ["desktop-action", key]
            self.window.worker([self.window.helpers / "monet-quick", *args],
                               lambda output: self.result(group, key, output),
                               lambda error: self.failed(group, key, error))
            return
        self.busy.discard(group)
        del self.queues[group]
        self.window.panelDismissed.emit()

    def result(self, group, key, output):
        try:
            result = json.loads(output)
        except (ValueError, TypeError):
            result = {}
        if not isinstance(result, dict) or result.get("ok") is not True:
            message = result.get("message") if isinstance(result, dict) else ""
            self.failed(group, key, message or "")
            return
        message = result.get("message")
        if key == "empty-trash":
            message = tr("Trash emptied.")
        if self.window.isVisible() and message:
            self.window.issue(message)
        self.next_action(group)

    def failed(self, group, key, message):
        title = ACTIONS[key].name
        if not message:
            message = tr("Some items may still be in Trash.") if key == "empty-trash" else tr("The desktop could not complete this action.")
        if self.window.isVisible():
            self.window.issue(message)
        else:
            if self.error is None:
                self.error = QMessageBox()
                self.error.setIcon(QMessageBox.Information)
                self.error.setStandardButtons(QMessageBox.Ok)
                self.error.setAttribute(Qt.WA_QuitOnClose, False)
                self.error.setTextFormat(Qt.PlainText)
                self.error.finished.connect(self.error_closed)
            self.error.setWindowTitle(title)
            self.error.setText(message)
            self.error.open()
            self.error.raise_()
            self.error.activateWindow()
        self.next_action(group)

    def error_closed(self, _):
        self.error.deleteLater()
        self.error = None
        self.window.panelDismissed.emit()
