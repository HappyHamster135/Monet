import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from PySide6.QtCore import (QObject, QProcess, QSettings, QSize, Qt, QTimer, QUrl, Signal, Slot)
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage, QDBusServiceWatcher, QDBusVirtualObject
from PySide6.QtGui import QAction, QCursor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QWidgetAction)
from actions import ACTIONS, clean_url, find_tools, preferences, tr
from pages import Downloads, Shelf, Snippets, row

MODULES = Path(__file__).resolve().parent
SERVICE = "org.monet.Utilities"

class Window(QMainWindow):
    def __init__(self, helpers):
        super().__init__()
        self.helpers = Path(helpers)
        self.settings = QSettings("Monet", "Utilities")
        self.favorites, self.hidden = preferences(self.settings)
        self.pages = {}
        self.notch_previews = {}
        self.floating_pads = set()
        self.pad_store = None
        self.agent_feed = None
        self.running = set()
        self.converting = False
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
        self.home()

    def session_feed(self):
        if self.agent_feed is None:
            from session_feed import SessionFeed
            self.agent_feed = SessionFeed(self)
        return self.agent_feed

    def filter(self):
        self.catalog.clear()
        for key, _ in find_tools(self.search.text(), self.favorites, self.hidden):
            action = ACTIONS[key]
            entry = QListWidgetItem(QIcon.fromTheme(action.icon), action.name)
            entry.setData(Qt.UserRole, key)
            entry.setToolTip(action.group)
            self.catalog.addItem(entry)
        self.catalog.setCurrentRow(0)
        if not self.catalog.count():
            self.status.showMessage("No matching tools. Use Customize to show hidden tools.")
        else:
            self.status.clearMessage()

    def open_selected(self, item=None):
        item = item or self.catalog.currentItem()
        if item:
            self.run_tool(item.data(Qt.UserRole))

    def home(self):
        self.setWindowTitle(tr("Monet Utilities"))
        self.title.setText("Utilities")
        self.back.hide()
        self.stack.setCurrentIndex(0)
        self.search.clear()
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

    def customize(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Customize Utilities")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose which tools appear. Star up to eight for the favorites wheel."))
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        tree = QTreeWidget()
        tree.setHeaderLabels(["Tool", "Show", "Favorite"])
        for key, action in ACTIONS.items():
            item = QTreeWidgetItem(tree, [action.name])
            item.setData(0, Qt.UserRole, key)
            item.setCheckState(1, Qt.Unchecked if key in self.hidden else Qt.Checked)
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
            if len(favorites) > 8:
                QMessageBox.information(dialog, "Favorites", "Choose up to eight favorites.")
                return
            agent_visibility_changed = ("agents" in self.hidden) != ("agents" in hidden)
            self.hidden, self.favorites = hidden, favorites
            self.settings.setValue("favorites", json.dumps(favorites))
            self.settings.setValue("hidden", json.dumps(hidden))
            self.settings.sync()
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
            self.home()

    def wheel(self):
        keys = [k for k in self.favorites if k in ACTIONS and k not in self.hidden and k != "wheel"][:8]
        if not keys:
            self.customize()
            return
        menu = QMenu(self)
        wheel = QWidget()
        wheel.setFixedSize(320, 320)
        for i, key in enumerate(keys):
            angle = 2 * math.pi * i / len(keys) - math.pi / 2
            button = QToolButton(wheel)
            button.setGeometry(round(116 + 101 * math.cos(angle)), round(132 + 116 * math.sin(angle)), 88, 56)
            button.setIcon(QIcon.fromTheme(ACTIONS[key].icon))
            button.setText(ACTIONS[key].name)
            button.setToolTip(ACTIONS[key].name)
            button.setAccessibleName(ACTIONS[key].name)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setIconSize(QSize(30, 30))
            def choose(checked=False, key=key):
                menu.close()
                QTimer.singleShot(0, lambda: self.run_tool(key))
            button.clicked.connect(choose)
        host = QWidgetAction(menu)
        host.setDefaultWidget(wheel)
        menu.addAction(host)
        center = QCursor.pos()
        from PySide6.QtCore import QPoint
        menu.exec(center - QPoint(160, 160))
        menu.deleteLater()

    def issue(self, text):
        self.status.showMessage(text[:500], 12000)

    def worker(self, argv, done, failed=None):
        job = QProcess(self)
        self.running.add(job)
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
        job.finished.connect(finish)
        def error(reason):
            if reason == QProcess.FailedToStart and job in self.running:
                self.running.remove(job)
                job.deleteLater()
                (failed or self.issue)("Could not start " + Path(argv[0]).name)
        job.errorOccurred.connect(error)
        job.start(str(argv[0]), [str(a) for a in argv[1:]])
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
            fans = []
            for entry in sorted(Path("/sys/class/hwmon").glob("hwmon*/fan*_input")):
                try:
                    label = entry.with_name(entry.name.replace("input", "label"))
                    name = label.read_text().strip() if label.exists() else entry.parent.joinpath("name").read_text().strip()
                    fans.append(f"{name}  {int(entry.read_text())} RPM")
                except (OSError, ValueError):
                    continue
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

    def capture_text(self):
        area = tempfile.TemporaryDirectory(prefix="monet-capture-")
        path = Path(area.name) / "selection.png"
        def fail(reason):
            area.cleanup()
            self.issue(reason)
        def captured(_):
            if not path.is_file():
                fail("Capture canceled.")
                return
            def read(out):
                area.cleanup()
                box = QDialog(self)
                box.setWindowTitle("Text from screen")
                layout = QVBoxLayout(box)
                editor = QPlainTextEdit(out.strip())
                layout.addWidget(editor)
                row(layout, ("Copy", lambda: QApplication.clipboard().setText(editor.toPlainText())), ("Close", box.accept))
                box.resize(480, 300)
                box.exec()
            self.worker([sys.executable, MODULES / "media.py", "read", path], read, fail)
        self.worker(["spectacle", "-brn", "-o", path], captured, fail)

    def compress(self):
        if self.converting:
            self.issue("A conversion is already running.")
            return
        source, _ = QFileDialog.getOpenFileName(self, "Compress media")
        if not source:
            return
        mode, ok = QInputDialog.getItem(self, "Output format", "Save as", ["MP4 video", "WebP image", "GIF animation"], 0, False)
        if not ok:
            return
        extension, opts = {"MP4 video": (".mp4", ["-c:v","libx264","-preset","veryfast","-crf","26","-c:a","aac"]),
                           "WebP image": (".webp", ["-frames:v","1","-c:v","libwebp","-quality","78"]),
                           "GIF animation": (".gif", ["-vf","fps=12,scale='min(720,iw)':-1","-loop","0"])}[mode]
        target, _ = QFileDialog.getSaveFileName(self, "Save compressed copy", str(Path(source).with_suffix("")) + "-small" + extension)
        if not target:
            return
        target = Path(target)
        if target.suffix.casefold() != extension:
            target = Path(str(target) + extension)
        if target.exists():
            self.issue("Choose a new file name for the compressed copy.")
            return
        try:
            temp = tempfile.TemporaryDirectory(prefix=".monet-media-", dir=target.parent)
        except OSError as error:
            self.issue(str(error))
            return
        output = Path(temp.name) / ("copy" + extension)
        self.converting = True
        self.issue("Compressing media…")
        def fail(reason):
            temp.cleanup()
            self.converting = False
            self.issue(reason)
        def finish(_):
            try:
                os.link(output, target)
            except OSError as error:
                fail(str(error))
                return
            temp.cleanup()
            self.converting = False
            self.issue("Saved " + target.name)
        self.worker(["nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                     "-threads","2","-filter_threads","1","-i",source,*opts,"-threads","2",output], finish, fail)

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

    def run_tool(self, key):
        action = ACTIONS.get(key)
        if not action:
            self.home()
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
            self.page(key, lambda: Shelf(self.settings))
        elif key == "notes":
            self.page(key, self.pad_page).edit.setFocus()
        elif key == "snippets":
            self.page(key, lambda: Snippets(self.settings))
        elif key == "calendars":
            from calendars import Calendars
            self.page(key, Calendars).reload()
        elif key == "downloads":
            self.page(key, lambda: Downloads(self.settings))
        elif key == "wheel":
            self.wheel()
        elif key == "media-keys":
            from media_keys import MediaKeys
            self.page(key, MediaKeys)
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
        elif key == "fans":
            import shutil
            if shutil.which("coolercontrol"):
                QProcess.startDetached("coolercontrol", [])
            else:
                self.show_devices()
                self.issue("Fan speeds are managed by this PC’s firmware. CoolerControl can manage supported fan controllers.")
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
        elif key == "color":
            def color(out):
                value = re.search(r"uint32 (\d+)", out)
                if value:
                    glyph = "#{:06X}".format(int(value[1]) & 0xffffff)
                    QApplication.clipboard().setText(glyph)
                    self.issue("Copied " + glyph)
                else:
                    self.issue("No color selected.")
            self.worker(["gdbus", "call", "--session", "--timeout", "120", "--dest", "org.kde.KWin", "--object-path",
                         "/ColorPicker", "--method", "org.kde.kwin.ColorPicker.pick"], color)
        elif key == "wallpaper":
            path, _ = QFileDialog.getOpenFileName(self, "Choose wallpaper", "", "Images (*.jpg *.jpeg *.png *.webp *.avif)")
            if path:
                self.worker(["plasma-apply-wallpaperimage", path], lambda _: self.issue("Wallpaper applied."))
        elif key == "awake":
            choices = {"30 minutes": "30", "1 hour": "60", "Until turned off": "on", "Turn off": "off"}
            mode, ok = QInputDialog.getItem(self, "Keep awake", "Duration", list(choices), 0, False)
            if ok:
                self.worker([self.helpers / "monet-quick", "keep-awake", choices[mode]], lambda _: self.issue("Keep-awake setting updated."))
        elif key in ("camera", "watch"):
            from capture import Preview
            preview = Preview(self, key == "camera")
            preview.show()
        elif key == "ocr":
            self.capture_text()
        elif key in ("record", "recordings"):
            from recordings import Recordings
            editor = self.page("recordings", lambda: Recordings(self))
            if key == "record":
                editor.capture("r")
        elif key == "compress":
            self.compress()

    @Slot("QStringList")
    def Open(self, args):
        key = args[0] if args else "tools"
        if key == "floating-pad" and len(args) == 2 and re.fullmatch(r"[a-f0-9]{32}", args[1]):
            self.floating_pad(args[1])
            return
        if key == "watch" and len(args) == 2 and re.fullmatch(r"[1-9][0-9]{0,9}", args[1]):
            from capture import Preview
            widget_id = args[1]
            preview = self.notch_previews.get(widget_id)
            if preview is None:
                preview = Preview(self, False, widget_id)
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
            shelf = self.page(key, lambda: Shelf(self.settings))
            urls = [QUrl(arg) for arg in args[1:101]]
            shelf.files.add_paths([u.toLocalFile() for u in urls if u.isLocalFile()])
        elif key == "agents" and key in self.hidden:
            self.home()
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
        if any(getattr(page, "applying_action", False) for page in self.pages.values()):
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
        if self.converting and QMessageBox.question(self, "Cancel conversion?", "A conversion is running. Cancel it and close Utilities?") != QMessageBox.Yes:
            event.ignore()
            return
        for preview in list(self.notch_previews.values()):
            preview.close()
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

    def release_if_unused(self):
        if self.window.agent_feed and self.window.agent_feed.views:
            return
        if not any(w.isVisible() for w in QApplication.topLevelWidgets()) and not self.window.running and not self.window.notch_previews:
            QApplication.quit()

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
        url = QUrl(address)
        path = url.toLocalFile()
        if not url.isLocalFile() or url.host() or not os.path.isabs(path) or "\0" in path:
            return False
        self.idle.start()
        shelf = self.window.ensure_page("shelf", lambda: Shelf(self.window.settings))
        shelf.files.add_paths([path])
        return os.path.normpath(path) in shelf.files.paths()

    @Slot(str)
    def Present(self, payload):
        try:
            args = json.loads(payload)
        except ValueError:
            return
        if isinstance(args, list) and len(args) <= 101 and all(isinstance(a, str) for a in args):
            self.window.Open(args)

class NotchPads(QDBusVirtualObject):
    """Only the desktop shell can read and edit notes over the session bus."""
    path = "/Scratchpad"
    shell = "org.kde.plasmashell"

    def __init__(self, bus, receiver):
        super().__init__(receiver)
        self.bus = bus
        self.receiver = receiver
        self.owner = ""
        self.watcher = QDBusServiceWatcher(self.shell, bus, QDBusServiceWatcher.WatchForOwnerChange, self)
        self.watcher.serviceOwnerChanged.connect(self.owner_changed)
        receiver.window.padsChanged.connect(self.changed)

    def owner_changed(self, name, previous, current):
        self.owner = current

    def changed(self):
        if self.owner:
            self.bus.send(QDBusMessage.createTargetedSignal(self.owner, self.path, SERVICE, "PadsChanged"))

    def introspect(self, path):
        return ('<interface name="org.monet.Utilities"><method name="Pad"><arg type="s" direction="in"/>'
                '<arg type="s" direction="out"/></method><signal name="PadsChanged"/></interface>')

    def handleMessage(self, message, connection):
        if message.interface() != SERVICE or message.member() != "Pad":
            return False
        if not self.owner:
            self.owner = self.bus.interface().serviceOwner(self.shell).value() or ""
        if not self.owner or message.service() != self.owner:
            reply = message.createErrorReply("org.freedesktop.DBus.Error.AccessDenied", "Only the desktop shell can access scratchpads.")
        elif message.signature() != "s":
            reply = message.createErrorReply("org.freedesktop.DBus.Error.InvalidArgs", "Expected a string.")
        else:
            self.receiver.idle.start()
            result = self.receiver.window.pads().for_notch(message.arguments()[0])
            reply = message.createReply(result)
        connection.send(reply)
        return True


def main(argv, helpers):
    app = QApplication(argv[:1])
    app.setApplicationName("Monet Utilities")
    app.setDesktopFileName("monet-utilities")
    args = argv[1:] or ["tools"]
    bus = QDBusConnection.sessionBus()
    def forward():
        if args == ["--pad-service"]:
            return True
        from PySide6.QtDBus import QDBus
        msg = QDBusMessage.createMethodCall(SERVICE, "/Utilities", SERVICE, "Present")
        msg.setArguments([json.dumps(args)])
        return bus.call(msg, QDBus.Block, 3000).type() != QDBusMessage.ErrorMessage
    if bus.isConnected() and bus.interface().isServiceRegistered(SERVICE).value() and forward():
        return 0
    window = Window(helpers if Path(helpers).is_absolute() else "/usr/libexec")
    receiver = Receiver(window)
    if bus.isConnected():
        if not bus.registerObject("/Utilities", SERVICE, receiver, QDBusConnection.ExportAllSlots):
            return 1
        bridge = NotchPads(bus, receiver)
        if not bus.registerVirtualObject(bridge.path, bridge):
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
    return app.exec()
