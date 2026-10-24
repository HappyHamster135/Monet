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

from . import disks, network, pc, system, words
from .system import account_name
from .words import N_, _, ntr, tr
from .qt import (Property, QFontDatabase, QGuiApplication, QObject, QProcess, QQmlApplicationEngine, QTimer, QUrl,
                 Signal, Slot)

HERE = Path(__file__).resolve().parent.parent
IMAGE = os.environ.get("MONET_IMAGE", "ghcr.io/happyhamster135/monet:latest")
STATE = Path(os.environ.get("MONET_SETUP_STATE", "/run/monet-setup/state.json"))
DEMO = os.environ.get("MONET_SETUP_DEMO", "")

# What the person sees while installing, and how much of the bar each part is.
PHASES = {
    "disk": (N_("Preparing the disk"), 0.00, 0.03),
    "download": (N_("Downloading Monet"), 0.03, 0.75),
    "install": (N_("Installing Monet"), 0.75, 0.93),
    "configure": (N_("Setting up your account"), 0.93, 0.95),
    "files": (N_("Bringing your files"), 0.95, 0.99),
    "finish": (N_("Finishing"), 0.99, 1.00),
}


# The apps offered on "Your apps", from Flathub: (ID, name, what it's for, ticked at first).
# They arrive after the first sign-in (monet-apps); the ticked ones and the built-in
# ones are what a PC that never chose gets (linux/libexec/monet-apps' EVERYDAY).
APPS = [
    ("app.zen_browser.zen", "Zen Browser", N_("The web"), True),
    ("org.libreoffice.LibreOffice", N_("Office"), N_("Documents, sheets, slides"), False),
    ("org.mozilla.Thunderbird", N_("Mail"), N_("Email and calendars"), False),
    ("com.discordapp.Discord", "Discord", N_("Talk while you play"), False),
    ("com.spotify.Client", "Spotify", N_("Music to stream"), False),
    ("org.localsend.localsend_app", "LocalSend", N_("Send files to your phone"), False),
    ("com.heroicgameslauncher.hgl", "Heroic", N_("Epic and GOG games"), False),
    ("org.prismlauncher.PrismLauncher", "Prism Launcher", "Minecraft", False),
    ("com.obsproject.Studio", "OBS Studio", N_("Record and stream games"), False),
    ("org.kde.krita", "Krita", N_("Paint and draw"), False),
]
# Built into Monet (image/Containerfile), so "Your apps" shows them as there
# already. A Monet without them (added to Bazzite by hand) gets them from
# Flathub with the everyday ones (monet-apps' EVERYDAY).
BUILT_IN = [
    ("org.kde.gwenview", N_("Photos")),
    ("org.kde.okular", N_("Documents")),
    ("org.kde.haruna", N_("Video")),
    ("org.kde.elisa", N_("Music")),
    ("org.kde.kcalc", N_("Calculator")),
]


def minutes_text(seconds):
    if seconds is None:
        return ""
    minutes = max(1, round(seconds / 60))
    return ntr("about %1 minute left", "about %1 minutes left", minutes)


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
        self._bring = True
        self._encrypt = True                 # on PCs with a TPM 2.0 (the choice shows only there)
        self._recovery = ""                  # the recovery key, once installed: shown once, kept nowhere
        self._name, self._password = "", ""
        self._apps = [app[-1] for app in APPS]
        self._phase, self._progress, self._status, self._error, self._log = "", 0.0, "", "", []
        self._proc = None
        # The demo is a PC that's fine, unless MONET_SETUP_DEMO_PC says otherwise ({"memory": 4}).
        self._pc = ({"newNvidia": True, "oldNvidia": "", "memory": 16, "tpm": True,
                     **json.loads(os.environ.get("MONET_SETUP_DEMO_PC", "{}"))}
                    if DEMO else pc.check())
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
        words.use(system.LANGUAGES[min(self._language, len(system.LANGUAGES) - 1)][1])
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
        # Windows on a full disk: Monet makes room, and Ann's files come along.
        self._disks = [{"path": "/dev/nvme0n1", "label": "Samsung SSD 990 PRO · 1 TB", "size": 10**12,
                        "erase": disks.plan_erase(10**12), "hasWindows": True, "keepWhy": "",
                        "keep": {"boot": 2048, "monet": 488000,
                                 "shrink": {"partition": "/dev/nvme0n1p3", "from": 999 * 10**9, "to": 487 * 10**9}},
                        "files": {"person": "Ann", "partition": "/dev/nvme0n1p3", "total": 41 * 10**9, "fits": True,
                                  "folders": {"Documents": "Users/Ann/Documents"}, "sizes": {}}}]
        phase = os.environ.get("MONET_SETUP_DEMO_PHASE")
        if phase:
            self._phase = phase
            self._progress, self._status = 0.46, "Downloading Monet · 2.6 of 5.7 GB · about 9 minutes left"
            if phase == "failed":
                self._error = "The connection dropped and didn't come back."
                self._log = ["download: 2.6 of 5.7 GB", "download: no data for 4 minutes"]
            if phase == "done" and self._pc.get("tpm"):
                self._recovery = "bvcbtnhk-lrdglgcd-jvhbfneb-kticcrhd-uvenrtct-dhfjlbfg-vcbrhcuj-ngeldrtb"

    # -- languages and keyboards --
    @Property("QVariant", constant=True)
    def languages(self):
        return [name for name, *_ in system.LANGUAGES]

    @Property("QVariant", notify=changed)
    def keyboards(self):
        return [_(keyboard[0]) for keyboard in system.KEYBOARDS]

    @Property(int, notify=changed)
    def language(self):
        return self._language

    @Property(int, notify=changed)
    def keyboard(self):
        return self._keyboard

    @Property(int, constant=True)
    def startStep(self):
        return getattr(self, "_step", 0)

    # The language Setup speaks: QML's tr() reads it, so every page says it again when it changes.
    @Property(str, notify=changed)
    def lang(self):
        return system.LANGUAGES[self._language][1]

    # Arabic and Hebrew read from right to left, and the sheet's layout with them.
    @Property(bool, notify=changed)
    def rtl(self):
        return self.lang[:2] in ("ar", "he")

    @Slot(str, str, result=str)
    def say(self, text, value):
        return tr(text, value)

    @Slot(str, str, str, result=str)
    def sayIn(self, context, text, value):
        return words.trc(context, text, value)

    @Slot(int)
    def setLanguage(self, index):
        self._language = index
        words.use(system.LANGUAGES[index][1])
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
        layout, variant = system.KEYBOARDS[self._keyboard][1:]
        self._save(step=1)
        try:
            Path("/run/monet-setup/keyboard").write_text(" ".join(system.xkb(layout, variant)).strip())
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
            return _("Type your name.")
        if len(password) < 6:
            return _("The password needs at least 6 characters.")
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
        return ([{"name": _(name), "detail": _("Built in"), "everyday": True, "picked": True, "index": -1}
                 for _id, name in BUILT_IN]
                + [{"name": _(name), "detail": _(detail), "everyday": everyday, "picked": picked, "index": i}
                   for i, ((_id, name, detail, everyday), picked) in enumerate(zip(APPS, self._apps))])

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

    def _chosen(self):
        return self._disks[min(self._disk, len(self._disks) - 1)] if self._disks else {}

    @Property(str, notify=changed)
    def roomNote(self):
        """Next to Windows on a full disk: how Monet makes room."""
        shrink = (self._chosen().get("keep") or {}).get("shrink")
        if self._mode != "keep" or not shrink:
            return ""
        return tr("Monet makes room by shrinking Windows' drive from %1 to %2. Nothing in Windows is lost, and it checks its drive once the next time it starts.",  # noqa: E501
                  disks.size_text(shrink["from"]), disks.size_text(shrink["to"]))

    @Property("QVariant", notify=changed)
    def files(self):
        """Windows' files that can come along: {"text", "fits"}, or None."""
        found = self._chosen().get("files")
        if self._mode != "keep" or not self._chosen().get("keep") or not found:
            return None
        size = disks.size_text(found["total"])
        if not found.get("fits"):
            return {"fits": False, "text": tr("Your files in Windows (%1) don't fit next to Monet. Open them from Files once Monet is installed.", size)}  # noqa: E501
        return {"fits": True, "text": tr("Desktop, Documents, Pictures, Music, Videos and Downloads from Windows (%1). They stay in Windows too.", size)}  # noqa: E501

    @Property(bool, notify=changed)
    def bring(self):
        return self._bring

    @Slot(bool)
    def setBring(self, on):
        self._bring = on
        self.changed.emit()

    # -- encrypting --
    @Property(bool, notify=changed)
    def tpm(self):
        return bool(self._pc.get("tpm"))

    @Property(bool, notify=changed)
    def encrypt(self):
        return self._encrypt

    @Slot(bool)
    def setEncrypt(self, on):
        self._encrypt = on
        self.changed.emit()

    @Property(str, notify=progressChanged)
    def recoveryKey(self):
        return self._recovery

    def _files_plan(self):
        found = self._chosen().get("files")
        if self._mode == "keep" and self._bring and found and found.get("fits"):
            return {key: found[key] for key in ("partition", "folders", "total")}
        return None

    # -- this PC --
    @Property(str, notify=changed)
    def pcBlocker(self):
        """Why this PC can't run Monet at all, if it can't: said from the first page."""
        return self._pc_blocker()

    def _pc_blocker(self):
        gb = self._pc["memory"]
        if gb is not None and gb < 3:
            return tr("This PC has %1 GB of memory. Monet needs at least 4 GB.", max(1, round(gb)))
        return ""

    @Property("QVariant", notify=changed)
    def pcNotes(self):
        """What's good to know about this PC before installing, though Monet runs on it."""
        notes = []
        # An older NVIDIA card gets the AMD and Intel Monet, whose open driver draws with it.
        if self._pc["oldNvidia"] == "only":
            notes.append(_("This PC's NVIDIA graphics card is older than the RTX 20 series. Monet draws with its open driver, fine for everyday things; games run best in Windows."))  # noqa: E501
        elif self._pc["oldNvidia"] == "beside":
            notes.append(_("This PC's NVIDIA graphics chip is older than the RTX 20 series, so Monet uses the built-in graphics. Games run best in Windows."))  # noqa: E501
        gb = self._pc["memory"]
        if gb is not None and 3 <= gb < 7:
            notes.append(tr("This PC has %1 GB of memory. Monet runs, but slows down with many apps open: 8 GB is better.", round(gb)))  # noqa: E501
        return notes

    @Property(str, notify=changed)
    def blocker(self):
        """Why Install can't go ahead on the chosen disk and mode, if it can't."""
        if self._pc_blocker():
            return self._pc_blocker()
        if not self._disks:
            return _("No disk found to install Monet on.")
        disk = self._disks[min(self._disk, len(self._disks) - 1)]
        if self._mode == "keep" and not disk["keep"]:
            return disk["keepWhy"]
        if self._mode == "erase" and not disk["erase"]:
            return _("This disk is too small for Monet (it needs 70 GB).")
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
        locale, zone_guess = system.LANGUAGES[self._language][1::2]
        layout, variant = system.KEYBOARDS[self._keyboard][1:]
        plan = {
            "image": pc.image_for(IMAGE, self._pc), "disk": disk["path"], "mode": self._mode,
            "sizes": disk[self._mode],
            "language": locale, "keyboard": layout, "variant": variant,
            "timezone": zone_guess,             # refined from the internet while installing
            "name": self._name, "account": account_name(self._name), "password": self._password,
            "wifi": self._joined,
            "apps": self.picked_apps(),
            "files": self._files_plan(),
            "encrypt": self._encrypt and bool(self._pc.get("tpm")),
        }
        fd, path = tempfile.mkstemp(prefix="monet-plan-", suffix=".json", dir="/run")
        with os.fdopen(fd, "w") as f:
            json.dump(plan, f)
        self._phase, self._error, self._log, self._progress = "disk", "", [], 0.0
        self._status = _(PHASES["disk"][0])
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
                print("install: " + line, file=sys.stderr, flush=True)
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
        parts = [_(title)]
        if event.get("got") is not None and event.get("total"):
            parts.append(tr("%1 of %2 GB", f"{event['got'] / 1e9:.1f}", f"{event['total'] / 1e9:.1f}"))
        if event.get("eta") is not None:
            parts.append(minutes_text(event["eta"]))
        if event.get("note"):
            parts.append(event["note"])
        self._status = " · ".join(parts)
        if event.get("log"):
            self._log.append(event["log"])
            # The journal too, where a test PC's serial console shows why an install stopped.
            print("install: " + event["log"], file=sys.stderr, flush=True)
        if event.get("error"):
            self._error = event["error"]
        if event.get("recovery"):
            self._recovery = event["recovery"]
        self._phase = "done" if event.get("done") else phase
        self.progressChanged.emit()

    def _finished(self, code, *_status):
        self._proc = None
        if self._phase != "done":
            self._phase = "failed"
            self._error = self._error or _("The installer stopped unexpectedly.")
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
