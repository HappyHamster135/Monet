import json
import os
from pathlib import Path
import re
import sys
from PySide6.QtCore import (QObject, QProcess, QSettings, Qt, QTimer, QUrl, Signal, Slot)
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage, QDBusServiceWatcher, QDBusVirtualObject
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QStackedWidget, QToolButton, QVBoxLayout, QWidget)
from actions import ACTIONS, DIRECT_ACTIONS, SEARCH_HINTS, clean_url, find_tools, preferences, tr
from pages import Downloads, Shelf, ShelfList, Snippets, row

MODULES = Path(__file__).resolve().parent
SERVICE = "org.monet.Utilities"

class Window(QMainWindow):
    panelDismissed = Signal()

    def __init__(self, helpers, defer_catalog=False):
        super().__init__()
        self.helpers = Path(helpers)
        self.settings = QSettings("Monet", "Utilities")
        self.favorites, self.hidden = preferences(self.settings)
        self.pages = {}
        self.notch_previews = {}
        self.mirror = None
        self.floating_pads = set()
        self.quick_panel = None
        self.favorites_wheel = None
        self.wheel_request = None
        self.wheel_serial = 0
        self.wheel_placement = None
        self.direct_actions = None
        self.pad_store = None
        self.agent_feed = None
        self.running = set()
        self.setWindowIcon(QIcon.fromTheme("applications-utilities"))
        self.resize(630, 490)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        top = QHBoxLayout()
        self.back = QToolButton()
        self.back.setIcon(QIcon.fromTheme("go-previous"))
        self.back.setAccessibleName("All tools")
        self.back.clicked.connect(self.home)
        top.addWidget(self.back)
        self.title = QLabel()
        font = self.title.font()
        font.setPointSizeF(font.pointSizeF() * 1.4)
        self.title.setFont(font)
        self.title.setTextFormat(Qt.PlainText)
        top.addWidget(self.title, 1)
        manage = QToolButton()
        manage.setIcon(QIcon.fromTheme("configure"))
        manage.setToolTip("Choose tools and favorites")
        manage.setAccessibleName(manage.toolTip())
        manage.clicked.connect(self.customize)
        top.addWidget(manage)
        layout.addLayout(top)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        home = QWidget()
        home_layout = QVBoxLayout(home)
        home_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a tool…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        self.search.returnPressed.connect(self.open_selected)
        home_layout.addWidget(self.search)
        self.catalog = QListWidget()
        self.catalog.setAlternatingRowColors(True)
        for key, step in ((Qt.Key_Down, 1), (Qt.Key_Up, -1)):
            shortcut = QShortcut(QKeySequence(key), self.search, activated=lambda step=step: self.step_result(step))
            shortcut.setContext(Qt.WidgetShortcut)
        self.catalog.itemClicked.connect(self.open_selected)
        for key in ("Return", "Enter"):
            shortcut = QShortcut(QKeySequence(key), self.catalog, activated=self.open_selected)
            shortcut.setContext(Qt.WidgetShortcut)
        home_layout.addWidget(self.catalog)
        self.stack.addWidget(home)
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.home)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self.home)
        self.catalog_pending = defer_catalog
        if defer_catalog:
            self.setWindowTitle(tr("Monet Utilities"))
        else:
            self.home()

    def showEvent(self, event):
        if self.catalog_pending and self.stack.currentIndex() == 0:
            self.home()
        super().showEvent(event)

    shelfChanged = Signal()

    def file_shelf(self):
        page = Shelf(self.settings)
        page.files.changed.connect(self.shelfChanged)
        return page

    def session_feed(self):
        if self.agent_feed is None:
            from session_feed import SessionFeed
            self.agent_feed = SessionFeed(self)
        return self.agent_feed

    def filter(self):
        self.catalog_pending = False
        self.catalog.clear()
        for key, _ in find_tools(self.search.text(), self.favorites, self.hidden):
            action = ACTIONS[key]
            entry = QListWidgetItem(QIcon.fromTheme(action.icon), action.name)
            entry.setData(Qt.UserRole, key)
            entry.setToolTip(tr(SEARCH_HINTS[key]) if key in SEARCH_HINTS else action.group)
            self.catalog.addItem(entry)
        self.catalog.setCurrentRow(0)
        if not self.catalog.count():
            self.status.showMessage("No matching tools. Use Customize to show hidden tools.")
        else:
            self.status.clearMessage()

    def step_result(self, step):
        if self.catalog.count():
            row = max(0, min(self.catalog.currentRow() + step, self.catalog.count() - 1))
            self.catalog.setCurrentRow(row)

    def open_selected(self, item=None):
        item = item or self.catalog.currentItem()
        if item:
            self.run_tool(item.data(Qt.UserRole))

    def home(self):
        self.setWindowTitle(tr("Monet Utilities"))
        self.title.setText("Utilities")
        self.back.hide()
        self.stack.setCurrentIndex(0)
        if self.search.text():
            self.search.clear()  # textChanged refreshes the list.
        else:
            self.filter()
        self.search.setFocus()

    def ensure_page(self, key, factory):
        if key not in self.pages:
            self.pages[key] = factory()
            self.stack.addWidget(self.pages[key])
        return self.pages[key]

    def page(self, key, factory):
        self.stack.setCurrentWidget(self.ensure_page(key, factory))
        self.setWindowTitle(ACTIONS[key].name)
        self.title.setText(ACTIONS[key].name)
        self.back.show()
        self.status.clearMessage()
        return self.pages[key]

    def customize(self, focus_tool=None):
        dialog = QDialog(self)
        dialog.setWindowTitle("Customize Utilities")
        layout = QVBoxLayout(dialog)
        hint = QLabel(tr("Choose which tools appear. Favorites open from the Quick Panel, and the first eight also appear in the wheel.")
                      + " " + tr("Hiding a tool also removes its controls from the notch."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        tree = QTreeWidget()
        tree.setHeaderLabels(["Tool", "Show", "Favorite"])
        for key, action in ACTIONS.items():
            item = QTreeWidgetItem(tree, [action.name])
            item.setData(0, Qt.UserRole, key)
            if key == focus_tool:
                tree.setCurrentItem(item, 1)
            item.setCheckState(1, Qt.Unchecked if key in self.hidden else Qt.Checked)
            if key != "quick-panel":
                item.setCheckState(2, Qt.Checked if key in self.favorites else Qt.Unchecked)
        tree.resizeColumnToContents(0)
        layout.addWidget(tree)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        def apply():
            hidden, favorites = [], []
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                key = item.data(0, Qt.UserRole)
                if item.checkState(1) != Qt.Checked:
                    hidden.append(key)
                elif item.checkState(2) == Qt.Checked:
                    favorites.append(key)
            visibility_changed = set(self.hidden) != set(hidden)
            agent_visibility_changed = ("agents" in self.hidden) != ("agents" in hidden)
            awake_changed = ("awake" in self.hidden) != ("awake" in hidden)
            alerts_changed = ("monitor-alerts" in self.hidden) != ("monitor-alerts" in hidden)
            self.hidden = hidden
            ordered = [key for key in self.favorites if key in favorites]
            self.save_favorites(ordered + [key for key in favorites if key not in ordered])
            self.settings.setValue("hidden", json.dumps(hidden))
            self.settings.sync()
            if awake_changed and self.settings.contains("awakeRules"):
                self.worker([self.helpers / "monet-quick", "keep-awake-rules"], lambda _: None, finish_on_close=True)
            if alerts_changed and self.settings.contains("monitorAlerts"):
                self.worker([sys.executable, MODULES / "monitor_alerts.py", "sync"], lambda _: None, finish_on_close=True)
            if visibility_changed:
                if "downloads" in hidden and "downloads" in self.pages:
                    downloads = self.pages.pop("downloads")
                    self.stack.removeWidget(downloads)
                    downloads.deleteLater()
                if "camera" in hidden and self.mirror:
                    self.mirror.close()
                if "watch" in hidden:
                    for preview in list(self.notch_previews.values()):
                        preview.close()
                QDBusConnection.sessionBus().send(QDBusMessage.createSignal("/Utilities", SERVICE, "ToolVisibilityChanged"))
            if agent_visibility_changed:
                if self.agent_feed:
                    self.agent_feed.refresh()
                if "agents" in self.pages:
                    self.pages["agents"].configure_provider()
                signal = QDBusMessage.createSignal("/Utilities", "org.monet.Utilities", "AgentVisibilityChanged")
                QDBusConnection.sessionBus().send(signal)
            dialog.accept()
        buttons.accepted.connect(apply)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(560, 420)
        if dialog.exec():
            if focus_tool and focus_tool in ACTIONS and focus_tool not in self.hidden:
                self.Open([focus_tool])
            else:
                self.home()
        dialog.deleteLater()

    def save_favorites(self, keys):
        self.favorites = list(dict.fromkeys(k for k in keys if k in ACTIONS and k != "quick-panel" and k not in self.hidden))
        self.settings.setValue("favorites", json.dumps(self.favorites))
        self.settings.sync()
        self.filter()

    def toggle_panel(self):
        if self.quick_panel and self.quick_panel.isVisible():
            self.quick_panel.hide()
            return
        self.settings.sync()
        self.favorites, self.hidden = preferences(self.settings)
        if "quick-panel" in self.hidden:
            self.panelDismissed.emit()
            return
        modal = QApplication.activeModalWidget()
        if modal:
            modal.raise_()
            modal.activateWindow()
            return
        if self.quick_panel is None:
            from quick_panel import QuickPanel
            self.quick_panel = QuickPanel()
            self.quick_panel.dismissed.connect(self.panelDismissed)
            self.quick_panel.reordered.connect(self.save_favorites)
            self.quick_panel.chosen.connect(self.open_favorite)
        self.quick_panel.present(self.favorites, self.hidden)

    def open_favorite(self, key):
        if key not in self.hidden and key in ACTIONS:
            if ACTIONS[key].command or key == "output":
                self.run_tool(key)
            else:
                self.Open([key])

    def wheel(self):
        if self.favorites_wheel and self.favorites_wheel.isVisible():
            self.favorites_wheel.hide()
            return
        if self.wheel_request is not None:
            self.wheel_request = None
            if self.wheel_placement:
                self.wheel_placement.stop()
            self.panelDismissed.emit()
            return
        self.settings.sync()
        self.favorites, self.hidden = preferences(self.settings)
        if "wheel" in self.hidden:
            self.panelDismissed.emit()
            return
        modal = QApplication.activeModalWidget()
        if modal:
            modal.raise_()
            modal.activateWindow()
            return
        keys = [k for k in self.favorites if k in ACTIONS and k not in self.hidden and k != "wheel"][:8]
        if not keys:
            if "quick-panel" not in self.hidden:
                if not (self.quick_panel and self.quick_panel.isVisible()):
                    self.toggle_panel()
                self.quick_panel.edit()
            else:
                self.customize()
                self.panelDismissed.emit()
            return
        if self.favorites_wheel is None:
            from favorites_wheel import FavoritesWheel
            self.favorites_wheel = FavoritesWheel()
            self.favorites_wheel.chosen.connect(self.open_favorite)
            self.favorites_wheel.dismissed.connect(self.wheel_dismissed)
        self.wheel_serial += 1
        token = str(self.wheel_serial)
        self.wheel_request = (token, keys)
        if QApplication.platformName().startswith("wayland"):
            # KWin arms its windowAdded handler before asking us to map the wheel.
            # A compositor without the KWin service can still open a normal chooser.
            from wheel_position import WheelPlacement
            try:
                self.wheel_placement = WheelPlacement(self, token, self.favorites_wheel.windowTitle())
            except OSError:
                self.show_wheel(token)
        else:
            self.show_wheel(token)

    def wheel_dismissed(self):
        if self.wheel_placement:
            self.wheel_placement.stop()
        self.panelDismissed.emit()

    def show_wheel(self, token, available=0):
        if self.wheel_request is None or self.wheel_request[0] != token:
            return False
        _, keys = self.wheel_request
        self.wheel_request = None
        if available <= 0:
            area = self.favorites_wheel.screen().availableGeometry()
            available = min(area.width(), area.height())
        self.favorites_wheel.present(keys, available)
        return True

    def issue(self, text):
        self.status.showMessage(text[:500], 12000)

    def worker(self, argv, done, failed=None, *, input_data=None, finish_on_close=False):
        job = QProcess(self)
        self.running.add(job)
        if finish_on_close:
            job.setProperty("finishOnClose", True)
        def close_if_requested():
            if finish_on_close and getattr(self, "close_after_process_action", False):
                if self.isVisible():
                    self.close_after_process_action = False
                else:
                    self.close()
        def finish(code, status):
            if job not in self.running:
                return
            out = bytes(job.readAllStandardOutput()).decode(errors="replace")
            err = bytes(job.readAllStandardError()).decode(errors="replace")
            self.running.remove(job)
            job.deleteLater()
            if code == 0 and status == QProcess.NormalExit:
                done(out)
            else:
                (failed or self.issue)(err.strip()[-400:] or "The operation could not be completed.")
            close_if_requested()
        job.finished.connect(finish)
        def error(reason):
            if reason == QProcess.FailedToStart and job in self.running:
                self.running.remove(job)
                job.deleteLater()
                (failed or self.issue)("Could not start " + Path(argv[0]).name)
                close_if_requested()
        job.errorOccurred.connect(error)
        job.start(str(argv[0]), [str(a) for a in argv[1:]])
        if input_data is not None:
            job.write(input_data)
            job.closeWriteChannel()
        return job

    def output_page(self, key, command):
        def make():
            box = QWidget()
            layout = QVBoxLayout(box)
            box.text = QPlainTextEdit()
            box.text.setReadOnly(True)
            layout.addWidget(box.text)
            box.refresh = lambda: self.worker(command, box.text.setPlainText, box.text.setPlainText)
            row(layout, ("Refresh", box.refresh))
            return box
        self.page(key, make).refresh()

    def show_devices(self):
        def make():
            box = QPlainTextEdit()
            box.setReadOnly(True)
            return box
        box = self.page("devices", make)
        def loaded(usb):
            from fan_control import hardware_fans
            fans = [f"{fan.name}  {fan.rpm} RPM" for fan in hardware_fans() if fan.rpm is not None]
            box.setPlainText("Fans\n" + ("\n".join(fans) or "No fan speed sensors reported.") + "\n\nUSB\n" + usb.strip())
        self.worker(["lsusb"], loaded)

    def cycle_output(self):
        def result(out):
            try:
                self.issue(json.loads(out)["message"])
            except (KeyError, ValueError):
                self.issue("The sound output could not be changed.")
        self.worker([self.helpers / "monet-quick", "cycle-output"], result)

    def cleaning_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Cleaning mode"))
        layout = QVBoxLayout(dialog)
        message = QLabel()
        message.setWordWrap(True)
        layout.addWidget(message)
        duration = QComboBox()
        duration.setAccessibleName(tr("Cleaning time"))
        for seconds, label in ((30, tr("30 seconds")), (60, tr("1 minute")), (120, tr("2 minutes"))):
            duration.addItem(label, seconds)
        saved = duration.findData(self.settings.value("cleaningSeconds", 60, type=int))
        duration.setCurrentIndex(saved if saved >= 0 else 1)
        options = QFormLayout()
        layout.addLayout(options)
        options.addRow(tr("Cleaning time"), duration)
        display = QComboBox(dialog)
        display.setObjectName("cleaningDisplay")
        display.setAccessibleName(tr("During cleaning"))
        display.addItem(tr("Lock the session"), "lock")
        native = QApplication.platformName().startswith("wayland") and any(
            (Path(root) / "kwin/plugins/monet_cleaning.so").is_file() for root in QApplication.libraryPaths())
        if native:
            display.addItem(tr("Darken displays"), "dark")
            display.addItem(tr("Keep desktop visible"), "visible")
        if native:
            options.addRow(tr("During cleaning"), display)
        else:
            display.hide()
        display.setCurrentIndex(max(0, display.findData(self.settings.value("cleaningDisplay", "lock"))))
        def describe():
            descriptions = {
                "lock": tr("Lock the screen while you wipe the keyboard, trackpad or display. When cleaning ends, unlock as usual."),
                "dark": tr("Pause desktop input and darken every display. Your desktop returns when cleaning ends."),
                "visible": tr("Pause desktop input while your apps stay visible. Click Finish cleaning or press Esc five times to return."),
            }
            message.setText(descriptions[display.currentData()])
        display.currentIndexChanged.connect(describe)
        describe()
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        start = buttons.addButton(tr("Start cleaning"), QDialogButtonBox.AcceptRole)
        start.setDefault(True)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(370, dialog.sizeHint().height())
        if dialog.exec() == QDialog.Accepted:
            seconds = duration.currentData()
            self.settings.setValue("cleaningSeconds", seconds)
            if native:
                self.settings.setValue("cleaningDisplay", display.currentData())
            if display.currentData() != "lock":
                self.start_desktop_cleaning(seconds, display.currentData() == "dark")
            else:
                self.worker([sys.executable, MODULES / "cleaning.py", str(seconds)], lambda _: None)

    def start_desktop_cleaning(self, seconds, dark):
        from PySide6.QtDBus import QDBusPendingCallWatcher
        bus = QDBusConnection.sessionBus()
        def request(path, interface, method, args, callback):
            message = QDBusMessage.createMethodCall("org.kde.KWin", path, interface, method)
            message.setArguments(args)
            watcher = QDBusPendingCallWatcher(bus.asyncCall(message, 3000), self)
            def finished(call):
                reply = call.reply()
                call.deleteLater()
                if reply.type() == QDBusMessage.ErrorMessage:
                    self.issue(tr("This option requires the Monet desktop cleaning component."))
                else:
                    callback(reply.arguments())
            watcher.finished.connect(finished)
        def began(result):
            if result != [True]:
                self.issue(tr("Could not start cleaning. Release the pointer and try again on an unlocked desktop."))
        # KWin returns false when the plugin is already loaded. Begin verifies
        # the Utilities owner, the time limit and the active session itself.
        def loaded(_):
            request("/org/monet/Cleaning", "org.monet.Cleaning", "Begin", [seconds, dark], began)
        request("/Plugins", "org.kde.KWin.Plugins", "LoadPlugin", ["monet_cleaning"], loaded)

    def link_settings(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        switch = QCheckBox(tr("Clean copied links automatically"))
        layout.addWidget(switch)
        detail = QLabel(tr("Remove common tracking parameters when you copy a plain web address. Formatted text, files and recognized signed links keep their original contents."))
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addStretch()
        command = [sys.executable, MODULES / "clipboard_links.py"]
        def read():
            switch.setEnabled(False)
            def show(result):
                switch.setChecked(result.strip() == "on")
                switch.setEnabled(True)
            self.worker([*command, "status"], show)
        def change(on):
            switch.setEnabled(False)
            def failed(message):
                self.issue(message)
                read()
            self.worker([*command, "on" if on else "off"], lambda _: read(), failed)
        switch.clicked.connect(change)
        page.refresh = read
        return page

    def pads(self):
        if self.pad_store is None:
            from scratchpads import Pads
            self.pad_store = Pads(self.settings)
            self.pad_store.changed.connect(self.padsChanged)
        return self.pad_store

    padsChanged = Signal()

    def floating_pad(self, ident):
        from pad_editor import PadEditor
        page = next((p for p in self.floating_pads if p.ident == ident), None)
        created = page is None
        if created:
            page = PadEditor(self.pads(), ident, floating=True)
            self.floating_pads.add(page)
            page.destroyed.connect(lambda: self.floating_pads.discard(page))
        page.showNormal() if page.isMinimized() else page.show()
        page.raise_()
        page.activateWindow()
        page.edit.setFocus()
        if created and QApplication.platformName().startswith("wayland"):
            # xdg-shell ignores WindowStaysOnTopHint. Scope the request to this pad.
            job = self.worker([sys.executable, MODULES / "float_pad.py", self.helpers], lambda _: None,
                              lambda _: page.message(tr("Could not keep this pad above other windows."))
                              if page in self.floating_pads else None)
            job.write(page.windowTitle().encode("utf-8"))
            job.closeWriteChannel()

    def pad_page(self):
        from pad_editor import PadEditor
        page = PadEditor(self.pads())
        page.openPad.connect(self.floating_pad)
        return page

    def select_from_screen(self, key, from_catalog=False):
        if key == "ocr":
            from screen_text import ScreenText
            page = self.ensure_page(key, lambda: ScreenText(self))
        else:
            from screen_colors import ScreenColors
            page = self.ensure_page(key, lambda: ScreenColors(self))
        page.pick(from_catalog)

    def camera_closed(self):
        self.mirror = None
        self.panelDismissed.emit()

    def run_tool(self, key):
        action = ACTIONS.get(key)
        if not action:
            self.home()
            return
        if key in DIRECT_ACTIONS:
            if self.direct_actions is None:
                from quick_actions import QuickActions
                self.direct_actions = QuickActions(self)
            self.direct_actions.trigger(key)
            return
        if action.command:
            program, *args = action.command
            program = str(self.helpers / program[1:]) if program.startswith("@") else program
            if key in ("clipboard", "mic"):
                self.worker([program, *args], lambda _: self.issue(action.name))
            elif not QProcess.startDetached(program, args)[0]:
                if not self.isVisible():
                    self.Open(["tools"])
                self.issue("Could not open " + action.name)
        elif key == "lock":
            self.cleaning_dialog()
        elif key == "shelf":
            self.page(key, self.file_shelf)
        elif key == "notes":
            self.page(key, self.pad_page).edit.setFocus()
        elif key == "scripts":
            from script_page import ScriptPage
            self.page(key, lambda: ScriptPage(self.settings)).refresh()
        elif key == "snippets":
            self.page(key, lambda: Snippets(self.settings))
        elif key == "calendars":
            from calendars import Calendars
            self.page(key, Calendars).reload()
        elif key == "downloads":
            self.page(key, lambda: Downloads(self.settings))
        elif key == "quick-panel":
            self.toggle_panel()
        elif key == "wheel":
            self.wheel()
        elif key == "media-keys":
            from media_keys import MediaKeys
            self.page(key, MediaKeys)
        elif key == "window-switcher":
            from window_switcher import WindowSwitcher
            self.page(key, WindowSwitcher)
        elif key == "extra-clicks":
            from extra_clicks import ExtraClicks
            self.page(key, ExtraClicks)
        elif key == "wheel-scrolling":
            from wheel_scrolling import WheelScrolling
            self.page(key, WheelScrolling)
        elif key == "quit-on-close":
            from quit_on_close import QuitOnClose
            self.page(key, QuitOnClose)
        elif key == "quit-protection":
            from quit_protection import QuitProtection
            self.page(key, QuitProtection)
        elif key == "link-settings":
            self.page(key, self.link_settings).refresh()
        elif key in ("clean", "plain"):
            clipboard = QApplication.clipboard()
            try:
                value = clipboard.text()
                if not value:
                    raise ValueError("Copy some text first.")
                clipboard.setText(clean_url(value) if key == "clean" else value)
                self.issue("Link copied." if key == "clean" else "Plain text copied.")
            except ValueError as error:
                self.issue(str(error))
        elif key in ("ports", "process-control"):
            from ports import ProcessBrowser
            self.page(key, lambda: ProcessBrowser(self, key == "ports")).refresh()
        elif key == "network":
            from network_page import NetworkPage
            self.page(key, lambda: NetworkPage(self))
        elif key == "monitor-alerts":
            from monitor_page import MonitorPage
            self.page(key, lambda: MonitorPage(self))
        elif key == "fans":
            from fan_page import Fans
            self.page(key, Fans)
        elif key == "homebrew":
            from brew_page import BrewPage
            self.page(key, lambda: BrewPage(self)).open()
        elif key == "agents":
            from agent_page import AgentUsage
            self.page(key, lambda: AgentUsage(self)).refresh()
        elif key == "devices":
            self.show_devices()
        elif key == "media":
            self.output_page(key, [sys.executable, MODULES / "media.py", "player"])
        elif key == "output":
            self.cycle_output()
        elif key in ("color", "ocr"):
            self.select_from_screen(key, from_catalog=True)
        elif key == "wallpaper":
            from wallpaper_page import WallpaperPage
            self.page(key, lambda: WallpaperPage(self))
        elif key == "awake":
            from awake_page import AwakePage
            self.page(key, lambda: AwakePage(self))
        elif key == "camera":
            from camera_window import CameraWindow
            if self.mirror is None:
                self.mirror = CameraWindow(self)
                self.mirror.finished.connect(self.camera_closed)
            self.mirror.showNormal()
            self.mirror.raise_()
            self.mirror.activateWindow()
        elif key == "watch":
            from capture import Preview
            preview = Preview(self)
            preview.show()
        elif key in ("record", "recordings"):
            from recordings import Recordings
            editor = self.page("recordings", lambda: Recordings(self))
            if key == "record":
                editor.capture("r")
        elif key == "compress":
            from compress_page import CompressPage
            page = self.page(key, CompressPage)
            page.closing = False
            page.inspect_next()

    @Slot("QStringList")
    def Open(self, args):
        key = args[0] if args else "tools"
        self.settings.sync()
        self.favorites, self.hidden = preferences(self.settings)
        if ("notes" if key == "floating-pad" else key) in self.hidden:
            if args == ["awake", "settings"]:
                self.Open(["tools"])
                QTimer.singleShot(0, lambda: self.customize("awake"))
                return
            self.panelDismissed.emit()
            return
        if key in ("color", "ocr"):
            if len(args) == 1:
                self.select_from_screen(key)
            else:
                self.panelDismissed.emit()
            return
        if key == "camera" and len(args) == 1:
            self.run_tool(key)
            return
        if key in DIRECT_ACTIONS:
            if len(args) == 1:
                self.run_tool(key)
            else:
                self.panelDismissed.emit()
            return
        if key == "wheel" and len(args) == 1:
            self.wheel()
            return
        if key == "quick-panel" and len(args) == 1:
            self.toggle_panel()
            return
        if key == "floating-pad" and len(args) == 2 and re.fullmatch(r"[a-f0-9]{32}", args[1]):
            self.floating_pad(args[1])
            return
        if key == "watch" and len(args) == 2 and re.fullmatch(r"[1-9][0-9]{0,9}", args[1]):
            from capture import Preview
            widget_id = args[1]
            preview = self.notch_previews.get(widget_id)
            if preview is None:
                preview = Preview(self, widget_id)
                self.notch_previews[widget_id] = preview
                preview.destroyed.connect(lambda: self.notch_previews.pop(widget_id, None))
            preview.edit()
            return
        self.showNormal() if self.isMinimized() else self.show()
        self.raise_()
        self.activateWindow()
        if key == "tools":
            self.home()
        elif key == "shelf":
            shelf = self.page(key, self.file_shelf)
            urls = [QUrl(arg) for arg in args[1:101]]
            shelf.files.add_paths([shelf.files.local_path(url) for url in urls])
        elif key == "agents" and len(args) == 2 and args[1] in ("codex", "claude", "session"):
            from agent_page import AgentUsage
            page = self.ensure_page(key, lambda: AgentUsage(self))
            if args[1] == "session":
                page.setCurrentIndex(1)
            else:
                page.open_provider(args[1])
            self.page(key, lambda: page)
        elif key in ACTIONS:
            self.run_tool(key)

    def closeEvent(self, event):
        notes = self.pages.get("notes")
        if notes and not notes.flush():
            event.ignore()
            return
        if (any(getattr(page, "applying_action", False) for page in self.pages.values()) or
                any(job.property("finishOnClose") for job in self.running)):
            self.close_after_process_action = True
            self.hide()
            event.ignore()
            return
        editor = self.pages.get("recordings")
        if editor and editor.recorder:
            # Spectacle still owns the active recording. Keep its process alive
            # until the user finishes it with the normal recording indicator.
            editor.close_after_capture = True
            self.hide()
            event.ignore()
            return
        if editor and editor.exporter:
            if QMessageBox.question(self, tr("Cancel export?"), tr("Cancel the recording export and close Utilities?")) != QMessageBox.Yes:
                event.ignore()
                return
            job = editor.exporter
            editor.cancel_export()
            job.waitForFinished(2000)
        compressor = self.pages.get("compress")
        if compressor and compressor.exporting:
            if QMessageBox.question(self, tr("Cancel compression?"), tr("Stop saving the remaining copies and close Utilities?")) != QMessageBox.Yes:
                event.ignore()
                return
        if self.direct_actions and self.direct_actions.busy:
            self.hide()
            event.ignore()
            return
        if compressor:
            compressor.close_jobs()
        if self.mirror:
            self.mirror.close()
        for preview in list(self.notch_previews.values()):
            preview.close()
        for key in ("color", "ocr"):
            if key in self.pages:
                self.pages[key].closing = True
        for job in list(self.running):
            job.kill()
            job.waitForFinished(1000)
        super().closeEvent(event)

class Receiver(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window

        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.setInterval(45000)
        self.idle.timeout.connect(self.release_if_unused)
        window.panelDismissed.connect(self.idle.start)

    def release_if_unused(self):
        if self.window.agent_feed and self.window.agent_feed.views:
            return
        if any(w.isVisible() for w in QApplication.topLevelWidgets()) or self.window.notch_previews:
            return
        editor = self.window.pages.get("recordings")
        if editor and (editor.recorder or editor.exporter):
            return
        compressor = self.window.pages.get("compress")
        if compressor and compressor.job:
            self.idle.start()
            return
        if self.window.running or any(self.window.pages[key].busy for key in ("color", "ocr") if key in self.window.pages):
            self.idle.start()
        else:
            QApplication.quit()

    @Slot(str)
    def WheelPlaced(self, token):
        placement = self.window.wheel_placement
        if placement and placement.token == token:
            placement.stop()

    @Slot(str, str, result=bool)
    def ShowWheel(self, token, available):
        if not available.isascii() or not available.isdecimal() or len(available) > 5:
            return False
        return self.window.show_wheel(token, int(available))

    @Slot(str, str)
    def OpenTool(self, key, token):
        self.window.settings.sync()
        self.window.favorites, self.window.hidden = preferences(self.window.settings)
        if key != "customize" and (key not in ACTIONS or key in self.window.hidden):
            return
        def launch():
            # Qt Wayland consumes this on the next window activation. External
            # tools inherit it when started directly from the command bar.
            if token:
                os.environ["XDG_ACTIVATION_TOKEN"] = token
            try:
                if key == "customize":
                    self.window.Open(["tools"])
                    QTimer.singleShot(0, self.window.customize)
                elif ACTIONS[key].command:
                    self.window.run_tool(key)
                    self.idle.start()
                else:
                    self.window.Open([key])
            finally:
                if token:
                    os.environ.pop("XDG_ACTIVATION_TOKEN", None)
        if len(token) <= 4096 and "\x00" not in token:
            QTimer.singleShot(0, launch)

    @Slot(str, result=bool)
    def AddToShelf(self, address):
        if "shelf" in self.window.hidden:
            return False
        path = ShelfList.local_path(QUrl(address))
        if path is None:
            return False
        self.idle.start()
        shelf = self.window.ensure_page("shelf", self.window.file_shelf)
        shelf.files.add_paths([path])
        return os.path.normpath(path) in shelf.files.paths()

    def shelf_request(self, payload):
        if "shelf" in self.window.hidden:
            return "{}"
        shelf = self.window.ensure_page("shelf", self.window.file_shelf)
        return shelf.files.for_notch(payload)

    def pad_request(self, payload):
        if "notes" in self.window.hidden:
            # A keystroke can still be waiting for autosave when the tab disappears.
            try:
                request = json.loads(payload)
            except ValueError:
                return '{"ok":false}'
            if not isinstance(request, dict) or request.get("action") != "save":
                return '{"ok":false}'
        return self.window.pads().for_notch(payload)

    @Slot(str)
    def Present(self, payload):
        try:
            args = json.loads(payload)
        except ValueError:
            return
        if isinstance(args, list) and len(args) <= 101 and all(isinstance(a, str) for a in args):
            self.window.Open(args)

class NotchPage(QDBusVirtualObject):
    """Private, on-demand views for the desktop shell."""
    shell = "org.kde.plasmashell"

    def __init__(self, bus, receiver, path, method, handler, changes):
        super().__init__(receiver)
        self.path = path
        self.method = method
        self.handler = handler
        self.signal_name = changes
        self.bus = bus
        self.receiver = receiver
        self.owner = ""
        self.watcher = QDBusServiceWatcher(self.shell, bus, QDBusServiceWatcher.WatchForOwnerChange, self)
        self.watcher.serviceOwnerChanged.connect(self.owner_changed)

    def owner_changed(self, name, previous, current):
        self.owner = current

    def changed(self):
        if self.owner:
            self.bus.send(QDBusMessage.createTargetedSignal(self.owner, self.path, SERVICE, self.signal_name))

    def introspect(self, path):
        return (f'<interface name="org.monet.Utilities"><method name="{self.method}"><arg type="s" direction="in"/>'
                f'<arg type="s" direction="out"/></method><signal name="{self.signal_name}"/></interface>')

    def handleMessage(self, message, connection):
        if message.interface() != SERVICE or message.member() != self.method:
            return False
        if not self.owner:
            self.owner = self.bus.interface().serviceOwner(self.shell).value() or ""
        if not self.owner or message.service() != self.owner:
            reply = message.createErrorReply("org.freedesktop.DBus.Error.AccessDenied", "Desktop shell only.")
        elif message.signature() != "s":
            reply = message.createErrorReply("org.freedesktop.DBus.Error.InvalidArgs", "Expected a string.")
        else:
            self.receiver.idle.start()
            result = self.handler(message.arguments()[0])
            reply = message.createReply(result)
        connection.send(reply)
        return True


def main(argv, helpers):
    activation_token = os.environ.get("XDG_ACTIVATION_TOKEN", "")
    app = QApplication(argv[:1])
    app.setApplicationName("Monet Utilities")
    app.setDesktopFileName("monet-utilities")
    args = argv[1:] or ["tools"]
    bus = QDBusConnection.sessionBus()
    def forward():
        if args == ["--pad-service"]:
            return True
        from PySide6.QtDBus import QDBus
        if args in (["quick-panel"], ["wheel"]) and activation_token:
            msg = QDBusMessage.createMethodCall(SERVICE, "/Utilities", SERVICE, "OpenTool")
            msg.setArguments([args[0], activation_token])
        else:
            msg = QDBusMessage.createMethodCall(SERVICE, "/Utilities", SERVICE, "Present")
            msg.setArguments([json.dumps(args)])
        return bus.call(msg, QDBus.Block, 3000).type() != QDBusMessage.ErrorMessage
    if bus.isConnected() and bus.interface().isServiceRegistered(SERVICE).value() and forward():
        return 0
    window = Window(helpers if Path(helpers).is_absolute() else "/usr/libexec",
                    defer_catalog=args in (["wheel"], ["quick-panel"], ["color"], ["ocr"], ["--pad-service"]))
    receiver = Receiver(window)
    if bus.isConnected():
        if not bus.registerObject("/Utilities", SERVICE, receiver, QDBusConnection.ExportAllSlots):
            return 1
        pads = NotchPage(bus, receiver, "/Scratchpad", "Pad", receiver.pad_request, "PadsChanged")
        shelf = NotchPage(bus, receiver, "/FileShelf", "Shelf", receiver.shelf_request, "ShelfChanged")
        window.padsChanged.connect(pads.changed)
        window.shelfChanged.connect(shelf.changed)
        if not bus.registerVirtualObject(pads.path, pads) or not bus.registerVirtualObject(shelf.path, shelf):
            return 1
        from session_feed import NotchSession
        sessions = NotchSession(bus, receiver)
        if not bus.registerVirtualObject(sessions.path, sessions):
            return 1
        if not bus.registerService(SERVICE):
            return int(not forward())
    if args == ["--pad-service"]:
        receiver.idle.start()
    else:
        QTimer.singleShot(0, lambda: window.Open(args))
    def dispose_windows():
        for widget in (window.favorites_wheel, window.quick_panel, window):
            if widget:
                widget.deleteLater()
    app.aboutToQuit.connect(dispose_windows)
    return app.exec()
