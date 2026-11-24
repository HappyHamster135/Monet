"""Choose which media players respond to desktop shortcuts."""
import json

from PySide6.QtCore import QSettings, QSignalBlocker, QTimer, Qt, Slot, SLOT
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusServiceWatcher
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from actions import tr

SERVICE = "org.kde.kded6"
PATH = "/org/monet/MediaKeys"
INTERFACE = "org.monet.MediaKeys1"


def media_apps():
    from gi.repository import Gio
    choices = {}
    for app in Gio.AppInfo.get_all():
        ident = app.get_id() or ""
        if not ident.endswith(".desktop") or not app.should_show():
            continue
        categories = set((app.get_categories() or "").split(";"))
        types = app.get_supported_types() or []
        if categories & {"AudioVideo", "Audio", "Video", "Player", "WebBrowser"} or any(
                mime.startswith(("audio/", "video/")) for mime in types):
            icon = app.get_icon()
            choices["app:" + ident[:-8]] = (app.get_display_name(), icon.to_string() if icon else "")
    return choices


def request(method):
    message = QDBusMessage.createMethodCall(SERVICE, PATH, INTERFACE, method)
    message.setAutoStartService(False)
    return message


class MediaKeys(QWidget):
    def __init__(self):
        super().__init__()
        self.config = QSettings("Monet", "MediaKeys")
        self.catalog = media_apps()
        self.running = {}
        self.query = None
        self.dirty = False
        self.bus = QDBusConnection.sessionBus()
        layout = QVBoxLayout(self)
        hint = QLabel(tr("Choose which apps can respond to playback keys on your keyboard."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setEnabled(False)
        self.list.setAccessibleName(tr("Apps that can use media keys"))
        layout.addWidget(self.list, 1)
        self.fallback = QComboBox()
        self.fallback.setEnabled(False)
        form = QFormLayout()
        form.addRow(tr("Play key when no player is available"), self.fallback)
        layout.addLayout(form)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.list.itemChanged.connect(self.change_permission)
        self.fallback.currentIndexChanged.connect(self.select_fallback)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(60)
        self.refresh_timer.timeout.connect(self.refresh)
        self.bus.connect(SERVICE, PATH, INTERFACE, "PlayersChanged", self, SLOT("refreshSoon()"))
        self.watcher = QDBusServiceWatcher(SERVICE, self.bus, QDBusServiceWatcher.WatchForOwnerChange, self)
        self.watcher.serviceOwnerChanged.connect(self.refreshSoon)
        self.rebuild()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    @Slot()
    def refreshSoon(self):
        if self.isVisible():
            self.refresh_timer.start()

    def refresh(self):
        if self.query is not None:
            self.dirty = True
            return
        self.query = QDBusPendingCallWatcher(self.bus.asyncCall(request("Players"), 1500), self)
        self.query.finished.connect(self.received)

    def received(self, query):
        try:
            running = json.loads(query.reply().arguments()[0]) if not query.isError() else None
        except (TypeError, IndexError, ValueError):
            running = None
        available = isinstance(running, dict)
        self.status.setText("" if available else tr("The desktop media controller is unavailable in this session."))
        self.list.setEnabled(available)
        self.fallback.setEnabled(available)
        self.query = None
        query.deleteLater()
        if self.running != (running or {}):
            self.running = running or {}
            self.rebuild()
        if self.dirty:
            self.dirty = False
            self.refreshSoon()

    def blocked(self):
        return set(self.config.value("blocked", [], type=list))

    def labels(self):
        try:
            labels = json.loads(self.config.value("labels", "{}"))
            return labels if isinstance(labels, dict) else {}
        except (TypeError, ValueError):
            return {}

    def rebuild(self):
        blocked = self.blocked()
        fallback = self.config.value("fallback", "")
        labels = self.labels()
        position = self.list.verticalScrollBar().value()
        selected = self.list.currentItem()
        selected = selected.data(Qt.UserRole) if selected else ""
        ids = set(self.catalog) | set(self.running) | blocked
        if fallback:
            ids.add("app:" + fallback)
        def display(key):
            name, _ = self.catalog.get(key, ("", ""))
            return name or self.running.get(key) or labels.get(key) or key.partition(":")[2]
        with QSignalBlocker(self.list), QSignalBlocker(self.fallback):
            self.list.clear()
            self.fallback.clear()
            self.fallback.addItem(tr("Do nothing"), "")
            for key in sorted(ids, key=lambda k: (display(k).casefold(), k)):
                name = display(key)
                icon = QIcon.fromTheme(self.catalog.get(key, ("", "audio-x-generic"))[1])
                item = QListWidgetItem(icon, name)
                item.setToolTip(key.partition(":")[2])
                item.setData(Qt.UserRole, key)
                item.setCheckState(Qt.Unchecked if key in blocked else Qt.Checked)
                self.list.addItem(item)
                if key == selected:
                    self.list.setCurrentItem(item)
                if key.startswith("app:") and (key in self.catalog or key == "app:" + fallback):
                    self.fallback.addItem(icon, name, key[4:])
            self.fallback.setCurrentIndex(max(0, self.fallback.findData(fallback)))
            self.list.verticalScrollBar().setValue(position)

    def change_permission(self, item):
        key = item.data(Qt.UserRole)
        self.config.sync()
        blocked = self.blocked()
        labels = self.labels()
        if item.checkState() == Qt.Checked:
            blocked.discard(key)
            labels.pop(key, None)
        else:
            blocked.add(key)
            labels[key] = item.text()
            if key == "app:" + self.config.value("fallback", ""):
                self.config.remove("fallback")
                with QSignalBlocker(self.fallback):
                    self.fallback.setCurrentIndex(0)
        self.config.setValue("blocked", sorted(blocked))
        self.config.setValue("labels", json.dumps(labels, ensure_ascii=False))
        self.save()

    def select_fallback(self):
        ident = self.fallback.currentData() or ""
        self.config.sync()
        if ident:
            key = "app:" + ident
            self.config.setValue("blocked", sorted(self.blocked() - {key}))
            labels = self.labels()
            labels.pop(key, None)
            self.config.setValue("labels", json.dumps(labels, ensure_ascii=False))
            self.config.setValue("fallback", ident)
            with QSignalBlocker(self.list):
                for i in range(self.list.count()):
                    item = self.list.item(i)
                    if item.data(Qt.UserRole) == key:
                        item.setCheckState(Qt.Checked)
                        break
        else:
            self.config.remove("fallback")
        self.save()

    def save(self):
        self.config.sync()
        if self.config.status() != QSettings.NoError:
            self.status.setText(tr("Could not save media key settings."))
            return
        self.bus.asyncCall(request("Reload"), 1000)
