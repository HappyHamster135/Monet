"""Monet Setup's window: the QML pages and what they ask of the PC.

The pages (qml/Main.qml) walk through Hello, Wi-Fi, the person, Ready, then
install. Everything that touches the PC happens here or in install.py, which
runs as its own process and reports progress as JSON lines.
"""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

from . import disks, network, system
from .system import account_name
from .qt import (Property, QFontDatabase, QGuiApplication, QObject, QProcess, QQmlApplicationEngine, QTimer, QUrl,
                 Signal, Slot)

HERE = Path(__file__).resolve().parent.parent
IMAGE = os.environ.get("MONET_IMAGE", "ghcr.io/happyhamster135/monet:latest")
STATE = Path(os.environ.get("MONET_SETUP_STATE", "/run/monet-setup/state.json"))
DEMO = os.environ.get("MONET_SETUP_DEMO", "")

# What the person sees while installing, and how much of the bar each part is.
PHASES = {
    "disk": ("Preparing the disk", 0.00, 0.03),
    "download": ("Downloading Monet", 0.03, 0.75),
    "install": ("Installing Monet", 0.75, 0.93),
    "configure": ("Setting up your account", 0.93, 0.98),
    "finish": ("Finishing", 0.98, 1.00),
}


# The apps offered on "Your apps", from Flathub: (ID, name, what it's for, ticked at first).
# They arrive after the first sign-in (monet-apps); the ticked ones are also what a PC
# that never chose gets (linux/libexec/monet-apps' EVERYDAY).
APPS = [
    ("app.zen_browser.zen", "Zen Browser", "The web", True),
    ("org.kde.gwenview", "Photos", "Your pictures", True),
    ("org.kde.okular", "Documents", "PDFs and e-books", True),
    ("org.kde.haruna", "Video", "Films and clips", True),
    ("org.kde.elisa", "Music", "Your songs", True),
    ("org.kde.kcalc", "Calculator", "Quick sums", True),
    ("org.libreoffice.LibreOffice", "Office", "Documents, sheets, slides", False),
    ("org.mozilla.Thunderbird", "Mail", "Email and calendars", False),
    ("com.discordapp.Discord", "Discord", "Talk while you play", False),
    ("com.spotify.Client", "Spotify", "Music to stream", False),
    ("com.obsproject.Studio", "OBS Studio", "Record and stream games", False),
    ("org.kde.krita", "Krita", "Paint and draw", False),
]


def minutes_text(seconds):
    if seconds is None:
        return ""
    minutes = max(1, round(seconds / 60))
    return "about 1 minute left" if minutes == 1 else f"about {minutes} minutes left"


class Setup(QObject):
    changed = Signal()
    wifiChanged = Signal()
    progressChanged = Signal()
    workDone = Signal(object, object)       # (what to call, the result), from a worker thread

    def __init__(self):
        super().__init__()
        self._language = 0
        self._keyboard = 0
        self._networks, self._wired, self._scanning = [], False, False
        self._joining, self._wifi_error, self._joined = False, "", ""
        self._disks, self._disk, self._mode = [], 0, "erase"
        self._name, self._password = "", ""
        self._apps = [ticked for *_, ticked in APPS]
        self._phase, self._progress, self._status, self._error, self._log = "", 0.0, "", "", []
        self._proc = None
        # Queued across threads: the callback runs on the window's thread.
        self.workDone.connect(lambda done, result: done(result))
        self._restore()
        self._started_with = self._keyboard
        if DEMO:
            self._demo()
        else:
            QTimer.singleShot(0, self.scan)
            QTimer.singleShot(0, self._load_disks)

    # -- state kept across a keyboard change (the window restarts) --
    def _restore(self):
        try:
            saved = json.loads(STATE.read_text())
        except (OSError, ValueError):
            return
        self._language, self._keyboard = saved.get("language", 0), saved.get("keyboard", 0)
        self._step = saved.get("step", 0)

    def _save(self, step=0):
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({"language": self._language, "keyboard": self._keyboard, "step": step}))
        except OSError:
            pass

    def _demo(self):
        self._networks = [{"name": "Harbor", "signal": 92, "secure": True, "active": False},
                          {"name": "Giverny 5G", "signal": 74, "secure": True, "active": False},
                          {"name": "Le Havre", "signal": 51, "secure": True, "active": False},
                          {"name": "Café Argenteuil", "signal": 28, "secure": False, "active": False}]
        self._disks = [{"path": "/dev/nvme0n1", "label": "Samsung SSD 990 PRO · 1 TB", "size": 10**12,
                        "erase": disks.plan_erase(10**12), "keep": None, "hasWindows": True,
                        "keepWhy": "Needs 71 GB of free space; this disk has 12 GB. "
                                   "Shrink Windows' drive in Disk Management first."}]
        phase = os.environ.get("MONET_SETUP_DEMO_PHASE")
        if phase:
            self._phase = phase
            self._progress, self._status = 0.46, "Downloading Monet · 2.6 of 5.7 GB · about 9 minutes left"
            if phase == "failed":
                self._error = "The connection dropped and didn't come back."
                self._log = ["download: 2.6 of 5.7 GB", "download: no data for 4 minutes"]

    # -- languages and keyboards --
    @Property("QVariant", constant=True)
    def languages(self):
        return [name for name, *_ in system.LANGUAGES]

    @Property("QVariant", constant=True)
    def keyboards(self):
        return [name for name, *_ in system.KEYBOARDS]

    @Property(int, notify=changed)
    def language(self):
        return self._language

    @Property(int, notify=changed)
    def keyboard(self):
        return self._keyboard

    @Property(int, constant=True)
    def startStep(self):
        return getattr(self, "_step", 0)

    @Slot(int)
    def setLanguage(self, index):
        self._language = index
        self.changed.emit()
        self.setKeyboard(system.keyboard_for(index))

    @Slot(int)
    def setKeyboard(self, index):
        if index != self._keyboard:
            self._keyboard = index
            self.changed.emit()

    @Slot(result=bool)
    def applyKeyboard(self):
        """Leaving Hello: the screen's keyboard is set when the window starts,
        so a new one means starting again with it (monet-setup-session does),
        on the next step. True when that's happening."""
        if DEMO or self._keyboard == self._started_with:
            return False
        _, layout, variant = system.KEYBOARDS[self._keyboard]
        self._save(step=1)
        try:
            Path("/run/monet-setup/keyboard").write_text(f"{layout} {variant}".strip())
        except OSError:
            return False
        QTimer.singleShot(0, lambda: QGuiApplication.exit(3))
        return True

    # -- Wi-Fi --
    @Property("QVariant", notify=wifiChanged)
    def networks(self):
        return self._networks

    @Property(bool, notify=wifiChanged)
    def wired(self):
        return self._wired

    @Property(bool, notify=wifiChanged)
    def scanning(self):
        return self._scanning

    @Property(bool, notify=wifiChanged)
    def joining(self):
        return self._joining

    @Property(str, notify=wifiChanged)
    def wifiError(self):
        return self._wifi_error

    @Property(str, notify=wifiChanged)
    def joined(self):
        return self._joined

    def _background(self, work, done):
        """Runs work() on a thread and done(result) back on the window's."""
        threading.Thread(target=lambda: self.workDone.emit(done, work()), daemon=True).start()

    @Slot()
    def scan(self):
        if DEMO or self._scanning:
            return
        self._scanning = True
        self.wifiChanged.emit()

        def done(result):
            self._wired, self._networks = result
            active = next((n["name"] for n in self._networks if n["active"]), "")
            self._joined = self._joined or active
            self._scanning = False
            self.wifiChanged.emit()

        self._background(lambda: (network.wired(), network.wifi_networks(rescan=True)), done)

    @Slot(str, str)
    def join(self, name, password):
        self._joining, self._wifi_error = True, ""
        self.wifiChanged.emit()
        if DEMO:
            QTimer.singleShot(600, lambda: self._joined_done(name, ""))
            return
        self._background(lambda: network.join(name, password), lambda error: self._joined_done(name, error))

    def _joined_done(self, name, error):
        self._joining, self._wifi_error = False, error
        if not error:
            self._joined = name
        self.wifiChanged.emit()

    # -- the person --
    @Slot(str, str, result=str)
    def setPerson(self, name, password):
        """Empty when fine; otherwise what's missing."""
        if not name.strip():
            return "Type your name."
        if len(password) < 6:
            return "The password needs at least 6 characters."
        self._name, self._password = name.strip(), password
        self.changed.emit()
        return ""

    @Property(str, notify=changed)
    def personName(self):
        return self._name

    @Property(str, notify=changed)
    def personPassword(self):
        return self._password

    @Slot(str, result=str)
    def accountFor(self, name):
        return account_name(name) if name.strip() else ""

    # -- apps --
    @Property("QVariant", notify=changed)
    def apps(self):
        return [{"name": name, "detail": detail, "everyday": everyday, "picked": picked}
                for (_, name, detail, everyday), picked in zip(APPS, self._apps)]

    @Slot(int)
    def toggleApp(self, index):
        if 0 <= index < len(self._apps):
            self._apps[index] = not self._apps[index]
            self.changed.emit()

    def picked_apps(self):
        return [app_id for (app_id, *_), picked in zip(APPS, self._apps) if picked]

    # -- disk and mode --
    def _load_disks(self):
        self._background(disks.offer, self._disks_loaded)

    def _disks_loaded(self, found):
        self._disks = found
        self.changed.emit()

    @Property("QVariant", notify=changed)
    def disks(self):
        return self._disks

    @Property(int, notify=changed)
    def disk(self):
        return self._disk

    @Property(str, notify=changed)
    def mode(self):
        return self._mode

    @Slot(int)
    def setDisk(self, index):
        self._disk = index
        self.changed.emit()

    @Slot(str)
    def setMode(self, mode):
        self._mode = mode
        self.changed.emit()

    @Property(str, notify=changed)
    def blocker(self):
        """Why Install can't go ahead on the chosen disk and mode, if it can't."""
        if not self._disks:
            return "No disk found to install Monet on."
        disk = self._disks[min(self._disk, len(self._disks) - 1)]
        if self._mode == "keep" and not disk["keep"]:
            return disk["keepWhy"]
        if self._mode == "erase" and not disk["erase"]:
            return "This disk is too small for Monet (it needs 70 GB)."
        return ""

    # -- installing --
    @Property(str, notify=progressChanged)
    def phase(self):
        return self._phase

    @Property(float, notify=progressChanged)
    def progress(self):
        return self._progress

    @Property(str, notify=progressChanged)
    def status(self):
        return self._status

    @Property(str, notify=progressChanged)
    def error(self):
        return self._error

    @Property(str, notify=progressChanged)
    def details(self):
        return "\n".join(self._log[-40:])

    @Slot()
    def install(self):
        if self._proc or self.blocker:
            return
        disk = self._disks[self._disk]
        locale, _, zone_guess = system.LANGUAGES[self._language][1:]
        _, layout, variant = system.KEYBOARDS[self._keyboard]
        plan = {
            "image": IMAGE, "disk": disk["path"], "mode": self._mode,
            "sizes": disk[self._mode],
            "language": locale, "keyboard": layout, "variant": variant,
            "timezone": zone_guess,             # refined from the internet while installing
            "name": self._name, "account": account_name(self._name), "password": self._password,
            "wifi": self._joined,
            "apps": self.picked_apps(),
        }
        fd, path = tempfile.mkstemp(prefix="monet-plan-", suffix=".json", dir="/run")
        with os.fdopen(fd, "w") as f:
            json.dump(plan, f)
        self._phase, self._error, self._log, self._progress = "disk", "", [], 0.0
        self._status = PHASES["disk"][0]
        self.progressChanged.emit()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._finished)
        self._proc.setWorkingDirectory(str(HERE))
        self._proc.start(sys.executable, ["-m", "monet_setup.install", path])

    def _read(self):
        while self._proc and self._proc.canReadLine():
            line = bytes(self._proc.readLine()).decode(errors="replace").strip()
            try:
                event = json.loads(line)
            except ValueError:
                self._log.append(line)
                continue
            self.report(event)

    def report(self, event):
        """One progress event from install.py."""
        phase = event.get("phase", self._phase)
        title, start, end = PHASES.get(phase, (phase, self._progress, self._progress))
        if "fraction" in event:
            self._progress = start + (end - start) * max(0.0, min(1.0, event["fraction"]))
        else:
            self._progress = max(self._progress, start)
        parts = [title]
        if event.get("got") is not None and event.get("total"):
            parts.append(f"{event['got'] / 1e9:.1f} of {event['total'] / 1e9:.1f} GB")
        if event.get("eta") is not None:
            parts.append(minutes_text(event["eta"]))
        if event.get("note"):
            parts.append(event["note"])
        self._status = " · ".join(parts)
        if event.get("log"):
            self._log.append(event["log"])
        if event.get("error"):
            self._error = event["error"]
        self._phase = "done" if event.get("done") else phase
        self.progressChanged.emit()

    def _finished(self, code, *_):
        self._proc = None
        if self._phase != "done":
            self._phase = "failed"
            self._error = self._error or "The installer stopped unexpectedly."
        self.progressChanged.emit()

    @Slot()
    def retry(self):
        self.install()

    @Slot()
    def restart(self):
        if not DEMO:
            os.system("systemctl reboot")

    @Property(str, constant=True)
    def version(self):
        try:
            return (HERE / "VERSION").read_text().strip()
        except OSError:
            return ""


def main():
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    app = QGuiApplication(sys.argv)
    folders = [HERE / "fonts"] + [Path(d) for d in os.environ.get("MONET_SETUP_FONTS", "").split(":") if d]
    for folder in folders:
        for font in folder.glob("*.[ot]tf"):
            QFontDatabase.addApplicationFont(str(font))
    setup = Setup()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("setup", setup)
    engine.rootContext().setContextProperty("art", QUrl.fromLocalFile(str(HERE / "art") + "/").toString())
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())
