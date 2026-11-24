"""On-demand tools. A file shelf holds references to files, including directories."""
import json
import os
from pathlib import Path
from PySide6.QtCore import QFileSystemWatcher, QMimeData, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDrag, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFileSystemModel, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QListWidgetItem, QMenu, QPlainTextEdit, QPushButton, QTreeView, QVBoxLayout, QWidget)
from actions import stored, tr

def row(layout, *actions):
    bar = QHBoxLayout()
    for label, fn in actions:
        button = QPushButton(label)
        button.clicked.connect(fn)
        bar.addWidget(button)
    bar.addStretch()
    layout.addLayout(bar)

class ShelfList(QListWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.add_paths(stored(settings, "shelf", []), restore=True)
        self.itemDoubleClicked.connect(lambda item: QDesktopServices.openUrl(QUrl.fromLocalFile(item.data(Qt.UserRole))))

    def paths(self):
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]

    def save(self):
        self.settings.setValue("shelf", json.dumps(self.paths()))

    def add_paths(self, paths, restore=False):
        known = set(self.paths())
        for value in paths:
            if not isinstance(value, str) or not os.path.isabs(value):
                continue
            path = os.path.normpath(value)
            if path in known or (not restore and not os.path.exists(path)):
                continue
            item = QListWidgetItem(QIcon.fromTheme("folder" if os.path.isdir(path) else "text-x-generic"),
                                   Path(path).name or path)
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.addItem(item)
            known.add(path)
        if not restore:
            self.save()

    def forget(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))
        self.save()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            event.setDropAction(Qt.CopyAction)
            event.accept()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.setDropAction(Qt.CopyAction)
        event.accept()

    def startDrag(self, actions):
        urls = [QUrl.fromLocalFile(item.data(Qt.UserRole)) for item in self.selectedItems()]
        if urls:
            mime = QMimeData()
            mime.setUrls(urls)
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)

class Shelf(QWidget):
    def __init__(self, settings):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drop files here. Drag them out to attach or copy them."))
        self.files = ShelfList(settings)
        layout.addWidget(self.files)
        row(layout, ("Add files…", self.choose), ("Remove from shelf", self.files.forget))

    def choose(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add to file shelf")
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
        self.names = QListWidget()
        self.names.addItems(list(self.entries))
        layout.addWidget(self.names, 1)
        self.names.currentTextChanged.connect(self.select)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Write a snippet…")
        layout.addWidget(self.edit, 2)
        row(layout, ("New snippet…", self.add), ("Copy", self.copy), ("Remove", self.remove))
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
        self.edit.blockSignals(True)
        self.edit.setPlainText(self.entries.get(name, ""))
        self.edit.blockSignals(False)

    def add(self):
        name, ok = QInputDialog.getText(self, "New snippet", "Name")
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
            QApplication.clipboard().setText(self.edit.toPlainText())

    def remove(self):
        if self.current:
            del self.entries[self.current]
            self.names.takeItem(self.names.currentRow())
            self.settings.setValue("snippets", json.dumps(self.entries))
