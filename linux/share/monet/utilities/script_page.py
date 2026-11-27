"""Manage the scripts users can choose in desktop search."""
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from actions import tr
from saved_scripts import library, save


class ScriptEditor(QDialog):
    def __init__(self, settings, script, parent):
        super().__init__(parent)
        self.settings = settings
        self.script = script
        self.setWindowTitle(tr("Edit script") if script else tr("Add script"))
        form = QFormLayout(self)
        self.name = QLineEdit(script.name if script else "")
        self.path = QLineEdit(script.path if script else "")
        self.path.setAccessibleName(tr("Executable file"))
        form.addRow(tr("Script name"), self.name)
        files = QHBoxLayout()
        files.addWidget(self.path)
        browse = QPushButton(tr("Browse…"))
        browse.clicked.connect(self.choose)
        files.addWidget(browse)
        form.addRow(tr("Executable file"), files)
        self.needs_text = QCheckBox(tr("Require text after the script name"))
        self.needs_text.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.needs_text.setChecked(bool(script and script.needs_text))
        form.addRow(self.needs_text)
        self.preview = QCheckBox(tr("Run while typing to preview the output"))
        self.preview.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.preview.setChecked(bool(script and script.preview))
        form.addRow(self.preview)
        hint = QLabel(tr("Enable previews for scripts that can run repeatedly. The text after the name is passed as one argument."))
        hint.setWordWrap(True)
        form.addRow(hint)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setTextFormat(Qt.PlainText)
        self.problem.hide()
        form.addRow(self.problem)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(tr("Save"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("Cancel"))
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.resize(480, max(form.totalHeightForWidth(480), form.sizeHint().height()))

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose a script"), self.path.text() or str(Path.home()))
        if path:
            self.path.setText(path)
            if not self.name.text().strip():
                self.name.setText(Path(path).stem)

    def commit(self):
        try:
            self.script = save(self.settings, self.name.text(), self.path.text(), self.needs_text.isChecked(),
                               self.preview.isChecked(), self.script.ident if self.script else None)
        except (ValueError, OSError) as error:
            self.problem.setText(str(error))
            self.problem.show()
            self.resize(self.width(), max(self.height(), self.layout().totalHeightForWidth(self.width())))
            return
        self.accept()


class ScriptPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        hint = QLabel(tr("Type script: and a saved name in the Command Bar. Enter runs the script and copies its text output."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setAccessibleName(tr("Saved scripts"))
        self.list.currentItemChanged.connect(self.select)
        self.list.itemDoubleClicked.connect(lambda *_: self.edit(self.current()))
        layout.addWidget(self.list, 1)
        self.detail = QLabel()
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail.setTextFormat(Qt.PlainText)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        add = QPushButton(tr("Add script…"))
        add.clicked.connect(lambda: self.edit(None))
        self.edit_button = QPushButton(tr("Edit…"))
        self.edit_button.clicked.connect(lambda: self.edit(self.current()))
        self.remove_button = QPushButton(tr("Remove from list"))
        self.remove_button.clicked.connect(self.remove)
        self.try_button = QPushButton(tr("Open in Command Bar"))
        self.try_button.clicked.connect(self.open_search)
        for button in (add, self.edit_button, self.remove_button, self.try_button):
            actions.addWidget(button)
        actions.addStretch()

    def current(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def refresh(self, ident=None):
        self.list.clear()
        selected = 0
        for script in library(self.settings):
            item = QListWidgetItem(script.name)
            item.setData(Qt.UserRole, script)
            self.list.addItem(item)
            if script.ident == ident:
                selected = self.list.row(item)
        self.list.setCurrentRow(selected)
        self.select()

    def select(self, *_):
        script = self.current()
        for button in (self.edit_button, self.remove_button, self.try_button):
            button.setEnabled(bool(script))
        self.detail.setText(script.path if script else tr("Add a script to make it available in desktop search."))

    def edit(self, script):
        dialog = ScriptEditor(self.settings, script, self)
        from inline_dialogs import present_dialog
        present_dialog(dialog,self,lambda:self.refresh(dialog.script.ident))

    def remove(self):
        script = self.current()
        if script:
            self.settings.remove("savedScripts/" + script.ident)
            self.settings.sync()
            self.refresh()

    def open_search(self):
        script = self.current()
        if script and not QProcess.startDetached("krunner", ["--runner", "monet-utilities",
                                                              tr("script") + ": " + script.name + " "])[0]:
            self.detail.setText(tr("Could not open the Command Bar."))
