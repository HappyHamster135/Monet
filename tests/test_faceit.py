"""FACEIT for Counter-Strike 2: CS2 plays in Monet, FACEIT's matches and anti-cheat only in
Windows. What Monet sees of FACEIT on Windows' drive, what Games shows on CS2's page, and that
Monet Bridge only runs FACEIT's own installers, signed by FACEIT, for the person to go through.

    python3 tools/test.py tests.test_faceit
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
GAMES = ROOT / "linux/share/monet/games"
FACEIT_RS = ROOT / "crates/monet-bridge/src/faceit.rs"
BRIDGE_RS = ROOT / "crates/monet-bridge/src/bridge.rs"


def helper(name):
    """One of Monet's helpers in linux/libexec, loaded as a module (they have no .py)."""
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_") + "_faceit", str(ROOT / "linux/libexec" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def put(path, data=b"MZ"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def bridge_region():
    """bridge.rs' FACEIT part, on its own."""
    text = BRIDGE_RS.read_text(encoding="utf-8")
    return text[text.index("- FACEIT, for Counter-Strike 2"):text.index("- updating, then off")]


class SeenOnWindowsDrive(unittest.TestCase):
    """monet-windows-drive, at Monet's start: FACEIT in Windows, by its programs and shortcuts on
    the drive, or by what Monet Bridge noted there. Only read."""

    def setUp(self):
        self.drive = helper("monet-windows-drive")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "drive"
        self.root.mkdir()

    def found(self, person="ann"):
        return self.drive.windows_faceit(self.root, person)

    def test_nothing_there(self):
        self.assertEqual(self.found(), {"anticheat": False, "client": False, "setup": None, "security": None})

    def test_its_programs_in_any_case(self):
        # NTFS keeps one name for a folder, in whatever case its installer gave it.
        put(self.root / "PROGRAM FILES/faceit ac/FACEITCLIENT.EXE")
        self.assertEqual(self.found()["anticheat"], True)
        self.assertEqual(self.found()["client"], False)
        # The app, in the person's own Windows account.
        ann = self.root / "Users/Ann"
        put(ann / "NTUSER.DAT", b"regf")
        put(ann / "AppData/Local/FACEIT/FACEIT.exe")
        self.assertEqual(self.found("ann")["client"], True)
        self.assertEqual(self.found(None)["client"], False)  # nobody's own account: not looked in

    def test_a_start_menu_shortcut_counts(self):
        put(self.root / "ProgramData/Microsoft/Windows/Start Menu/Programs/FACEIT AC/FACEIT AC.lnk")
        put(self.root / "ProgramData/Microsoft/Windows/Start Menu/Programs/FACEIT/FACEIT.lnk")
        self.assertEqual((self.found()["anticheat"], self.found()["client"]), (True, True))

    def test_a_link_isnt_followed(self):
        elsewhere = put(Path(self.temp.name) / "elsewhere/FACEIT.lnk")
        menu = self.root / "ProgramData/Microsoft/Windows/Start Menu/Programs"
        menu.mkdir(parents=True)
        (menu / "FACEIT").symlink_to(elsewhere.parent, target_is_directory=True)
        self.assertFalse(self.found()["client"])
        note = put(Path(self.temp.name) / "elsewhere/faceit.json", json.dumps({"v": 1, "installed": {"client": True}}).encode())
        (self.root / "ProgramData/Monet").mkdir(parents=True)
        (self.root / "ProgramData/Monet/faceit.json").symlink_to(note)
        self.assertFalse(self.found()["client"])

    def test_what_monet_bridge_noted(self):
        note = {"v": 1, "checked": 1700000100, "installed": {"anticheat": True, "client": False, "other": True},
                "setup": {"when": 1700000000, "steps": {"anticheat": "installed", "client": "not-finished", "x": "installed"}},
                "security": {"secureBoot": True, "tpm": "2.0", "vbs": False, "memoryIntegrity": None}}
        put(self.root / "ProgramData/Monet/faceit.json", json.dumps(note).encode())
        found = self.found()
        self.assertEqual((found["anticheat"], found["client"]), (True, False))
        self.assertEqual(found["setup"], {"when": 1700000000, "steps": {"anticheat": "installed", "client": "not-finished"}})
        self.assertEqual(found["security"], {"secureBoot": True, "tpm": "2.0", "vbs": False, "memoryIntegrity": None})
        # Anything odd in it is dropped, not shown.
        odd = dict(note, setup={"when": 1, "steps": {"client": "rm -rf"}}, security={"secureBoot": "yes", "tpm": "<b>2.0</b>"})
        put(self.root / "ProgramData/Monet/faceit.json", json.dumps(odd).encode())
        found = self.found()
        self.assertEqual(found["setup"], {"when": 1, "steps": {}})
        self.assertEqual(found["security"], {"secureBoot": None, "tpm": "", "vbs": None, "memoryIntegrity": None})
        for broken in (b"{", b"[]", json.dumps({"v": 2, "installed": {"client": True}}).encode()):
            put(self.root / "ProgramData/Monet/faceit.json", broken)
            self.assertEqual(self.found()["setup"], None)
            self.assertFalse(self.found()["client"])

    def test_it_goes_into_monets_note_of_the_drive(self):
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn("launchers=windows_launchers(DRIVE, person[0]), faceit=windows_faceit(DRIVE, person[0]))", script)

    def test_the_same_places_as_monet_bridge(self):
        rust = FACEIT_RS.read_text(encoding="utf-8")
        for key, part in self.drive.FACEIT_PARTS.items():
            block = rust[rust.index(f'key: "{key}"'):]
            block = block[:block.index("},")]
            places = re.findall(r'Place::(ProgramFiles|LocalAppData)\("([^"]+)"\)', block)
            seen = {("Program Files/" if where == "ProgramFiles" else "AppData/Local/") + rest.replace("\\\\", "/")
                    for where, rest in places}
            self.assertEqual(seen, set(part["everyone"]) | set(part["own"]), key)
            names = re.search(r"shortcuts: &\[([^\]]*)\]", block).group(1)
            self.assertEqual(set(re.findall(r'"([^"]+)"', names)), set(part["shortcuts"]), key)
        # And the same words for how setting each part up went.
        steps = re.search(r"pub enum Step \{(.*?)\n\}", rust, re.S).group(1)
        variants = re.findall(r"^    ([A-Z]\w+),", steps, re.M)
        kebab = {re.sub(r"(?<!^)([A-Z])", r"-\1", v).lower() for v in variants}
        self.assertEqual(kebab, self.drive.FACEIT_STEPS)


class OnItsPage(unittest.TestCase):
    """monet-quick faceit: what CS2's page in Games says, from what's here already."""

    def setUp(self):
        self.q = helper("monet-quick")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.efivars = Path(self.temp.name) / "firmware/efi/efivars"
        self.efivars.mkdir(parents=True)
        self.chips = Path(self.temp.name) / "tpm"
        self.chips.mkdir()

    def faceit(self, found=None, boot=1, tpm="2"):
        (self.efivars / self.q.SECURE_BOOT_VAR).write_bytes(b"\x06\x00\x00\x00" + bytes([boot]))
        for chip in self.chips.iterdir():
            (chip / "tpm_version_major").unlink()
            chip.rmdir()
        if tpm:
            put(self.chips / "tpm0/tpm_version_major", tpm.encode() + b"\n")
        state = {"state": "open"} if found is None else {"state": "open", "faceit": found}
        return self.q.faceit(state, self.efivars, self.chips)

    def test_before_monet_could_look(self):
        found = self.faceit()
        self.assertEqual((found["looked"], found["ready"], found["problem"]), (False, False, ""))
        self.assertEqual((found["secureBoot"], found["tpm"], found["windows"]), ("on", True, None))

    def test_ready_once_both_are_there(self):
        half = self.faceit({"anticheat": True, "client": False})
        self.assertEqual((half["looked"], half["ready"]), (True, False))
        ready = self.faceit({"anticheat": True, "client": True, "setup": {"when": 1, "steps": {"anticheat": "not-finished"}},
                             "security": {"secureBoot": True, "tpm": "2.0", "vbs": True, "memoryIntegrity": True}})
        self.assertEqual((ready["ready"], ready["problem"]), (True, ""))   # set up by hand since: no problem
        self.assertEqual(ready["windows"]["vbs"], True)

    def test_how_setting_up_last_stopped(self):
        for steps, problem in (({"anticheat": "no-download", "client": "skipped"}, "no-download"),
                               ({"anticheat": "there", "client": "not-signed"}, "not-signed"),
                               ({"anticheat": "not-finished", "client": "skipped"}, "not-finished"),
                               ({"anticheat": "skipped", "client": "skipped"}, "not-finished"),  # the PC restarted midway
                               ({"anticheat": "stopped", "client": "skipped"}, "stopped"),
                               ({"anticheat": "installed", "client": "installed"}, "")):
            found = self.faceit({"anticheat": False, "client": False, "setup": {"when": 1, "steps": steps}})
            self.assertEqual(found["problem"], problem, steps)

    def test_secure_boot_and_the_tpm_as_monet_sees_them(self):
        self.assertEqual(self.faceit(boot=0)["secureBoot"], "off")
        self.assertFalse(self.faceit(tpm="1")["tpm"])
        self.assertFalse(self.faceit(tpm="")["tpm"])            # off in the firmware: Linux doesn't see it
        # Monet Setup asks the same.
        sys.path.insert(0, str(ROOT / "setup"))
        try:
            from monet_setup import pc
        finally:
            sys.path.remove(str(ROOT / "setup"))
        for version in ("2", "1", ""):
            self.faceit(tpm=version)
            self.assertEqual(pc.tpm2(self.chips), self.q.tpm2(self.chips), version)

    def test_games_asks_for_it(self):
        out = []
        with mock.patch.object(self.q, "shared_state", lambda: {"state": "open", "faceit": {"anticheat": True, "client": True}}), \
                mock.patch.object(self.q, "emit", out.append):
            self.q.main(["faceit"])
        self.assertTrue(out[0]["ready"])
        self.assertEqual(self.q.FACEIT_GAME, "steam:730")


class OnlyFaceitsOwn(unittest.TestCase):
    """What Monet Bridge does in Windows, as its source says it (the logic's own tests are in
    faceit.rs): FACEIT's own downloads, checked, run for the person to go through, nothing turned off."""

    def test_faceits_own_downloads_with_where_they_come_from(self):
        rust = FACEIT_RS.read_text(encoding="utf-8")
        self.assertIn('url: "https://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe"', rust)
        self.assertIn('url: "https://faceit-client.faceit-cdn.net/release/FACEIT-setup-latest.exe"', rust)
        self.assertIn("https://support.faceit.com/hc/en-us/articles/23117181142556", rust)
        self.assertIn("https://www.faceit.com/en/anti-cheat", rust)
        self.assertIn('publishers: &["FACEIT LTD", "FACEIT LIMITED"]', rust)
        self.assertEqual(re.findall(r'url: "(\w+)://', rust), ["https", "https"])

    def test_checked_downloaded_and_run_for_the_person(self):
        region = bridge_region()
        # HTTPS only, redirects too, with Windows' own curl.
        self.assertIn('"--proto", "=https", "--proto-redir", "=https", "--tlsv1.2"', region)
        self.assertIn('system.join("System32\\\\curl.exe")', region)
        # Windows checks the signature (the file's name never goes into the script) ...
        self.assertIn("Get-AuthenticodeSignature -LiteralPath $env:MONET_FILE", region)
        self.assertIn('.env("MONET_FILE", file)', region)
        # ... and again as the person, right before it opens in its own window.
        person = region[region.index("fn kit_as_person("):region.index("fn open_kit(")]
        self.assertLess(person.index("kit_installer_checked(kit, part)"), person.index("win::open_uri(&file.to_string_lossy())"))
        self.assertIn("s.valid && kit.signed_by_maker(&s.subject)", region)
        # In Monet's own folder, which only administrators change.
        self.assertIn("data_dir().join(kit.key)", region)
        # Never quietly: no switch that would skip the installer's own questions or terms.
        for quiet in ("/VERYSILENT", "/SILENT", "/SUPPRESSMSGBOXES", "\"/S\"", "--silent\"]"):
            self.assertNotIn(quiet, region.replace('"--fail", "--silent", "--show-error"', ""))

    def test_protections_are_only_asked_about(self):
        region = bridge_region()
        protections = region[region.index("const PROTECTIONS"):region.index("fn kit_protections(")]
        for reads in ("Confirm-SecureBootUEFI", "Win32_Tpm", "Win32_DeviceGuard"):
            self.assertIn(reads, protections)
        for changes in ("Set-", "reg add", "bcdedit", "Disable-", "Enable-", "Remove-", "HypervisorEnforcedCodeIntegrity"):
            self.assertNotIn(changes, region)
        # Nor does Windows' game profile turn memory integrity off unless asked.
        profile = (ROOT / "windows/GameProfile.ps1").read_text(encoding="utf-8")
        self.assertIn("if ($DisableMemoryIntegrity) {", profile)

    def test_the_trips(self):
        request = (ROOT / "crates/monet-core/src/request.rs").read_text(encoding="utf-8")
        self.assertIn('pub const TASKS: &[&str] = &["launchers", "update", "faceit-setup", "faceit"];', request)
        monet = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        self.assertIn('["play", id] if args.iter().any(|a| a == "--faceit") => switch(Some(id), Some("faceit"), confirm),', monet)
        self.assertIn('["windows"] if args.iter().any(|a| a == "--faceit") => switch(None, Some("faceit-setup"), confirm),', monet)
        bridge = BRIDGE_RS.read_text(encoding="utf-8")
        self.assertIn("return kit_setup_trip(efi, state, kit);", bridge)
        self.assertIn("Some(kit) if req.game.as_deref() == Some(kit.game) => {", bridge)
        self.assertIn("let pending = Pending { game: id.clone(), created: now(), open: before, quietly: false };", bridge)
        # The anti-cheat runs before the game, as FACEIT wants.
        self.assertIn("kit_as_person(key, !pending.game.is_empty());", bridge)
        cover = (ROOT / "crates/monet-bridge/src/cover.rs").read_text(encoding="utf-8")
        self.assertIn("Read their terms and accept them only if you agree: Monet never does that for you, and turns nothing off.", cover)


class InGames(unittest.TestCase):
    """CS2's page in Games: FACEIT's card, its one action, and the sheet before the restart."""

    def test_the_card(self):
        page = (GAMES / "GamePage.qml").read_text(encoding="utf-8")
        self.assertIn("readonly property bool faceitHere: game.id === app.faceitGame && app.windowsHere", page)
        card = page[page.index("id: faceitCard"):]
        self.assertIn("visible: page.faceitHere", card)
        self.assertIn('kind: "lily"', card)
        self.assertIn('text: page.faceitReady ? i18n("Play on FACEIT") : i18n("Set up FACEIT")', card)
        self.assertIn("onClicked: page.faceitReady ? page.app.playOnFaceit(page.game) : page.app.setUpFaceit(page.game)", card)
        self.assertIn('visible: page.faceit.secureBoot === "off"', card)
        self.assertIn("onActiveFocusChanged: if (activeFocus) page.reveal(this)", card)
        # Every word through Monet's catalog, but FACEIT's own name.
        for literal in re.findall(r'text: "([^"]+)"', card):
            self.assertEqual(literal, "FACEIT")
        # Mist and smoke: the page's own colors.
        self.assertNotIn("Kirigami.Theme", card)
        # Ordinary Play stays as it is.
        self.assertIn('text: page.game.plays === "windows" ? i18n("Play on Windows") : i18n("Play in Monet")', page)

    def test_the_restart(self):
        games = (GAMES / "Games.qml").read_text(encoding="utf-8")
        self.assertIn('readonly property string faceitGame: "steam:730"', games)
        go = games[games.index("function go() {"):games.index("// Let the sun start setting")]
        # As ever for a game, then FACEIT's own restarts.
        self.assertIn('launch.command = game ? ["monet", "play", game.windows] : ["monet", "windows"]', go)
        self.assertIn('if (task === "faceit-setup")\n            launch.command = ["monet", "windows", "--faceit"]', go)
        self.assertIn('else if (task === "faceit")\n            launch.command = ["monet", "play", faceitGame, "--faceit"]', go)
        self.assertIn('run(["helper", "open", "security"])', games)
        self.assertIn('i18n("Restart & Set up")', games)


try:
    from PySide6.QtCore import QObject, QTimer, QUrl, Qt, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401 (the window's own type, with its items)
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class GamesHelper(QObject):
        """Games' helper, made up: CS2 in the library, FACEIT as each test says; nothing runs."""
        done = Signal(int, str, int, str)
        wanted = Signal(str)

        def __init__(self, faceit):
            super().__init__()
            self.ticket, self.faceit, self.ran = 0, faceit, []

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1
            ticket, command = self.ticket, [str(c) for c in command]
            self.ran.append(command)
            answer = {"library": [{"id": "steam:730", "name": "Counter-Strike 2", "store": "steam", "plays": "monet", "why": "",
                                   "here": "steam:730", "windows": "", "shared": False, "move": False, "progress": None,
                                   "locate": "", "art": "", "last": 0, "minutes": 0, "size": 0, "favorite": False,
                                   "tall": "", "hero": ""},
                                  {"id": "steam:570", "name": "Dota 2", "store": "steam", "plays": "monet", "why": "",
                                   "here": "steam:570", "windows": "", "shared": False, "move": False, "progress": None,
                                   "locate": "", "art": "", "last": 0, "minutes": 0, "size": 0, "favorite": False,
                                   "tall": "", "hero": ""}],
                      "faceit": self.faceit, "shared": {"state": "open"}}.get(command[1] if len(command) > 1 else "", {})
            out = "Windows   Ready\n" if command == ["monet"] else json.dumps(answer)
            QTimer.singleShot(1, lambda: self.done.emit(ticket, out, 0, ""))
            return ticket


@unittest.skipUnless(QT, "Qt/Kirigami runtime")
class GamesWindow(unittest.TestCase):
    NOT_YET = {"looked": True, "client": False, "anticheat": False, "ready": False, "problem": "",
               "secureBoot": "off", "tpm": True, "windows": None}

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.temp = tempfile.TemporaryDirectory()
        cls.identity = (cls.app.organizationName(), cls.app.applicationName())
        cls.app.setOrganizationName("monet-faceit-tests")
        cls.app.setApplicationName("games")
        from PySide6.QtCore import QSettings
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, cls.temp.name)
        cls.games = helper("monet-games")

    @classmethod
    def tearDownClass(cls):
        cls.app.setOrganizationName(cls.identity[0])
        cls.app.setApplicationName(cls.identity[1])
        cls.temp.cleanup()

    def open(self, faceit):
        self.engine, self.helper, self.errors = QQmlApplicationEngine(), GamesHelper(faceit), []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        context = self.engine.rootContext()
        self.words = self.games.Words()
        context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "blurBehind": False,
                            "art": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(GAMES / "Games.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.addCleanup(self.close)
        self.wait_for(lambda: self.window.property("loaded"))

    def close(self):
        self.window.close()
        self.engine.deleteLater()
        QTest.qWait(10)
        self.assertEqual(self.errors, [])

    def wait_for(self, condition, seconds=3):
        deadline = time.monotonic() + seconds
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition())

    def item(self, name):
        todo = [self.window.contentItem()]
        while todo:
            item = todo.pop()
            if item.objectName() == name:
                return item
            todo.extend(item.childItems())
        self.fail(name + " missing")

    def page(self, game):
        self.window.setProperty("pageId", game)
        QTest.qWait(60)

    def press(self, name):
        self.item(name).forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(30)

    def go_with_the_keys(self, label):
        """The sheet has the keys (on Cancel or the bright button): Tab to the bright one, Enter."""
        QTest.qWait(450)
        for _ in range(3):
            if self.window.activeFocusItem().property("text") == label:
                break
            QTest.keyClick(self.window, Qt.Key_Tab)
            QTest.qWait(20)
        self.assertEqual(self.window.activeFocusItem().property("text"), label)
        QTest.keyClick(self.window, Qt.Key_Return)

    def test_set_up_faceit_from_cs2s_page_with_the_keys(self):
        self.open(self.NOT_YET)
        self.page("steam:730")
        self.wait_for(lambda: ["helper", "faceit"] in self.helper.ran)
        card = self.item("faceit")
        self.wait_for(lambda: card.isVisible())
        self.assertEqual(self.item("faceitAction").property("text"), "Set up FACEIT")
        self.assertTrue(self.item("faceitSecurity").isVisible())   # Secure Boot is off: how to turn it on
        self.press("faceitSecurity")
        self.assertIn(["helper", "open", "security"], self.helper.ran)
        self.press("faceitAction")
        self.wait_for(lambda: self.window.property("sheetOpen"))
        self.assertEqual(self.window.property("task"), "faceit-setup")
        texts = self.texts()
        self.assertIn("Set up FACEIT in Windows?", texts)
        self.assertIn("Restart & Set up", texts)
        self.go_with_the_keys("Restart & Set up")
        self.wait_for(lambda: ["monet", "windows", "--faceit"] in self.helper.ran, 4)

    def test_play_on_faceit_once_its_there(self):
        self.open(dict(self.NOT_YET, client=True, anticheat=True, ready=True, secureBoot="on",
                       windows={"secureBoot": True, "tpm": "2.0", "vbs": False, "memoryIntegrity": False}))
        self.page("steam:730")
        self.wait_for(lambda: self.item("faceitAction").property("text") == "Play on FACEIT")
        self.assertFalse(self.item("faceitSecurity").isVisible())
        self.assertIn("Virtualization-based security", " ".join(self.texts()))
        self.press("faceitAction")
        self.wait_for(lambda: self.window.property("sheetOpen"))
        self.assertIn("Play Counter-Strike 2 on FACEIT?", self.texts())
        self.go_with_the_keys("Restart & Play")
        self.wait_for(lambda: ["monet", "play", "steam:730", "--faceit"] in self.helper.ran, 4)

    def test_only_on_counter_strikes_page(self):
        self.open(self.NOT_YET)
        self.page("steam:570")
        QTest.qWait(60)
        self.assertFalse(self.item("faceit").isVisible())
        self.assertNotIn(["helper", "faceit"], self.helper.ran)

    def texts(self):
        found, todo = [], [self.window.contentItem()]
        while todo:
            item = todo.pop()
            todo.extend(item.childItems())
            if item.isVisible() and isinstance(item.property("text"), str):
                found.append(item.property("text"))
        return found


if __name__ == "__main__":
    unittest.main()
