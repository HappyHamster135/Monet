"""Browse installed wallpapers and linked folders in the native Utilities window."""
from collections import OrderedDict
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QSize, QStandardPaths, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
                               QLabel, QListView, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QToolButton, QVBoxLayout, QWidget)

from actions import tr
from wallpapers import Collection, apply, catalog, formats, thumbnail


class Updates(QObject):
    catalog = Signal(object, object, str)
    preview = Signal(object, int, object, object)
    applied = Signal(str)


class WallpaperPage(QWidget):
    rows_per_page = 8

    def __init__(self, window):
        super().__init__()
        self.window_owner = window
        self.settings = window.settings
        self.collection = Collection(self.settings)
        self.readers = QThreadPool(self)
        self.readers.setMaxThreadCount(1)
        self.updates = Updates()
        self.updates.catalog.connect(self.got_catalog, Qt.QueuedConnection)
        self.updates.preview.connect(self.got_preview, Qt.QueuedConnection)
        self.updates.applied.connect(self.applied, Qt.QueuedConnection)
        self.scan = Event()
        self.previews = Event()
        self.cache = OrderedDict()
        self.entries = []
        self.filtered = []
        self.number = 0
        self.applying = False
        box = QVBoxLayout(self)
        top = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.setAccessibleName(tr("Wallpaper collection"))
        for title, key in [(tr("All wallpapers"), "all"), (tr("Included wallpapers"), "included"), (tr("My pictures"), "own")]:
            self.filter.addItem(title, key)
        index = self.filter.findData(self.settings.value("wallpaper/filter", "all"))
        self.filter.setCurrentIndex(max(0, index))
        self.filter.currentIndexChanged.connect(self.filter_changed)
        top.addWidget(self.filter)
        top.addStretch()
        sources = QToolButton()
        sources.setText(tr("Collection"))
        sources.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(sources)
        menu.addAction(tr("Add pictures…"), self.add_pictures)
        menu.addAction(tr("Add folder…"), self.add_folder)
        menu.addSeparator()
        self.remove_picture = menu.addAction(tr("Remove selected picture"), self.forget_selected)
        self.remove_picture.setEnabled(False)
        menu.addAction(tr("Manage sources…"), self.manage)
        sources.setMenu(menu)
        top.addWidget(sources)
        box.addLayout(top)

        self.grid = QListWidget()
        self.grid.setAccessibleName(tr("Wallpapers"))
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setMovement(QListView.Static)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setIconSize(QSize(120, 70))
        self.grid.setGridSize(QSize(130, 102))
        self.grid.setWordWrap(False)
        self.grid.setUniformItemSizes(True)
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid.currentRowChanged.connect(self.selection_changed)
        self.grid.itemDoubleClicked.connect(self.apply_selected)
        for key in ("Return", "Enter"):
            shortcut = QShortcut(QKeySequence(key), self.grid, activated=self.apply_selected)
            shortcut.setContext(Qt.WidgetShortcut)
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self.picture_menu)
        box.addWidget(self.grid, 1)
        pages = QHBoxLayout()
        self.previous = self.arrow("go-previous", tr("Previous wallpapers"), -1)
        self.next = self.arrow("go-next", tr("Next wallpapers"), 1)
        self.count = QLabel()
        pages.addWidget(self.previous)
        pages.addWidget(self.count)
        pages.addWidget(self.next)
        pages.addStretch()
        light = QPushButton(tr("Light and wallpaper settings"))
        light.clicked.connect(lambda: window.run_tool("theme"))
        pages.addWidget(light)
        box.addLayout(pages)
        bottom = QHBoxLayout()
        self.all_screens = QCheckBox(tr("Apply to all displays"))
        self.all_screens.setChecked(self.settings.value("wallpaper/allDisplays", True, type=bool))
        self.all_screens.toggled.connect(lambda value: self.settings.setValue("wallpaper/allDisplays", value))
        self.all_screens.setToolTip(tr("Turn off to change only the display containing this window."))
        bottom.addWidget(self.all_screens)
        bottom.addStretch()
        self.use = QPushButton(tr("Apply wallpaper"))
        self.use.setEnabled(False)
        self.use.clicked.connect(self.apply_selected)
        bottom.addWidget(self.use)
        box.addLayout(bottom)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        box.addWidget(self.status)

    def arrow(self, icon, label, step):
        button = QToolButton()
        button.setIcon(QIcon.fromTheme(icon))
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.clicked.connect(lambda: self.move_page(step))
        return button

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        self.scan.set()
        self.previews.set()
        super().hideEvent(event)

    def refresh(self):
        self.scan.set()
        self.previews.set()
        if not self.isVisible():
            return
        self.scan = token = Event()
        roots = [Path(p) / "wallpapers" for p in QStandardPaths.standardLocations(QStandardPaths.GenericDataLocation)]
        c = self.collection
        sources = (tuple(c.files), tuple(c.folders), set(c.hidden))
        self.status.setText(tr("Loading wallpapers…"))
        updates = self.updates
        def read():
            try:
                entries = catalog(roots, *sources, token)
                if not token.is_set():
                    updates.catalog.emit(token, entries, "")
            except OSError as error:
                if not token.is_set():
                    updates.catalog.emit(token, [], str(error))
        self.readers.start(read)

    @Slot(object, object, str)
    def got_catalog(self, token, entries, error):
        if token is not self.scan or token.is_set():
            return
        self.entries = entries
        self.show_page()
        self.status.setText(error or ("" if self.filtered else tr("No wallpapers here yet. Add pictures or a folder from Collection.")))

    def filter_changed(self):
        self.settings.setValue("wallpaper/filter", self.filter.currentData())
        self.number = 0
        self.show_page()
        self.status.setText("" if self.filtered else tr("No wallpapers here yet. Add pictures or a folder from Collection."))

    def move_page(self, step):
        self.number += step
        self.show_page()

    def show_page(self):
        self.previews.set()
        self.previews = token = Event()
        choice = self.filter.currentData()
        self.filtered = [e for e in self.entries if choice == "all" or e.personal == (choice == "own")]
        total = (len(self.filtered) + self.rows_per_page - 1) // self.rows_per_page
        self.number = max(0, min(self.number, total - 1))
        offset = self.number * self.rows_per_page
        page = self.filtered[offset:offset + self.rows_per_page]
        selected = self.grid.currentItem()
        previous_path = selected.data(Qt.UserRole) if selected else None
        self.grid.clear()
        placeholder = QIcon.fromTheme("image-x-generic")
        for row, entry in enumerate(page):
            item = QListWidgetItem(placeholder, entry.name)
            item.setSizeHint(QSize(128, 98))
            item.setData(Qt.UserRole, str(entry.target))
            item.setToolTip(entry.name + "\n" + str(entry.target))
            self.grid.addItem(item)
            if str(entry.target) == previous_path:
                self.grid.setCurrentRow(row)
        self.previous.setEnabled(self.number > 0)
        self.next.setEnabled(self.number + 1 < total)
        self.count.setText(tr("Page {page} of {total}").format(page=self.number + 1, total=total) if total else "")
        self.selection_changed()
        updates = self.updates
        while len(self.cache) > 64 - self.rows_per_page:
            self.cache.popitem(last=False)
        cached = set(self.cache)
        def read():
            for row, entry in enumerate(page):
                if token.is_set():
                    return
                try:
                    stat = entry.preview.stat()
                except OSError:
                    continue
                key = (entry.preview, stat.st_mtime_ns, stat.st_size)
                image = None if key in cached else thumbnail(entry.preview)
                if not token.is_set():
                    updates.preview.emit(token, row, key, image)
        if page:
            self.readers.start(read)

    @Slot(object, int, object, object)
    def got_preview(self, token, row, key, image):
        if token is not self.previews or token.is_set():
            return
        if image is not None and not image.isNull():
            self.cache[key] = QIcon(QPixmap.fromImage(image))
        if key in self.cache:
            self.cache.move_to_end(key)
            self.grid.item(row).setIcon(self.cache[key])

    def selection_changed(self):
        entry = self.selected()
        self.use.setEnabled(entry is not None and not self.applying)
        self.remove_picture.setEnabled(entry is not None and entry.personal)

    def selected(self):
        row = self.grid.currentRow()
        index = self.number * self.rows_per_page + row
        if 0 <= row and index < len(self.filtered):
            return self.filtered[index]
        return None

    def apply_selected(self):
        entry = self.selected()
        if self.applying or not entry:
            return
        screen = self.window().screen()
        connector = None
        if not self.all_screens.isChecked():
            connector = screen.name() if screen else ""
        self.applying = True
        self.selection_changed()
        self.status.setText(tr("Applying wallpaper…"))
        updates = self.updates
        def work():
            try:
                apply(entry, connector)
                message = tr("Applied {name}.").format(name=entry.name)
            except Exception as error:
                message = str(error)
            updates.applied.emit(message)
        QThreadPool.globalInstance().start(work)

    @Slot(str)
    def applied(self, message):
        self.applying = False
        self.status.setText(message)
        self.selection_changed()

    def add_pictures(self):
        mask = " ".join("*." + ext for ext in sorted(formats()))
        paths, _ = QFileDialog.getOpenFileNames(self, tr("Add pictures…"), "", tr("Pictures ({formats})").format(formats=mask))
        if paths:
            self.collection.add(paths)
            self.show_personal()

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr("Add folder…"))
        if path:
            self.collection.add([path], folder=True)
            self.show_personal()

    def show_personal(self):
        self.filter.setCurrentIndex(self.filter.findData("own"))
        self.number = 0
        self.refresh()

    def picture_menu(self, point):
        item = self.grid.itemAt(point)
        if not item:
            return
        self.grid.setCurrentItem(item)
        entry = self.selected()
        if entry and entry.personal:
            menu = QMenu(self)
            remove = menu.addAction(tr("Remove from collection"))
            if menu.exec(self.grid.viewport().mapToGlobal(point)) == remove:
                self.forget_selected()

    def forget_selected(self):
        entry = self.selected()
        if entry and entry.personal:
            self.collection.forget(entry.target)
            self.refresh()

    def manage(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Manage wallpaper sources"))
        box = QVBoxLayout(dialog)
        hint = QLabel(tr("Remove a link here to take it out of your collection. Your pictures stay on disk."))
        hint.setWordWrap(True)
        box.addWidget(hint)
        sources = QListWidget()
        for folder, paths in [(True, self.collection.folders), (False, self.collection.files)]:
            for path in sorted(paths):
                item = QListWidgetItem(QIcon.fromTheme("folder" if folder else "image-x-generic"), str(path))
                item.setToolTip(str(path))
                item.setData(Qt.UserRole, (str(path), folder))
                sources.addItem(item)
        box.addWidget(sources)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        remove = buttons.addButton(tr("Remove from collection"), QDialogButtonBox.ActionRole)
        remove.setEnabled(False)
        sources.currentItemChanged.connect(lambda current, old: remove.setEnabled(current is not None))
        def forget():
            item = sources.takeItem(sources.currentRow())
            path, folder = item.data(Qt.UserRole)
            self.collection.forget(Path(path), folder)
            self.refresh()
        remove.clicked.connect(forget)
        buttons.rejected.connect(dialog.reject)
        box.addWidget(buttons)
        dialog.resize(440, 290)
        from inline_dialogs import present_dialog
        present_dialog(dialog,self)
