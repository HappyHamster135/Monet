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
import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import checkpoint, disks, network, pc, system, words
from .system import account_name
from .words import N_, _, ntr, tr
from .qt import (Property, QFontDatabase, QGuiApplication, QLocale, QObject, QProcess, QQmlApplicationEngine, QTime,
                 QTimer, QUrl, Signal, Slot)

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
    clockChanged = Signal()                 # the time in the chosen time zone, each few seconds

    def __init__(self):
        super().__init__()
        self._language = 0
        self._keyboard = 0
        # The time zone: the language's guess, then the internet's once online, unless chosen.
        self._zones = system.time_zones()
        self._zone, self._zone_chosen, self._zone_asked = "", False, False
        self._networks, self._wired, self._scanning = [], False, False
        self._joining, self._wifi_error, self._joined = False, "", ""
        self._offline = False
        self._disks, self._disk, self._mode = [], -1, ""
        self._bring = False
        self._disk_loading, self._disk_busy, self._files_busy = True, False, False
        self._disk_generation, self._resume_id, self._reviewed = 0, '', False
        self._gentle, self._health, self._restarting, self._restart_error = False, '', False, ''
        self._files_lock = threading.Lock()
        self._reading, self._exit_code = False, None
        self._read_queued, self._done_received, self._plan_path = False, False, None
        self._encrypt = True                 # on PCs with a TPM 2.0 (the choice shows only there)
        self._recovery = ""                  # the recovery key, once installed: shown once, kept nowhere
        self._untrusted = None               # an installed Monet's key the firmware doesn't trust yet
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
        self._zone = self._zone or system.LANGUAGES[self._language][3]
        self._started_with = self._keyboard
        self._clock = QTimer(self)
        self._clock.setInterval(15000)
        self._clock.timeout.connect(self.clockChanged.emit)
        self._clock.start()
        if DEMO:
            self._demo()
        else:
            QTimer.singleShot(0, self.scan)
            QTimer.singleShot(0, self._load_disks)
            QTimer.singleShot(0, lambda: self._background(pc.untrusted_key, self._found_untrusted))

    # -- state kept across a keyboard change (the window restarts) --
    def _restore(self):
        try:
            saved = json.loads(STATE.read_text())
        except (OSError, ValueError):
            return
        self._language, self._keyboard = saved.get("language", 0), saved.get("keyboard", 0)
        self._zone, self._zone_chosen = saved.get("zone", ""), saved.get("zoneChosen", False)
        words.use(system.LANGUAGES[min(self._language, len(system.LANGUAGES) - 1)][1])
        self._step = saved.get("step", 0)

    def _save(self, step=0):
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({"language": self._language, "keyboard": self._keyboard, "step": step,
                                         "zone": self._zone, "zoneChosen": self._zone_chosen}))
        except OSError:
            pass

    def _demo(self):
        self._disk_loading = False
        self._disk, self._mode = 0, 'erase'
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
        if not self._zone_chosen:
            self._zone = system.LANGUAGES[index][3]
        self.changed.emit()
        self.clockChanged.emit()
        self.setKeyboard(system.keyboard_for(index))

    # -- the time zone: a region, then a city in it --
    def _regions(self):
        return [region for region in system.REGIONS if any(system.zone_region(z) == region for z in self._zones)]

    def _in_region(self, region):
        return [zone for zone in self._zones if system.zone_region(zone) == region]

    @Property("QVariant", notify=changed)
    def regions(self):
        return [_(system.REGIONS[region]) for region in self._regions()]

    @Property(int, notify=changed)
    def region(self):
        here = system.zone_region(self._zone)
        return self._regions().index(here) if here in self._regions() else -1

    @Property("QVariant", notify=changed)
    def cities(self):
        return [system.zone_city(zone) for zone in self._in_region(system.zone_region(self._zone))]

    @Property(int, notify=changed)
    def city(self):
        zones = self._in_region(system.zone_region(self._zone))
        return zones.index(self._zone) if self._zone in zones else -1

    def _choose_zone(self, zone):
        self._zone, self._zone_chosen = zone, True
        self.changed.emit()
        self.clockChanged.emit()

    @Slot(int)
    def setRegion(self, index):
        """Another region: its city of the language's own time zone if it's there, else its first."""
        regions = self._regions()
        if 0 <= index < len(regions) and regions[index] != system.zone_region(self._zone):
            zones = self._in_region(regions[index])
            guess = system.LANGUAGES[self._language][3]
            self._choose_zone(guess if guess in zones else zones[0])

    @Slot(int)
    def setCity(self, index):
        zones = self._in_region(system.zone_region(self._zone))
        if 0 <= index < len(zones):
            self._choose_zone(zones[index])

    @Property(str, notify=clockChanged)
    def zoneNow(self):
        """The time now in the chosen time zone, as this language writes a time ("14:32", "2:32 PM")."""
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(self._zone))
        except Exception:      # no time zone data here (a demo on another system)
            return ""
        return QLocale(self.lang.split(".")[0]).toString(QTime(now.hour, now.minute), QLocale.FormatType.ShortFormat)

    def _ask_zone(self):
        """Online for the first time: where the PC is, from the internet, unless a zone was chosen."""
        if self._zone_asked or self._zone_chosen or DEMO:
            return
        self._zone_asked = True

        def done(zone):
            if not self._zone_chosen and zone in self._zones and zone != self._zone:
                self._zone = zone
                self.changed.emit()
                self.clockChanged.emit()

        self._background(lambda: system.guess_time_zone(self._zone), done)

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
            if self._wired or self._joined:
                self._ask_zone()

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
            self._ask_zone()
        self.wifiChanged.emit()

    # -- the person --
    @Slot(str, str, str, result=str)
    def setPerson(self, name, password, again):
        """Empty when fine; otherwise what's wrong. Any password goes, or none at all
        (Monet then signs them in by itself): it's their PC."""
        if not name.strip():
            return _("Type your name.")
        if password != again:
            return _("The passwords don't match.")
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
        self._background(lambda: disks.offer(details=False), self._disks_loaded)

    def _disks_loaded(self, found):
        self._disks = found
        self._disk_loading = False
        self.changed.emit()

    @Property(bool, notify=changed)
    def diskLoading(self):
        return self._disk_loading

    @Property(bool, notify=changed)
    def offline(self):
        return self._offline

    @Slot(bool)
    def setOffline(self, value):
        self._offline = value
        self._reviewed = False
        self.changed.emit()

    @Property(bool, notify=changed)
    def diskBusy(self):
        return self._disk_busy or self._files_busy

    @Property(bool, notify=changed)
    def reviewed(self):
        return self._reviewed

    @Slot(bool)
    def setReviewed(self, value):
        self._reviewed = value
        self.changed.emit()

    @Property(bool, notify=changed)
    def gentle(self):
        return self._gentle

    @Slot(bool)
    def setGentle(self, value):
        self._gentle = value
        self.changed.emit()

    @Slot()
    def refreshDisks(self):
        if self._proc or self._disk_loading or DEMO:
            return
        self._disk_generation += 1
        self._disk, self._mode, self._resume_id = -1, '', ''
        self._disks = []
        self._reviewed, self._disk_busy, self._files_busy = False, False, False
        self._disk_loading = True
        self.changed.emit()
        self._load_disks()

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
        if self._proc or self._disk_loading or index < 0 or index >= len(self._disks):
            return
        self._disk = index
        self._disk_generation += 1
        generation = self._disk_generation
        self._mode, self._resume_id, self._bring, self._reviewed = '', '', False, False
        self._files_busy = False
        self._disk_busy = not DEMO
        self.changed.emit()
        if DEMO:
            return
        chosen = dict(self._chosen())
        def probe():
            try:
                current = checkpoint.current_disk(chosen['path'])
                if current is None or disks.identity(current) != chosen['identity']:
                    return None
                return checkpoint.probe(current)
            except Exception:
                return None
        def done(receipt):
            if generation != self._disk_generation: return
            self._chosen()['resume'] = receipt
            self._disk_busy = False
            self.changed.emit()
        self._background(probe, done)

    @Slot(str)
    def setMode(self, mode):
        if self._proc or mode not in ('erase', 'keep', 'resume') or not self._chosen():
            return
        if self._disk_busy or mode == 'resume' and not self._chosen().get('resume'):
            return
        self._mode = mode
        self._resume_id, self._reviewed, self._bring = '', False, False
        self.changed.emit()
        if mode == 'keep' and not self._chosen().get('checked', bool(self._chosen().get('keep'))):
            self._disk_busy = True
            generation = self._disk_generation
            chosen = dict(self._chosen())
            def inspect():
                try: return disks.inspect_keep(chosen)
                except Exception:
                    return dict(keep=None, keepWhy=_('This drive could not be checked. Refresh the drive list and try again.'), checked=True)
            def done(result):
                if generation != self._disk_generation: return
                self._chosen().update(result); self._disk_busy = False
                self.changed.emit()
            self._background(inspect, done)
            self.changed.emit()

    def _chosen(self):
        return self._disks[self._disk] if 0 <= self._disk < len(self._disks) else {}

    @Property(str, notify=changed)
    def driveSummary(self):
        chosen = self._chosen()
        if not chosen: return ''
        target = chosen['label'] + ' (' + chosen['path'] + ')'
        if self._mode == 'erase':
            return tr('Erase everything on %1. All other drives will be kept unchanged.', target)
        if self._mode == 'keep':
            return tr('Keep existing partitions on %1 and add Monet in the available space. All other drives will be kept unchanged.', target)
        if self._mode == 'resume':
            return tr('Resume the interrupted installation on %1 without formatting it again. All other drives will be kept unchanged.', target)
        return tr('Selected drive: %1. Choose what to keep or erase below.', target)

    @Property(str, notify=changed)
    def completionText(self):
        chosen = self._chosen()
        receipt = chosen.get('resume') or {}
        mode = receipt.get('mode') if self._mode == 'resume' else self._mode
        sizes = receipt.get('sizes') if self._mode == 'resume' else chosen.get(self._mode)
        if mode == 'erase' and (sizes or {}).get('windows', 0) > 0:
            return _('Take out the USB stick and restart. After you sign in, Monet gets Windows ready for your games by itself.')
        if mode == 'keep' and chosen.get('hasWindows'):
            return _('Take out the USB stick and restart. Your PC starts in Monet, and Windows is one click away.')
        return _('Take out the USB stick and restart. Your PC starts in Monet.')

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
        if self._proc or self._files_busy: return
        self._bring = on
        if on and self._mode == 'keep' and self._chosen().get('keep') and not self._chosen().get('files') and not DEMO:
            generation = self._disk_generation
            expected = dict(self._chosen()); self._files_busy = True
            def measure():
                try:
                    with self._files_lock:
                        current = checkpoint.current_disk(expected['path'])
                        if (current is None or disks.identity(current) != expected['identity']
                                or disks.layout(current) != expected['layout'] or disks.in_use(current)):
                            return None
                        found = disks.windows_files(current)
                        if found:
                            found['fits'] = found['total'] // disks.MIB <= expected['keep']['monet'] - disks.MONET_OWN_MIB
                        return found
                except (OSError, ValueError, KeyError):
                    return None
            def done(found):
                if generation != self._disk_generation: return
                self._files_busy = False; self._chosen()['files'] = found
                if not found: self._bring = False
                self.changed.emit()
            self._background(measure, done)
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
        if getattr(self, '_disk_loading', False):
            return _('Looking for drives…')
        if not self._disks:
            return _("No disk found to install Monet on.")
        disk = self._chosen()
        if not disk:
            return _('Choose the drive where Monet will be installed.')
        if disk.get('busy'):
            return _('This drive is in use. Close its files and unmount it before installing.')
        if getattr(self, '_disk_busy', False) or getattr(self, '_files_busy', False):
            return _('Checking the selected drive…')
        if self._mode not in ('erase', 'keep', 'resume'):
            return _('Choose what to keep or erase on the selected drive.')
        if getattr(self, '_offline', False) and self._mode != 'resume':
            return _('Connect to the internet to start a new installation, or choose Resume interrupted installation.')
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
        if self._proc or self.blocker or not self._reviewed or DEMO:
            return
        disk = self._disks[self._disk]
        locale = system.LANGUAGES[self._language][1]
        layout, variant = system.KEYBOARDS[self._keyboard][1:]
        plan = {
            "image": pc.image_for(IMAGE, self._pc), "disk": disk["path"], "mode": self._mode,
            "sizes": disk.get(self._mode), 'identity': disk['identity'], 'layout': disk['layout'],
            'resume': disk['resume']['id'] if self._mode == 'resume' else self._resume_id,
            'gentle': self._gentle,
            'offline': self._offline,
            "language": locale, "keyboard": layout, "variant": variant,
            "timezone": self._zone,
            "name": self._name, "account": account_name(self._name), "password": self._password,
            "wifi": self._joined,
            "apps": self.picked_apps(),
            "files": self._files_plan(),
            "encrypt": self._encrypt and bool(self._pc.get("tpm")),
        }
        fd, path = tempfile.mkstemp(prefix="monet-plan-", suffix=".json", dir="/run")
        self._plan_path = Path(path)
        with os.fdopen(fd, "w") as f:
            json.dump(plan, f)
        self._phase, self._error, self._log, self._progress = "disk", "", [], 0.0
        self._exit_code, self._done_received = None, False
        self._status = _(PHASES["disk"][0])
        self.progressChanged.emit()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._finished)
        self._proc.errorOccurred.connect(self._process_error)
        self._proc.setWorkingDirectory(str(HERE))
        self._proc.start(sys.executable, ["-m", "monet_setup.install", path])

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._phase, self._error = 'failed', _('The installer could not start. Try again.')
            self._proc.deleteLater(); self._proc = None
            if self._plan_path: self._plan_path.unlink(missing_ok=True)
            self.progressChanged.emit()

    def _read(self, final=False):
        self._read_queued = False
        deadline, count = time.monotonic() + .008, 0
        self._reading = True
        try:
            while self._proc and (self._proc.canReadLine() or ((final or self._exit_code is not None) and self._proc.bytesAvailable())):
                line = bytes(self._proc.readLine(65537)).decode(errors="replace").strip()
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict): raise ValueError('not an event')
                except ValueError:
                    self._append_log(line)
                else:
                    self.report(event)
                count += 1
                if count >= 64 or time.monotonic() >= deadline: break
        finally:
            self._reading = False
        self.progressChanged.emit()
        if self._proc and (self._proc.canReadLine() or (self._exit_code is not None and self._proc.bytesAvailable())):
            if not self._read_queued:
                self._read_queued = True
                QTimer.singleShot(0, self._read)
        elif self._proc and self._exit_code is not None:
            self._proc.deleteLater(); self._proc = None
            self._phase = 'done' if self._exit_code == 0 and self._done_received and not self._error else 'failed'
            if self._phase == 'failed': self._error = self._error or _('The installer stopped unexpectedly.')
            if self._plan_path: self._plan_path.unlink(missing_ok=True)
            self.progressChanged.emit()

    def _append_log(self, text):
        text = str(text)[:4096]
        self._log = (self._log + [text])[-200:]
        print('install: ' + text, file=sys.stderr, flush=True)

    def report(self, event):
        """One progress event from install.py."""
        if event.get('resume'):
            self._resume_id = event['resume']
        if isinstance(event.get('health'), dict):
            health = event['health']; status = []
            if isinstance(health.get('temperature'), (int, float)):
                status.append(tr('Highest reported temperature: %1 °C', round(health['temperature'])))
            if isinstance(health.get('available'), (int, float)):
                status.append(tr('Available memory: %1 GB', f"{health['available'] / 1e9:.1f}"))
            status.append(tr('Elapsed: %1 min', max(1, int(health.get('elapsed', 0)) // 60)))
            self._health = ' · '.join(status)
            if not getattr(self, '_reading', False): self.progressChanged.emit()
            return
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
            self._append_log(event['log'])
            # The journal too, where a test PC's serial console shows why an install stopped.
        if event.get("error"):
            self._error = event["error"]
        if event.get("recovery"):
            self._recovery = event["recovery"]
        if event.get('done'):
            self._done_received = True
        self._phase = 'done' if event.get('done') and not getattr(self, '_proc', None) else phase
        if not getattr(self, '_reading', False): self.progressChanged.emit()

    def _finished(self, code, *_status):
        self._exit_code = code
        self._read(final=True)

    @Property(str, notify=progressChanged)
    def health(self):
        return self._health

    @Property(bool, notify=progressChanged)
    def restarting(self):
        return self._restarting

    @Property(str, notify=progressChanged)
    def restartError(self):
        return self._restart_error

    @Slot()
    def retry(self):
        self.install()

    @Slot()
    def restart(self):
        if DEMO or self._restarting:
            return
        self._restarting, self._restart_error = True, ''
        self.progressChanged.emit()
        def reboot():
            try:
                return subprocess.run(['systemctl', 'reboot'], capture_output=True, timeout=15).returncode == 0
            except (OSError, subprocess.TimeoutExpired): return False
        def done(ok):
            if not ok:
                self._restarting = False
                self._restart_error = _('Restart could not be requested. You can try again; your installation is saved.')
            self.progressChanged.emit()
        self._background(reboot, done)

    # -- a Monet installed here whose first start's blue screen was skipped --
    def _found_untrusted(self, key):
        self._untrusted = key
        self.changed.emit()

    @Property(bool, notify=changed)
    def untrusted(self):
        return self._untrusted is not None or os.environ.get("MONET_SETUP_DEMO_UNTRUSTED") == "1"

    @Slot()
    def trustAndRestart(self):
        """Asks the firmware again to trust that Monet's key, and restarts into the blue screen."""
        if DEMO or self._untrusted is None:
            return
        self._background(lambda: pc.trust(self._untrusted), lambda _result: self.restart())

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
