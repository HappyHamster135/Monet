"""Desktop scratchpad editor. A floating pad is an independent top-level window."""
from PySide6.QtCore import QByteArray, QIODevice, QSaveFile, QSignalBlocker, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextDocument
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from actions import tr


class PreviewDocument(QTextDocument):
    # Scratchpad preview is local text, including when the note contains an image link.
    def loadResource(self, kind, url):
        return QByteArray()


class PadEditor(QWidget):
    openPad = Signal(str)

    def __init__(self, pads, ident="", floating=False):
        super().__init__()
        self.pads = pads
        self.floating = floating
        self.ident = ident
        self.revision = 0
        self.dirty = False
        self.busy = False
        self.setWindowIcon(QApplication.windowIcon())
        if floating:
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.setWindowFlag(Qt.WindowStaysOnTopHint)
            self.resize(400, 290)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        layout.addLayout(bar)
        self.choice = QComboBox()
        self.choice.setAccessibleName(tr("Choose a pad"))
        self.choice.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        bar.addWidget(self.choice, 1)
        self.create = QPushButton(tr("New pad"))
        self.create.clicked.connect(self.new)
        bar.addWidget(self.create)
        more = QToolButton()
        more.setText(tr("Pad options"))
        more.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(more)
        more.setMenu(self.menu)
        bar.addWidget(more)
        if not floating:
            self.menu.addAction(tr("Open floating pad"), self.detach)
        self.menu.addAction(tr("Rename…"), self.rename)
        self.preview_action = self.menu.addAction(tr("Preview Markdown"))
        self.preview_action.setCheckable(True)
        self.preview_action.toggled.connect(self.preview)
        self.menu.addAction(tr("Copy all"), self.copy)
        self.menu.addAction(tr("Export text…"), self.export)
        self.menu.addSeparator()
        self.menu.addAction(tr("Delete pad…"), self.remove)
        self.edit = QPlainTextEdit()
        self.edit.setAccessibleName(tr("Pad text"))
        self.edit.setPlaceholderText(tr("Write a note…"))
        layout.addWidget(self.edit, 1)
        self.rendered = QTextBrowser()
        self.rendered.setOpenLinks(False)
        self.rendered.setOpenExternalLinks(False)
        self.rendered.setDocument(PreviewDocument(self.rendered))
        self.rendered.hide()
        layout.addWidget(self.rendered, 1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.hide()
        row = QHBoxLayout()
        row.addWidget(self.status, 1)
        self.retry = QPushButton(tr("Try again"))
        self.retry.clicked.connect(self.retry_io)
        self.retry.hide()
        row.addWidget(self.retry)
        layout.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(240)
        self.timer.timeout.connect(self.flush)
        self.edit.textChanged.connect(self.edited)
        self.choice.activated.connect(self.choose)
        self.pads.changed.connect(self.refresh)
        shortcut = QShortcut(QKeySequence.Save, self, activated=self.flush)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.edit.setReadOnly(True)
        QApplication.instance().aboutToQuit.connect(self.flush)
        self.refresh()
        self.edit.setFocus()

    def retry_io(self):
        if self.dirty:
            self.flush()
        else:
            self.refresh()

    def message(self, text, retry=False):
        self.retry.setVisible(retry)
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def show_result(self, result):
        ok = result.get("ok")
        if not ok and "pad" not in result:
            if result.get("problem") == "name":
                self.message(tr("Choose a name with 1 to 100 characters on one line."))
            else:
                self.message(tr("Could not save or load this pad. Your text is still in the editor."), retry=True)
            return False
        if self.retry.isVisibleTo(self):
            self.message("")
        self.edit.setReadOnly(False)
        pad = result["pad"]
        self.ident, self.revision = pad["id"], pad["revision"]
        with QSignalBlocker(self.choice):
            self.choice.clear()
            for entry in result["pads"]:
                self.choice.addItem(entry["name"], entry["id"])
            self.choice.setCurrentIndex(self.choice.findData(self.ident))
        if self.edit.toPlainText() != pad["body"]:
            with QSignalBlocker(self.edit):
                self.edit.setPlainText(pad["body"])
        if self.preview_action.isChecked():
            self.render_markdown(pad["body"])
        self.dirty = False
        self.setWindowTitle(tr("%1 · Scratchpad").replace("%1", pad["name"]))
        if result.get("recovered"):
            self.message(tr("This pad changed in another window. Your edits were saved in a separate pad."))
        elif not ok:
            self.message(tr("This pad changed. Review it and try again."))
        return bool(ok)

    def apply(self, action, value=""):
        self.busy = True
        try:
            result = self.pads.request(action, self.ident, self.revision, value)
            return self.show_result(result)
        finally:
            self.busy = False

    def refresh(self):
        if not self.busy and not self.dirty:
            self.apply("view")

    def edited(self):
        self.dirty = True
        self.message("")
        self.timer.start()

    def flush(self):
        self.timer.stop()
        return not self.dirty or self.apply("save", self.edit.toPlainText())

    def choose(self, index):
        requested = self.choice.itemData(index)
        if not self.flush():
            self.choice.setCurrentIndex(self.choice.findData(self.ident))
            return
        previous = self.ident
        self.ident = requested
        if not self.apply("select"):
            self.ident = previous
            self.choice.setCurrentIndex(self.choice.findData(previous))
        self.edit.setFocus()

    def new(self):
        if self.flush() and self.apply("new"):
            self.preview_action.setChecked(False)
            self.edit.setFocus()

    def detach(self):
        if self.flush():
            self.openPad.emit(self.ident)

    def rename(self):
        name, ok = QInputDialog.getText(self, tr("Rename pad"), tr("Pad name"), text=self.choice.currentText())
        if ok and name.strip() and self.flush():
            self.apply("rename", name)

    def copy(self):
        QApplication.clipboard().setText(self.edit.toPlainText())

    def render_markdown(self, text):
        self.rendered.document().setMarkdown(text, QTextDocument.MarkdownDialectGitHub | QTextDocument.MarkdownNoHTML)

    def preview(self, on):
        if on:
            self.render_markdown(self.edit.toPlainText())
        self.rendered.setVisible(on)
        self.edit.setVisible(not on)

    def export(self):
        dest, _ = QFileDialog.getSaveFileName(self, tr("Export pad"), "", tr("Text files (*.txt);;Markdown (*.md);;All files (*)"))
        if not dest:
            return
        data = self.edit.toPlainText().encode("utf-8")
        file = QSaveFile(dest)
        if not file.open(QIODevice.WriteOnly) or file.write(data) != len(data) or not file.commit():
            self.message(tr("The pad could not be exported."))

    def remove(self):
        if not self.flush():
            return
        ident, revision = self.ident, self.revision
        if QMessageBox.question(self, tr("Delete pad"), tr("Delete “%1” and its text?").replace("%1", self.choice.currentText()),
                                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes:
            if (ident, revision) == (self.ident, self.revision):
                self.apply("delete")
            else:
                self.message(tr("This pad changed. Review it and try again."))

    def hideEvent(self, event):
        self.flush()
        super().hideEvent(event)

    def closeEvent(self, event):
        if self.flush():
            super().closeEvent(event)
        else:
            event.ignore()
