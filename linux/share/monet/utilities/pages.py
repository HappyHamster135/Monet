"""On-demand desktop tools."""
import json
import os
from pathlib import Path
from html import escape
from PySide6.QtCore import QFileSystemWatcher, QTimer, QMimeDatabase, QProcess, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDrag, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QFileSystemModel, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QTreeView, QVBoxLayout, QWidget)
from actions import stored, tr
from shelf_content import ShelfEntry, from_mime, to_mime

def row(layout, *actions):
    bar = QHBoxLayout()
    for label, fn in actions:
        button = QPushButton(label)
        button.clicked.connect(fn)
        bar.addWidget(button)
    bar.addStretch()
    layout.addLayout(bar)

class ShelfList(QListWidget):
    changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.mime_types = QMimeDatabase()
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.add_entries((ShelfEntry.restore(record) for record in stored(settings, "shelf", [])), restore=True)
        self.itemActivated.connect(self.open_item)
        QShortcut(QKeySequence.Copy, self, activated=self.copy_selection, context=Qt.WidgetShortcut)
        QShortcut(QKeySequence.Paste, self, activated=self.paste, context=Qt.WidgetShortcut)

    def entries(self):
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]

    def paths(self):
        return [entry.value for entry in self.entries() if entry.kind == "file"]

    def save(self):
        self.settings.setValue("shelf", json.dumps([entry.record() for entry in self.entries()]))
        self.changed.emit()

    def add_paths(self, paths):
        self.add_entries(ShelfEntry.file(path) for path in paths)

    def add_entries(self, entries, restore=False):
        known = set(self.entries())
        before = self.count()
        for entry in entries:
            if not entry or entry in known:
                continue
            if entry.kind == "file":
                if not restore and not os.path.exists(entry.value):
                    continue
                icon = "folder" if os.path.isdir(entry.value) else self.mime_types.mimeTypeForFile(entry.value, QMimeDatabase.MatchExtension).iconName()
            else:
                icon = "internet-web-browser" if entry.kind == "link" else "edit-paste"
            item = QListWidgetItem(QIcon.fromTheme(icon), entry.name())
            item.setData(Qt.UserRole, entry)
            item.setData(Qt.UserRole + 1, icon)
            item.setToolTip("<qt>" + escape(entry.value[:500]).replace("\n", "<br>") + "</qt>")
            self.addItem(item)
            known.add(entry)
        if not restore and self.count() != before:
            self.save()

    def remove_keys(self, keys):
        before = self.count()
        for i in reversed(range(before)):
            if self.item(i).data(Qt.UserRole).key in keys:
                self.takeItem(i)
        if before != self.count():
            self.save()

    def forget(self):
        self.remove_keys({item.data(Qt.UserRole).key for item in self.selectedItems()})

    def open_item(self, item):
        entry = item.data(Qt.UserRole)
        if entry.kind != "text":
            QDesktopServices.openUrl(QUrl(entry.uri()))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Text"))
        layout = QVBoxLayout(dialog)
        preview = QPlainTextEdit()
        preview.setPlainText(entry.value)
        preview.setReadOnly(True)
        layout.addWidget(preview)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        copy = buttons.addButton(tr("Copy"), QDialogButtonBox.ActionRole)
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(entry.value))
        layout.addWidget(buttons)
        dialog.resize(480, 300)
        dialog.exec()

    @staticmethod
    def local_path(url):
        entry = ShelfEntry.from_url(url)
        return entry.value if entry and entry.kind == "file" else None

    def for_notch(self, payload):
        try:
            request = json.loads(payload)
        except ValueError:
            return "{}"
        if not isinstance(request, dict) or request.get("action") not in ("view", "add", "remove"):
            return "{}"
        action = request["action"]
        modern = request.get("version") == 2
        urls = request.get("urls", [])
        if not isinstance(urls, list) or (action == "add" and len(urls) > 100):
            return "{}"
        entries = []
        for url in urls:
            entry = ShelfEntry.from_url(QUrl(url)) if isinstance(url, str) else None
            if not entry or (not modern and entry.kind != "file"):
                return "{}"
            entries.append(entry)
        if modern and "text" in request:
            entry = ShelfEntry.from_text(request["text"])
            if not entry or entries or action != "add":
                return "{}"
            entries.append(entry)
        if action == "add":
            self.add_entries(entries)
        elif action == "remove":
            keys = request.get("keys", []) if modern else []
            if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
                return "{}"
            self.remove_keys(set(keys).union(entry.key for entry in entries))
        rows = []
        for i in range(self.count()):
            item = self.item(i)
            entry = item.data(Qt.UserRole)
            if not modern and entry.kind != "file":
                continue
            row = {"name": item.text(), "icon": item.data(Qt.UserRole + 1), "url": entry.uri(), "path": entry.value}
            if modern:
                row.update(key=entry.key, kind=entry.kind)
            rows.append(row)
        missing = bool(action == "add" and set(entries).difference(self.entries()))
        return json.dumps({"version": 2, "rows": rows, "missing": missing})

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if (event.source() is not self and not mime.hasFormat("application/x-monet-shelf-drag")
                and event.possibleActions() & Qt.CopyAction and from_mime(mime)):
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is self or not event.possibleActions() & Qt.CopyAction:
            event.ignore()
        else:
            event.setDropAction(Qt.CopyAction)
            event.accept()

    def dropEvent(self, event):
        self.dragEnterEvent(event)
        if event.isAccepted():
            self.add_entries(from_mime(event.mimeData()))

    def selected_entries(self):
        return [item.data(Qt.UserRole) for item in sorted(self.selectedItems(), key=self.row)]

    def copy_selection(self):
        entries = self.selected_entries()
        if entries:
            QGuiApplication.clipboard().setMimeData(to_mime(entries))

    def paste(self):
        mime = QGuiApplication.clipboard().mimeData()
        if mime:
            self.add_entries(from_mime(mime))

    def startDrag(self, actions):
        entries = self.selected_entries()
        if entries:
            drag = QDrag(self)
            mime = to_mime(entries)
            mime.setData("application/x-monet-shelf-drag", b"1")
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)

class Shelf(QWidget):
    def __init__(self, settings):
        super().__init__()
        layout = QVBoxLayout(self)
        hint = QLabel(tr("Drop files, links or selected text here. Drag them out to use them in another app."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.files = ShelfList(settings)
        layout.addWidget(self.files)
        row(layout, (tr("Add files…"), self.choose), (tr("Paste"), self.files.paste),
            (tr("Remove from shelf"), self.files.forget))

    def choose(self):
        paths, _ = QFileDialog.getOpenFileNames(self, tr("Add files…"))
        self.files.add_paths(paths)

class Downloads(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        self.path = QLabel()
        self.path.setTextFormat(Qt.PlainText)
        self.path.setWordWrap(True)
        layout.addWidget(self.path)
        self.model = QFileSystemModel(self)
        self.model.setReadOnly(True)
        self.view = QTreeView()
        self.view.setModel(self.model)
        self.view.setRootIsDecorated(False)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(3, Qt.DescendingOrder)
        self.view.setColumnWidth(0, 245)
        self.view.doubleClicked.connect(lambda index: QDesktopServices.openUrl(QUrl.fromLocalFile(self.model.filePath(index))))
        layout.addWidget(self.view)
        self.folder_watch = QFileSystemWatcher(self)
        self.folder_watch.directoryChanged.connect(self.refresh)
        self.unavailable = QLabel(tr("The watched folder is unavailable."))
        layout.addWidget(self.unavailable)
        row(layout, (tr("Watch another folder…"), self.choose), (tr("Use Downloads folder"), self.reset_folder))
        self.refresh()

    def refresh(self):
        path = self.settings.value("downloads", "")
        if not isinstance(path, str) or not os.path.isabs(path):
            path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        self.path.setText(path)
        available = os.path.isdir(path) and os.access(path, os.R_OK | os.X_OK)
        index = self.model.setRootPath(path) if available else None
        available = bool(index and index.isValid())
        if available:
            self.view.setRootIndex(index)
        self.view.setVisible(available)
        self.unavailable.setVisible(not available)
        # Watch the parent to detect removal or reconnection without revisiting
        # the system roots while the selected folder is unavailable.
        if self.isVisible():
            parent = Path(path).parent
            while not parent.is_dir() and parent != parent.parent:
                parent = parent.parent
            desired = str(parent)
            watched = self.folder_watch.directories()
            if desired not in watched:
                if watched:
                    self.folder_watch.removePaths(watched)
                self.folder_watch.addPath(desired)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        watched = self.folder_watch.directories()
        if watched:
            self.folder_watch.removePaths(watched)
        super().hideEvent(event)

    def reset_folder(self):
        self.settings.remove("downloads")
        self.refresh()

    def choose(self):
        path = QFileDialog.getExistingDirectory(self, tr("Watch a folder"), self.path.text())
        if path:
            self.settings.setValue("downloads", path)
            self.refresh()

class Snippets(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.current = None
        layout = QVBoxLayout(self)
        self.entries = stored(settings, "snippets", {})
        self.shortcuts = stored(settings, "snippetShortcuts", {})
        self.variables = stored(settings, "snippetVariables", {})
        self.names = QListWidget()
        self.names.addItems(list(self.entries))
        layout.addWidget(self.names, 1)
        self.names.currentTextChanged.connect(self.select)
        self.edit = QPlainTextEdit()
        self.edit.setInputMethodHints(Qt.ImhSensitiveData)
        self.edit.setPlaceholderText(tr("Write a snippet…"))
        layout.addWidget(self.edit, 2)
        self.shortcut = QPushButton()
        self.shortcut.clicked.connect(self.edit_shortcut)
        options = QHBoxLayout()
        options.addWidget(self.shortcut, 1)
        self.variables_button = QPushButton(tr("Variables"))
        self.variables_menu = QMenu(self.variables_button)
        self.expand_action = self.variables_menu.addAction(tr("Expand variables in this snippet"))
        self.expand_action.setCheckable(True)
        self.expand_action.triggered.connect(self.enable_variables)
        self.variables_menu.addSeparator()
        for label, token in ((tr("Current date"), "{{date}}"), (tr("Current time"), "{{time}}"),
                             (tr("Date and time"), "{{datetime}}"), (tr("Clipboard text"), "{{clipboard}}")):
            self.variables_menu.addAction(label, lambda checked=False, value=token: self.insert_variable(value))
        self.variables_menu.addAction(tr("Custom date or time…"), self.custom_format)
        self.variables_button.setMenu(self.variables_menu)
        options.addWidget(self.variables_button)
        layout.addLayout(options)
        row(layout, (tr("New snippet…"), self.add), (tr("Copy"), self.copy), (tr("Remove"), self.remove),
            (tr("Set up typing…"), self.setup))
        self.select("")
        self.names.setCurrentRow(0)
        self.edit.setEnabled(self.current is not None)
        self.edit.textChanged.connect(self.save)

    def save(self):
        if self.current:
            self.entries[self.current] = self.edit.toPlainText()
            self.settings.setValue("snippets", json.dumps(self.entries))

    def select(self, name):
        self.current = name or None
        self.edit.setEnabled(bool(name))
        self.shortcut.setEnabled(bool(name))
        self.variables_button.setEnabled(bool(name))
        self.expand_action.setChecked(self.variables.get(name) is True)
        trigger = self.shortcuts.get(name)
        self.shortcut.setText(tr("Typing shortcut: %s") % (";" + trigger + ";")
                              if isinstance(trigger, str) and trigger else tr("Add typing shortcut…"))
        self.edit.blockSignals(True)
        self.edit.setPlainText(self.entries.get(name, ""))
        self.edit.blockSignals(False)

    def enable_variables(self, enabled):
        if self.current:
            if enabled:
                self.variables[self.current] = True
            else:
                self.variables.pop(self.current, None)
            self.settings.setValue("snippetVariables", json.dumps(self.variables))
            self.expand_action.setChecked(enabled)

    def insert_variable(self, token):
        if self.current and token:
            self.enable_variables(True)
            self.edit.insertPlainText(token)
            self.edit.setFocus()

    def custom_format(self):
        from snippet_format import choose_format
        self.insert_variable(choose_format(self))

    def edit_shortcut(self):
        from snippet_rules import valid_shortcut
        name = self.current
        if not name:
            return
        current = self.shortcuts.get(name, "")
        while True:
            choice, ok = QInputDialog.getText(
                self, tr("Typing shortcut"),
                tr("Use a word such as hello to expand ;hello; as you type. Leave it empty to remove the shortcut."),
                text=current, inputMethodHints=Qt.ImhSensitiveData)
            if not ok:
                return
            current = choice.strip()
            if current and not valid_shortcut(current):
                QMessageBox.information(self, tr("Typing shortcut"),
                                        tr("Use up to 40 letters, numbers, underscores or hyphens."))
                continue
            if current and any(key != name and value == current for key, value in self.shortcuts.items()):
                QMessageBox.information(self, tr("Typing shortcut"), tr("Another snippet already uses this shortcut."))
                continue
            if current:
                self.shortcuts[name] = current
            else:
                self.shortcuts.pop(name, None)
            self.settings.setValue("snippetShortcuts", json.dumps(self.shortcuts))
            self.settings.sync()
            self.select(name)
            return

    def setup(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Set up snippet typing"))
        layout = QVBoxLayout(dialog)
        help_text = QLabel(tr("Choose IBus Wayland in Virtual Keyboard, then enable Monet Text Snippets. You can switch input methods in IBus Preferences."))
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        def launch(command, args):
            if not QProcess.startDetached(command, args)[0]:
                QMessageBox.information(dialog, dialog.windowTitle(), tr("The input settings could not be opened."))
        row(layout, (tr("Virtual Keyboard"), lambda: launch("systemsettings", ["kcm_virtualkeyboard"])),
            (tr("IBus Preferences"), lambda: launch("ibus-setup", [])))
        enable = QPushButton(tr("Enable Monet Text Snippets"))
        layout.addWidget(enable)
        feedback = QLabel()
        feedback.setWordWrap(True)
        layout.addWidget(feedback)
        process = QProcess(dialog)
        def activate():
            enable.setEnabled(False)
            feedback.setText(tr("Connecting to IBus…"))
            process.start("/usr/bin/python3", [str(Path(__file__).with_name("snippet_input.py")), "--activate"])
        def result(code, status):
            enable.setEnabled(True)
            if status == QProcess.NormalExit and code == 0:
                feedback.setText(tr("Snippet typing is active."))
            elif code == 1:
                feedback.setText(tr("IBus is unavailable. Select IBus Wayland in Virtual Keyboard and apply the change."))
            elif code == 2:
                feedback.setText(tr("IBus has not loaded Monet Text Snippets yet. Reopen IBus Wayland or sign in again."))
            else:
                feedback.setText(tr("Could not activate snippet typing. Check the input methods in IBus Preferences."))
        deadline = QTimer(dialog)
        deadline.setSingleShot(True)
        deadline.timeout.connect(process.kill)
        process.started.connect(lambda: deadline.start(10000))
        process.finished.connect(lambda *_: deadline.stop())
        process.finished.connect(result)
        process.errorOccurred.connect(lambda error: result(-1, QProcess.CrashExit) if error == QProcess.FailedToStart else None)
        enable.clicked.connect(activate)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        dialog.deleteLater()

    def add(self):
        name, ok = QInputDialog.getText(self, tr("New snippet"), tr("Name"), inputMethodHints=Qt.ImhSensitiveData)
        name = name.strip()
        if ok and name:
            if name not in self.entries:
                self.entries[name] = ""
                self.names.addItem(name)
            self.names.setCurrentItem(self.names.findItems(name, Qt.MatchExactly)[0])
            self.save()
            self.edit.setFocus()

    def copy(self):
        from PySide6.QtWidgets import QApplication
        if self.current:
            clipboard = QApplication.clipboard()
            text = self.edit.toPlainText()
            if self.expand_action.isChecked():
                from snippet_variables import ClipboardUnavailable, current_text, expand
                try:
                    # An offer owned by this window cannot answer a Wayland
                    # reader while this GUI thread is waiting for it.
                    local = clipboard.ownsClipboard() or QGuiApplication.platformName() != "wayland"
                    text = expand(text, clipboard.text if local else current_text)
                except ClipboardUnavailable:
                    QMessageBox.information(self, tr("Text snippets"), tr("Copy some text first."))
                    return
            clipboard.setText(text)

    def remove(self):
        if self.current:
            del self.entries[self.current]
            self.enable_variables(False)
            self.shortcuts.pop(self.current, None)
            self.settings.setValue("snippetShortcuts", json.dumps(self.shortcuts))
            self.names.takeItem(self.names.currentRow())
            self.settings.setValue("snippets", json.dumps(self.entries))
