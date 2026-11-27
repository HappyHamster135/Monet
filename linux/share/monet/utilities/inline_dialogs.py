"""Present tool sub-editors in the same scroll surface, with ordinary dialog fallback."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QInputDialog, QLineEdit
from notch_style import ResponsiveTool


def present_dialog(dialog, parent, accepted=None, finished=None):
    widget = parent
    while widget is not None:
        host = getattr(widget, '_inline_dialog_host', None)
        if host:
            host.open(dialog, accepted, finished)
            return
        widget = widget.parentWidget()
    result = dialog.exec()
    if result == QDialog.Accepted and accepted: accepted()
    if finished: finished(result)
    dialog.deleteLater()


def text_prompt(parent, title, caption, accepted, password=False):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title); dialog.setLabelText(caption)
    dialog.setInputMode(QInputDialog.TextInput)
    if password: dialog.setTextEchoMode(QLineEdit.Password)
    present_dialog(dialog,parent,lambda:accepted(dialog.textValue()))


class InlineDialogs:
    def __init__(self, scroll):
        self.scroll = scroll
        self.stack = []

    def attach(self, page):
        page._inline_dialog_host = self

    def open(self, dialog, accepted, finished):
        previous = self.scroll.takeWidget()
        previous.hide()
        self.stack.append((previous,dialog))
        dialog.setWindowFlags(Qt.Widget)
        dialog.setModal(False)
        dialog.setProperty('notchInline', previous.property('notchInline'))
        self.attach(dialog)
        dialog.setMinimumSize(0,0); dialog.setMaximumSize(16777215,16777215)
        self.scroll.setWidget(dialog)
        dialog.notch_layout = ResponsiveTool(dialog,self.scroll)
        def complete(result):
            # A page switch rejects nested editors before detaching the page.
            if self.stack and self.stack[-1][1] is dialog:
                self.stack.pop()
                self.scroll.takeWidget(); dialog.hide()
                self.scroll.setWidget(previous); previous.show()
                if hasattr(previous,'notch_layout'): previous.notch_layout.timer.start(0)
            if result == QDialog.Accepted and accepted: accepted()
            if finished: finished(result)
            dialog.deleteLater()
        dialog.finished.connect(complete)
        dialog.show()

    def back(self):
        if not self.stack: return False
        self.stack[-1][1].reject()
        return True

    def close(self):
        while self.stack: self.back()
