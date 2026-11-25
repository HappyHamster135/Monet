"""Edit the profiles and nested menus opened by the pointer wheel."""
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QPushButton, QStyle, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from actions import ACTIONS, preferences, tr
from wheel_profiles import Entry, Profile, SLOTS, favorites_profile, profiles, save_profile, shortcut_components, web_address


def pick(owner, title, choices):
    dialog = QDialog(owner)
    dialog.setWindowTitle(title)
    dialog.resize(400, 380)
    layout = QVBoxLayout(dialog)
    query = QLineEdit()
    query.setPlaceholderText(tr("Search"))
    query.setClearButtonEnabled(True)
    layout.addWidget(query)
    items = QListWidget()
    items.setAccessibleName(title)
    layout.addWidget(items)
    for entry in sorted(choices, key=lambda e: e.title.casefold()):
        row = QListWidgetItem(QIcon.fromTheme(entry.icon_name), entry.title, items)
        row.setToolTip(entry.value)
        row.setData(Qt.UserRole, entry)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    items.itemActivated.connect(lambda _: dialog.accept())
    def filter_rows(text):
        needle = text.strip().casefold()
        first = None
        for i in range(items.count()):
            row = items.item(i)
            row.setHidden(needle not in (row.text() + " " + row.toolTip()).casefold())
            if first is None and not row.isHidden():
                first = row
        items.setCurrentItem(first)
        buttons.button(QDialogButtonBox.Ok).setEnabled(first is not None)
    query.textChanged.connect(filter_rows)
    filter_rows("")
    if dialog.exec() and items.currentItem() and not items.currentItem().isHidden():
        return items.currentItem().data(Qt.UserRole)
    return None


class ItemTree(QTreeWidget):
    moved = Signal()

    def move_item(self, item, target, index):
        source = item.parent() or self.invisibleRootItem()
        pos = source.indexOfChild(item)
        ancestor = target
        while ancestor is not None:
            if ancestor is item:
                return False
            ancestor = ancestor.parent()
        if source is not target and target.childCount() >= SLOTS:
            return False
        if source is target and pos < index:
            index -= 1
        source.takeChild(pos)
        target.insertChild(index, item)
        target.setExpanded(True)
        self.setCurrentItem(item)
        self.moved.emit()
        return True

    def dropEvent(self, event):
        event.ignore()
        item = self.currentItem()
        if not item or item is self.topLevelItem(0) or event.source() is not self:
            return
        over = self.itemAt(event.position().toPoint())
        position = self.dropIndicatorPosition()
        if over is None or position == QAbstractItemView.OnViewport:
            return
        if position == QAbstractItemView.OnItem:
            if over is not self.topLevelItem(0) and over.data(0, Qt.UserRole).kind != "menu":
                return
            target = over
        else:
            target = over.parent()
        if target is None or (target is not item.parent() and target.childCount() >= SLOTS):
            return
        super().dropEvent(event)
        if event.isAccepted():
            target.setExpanded(True)
            self.moved.emit()


class WheelEditor(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.settings = owner.settings
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        layout.addLayout(header)
        label = QLabel(tr("Active wheel"))
        self.selector = QComboBox()
        self.selector.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.selector.setMinimumContentsLength(8)
        label.setBuddy(self.selector)
        header.addWidget(label)
        header.addWidget(self.selector, 1)
        new = QPushButton(tr("New wheel…"), clicked=self.new_profile)
        header.addWidget(new)
        self.options = QToolButton()
        self.options.setText(tr("Wheel options"))
        self.options.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.options.setAccessibleName(tr("Wheel options"))
        self.options.setToolTip(tr("Wheel options"))
        menu = QMenu(self.options)
        menu.addAction(tr("Keyboard shortcut…"), self.edit_shortcut)
        self.rename_wheel = menu.addAction(tr("Rename wheel…"), self.rename_profile)
        self.delete_wheel = menu.addAction(tr("Delete wheel…"), self.delete_profile)
        self.options.setMenu(menu)
        self.options.setPopupMode(QToolButton.InstantPopup)
        header.addWidget(self.options)
        self.selector.currentIndexChanged.connect(self.select_profile)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.tree = ItemTree()
        self.tree.setAccessibleName(tr("Wheel items"))
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.moved.connect(self.save_items)
        self.tree.currentItemChanged.connect(self.update_controls)
        layout.addWidget(self.tree, 1)
        bar = QHBoxLayout()
        layout.addLayout(bar)
        self.add = QPushButton(tr("Add item"))
        menu = QMenu(self.add)
        for kind, label in (("tool", tr("Utility…")), ("app", tr("Application…")), ("file", tr("File…")),
                            ("folder", tr("Folder…")), ("url", tr("Web link…")), ("shortcut", tr("Desktop shortcut…")),
                            ("menu", tr("Submenu…"))):
            menu.addAction(label, lambda checked=False, k=kind: self.add_item(k))
        self.add.setMenu(menu)
        bar.addWidget(self.add)
        self.edit_favorites = QPushButton(tr("Edit Quick Panel favorites…"), clicked=self.defaults)
        bar.addWidget(self.edit_favorites)
        bar.addStretch()
        self.up = self.control(bar, "go-up", tr("Move up"), lambda: self.move(-1))
        self.down = self.control(bar, "go-down", tr("Move down"), lambda: self.move(1))
        self.indent = self.control(bar, "format-indent-more", tr("Move into preceding submenu"), self.move_in)
        self.outdent = self.control(bar, "format-indent-less", tr("Move out of submenu"), self.move_out)
        self.rename = self.control(bar, "edit-rename", tr("Rename item…"), self.rename_item)
        self.remove = self.control(bar, "list-remove", tr("Remove item"), self.remove_item)

    @staticmethod
    def control(layout, icon, label, fn):
        button = QToolButton()
        arrows = {"go-up": QStyle.SP_ArrowUp, "go-down": QStyle.SP_ArrowDown,
                  "format-indent-more": QStyle.SP_ArrowRight, "format-indent-less": QStyle.SP_ArrowLeft}
        if icon in arrows:
            button.setIcon(QIcon.fromTheme(icon, button.style().standardIcon(arrows[icon])))
        else:
            button.setText(label)
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setAccessibleName(label)
        button.setToolTip(label)
        button.clicked.connect(fn)
        layout.addWidget(button)
        return button

    def refresh(self):
        self.settings.sync()
        self.profiles = profiles(self.settings)
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem(tr("Quick Panel favorites"), "")
        for key, profile in sorted(self.profiles.items(), key=lambda pair: pair[1].name.casefold()):
            self.selector.addItem(profile.name, key)
        selected = self.selector.findData(self.settings.value("activeWheel", ""))
        self.selector.setCurrentIndex(max(0, selected))
        self.selector.blockSignals(False)
        self.display()

    def select_profile(self):
        self.settings.setValue("activeWheel", self.selector.currentData())
        self.settings.sync()
        self.display()

    def display(self):
        key = self.selector.currentData()
        self.favorites, self.hidden = preferences(self.settings)
        profile = self.profiles[key] if key else favorites_profile([k for k in self.favorites if k not in self.hidden])
        self.tree.blockSignals(True)
        self.tree.clear()
        self.root = QTreeWidgetItem(self.tree, [profile.name])
        self.root.setIcon(0, QIcon.fromTheme("view-more"))
        self.root.setFlags(self.root.flags() & ~Qt.ItemIsDragEnabled)
        for entry in profile.items:
            self.add_row(self.root, entry)
        self.tree.setCurrentItem(self.root)
        self.tree.blockSignals(False)
        self.tree.expandAll()
        self.tree.setDragDropMode(QAbstractItemView.InternalMove if key else QAbstractItemView.NoDragDrop)
        self.hint.setText(tr("Select a submenu to add items inside it. Each menu holds up to eight items.") if key
                          else tr("This wheel follows the first eight Quick Panel favorites."))
        self.options.setEnabled(bool(key))
        self.edit_favorites.setVisible(not key and "quick-panel" not in self.hidden)
        self.add.setVisible(bool(key))
        self.update_controls()

    def add_row(self, parent, entry):
        row = QTreeWidgetItem(parent, [entry.title])
        row.setData(0, Qt.UserRole, entry)
        fallback = QStyle.SP_DirIcon if entry.kind == "menu" or entry.icon_name == "folder" else QStyle.SP_FileIcon
        row.setIcon(0, QIcon.fromTheme(entry.icon_name, self.style().standardIcon(fallback)))
        row.setToolTip(0, entry.value or entry.title)
        if entry.kind == "menu":
            row.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        else:
            row.setFlags(row.flags() & ~Qt.ItemIsDropEnabled)
        for child in entry.children:
            self.add_row(row, child)
        return row

    def read_rows(self, parent):
        result = []
        for i in range(parent.childCount()):
            row = parent.child(i)
            entry = row.data(0, Qt.UserRole)
            result.append(replace(entry, children=self.read_rows(row)) if entry.kind == "menu" else entry)
        return tuple(result)

    def save_items(self):
        key = self.selector.currentData()
        if key:
            profile = Profile(self.selector.currentText(), self.read_rows(self.root))
            save_profile(self.settings, key, profile)
            self.profiles[key] = profile
        self.update_controls()

    def profile_name(self, old=""):
        value, ok = QInputDialog.getText(self, tr("Wheel name"), tr("Name"), text=old)
        name = value.strip()
        if not ok or not name:
            return ""
        if name.casefold() != old.casefold() and any(self.selector.itemText(i).casefold() == name.casefold()
                                                     for i in range(self.selector.count())):
            self.owner.issue(tr("A wheel with that name already exists."))
            return ""
        return name

    def new_profile(self):
        if name := self.profile_name():
            key = save_profile(self.settings, "", Profile(name, ()))
            self.settings.setValue("activeWheel", key)
            self.refresh()

    def edit_shortcut(self):
        from PySide6.QtQuickWidgets import QQuickWidget
        from wheel_shortcuts import assign, current
        import dbus
        key = self.selector.currentData()
        name = self.selector.currentText()
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Keyboard shortcut"))
        layout = QVBoxLayout(dialog)
        label = QLabel(tr("Open wheel “%1”").replace("%1", name))
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        layout.addWidget(label)
        recorder = QQuickWidget(dialog)
        # KDE inhibits existing desktop shortcuts only while recording keys.
        # We check conflicts on Save so another app never loses its binding.
        recorder.setInitialProperties({"checkForConflictsAgainst": 0, "multiKeyShortcutsAllowed": False,
                                       "showClearButton": False, "showCancelButton": False})
        recorder.setResizeMode(QQuickWidget.SizeRootObjectToView)
        recorder.loadFromModule("org.kde.kquickcontrols", "KeySequenceItem")
        item = recorder.rootObject()
        if not item:
            self.owner.issue(tr("The desktop shortcut recorder is unavailable."))
            dialog.deleteLater()
            return
        try:
            item.setProperty("keySequence", current(key, name))
        except dbus.DBusException:
            self.owner.issue(tr("Couldn’t reach the desktop shortcut service."))
            dialog.deleteLater()
            return
        recorder.setFixedHeight(max(32, round(item.implicitHeight())))
        recorder.setMinimumWidth(recorder.fontMetrics().horizontalAdvance("Meta+Ctrl+Shift+F12") + 48)
        recorder.setClearColor(dialog.palette().window().color())
        row = QHBoxLayout()
        layout.addLayout(row)
        row.addWidget(recorder, 1)
        clear = QPushButton(tr("Clear"))
        clear.clicked.connect(lambda: item.setProperty("keySequence", QKeySequence()))
        def update_clear():
            clear.setEnabled(not item.property("keySequence").isEmpty())
        item.keySequenceChanged.connect(update_clear)
        update_clear()
        row.addWidget(clear)
        status = QLabel()
        status.setTextFormat(Qt.PlainText)
        status.setWordWrap(True)
        status.hide()
        layout.addWidget(status)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def save():
            try:
                assign(key, name, self.owner.helpers, item.property("keySequence"))
            except (OSError, ValueError) as error:
                status.setText(str(error))
            except dbus.DBusException:
                status.setText(tr("Couldn’t reach the desktop shortcut service."))
            else:
                dialog.accept()
                return
            status.show()

        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()
        dialog.deleteLater()

    def rename_profile(self):
        if name := self.profile_name(self.selector.currentText()):
            key = self.selector.currentData()
            from wheel_shortcuts import rename
            import dbus
            try:
                rename(key, name, self.owner.helpers)
            except (OSError, dbus.DBusException):
                self.owner.issue(tr("Couldn’t update the wheel shortcut."))
                return
            save_profile(self.settings, key, replace(self.profiles[key], name=name))
            self.refresh()

    def delete_profile(self):
        key = self.selector.currentData()
        if key and QMessageBox.question(self, tr("Delete wheel?"),
                tr("Remove the wheel “%1” and its items?").replace("%1", self.selector.currentText())) == QMessageBox.Yes:
            from wheel_shortcuts import remove
            import dbus
            try:
                remove(key)
            except (OSError, dbus.DBusException):
                self.owner.issue(tr("Couldn’t remove the wheel shortcut."))
                return
            self.settings.remove("wheelProfiles/" + key)
            self.settings.setValue("activeWheel", "")
            self.refresh()

    def destination(self):
        row = self.tree.currentItem()
        if row is self.root or (row and row.data(0, Qt.UserRole).kind == "menu"):
            return row
        return (row.parent() if row else None) or self.root

    def update_controls(self):
        custom = bool(self.selector.currentData())
        row = self.tree.currentItem()
        if row is self.root:
            row = None
        parent = (row.parent() if row else None) or self.root
        index = parent.indexOfChild(row) if row else -1
        previous = parent.child(index-1) if index > 0 else None
        for button in (self.up, self.down, self.indent, self.outdent, self.rename, self.remove):
            button.setVisible(custom)
        self.add.setEnabled(custom and self.destination().childCount() < SLOTS)
        self.up.setEnabled(index > 0)
        self.down.setEnabled(0 <= index < parent.childCount()-1)
        self.indent.setEnabled(bool(previous and previous.data(0, Qt.UserRole).kind == "menu" and previous.childCount() < SLOTS))
        outer = parent.parent() or self.tree.invisibleRootItem()
        self.outdent.setEnabled(bool(row and parent is not self.root and outer.childCount() < SLOTS))
        self.rename.setEnabled(row is not None)
        self.remove.setEnabled(row is not None)

    def move(self, delta):
        row = self.tree.currentItem()
        parent = row.parent() or self.tree.invisibleRootItem()
        self.tree.move_item(row, parent, parent.indexOfChild(row) + (2 if delta > 0 else -1))

    def move_in(self):
        row = self.tree.currentItem()
        parent = row.parent() or self.tree.invisibleRootItem()
        prev = parent.child(parent.indexOfChild(row)-1)
        self.tree.move_item(row, prev, prev.childCount())

    def move_out(self):
        row = self.tree.currentItem()
        parent = row.parent()
        outer = parent.parent() or self.tree.invisibleRootItem()
        self.tree.move_item(row, outer, outer.indexOfChild(parent)+1)

    def rename_item(self):
        row = self.tree.currentItem()
        name, ok = QInputDialog.getText(self, tr("Rename item…"), tr("Name"), text=row.text(0))
        if ok and name.strip():
            row.setText(0, name.strip())
            row.setData(0, Qt.UserRole, replace(row.data(0, Qt.UserRole), name=name.strip()))
            self.save_items()

    def remove_item(self):
        row = self.tree.currentItem()
        if row.childCount() and QMessageBox.question(self, tr("Remove submenu?"),
                tr("Remove this submenu and its items from the wheel?")) != QMessageBox.Yes:
            return
        parent = row.parent() or self.tree.invisibleRootItem()
        parent.takeChild(parent.indexOfChild(row))
        self.save_items()

    def defaults(self):
        self.owner.toggle_panel()
        if self.owner.quick_panel:
            self.owner.quick_panel.edit()

    def add_item(self, kind):
        parent = self.destination()
        if not self.selector.currentData() or parent.childCount() >= SLOTS:
            return
        entry = self.choose_entry(kind)
        if entry:
            row = self.add_row(parent, entry)
            parent.setExpanded(True)
            self.tree.setCurrentItem(row)
            self.save_items()

    def choose_entry(self, kind):
        if kind == "tool":
            return pick(self, tr("Choose a utility"), (Entry("tool", k) for k in ACTIONS if k != "wheel" and k not in self.hidden))
        if kind == "app":
            from quit_protection import installed_apps
            return pick(self, tr("Choose an application"), (Entry("app", k, name, icon)
                        for k, (name, icon) in installed_apps().items()))
        if kind in ("file", "folder"):
            path = (QFileDialog.getExistingDirectory(self, tr("Choose a folder")) if kind == "folder"
                    else QFileDialog.getOpenFileName(self, tr("Choose a file"))[0])
            if path:
                return Entry("file", path, Path(path).name or path, "folder" if kind == "folder" else "text-x-generic")
        elif kind == "url":
            text, ok = QInputDialog.getText(self, tr("Web link…"), tr("Web address"))
            if ok:
                if url := web_address(text):
                    from PySide6.QtCore import QUrl
                    return Entry("url", url, QUrl(url).host())
                self.owner.issue(tr("Enter a valid web link."))
        elif kind == "menu":
            name, ok = QInputDialog.getText(self, tr("Submenu…"), tr("Name"))
            if ok and name.strip():
                return Entry("menu", name=name.strip())
        elif kind == "shortcut":
            import dbus
            try:
                api, components = shortcut_components()
                component = pick(self, tr("Shortcut group"), (Entry("shortcut", str(c[0]), str(c[1] or c[0])) for c in components))
                if component:
                    actions = api.allActionsForComponent([component.value, "", "", ""], timeout=2)
                    return pick(self, tr("Desktop shortcut…"), (Entry("shortcut", str(a[1]), str(a[3] or a[1]), component=str(a[0]))
                                for a in actions if a[0] and a[1]))
            except dbus.DBusException:
                self.owner.issue(tr("Desktop shortcuts are unavailable."))
        return None
