import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from PySide6.QtCore import (QObject, QProcess, QSettings, QSize, Qt, QTimer, QUrl, Slot)
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PySide6.QtGui import QAction, QCursor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QWidgetAction)
from actions import ACTIONS, DEFAULT_FAVORITES, clean_url
from pages import Downloads, Shelf, Writing, row, stored

MODULES = Path(__file__).resolve().parent
SERVICE = "org.monet.Utilities"

class Window(QMainWindow):
    def __init__(self, helpers):
        super().__init__()
        self.helpers = Path(helpers)
        self.settings = QSettings("Monet", "Utilities")
        self.favorites = stored(self.settings, "favorites", DEFAULT_FAVORITES)
        self.hidden = stored(self.settings, "hidden", [])
        self.pages = {}
        self.notch_previews = {}
        self.running = set()
        self.converting = False
        self.setWindowTitle("Monet Utilities")
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

    def filter(self):
        words = self.search.text().casefold().split()
        self.catalog.clear()
        order = list(dict.fromkeys([*self.favorites, *ACTIONS]))
        for key in order:
            action = ACTIONS.get(key)
            if not action or key in self.hidden or not all(w in (action.name + " " + action.group).casefold() for w in words):
                continue
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
        self.title.setText("Utilities")
        self.back.hide()
        self.stack.setCurrentIndex(0)
        self.search.clear()
        self.filter()
        self.search.setFocus()

    def page(self, key, factory):
        if key not in self.pages:
            self.pages[key] = factory()
            self.stack.addWidget(self.pages[key])
        self.stack.setCurrentWidget(self.pages[key])
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
            self.hidden, self.favorites = hidden, favorites
            self.settings.setValue("favorites", json.dumps(favorites))
            self.settings.setValue("hidden", json.dumps(hidden))
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

    def agent_usage(self):
        def make():
            box = QWidget()
            layout = QVBoxLayout(box)
            label = QLabel("Select a local Codex, Claude Code, Copilot CLI session log, or an OpenCode database.")
            label.setWordWrap(True)
            layout.addWidget(label)
            box.text = QPlainTextEdit()
            box.text.setReadOnly(True)
            layout.addWidget(box.text)
            def refresh():
                self.settings.sync()
                if not self.settings.value("agentFile", ""):
                    box.text.setPlainText("No session selected.")
                    return
                self.worker([sys.executable, MODULES / "agents.py"], lambda out: box.text.setPlainText(
                    out.strip() or "No usage figures were reported in recent session events."))
            def choose():
                file, _ = QFileDialog.getOpenFileName(self, "Choose a local session log or database")
                if file:
                    self.settings.setValue("agentFile", file)
                    refresh()
            def clear():
                self.settings.remove("agentFile")
                refresh()
            row(layout, ("Choose session…", choose), ("Refresh", refresh), ("Forget", clear))
            box.refresh = refresh
            return box
        self.page("agents", make).refresh()

    def cycle_output(self):
        def names(out):
            found = [line.split("\t")[1] for line in out.splitlines() if "\t" in line]
            if len(found) < 2:
                self.issue("Only one sound output is available." if found else "No sound output is available.")
                return
            def current(value):
                index = found.index(value.strip()) + 1 if value.strip() in found else 0
                self.worker(["pactl", "set-default-sink", found[index % len(found)]], lambda _: self.issue("Sound output changed."))
            self.worker(["pactl", "get-default-sink"], current)
        self.worker(["pactl", "list", "short", "sinks"], names)

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

    def run_tool(self, key):
        action = ACTIONS.get(key)
        if not action:
            self.home()
            return
        if action.command:
            program, *args = action.command
            program = str(self.helpers / program[1:]) if program.startswith("@") else program
            if key in ("clipboard", "mic", "lock"):
                self.worker([program, *args], lambda _: self.issue(action.name))
            elif not QProcess.startDetached(program, args)[0]:
                self.issue("Could not open " + action.name)
        elif key == "shelf":
            self.page(key, lambda: Shelf(self.settings))
        elif key in ("notes", "snippets"):
            self.page(key, lambda: Writing(self.settings, key == "snippets"))
        elif key == "calendars":
            from calendars import Calendars
            self.page(key, Calendars).reload()
        elif key == "downloads":
            self.page(key, lambda: Downloads(self.settings))
        elif key == "wheel":
            self.wheel()
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
        elif key == "ports":
            self.output_page(key, ["ss", "-lntup"])
        elif key == "fans":
            import shutil
            if shutil.which("coolercontrol"):
                QProcess.startDetached("coolercontrol", [])
            else:
                self.show_devices()
                self.issue("Fan speeds are managed by this PC’s firmware. CoolerControl can manage supported fan controllers.")
        elif key == "agents":
            self.agent_usage()
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
        elif key == "compress":
            self.compress()

    @Slot("QStringList")
    def Open(self, args):
        key = args[0] if args else "tools"
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
        elif key in ACTIONS:
            self.run_tool(key)

    def closeEvent(self, event):
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

    @Slot(str)
    def Present(self, payload):
        try:
            args = json.loads(payload)
        except ValueError:
            return
        if isinstance(args, list) and len(args) <= 101 and all(isinstance(a, str) for a in args):
            self.window.Open(args)

def main(argv, helpers):
    app = QApplication(argv[:1])
    app.setApplicationName("Monet Utilities")
    app.setDesktopFileName("monet-utilities")
    args = argv[1:] or ["tools"]
    bus = QDBusConnection.sessionBus()
    def forward():
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
        if not bus.registerService(SERVICE):
            return int(not forward())
    QTimer.singleShot(0, lambda: window.Open(args))
    return app.exec()
