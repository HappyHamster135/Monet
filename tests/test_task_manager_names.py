"""Task Manager says what is what (0.9.8-7): each Steam game by its own name and icon, every app
by its own name where KDE missed it, what a browser's window shows under its name, which app a
process belongs to, and System, so the Applications rows add up to the cards above them."""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
FACES = ROOT / "linux/share/ksysguard/sensorfaces"
NAMES_JS = FACES / "org.monet.performance/contents/ui/appnames.js"

try:
    from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, QUrl,
                                Property, Signal, Slot)
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QJSEngine, QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401 (items come back as Quick's)
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False

# libksysguard 6.8 (processcore/cgroup.cpp, s_appIdFromProcessGroupPattern): the app id it takes
# from each part of a process's cgroup, last part first, then looks up as <id>.desktop
# (KService::serviceByMenuId) and shows as is when nothing is called that.
KSYSGUARD_APP_ID = re.compile(r"(apps|app|flatpak|dbus)-(?:[^-]*-)?([^-]+(?=-.*\.scope)|[^@]+(?=(?:@.*)?\.service|.slice))")


def ksysguard_app_id(cgroup):
    for part in reversed(cgroup.split("/")):
        found = KSYSGUARD_APP_ID.search(part)
        if found:
            return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m[1], 16)), found[2])
    return ""


# plasma-systemmonitor 6.8's Applications page (ApplicationsTableView.qml, cgroupMapping): the
# units it files under Background Services.
KDE_SERVICES = ("session.slice", "background.slice", "org.a11y.atspi.Registry", "org.kde.discover.notifier", "geoclue",
                "org.kde.kunifiedpush", "dconf.service", "flatpak-session-helper.service", "gpg-agent.service",
                "org.kde.xwaylandvideobridge", "org.kde.kalendarac", "xdg-desktop-portal-gtk.service", "org.kde.kdeconnect",
                "org.kde.kwalletd6", "org.kde.kclockd")


def kde_rows(tree, entries, uid=1000):
    """KDE's Applications rows for a cgroup tree ({path: [pid]}), as libksysguard 6.8 makes them
    (ApplicationDataModel): only units under the account's own manager, an app's when its unit is
    app-* (or Flatpak's), Background Services' when mapped, grouped by the app's menu entry."""
    root = f"/user.slice/user-{uid}.slice/user@{uid}.service/"
    apps = {}
    for path, pids in tree.items():
        if not path.startswith(root) or not path.endswith((".service", ".scope")):
            continue
        if any(unit.lower() in path.lower() for unit in KDE_SERVICES):
            key = "services"
        elif "/app-" in path or ("/flatpak" in path and path.endswith("scope")):
            raw = ksysguard_app_id(path)
            key = raw + ".desktop" if raw + ".desktop" in entries else raw
        else:
            continue
        apps.setdefault(key, []).extend(pids)
    return [{"key": key, "pids": pids} for key, pids in apps.items()]


def manifest(library, appid, name):
    folder = library / "steamapps"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n\t"StateFlags"\t\t"4"\n}}\n', encoding="utf-8")


def library_list(steam, libraries):
    """libraryfolders.vdf: {path: [appid, ...]}."""
    parts = []
    for i, (path, apps) in enumerate(libraries.items()):
        listed = "".join(f'\t\t\t"{a}"\t\t"1000"\n' for a in apps)
        parts.append(f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{path}"\n\t\t"apps"\n\t\t{{\n{listed}\t\t}}\n\t}}\n')
    (steam / "steamapps").mkdir(parents=True, exist_ok=True)
    (steam / "steamapps/libraryfolders.vdf").write_text('"libraryfolders"\n{\n' + "".join(parts) + "}\n", encoding="utf-8")


class SteamScopes(unittest.TestCase):
    """What KDE looks up for a game: the assumption Monet's entries are named after."""

    def test_libksysguard_takes_app_and_the_steam_id_from_steams_scope(self):
        here = "/user.slice/user-1000.slice/user@1000.service/app.slice/"
        self.assertEqual(ksysguard_app_id(here + "app-steam-app3241660-41235.scope"), "app3241660")
        # Without Steam's own name in front, the same id.
        self.assertEqual(ksysguard_app_id(here + "app-app3241660-41235.scope"), "app3241660")
        # Flatpak's apps and the ones Plasma starts, as the Applications page shows them.
        self.assertEqual(ksysguard_app_id(here + "app-flatpak-org.chromium.Chromium-2381.scope"), "org.chromium.Chromium")
        self.assertEqual(ksysguard_app_id(here + "app-org.kde.konsole-4242.scope"), "org.kde.konsole")
        self.assertEqual(ksysguard_app_id(here + "app-steam@autostart.service"), "steam")
        # Dashes in an id are written \\x2d.
        self.assertEqual(ksysguard_app_id(here + "app-org.example.my\\x2dapp-12.scope"), "org.example.my-app")

    def test_the_pattern_is_libksysguards_own(self):
        # Pinned to the 6.8 source: if KDE changes it, look at what it does with Steam's scopes again.
        self.assertEqual(KSYSGUARD_APP_ID.pattern,
                         r"(apps|app|flatpak|dbus)-(?:[^-]*-)?([^-]+(?=-.*\.scope)|[^@]+(?=(?:@.*)?\.service|.slice))")


class GameEntries(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.q = quick_helper()
        self.steam = self.root / "home/.local/share/Steam"
        self.drive = self.root / "drive/SteamLibrary"
        self.data = self.root / "home/.local/share"
        self.apps = self.data / "applications"
        for patcher in (patch.object(self.q, "STEAM_ROOTS", (self.steam,)),
                        patch.object(self.q, "DATA_HOME", self.data),
                        patch.object(self.q, "data_dirs", lambda: [self.data, self.root / "usr/share"])):
            patcher.start()
            self.addCleanup(patcher.stop)
        manifest(self.steam, "3241660", "R.E.P.O.")
        manifest(self.drive, "730", "Counter-Strike 2")
        manifest(self.steam, "1493710", "Proton Experimental")  # a tool, never a game
        library_list(self.steam, {self.steam: ["3241660", "1493710"], self.drive: ["730"]})

    def entry(self, name):
        return self.q.desktop_entry((self.apps / name).read_text(encoding="utf-8"))

    def test_each_installed_game_gets_a_hidden_entry_named_as_kde_looks_it_up(self):
        self.assertEqual(self.q.game_names(), {"written": ["app3241660.desktop", "app730.desktop"], "removed": []})
        repo = self.entry("app3241660.desktop")
        self.assertEqual(repo["Name"], "R.E.P.O.")
        self.assertEqual(repo["Type"], "Application")
        # Out of the menu, search and Monet's own lists; Monet's, so uninstalling takes it away.
        self.assertEqual(repo["NoDisplay"], "true")
        self.assertEqual(repo["X-Monet"], "true")
        self.assertEqual(repo["X-Monet-Steam-Game"], "3241660")
        # Should anything open it, Steam shows the game: nothing starts a game by itself.
        self.assertEqual(repo["Exec"], "xdg-open steam://nav/games/details/3241660")
        self.assertNotRegex(repo["Exec"], self.q.LAUNCHER_GAME)
        self.assertFalse(self.q.shown_in_menu(repo))
        self.assertFalse((self.apps / "app1493710.desktop").exists())
        # Nothing changed, nothing written.
        self.assertEqual(self.q.game_names(), {"written": [], "removed": []})

    def test_the_games_icon_is_steams_own(self):
        # Steam's own, in the icon theme, when it added the game to the menu itself.
        icons = self.data / "icons/hicolor/32x32/apps"
        icons.mkdir(parents=True)
        (icons / "steam_icon_3241660.png").write_bytes(b"png")
        # Else the one in Steam's picture cache: appid/<checksum>.jpg (newer Steam), appid_icon.jpg (older).
        cache = self.steam / "appcache/librarycache"
        (cache / "730").mkdir(parents=True)
        (cache / "730/library_600x900.jpg").write_bytes(b"jpg")
        checksum = cache / "730" / ("0123456789abcdef0123456789abcdef01234567" + ".jpg")
        checksum.write_bytes(b"jpg")
        self.q.game_names()
        self.assertEqual(self.entry("app3241660.desktop")["Icon"], "steam_icon_3241660")
        self.assertEqual(self.entry("app730.desktop")["Icon"], str(checksum))
        checksum.unlink()
        (cache / "730_icon.jpg").write_bytes(b"jpg")
        self.assertEqual(self.q.game_names()["written"], ["app730.desktop"])
        self.assertEqual(self.entry("app730.desktop")["Icon"], str(cache / "730_icon.jpg"))
        # Without either, a game pad.
        (cache / "730_icon.jpg").unlink()
        self.q.game_names()
        self.assertEqual(self.entry("app730.desktop")["Icon"], "applications-games")

    def test_an_uninstalled_game_goes_and_one_on_a_drive_not_mounted_stays(self):
        self.q.game_names()
        # The drive isn't mounted: its manifests can't be read, but Steam still lists the game.
        shutil.rmtree(self.drive)
        self.assertEqual(self.q.game_names(), {"written": [], "removed": []})
        self.assertTrue((self.apps / "app730.desktop").exists())
        # Uninstalled: neither manifest nor list has it.
        (self.steam / "steamapps/appmanifest_3241660.acf").unlink()
        library_list(self.steam, {self.steam: [], self.drive: ["730"]})
        self.assertEqual(self.q.game_names(), {"written": [], "removed": ["app3241660.desktop"]})
        self.assertFalse((self.apps / "app3241660.desktop").exists())

    def test_someones_own_entry_of_that_name_stays_theirs(self):
        self.apps.mkdir(parents=True)
        mine = "[Desktop Entry]\nType=Application\nName=My REPO\nExec=repo-launcher\n"
        (self.apps / "app3241660.desktop").write_text(mine)
        (self.apps / "app999.desktop").write_text(mine)  # no game: still theirs
        self.q.game_names()
        self.assertEqual((self.apps / "app3241660.desktop").read_text(), mine)
        self.assertEqual((self.apps / "app999.desktop").read_text(), mine)

    def test_a_name_is_one_line_of_text(self):
        manifest(self.steam, "3241660", "R.E.P.O.\\\tDeluxe")
        self.q.game_names()
        text = (self.apps / "app3241660.desktop").read_text()
        self.assertIn("Name=R.E.P.O.\\\\ Deluxe\n", text)
        self.assertEqual(len([line for line in text.splitlines() if line.startswith("Name")]), 1)


class AppNames(unittest.TestCase):
    """monet-quick app-names: what the Task Manager asks about the rows (and windows) KDE couldn't name."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.q = quick_helper()
        self.home = self.root / "home/applications"
        self.flatpak = self.root / "flatpak/exports/share/applications"
        self.icons = self.root / "flatpak/exports/share/icons"
        self.steam = self.root / "Steam"
        manifest(self.steam, "3241660", "R.E.P.O.")
        for patcher in (patch.object(self.q, "STEAM_ROOTS", (self.steam,)),
                        patch.object(self.q, "data_dirs", lambda: [self.root / "home"]),
                        patch.object(self.q, "icon_files", lambda names: {})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def entry(self, folder, name, text):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("[Desktop Entry]\nType=Application\n" + text)

    def names(self, *ids):
        return self.q.app_names(list(ids), dirs=[self.home, self.flatpak], flatpak_icons=(self.icons,))

    def test_a_steam_game_by_its_name(self):
        self.assertEqual(self.names("app3241660"), {"app3241660": {"name": "R.E.P.O.", "icon": "applications-games"}})
        self.assertEqual(self.names("app1"), {})

    def test_a_flatpak_app_kde_missed_by_its_entry_and_exported_icon(self):
        self.entry(self.flatpak, "org.chromium.Chromium.desktop", "Name=Chromium\nName[sv]=Chromium-webbläsare\n"
                   "Icon=org.chromium.Chromium\nExec=flatpak run org.chromium.Chromium\nX-Flatpak=org.chromium.Chromium\n")
        icon = self.icons / "hicolor/128x128/apps/org.chromium.Chromium.png"
        icon.parent.mkdir(parents=True)
        icon.write_bytes(b"png")
        self.assertEqual(self.names("org.chromium.Chromium"), {"org.chromium.Chromium": {"name": "Chromium", "icon": str(icon)}})
        # In another letter case, too; in the session's language.
        with patch.dict(os.environ, {"LANGUAGE": "sv_SE"}):
            self.assertEqual(self.names("org.chromium.chromium")["org.chromium.chromium"]["name"], "Chromium-webbläsare")
        # An icon a theme on the path has goes by its name.
        with patch.object(self.q, "icon_files", lambda names: {n: [(0, 48, Path("/x.png"))] for n in names}):
            self.assertEqual(self.names("org.chromium.Chromium")["org.chromium.Chromium"]["icon"], "org.chromium.Chromium")

    def test_a_web_app_window_by_its_own_entry(self):
        web = "chrome-cadlkienfkclaiaibeoongdcgmdikeeg-Default"
        # A Flatpak browser's portal puts the browser's id in front of the web app's entry.
        self.entry(self.home, f"org.chromium.Chromium.flextop.{web}.desktop",
                   "Name=ChatGPT\nIcon=/home/me/.local/share/icons/chatgpt.png\nExec=chromium --app-id=cadlk\n")
        self.entry(self.home, "zen-pwa.desktop", "Name=Calendar\nIcon=calendar\nStartupWMClass=FFPWA-01ABC\nExec=x\n")
        self.assertEqual(self.names(web, "FFPWA-01ABC"), {
            web: {"name": "ChatGPT", "icon": "/home/me/.local/share/icons/chatgpt.png"},
            "FFPWA-01ABC": {"name": "Calendar", "icon": "calendar"}})

    def test_hidden_entries_and_odd_ids_are_not_names(self):
        self.entry(self.home, "gone.desktop", "Name=Gone\nHidden=true\nExec=x\n")
        self.assertEqual(self.names("gone", "", "a b", "../x", "x" * 300), {})

    def test_the_command_takes_hex_and_answers_json(self):
        env = dict(os.environ, HOME=str(self.root / "home"), XDG_DATA_HOME=str(self.root / "home"),
                   XDG_DATA_DIRS=str(self.root / "none"))
        steam = self.root / "home/Steam"
        manifest(steam, "3241660", "R.E.P.O.")
        done = subprocess.run([sys.executable, str(ROOT / "linux/libexec/monet-quick"), "app-names",
                               "app3241660".encode().hex(), "app5".encode().hex()],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"app3241660": {"name": "R.E.P.O.", "icon": "applications-games"}})
        # Anything else isn't asked.
        bad = subprocess.run([sys.executable, str(ROOT / "linux/libexec/monet-quick"), "app-names", "zz"],
                             capture_output=True, text=True, env=env, timeout=60)
        self.assertNotIn("R.E.P.O.", bad.stdout)


class Arrival(unittest.TestCase):
    """The entries come as Steam's libraries change and a minute after sign-in."""

    def test_a_path_unit_watches_steams_libraries(self):
        path = (ROOT / "linux/systemd/user/monet-game-names.path").read_text()
        self.assertIn("PathChanged=%h/.local/share/Steam/steamapps\n", path)
        self.assertIn("PathChanged=%h/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps\n", path)
        self.assertIn("WantedBy=default.target", path)
        service = (ROOT / "linux/systemd/user/monet-game-names.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-quick game-names\n", service)
        self.assertIn("StartLimitIntervalSec=0", service)
        self.assertIn("Type=oneshot", service)
        install = (ROOT / "linux/install.sh").read_text()
        for unit in ("monet-game-names.path", "monet-game-names.service"):
            self.assertIn(f'put 644 "$SRC/systemd/user/{unit}" "$USERUNITDIR/{unit}"', install)
        self.assertEqual(install.count("systemctl --global enable monet-game-names.path"), 2)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn("rm -f /etc/systemd/user/monet-game-names.path /etc/systemd/user/monet-game-names.service", uninstall)
        self.assertIn("systemctl --global disable monet-game-names.path", uninstall)
        # Uninstalling takes Monet's entries away with the rest of its menu entries.
        self.assertIn("grep -l -x 'X-Monet=true' \"$HOME\"/.local/share/applications/*.desktop", uninstall)

    def test_sign_in_makes_them_when_steam_changed_while_signed_out(self):
        session = (ROOT / "linux/libexec/monet-session").read_text()
        later = session.split('if [ "${1:-}" = --later ]; then', 1)[1].split("\nfi\n", 1)[0]
        self.assertIn('"$LIBEXECDIR/monet-quick" game-names >/dev/null 2>&1', later)
        looked = session.split("apps_now() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn('"$DATA/Steam/steamapps"', looked)
        self.assertIn('"$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"', looked)

    def test_monets_other_lists_leave_hidden_entries_out(self):
        q = quick_helper()
        entry = q.desktop_entry(q.game_entries([(Path("/s"), "3241660", "R.E.P.O.", {})])["app3241660.desktop"])
        # The menu's lists, Reopen your work and the crash note all skip entries out of the menu.
        self.assertFalse(q.shown_in_menu(entry))
        with patch.object(q, "entry_by_id", lambda app: entry), patch.object(q, "starts_anyway", lambda app: False):
            self.assertEqual(q.reopenable(["app3241660.desktop"]), [])


class KdeTables(unittest.TestCase):
    """The Task Manager build refuses a KDE source whose tables no longer have what Monet's faces use."""

    def patch_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("task_manager_patch", ROOT / "image/task-manager/patch.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_a_changed_table_stops_the_build(self):
        patch_module = self.patch_module()
        with tempfile.TemporaryDirectory() as folder:
            for name, anchors in patch_module.FACE_ANCHORS.items():
                path = Path(folder) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// KDE's file\n" + "\n".join(anchors) + "\n")
            patch_module.check_faces(folder)
            table = Path(folder) / "src/faces/applicationstable/contents/ui/ApplicationsTableView.qml"
            table.write_text(table.read_text().replace("property alias sourceModel: appModel", "property alias source: appModel"))
            with self.assertRaisesRegex(ValueError, "Task Manager source changed"):
                patch_module.check_faces(folder)

    def test_what_monets_faces_use_is_what_the_build_checks(self):
        anchors = "\n".join(a for group in self.patch_module().FACE_ANCHORS.values() for a in group)
        ui = FACES / "org.monet.applications/contents/ui"
        apps = (ui / "Apps.qml").read_text()
        for used in ("sourceModel", "selectedApplications", "view", "delegate", "commandColumn"):
            self.assertIn(used, apps)
            self.assertIn(used, anchors)
        for used in ("hiddenAttributes", "columnDisplay", "applicationOverrides", "iconColumn"):
            self.assertIn(used, anchors)
        processes = (FACES / "org.monet.processes/contents/ui/Processes.qml").read_text()
        for used in ("processModel", "flatList"):
            self.assertIn(used, processes)
            self.assertIn(used, anchors)
        self.assertIn("pidColumn", (FACES / "org.monet.processes/contents/ui/ProcessCell.qml").read_text())
        self.assertIn("check_faces(source)", (ROOT / "image/task-manager/patch.py").read_text())

    def test_the_faces_use_monets_pieces(self):
        for face, piece in (("org.monet.applications", "Apps {"), ("org.monet.processes", "Processes {")):
            full = (FACES / face / "contents/ui/FullRepresentation.qml").read_text()
            self.assertIn(piece, full)
            self.assertIn(".attach(face.contentItem)", full)
        # The helper's path is filled in by install.sh, as in every face.
        self.assertIn('property string helper: "@LIBEXECDIR@/monet-quick"',
                      (FACES / "org.monet.performance/contents/ui/AppNames.qml").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('fill "$DATADIR"/ksysguard/sensorfaces/org.monet.*/contents/ui/*.qml', install)
        # Monet's own page keeps CPU scaled to every processor, the card's measure.
        page = (ROOT / "linux/share/plasma-systemmonitor/monet-applications.page").read_text()
        self.assertIn('"usage":"lineScaled"', page)


@unittest.skipUnless(QT, "requires PySide6")
class Logic(unittest.TestCase):
    """appnames.js: what both tables show, run as Qt runs it."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QJSEngine()
        text = NAMES_JS.read_text(encoding="utf-8").replace(".pragma library", "")
        result = cls.engine.evaluate(text, str(NAMES_JS))
        assert not result.isError(), result.toString()

    def call(self, name, *args):
        script = "%s(%s)" % (name, ", ".join(json.dumps(a) for a in args))
        value = self.engine.evaluate(script)
        self.assertFalse(value.isError(), value.toString())
        return value.toVariant()

    def test_rows_kde_couldnt_name(self):
        self.assertTrue(self.call("unresolved", "app3241660", "", ""))
        self.assertFalse(self.call("unresolved", "Steam", "steam.desktop", "steam"))
        self.assertFalse(self.call("unresolved", "services", "", ""))
        self.assertEqual(self.call("toAsk", ["app1", "app1", "a b", "app2"], {"app2": True}), ["app1"])
        self.assertEqual(self.call("hex", "app3241660"), "app3241660".encode().hex())
        self.assertEqual(self.call("hex", "Zoë🎮"), "Zoë🎮".encode().hex())
        merged = self.call("overrides", {"services": {"appName": "Background Services"}},
                           {"app1": {"name": "R.E.P.O.", "icon": "/i.jpg"}, "services": {"name": "x"}, "app2": None})
        self.assertEqual(merged, {"services": {"appName": "Background Services"},
                                  "app1": {"appName": "R.E.P.O.", "iconName": "/i.jpg"}})

    def test_windows_front_first(self):
        windows = [{"pid": 7, "title": "Back", "order": 1}, {"pid": 7, "title": "Hidden", "minimized": True, "order": 9},
                   {"pid": 7, "title": "Top", "order": 5}, {"pid": 8, "title": "Other app", "active": True},
                   {"pid": 0, "title": "No process"}]
        self.assertEqual([w["title"] for w in self.call("windowsOf", [7, 9], windows)], ["Top", "Back", "Hidden"])
        windows[0]["active"] = True
        self.assertEqual(self.call("windowsOf", [7], windows)[0]["title"], "Back")

    def test_titles_without_the_apps_name(self):
        for title, names, clean in (("ChatGPT - Chromium", ["Chromium"], "ChatGPT"),
                                    ("ChatGPT — Zen Browser", ["Zen Browser"], "ChatGPT"),
                                    ("A - B - Chromium - Person 1", ["Chromium"], "A - B"),
                                    ("Chromium", ["Chromium"], "Chromium"),
                                    ("#general | Friends - Discord", ["Discord"], "#general | Friends"),
                                    ("Song   Title", ["Spotify"], "Song Title")):
            self.assertEqual(self.call("cleanTitle", title, names), clean, title)

    def test_the_second_line(self):
        chromium = {"name": "Chromium", "menuId": "org.chromium.Chromium.desktop", "id": "Chromium"}
        web = "chrome-cadlkienfkclaiaibeoongdcgmdikeeg-Default"
        tab = {"pid": 1, "title": "ChatGPT - Chromium", "appId": "org.chromium.Chromium", "appName": "Chromium"}
        mail = {"pid": 1, "title": "Inbox (3) - Chromium", "appId": "org.chromium.Chromium", "appName": "Chromium"}
        app = {"pid": 1, "title": "ChatGPT", "appId": web, "appName": "ChatGPT", "icon": "chatgpt"}
        self.assertEqual(self.call("windowLine", chromium, [tab], {}), {"text": "ChatGPT", "icon": "", "more": 0})
        self.assertEqual(self.call("windowLine", chromium, [tab, mail, tab], {}), {"text": "ChatGPT", "icon": "", "more": 1})
        # A web app's window by the web app's own name and icon, from KDE or monet-quick.
        self.assertEqual(self.call("windowLine", chromium, [app, mail], {}), {"text": "ChatGPT", "icon": "chatgpt", "more": 1})
        unnamed = dict(app, appName="", title="New chat")
        self.assertEqual(self.call("windowLine", chromium, [unnamed], {web: {"name": "ChatGPT", "icon": "/c.png"}}),
                         {"text": "ChatGPT", "icon": "/c.png", "more": 0})
        self.assertEqual(self.call("windowLine", chromium, [unnamed], {}), {"text": "New chat", "icon": "", "more": 0})
        # A game's window is called what the game is: nothing more to say.
        repo = {"name": "R.E.P.O.", "menuId": "app3241660.desktop", "id": "R.E.P.O."}
        self.assertEqual(self.call("windowLine", repo, [{"pid": 2, "title": "R.E.P.O.", "appId": "steam_app_3241660",
                                                         "appName": "Steam"}], {})["text"], "")
        self.assertEqual(self.call("windowLine", repo, [], {})["text"], "")
        # A row KDE couldn't name, by its own window's app.
        self.assertEqual(self.call("windowName", {"id": "org.chromium.Chromium", "name": "org.chromium.Chromium"},
                                   [tab])["name"], "Chromium")
        self.assertIsNone(self.call("windowName", {"id": "app1", "name": "app1"}, [tab]))

    def test_system_is_what_the_cards_count_and_no_app_does(self):
        # 88% of every processor on a PC with 8, apps adding up to 160 of its 800: System 544.
        self.assertAlmostEqual(self.call("systemShare", "usage", 0, 88, 160, 800), 544)
        self.assertAlmostEqual(self.call("cpuShown", 544, 800, "lineScaled"), 68)
        self.assertAlmostEqual(self.call("cpuShown", 544, 800, "line"), 544)
        # Memory in KiB (KDE's 101) from the card's bytes; network and storage in bytes a second (200).
        self.assertAlmostEqual(self.call("systemShare", "vmPSS", 101, 8 * 1024 ** 3, 6 * 1024 ** 2, 0), 2 * 1024 ** 2)
        self.assertAlmostEqual(self.call("systemShare", "netInbound", 200, 5000, 1000, 0), 4000)
        self.assertAlmostEqual(self.call("systemShare", "ioCharactersActuallyWrittenRate", 200, 100, 300, 0), 0)
        # Columns no card compares with, and cards not read yet.
        self.assertTrue(math.isnan(self.call("systemShare", "monetGraphics", 0, 50, 10, 0)))
        self.assertTrue(math.isnan(self.call("systemShare", "usage", 0, None, 10, 800)))

    def test_the_busiest_first(self):
        found = self.call("busiest", [{"name": "kswapd0", "pid": 90, "values": {"usage": 120}},
                                      {"name": "rpm-ostree", "pid": 91, "values": {"usage": 40}},
                                      {"name": "idle", "pid": 92, "values": {"usage": 0}}, {"name": "x", "pid": 0}], 5)
        self.assertEqual(found, [{"name": "kswapd0", "pid": 90, "usage": 120}, {"name": "rpm-ostree", "pid": 91, "usage": 40}])
        self.assertEqual([p["name"] for p in self.call("systemProcesses", [{"name": "a", "uid": 0}, {"name": "b", "uid": 1000}], 1000)],
                         ["a"])

    def test_other_is_named_for_what_its_mostly_doing(self):
        java = [{"name": "java", "values": {"usage": 150}} for _ in range(8)]
        idle = [{"name": "systemd", "values": {"usage": 0}}, {"name": "python3", "values": {"usage": 1}}]
        self.assertEqual(self.call("mostlyOne", java + idle), {"program": "Java", "count": 8})
        # Nothing busy, or nothing that's most of it: no one program to name.
        self.assertIsNone(self.call("mostlyOne", idle))
        self.assertIsNone(self.call("mostlyOne", [{"name": "a", "values": {"usage": 40}}, {"name": "b", "values": {"usage": 30}},
                                                  {"name": "c", "values": {"usage": 30}}]))
        self.assertEqual(self.call("programName", "/opt/game/REPO.exe"), "REPO")
        self.assertEqual(self.call("rowKey", "R.E.P.O.", "", {"app3241660": {"name": "R.E.P.O."}}), "app3241660")
        self.assertEqual(self.call("rowKey", "Konsole", "org.kde.konsole.desktop", {}), "org.kde.konsole.desktop")
        self.assertEqual(self.call("rowKey", "app5", "", {}), "app5")
        merged = self.call("overrides", {"services": {"appName": "Background Services"}}, {},
                           {"services": {"usage": 30}, "org.kde.konsole.desktop": {"usage": 1210}})
        self.assertEqual(merged, {"services": {"appName": "Background Services", "usage": 30},
                                  "org.kde.konsole.desktop": {"usage": 1210}})

    def test_every_process_lands_in_a_row(self):
        """The owner's PC: eight java processes of theirs outside every app's unit, the card at 88%
        and KDE's rows at about 20%. On a made-up cgroup tree, KDE's rows as libksysguard 6.8 makes
        them, then Monet's: every process of the account in a row, the rest in System."""
        user = "/user.slice/user-1000.slice/user@1000.service"
        tree = {  # cgroup: [(pid, parent, uid, name, CPU: 100 a processor)]
            user + "/init.scope": [(1500, 1, 1000, "systemd", 0), (1501, 1500, 1000, "(sd-pam)", 0)],
            user + "/app.slice/app-steam@autostart.service": [(2001, 1500, 1000, "steam", 4), (2002, 2001, 1000, "steamwebhelper", 12)],
            user + "/app.slice/app-steam-app3241660-41235.scope": [(3001, 2001, 1000, "reaper", 0), (3002, 3001, 1000, "REPO.exe", 137)],
            user + "/app.slice/app-flatpak-org.chromium.Chromium-1.scope": [(4001, 1500, 1000, "chrome", 13), (4002, 4001, 1000, "chrome", 5)],
            user + "/app.slice/app-org.kde.konsole-77.scope": [(5001, 1500, 1000, "konsole", 2)],
            # A terminal tab in a scope of its own, not named for an app: it's Konsole's.
            user + "/app.slice/konsole-session-1.scope": [(5101, 5001, 1000, "bash", 0), (5102, 5101, 1000, "java", 110)],
            # A unit of its own (systemd-run --user, a timer's job), and Monet's own service.
            user + "/app.slice/run-u42.service": [(6000 + i, 1500, 1000, "java", 150) for i in range(1, 8)],
            user + "/app.slice/monet-rest.service": [(7001, 1500, 1000, "python3", 1)],
            user + "/session.slice/plasma-kwin_wayland.service": [(8001, 1500, 1000, "kwin_wayland", 31)],
            user + "/session.slice/plasma-plasmashell.service": [(8002, 1500, 1000, "plasmashell", 14)],
            # Signed in over SSH: outside the user's manager altogether.
            "/user.slice/user-1000.slice/session-3.scope": [(9000, 1, 0, "sshd-session", 0), (9001, 9000, 1000, "bash", 0),
                                                             (9002, 9001, 1000, "java", 160)],
            "/system.slice/rpm-ostreed.service": [(100, 1, 0, "rpm-ostree", 40)],
            "/user.slice/user-1001.slice/user@1001.service/app.slice/app-firefox-9.scope": [(1100, 1, 1001, "firefox", 20)],
            "/": [(90, 2, 0, "kswapd0", 60)],
        }
        entries = {"steam.desktop", "app3241660.desktop", "org.chromium.Chromium.desktop", "org.kde.konsole.desktop"}
        rows = kde_rows({path: [p[0] for p in procs] for path, procs in tree.items()}, entries)
        processes = [{"pid": pid, "ppid": parent, "uid": uid, "name": name, "values": {"usage": usage}}
                     for procs in tree.values() for pid, parent, uid, name, usage in procs]
        keys = {row["key"] for row in rows}
        self.assertEqual(keys, {"steam.desktop", "app3241660.desktop", "org.chromium.Chromium.desktop",
                                "org.kde.konsole.desktop", "services"})
        in_rows = {pid for row in rows for pid in row["pids"]}
        # What KDE alone shows: none of the java processes.
        self.assertFalse({p["pid"] for p in processes if p["name"] == "java"} & in_rows)
        result = self.call("account", rows, processes, ["usage"])
        self.assertEqual(result["mine"], 1000)
        # Konsole's row gains its tab's bash and java.
        self.assertEqual(result["gained"], {"org.kde.konsole.desktop": 2})
        self.assertEqual(result["totals"], {"org.kde.konsole.desktop": {"usage": 112}})
        other = result["other"]
        self.assertEqual(sorted(p["pid"] for p in other), [1500, 1501, 6001, 6002, 6003, 6004, 6005, 6006, 6007, 7001, 9001, 9002])
        self.assertEqual(self.call("mostlyOne", other), {"program": "Java", "count": 8})
        system = self.call("systemProcesses", processes, result["mine"])
        self.assertEqual(sorted(p["name"] for p in system), ["firefox", "kswapd0", "rpm-ostree", "sshd-session"])
        # Every process in exactly one row: the rows with what they gained, Other and System.
        row_usage = {row["key"]: sum(p["values"]["usage"] for p in processes if p["pid"] in row["pids"]) for row in rows}
        row_usage.update({key: total["usage"] for key, total in result["totals"].items()})
        shown = sum(row_usage.values()) + sum(p["values"]["usage"] for p in other) + sum(p["values"]["usage"] for p in system)
        self.assertEqual(shown, sum(p["values"]["usage"] for p in processes))
        # The card is the whole PC: what isn't in a process (interrupts) is System's too.
        cpu_max, card = 2000, 88  # 20 processors, 88%
        counted = sum(row_usage.values()) + sum(p["values"]["usage"] for p in other)
        self.assertAlmostEqual(self.call("systemShare", "usage", 0, card, counted, cpu_max), card / 100 * cpu_max - counted)

    def test_the_app_a_process_belongs_to(self):
        repo = {"id": "app3241660.desktop", "name": "R.E.P.O."}
        self.assertEqual(self.call("processApp", "REPO.exe", repo, None, True), "R.E.P.O.")
        self.assertEqual(self.call("processApp", "steam", {"id": "steam.desktop", "name": "Steam"}, None, True), "")
        self.assertEqual(self.call("processApp", "kwin_wayland", {"id": "services", "name": "Background Services"}, None, True), "")
        # In the tree, where the app's group begins.
        self.assertEqual(self.call("processApp", "REPO.exe", repo, repo, False), "")
        self.assertEqual(self.call("processApp", "REPO.exe", repo, repo, True), "R.E.P.O.")
        self.assertEqual(self.call("processApp", "reaper", repo, {"id": "steam.desktop", "name": "Steam"}, False), "R.E.P.O.")
        self.assertEqual(self.call("processApp", "bash", None, None, True), "")


# Stand-ins for KDE's modules, each as much as Monet's table pieces use of it.
STUBS = {
    "org/kde/kirigami/qmldir": "module org.kde.kirigami\nsingleton Units 1.0 Units.qml\nsingleton Theme 1.0 Theme.qml\n"
                               "Icon 1.0 Icon.qml\nSeparator 1.0 Separator.qml\n",
    "org/kde/kirigami/Units.qml": "pragma Singleton\nimport QtQuick\nQtObject { property int smallSpacing: 4; "
                                  "property int largeSpacing: 8; property int gridUnit: 18; property QtObject iconSizes: "
                                  "QtObject { property int small: 16; property int smallMedium: 22; property int medium: 32 } }\n",
    "org/kde/kirigami/Theme.qml": "pragma Singleton\nimport QtQuick\nQtObject { property color textColor: 'black'; "
                                  "property color disabledTextColor: 'gray'; property color highlightColor: 'teal'; "
                                  "property color highlightedTextColor: 'white'; property color backgroundColor: 'white'; "
                                  "property font smallFont: Qt.font({pointSize: 8}); property font defaultFont: Qt.font({pointSize: 10}) }\n",
    "org/kde/kirigami/Icon.qml": "import QtQuick\nItem { enum Status { Null, Ready, Loading, Error }\n"
                                 "property var source; property var fallback; property bool animated; property int status: Icon.Ready }\n",
    "org/kde/kirigami/Separator.qml": "import QtQuick\nRectangle { implicitHeight: 1 }\n",
    "org/kde/ksysguard/table/qmldir": "module org.kde.ksysguard.table\nFirstCellDelegate 1.0 FirstCellDelegate.qml\n"
                                      "TextCellDelegate 1.0 TextCellDelegate.qml\n",
    "org/kde/ksysguard/table/FirstCellDelegate.qml": "import QtQuick.Controls\nTreeViewDelegate { property string iconName; "
                                                     "property real iconSize: 22; property bool treeDecorationVisible }\n",
    "org/kde/ksysguard/table/TextCellDelegate.qml": "import QtQuick.Controls\nTreeViewDelegate { objectName: 'monetText' }\n",
    "org/kde/ksysguard/formatter/qmldir": "module org.kde.ksysguard.formatter\nsingleton Formatter 1.0 Formatter.qml\n",
    "org/kde/ksysguard/formatter/Formatter.qml": "pragma Singleton\nimport QtQuick\nQtObject { function formatValue(value, unit) "
                                                 "{ return (Math.round(Number(value) * 10) / 10) + ' u' + unit } }\n",
    "org/kde/ksysguard/process/qmldir": "module org.kde.ksysguard.process\nProcessDataModel 1.0 ProcessDataModel.qml\n"
                                        "ApplicationDataModel 1.0 ApplicationDataModel.qml\nsingleton Fake 1.0 Fake.qml\n",
    "org/kde/ksysguard/process/Fake.qml": "pragma Singleton\nimport QtQuick\nQtObject { property var processes: []; property var apps: [] }\n",
    "org/kde/ksysguard/process/ApplicationDataModel.qml": """import QtQuick
QtObject {
    id: model
    property bool enabled
    property var enabledAttributes: []
    property var applicationOverrides: ({})
    signal rowsInserted()
    function rowCount() { return Fake.apps.length }
    function index(row, column) { return {row: row, column: column} }
    function data(index, role) {
        const row = Fake.apps[index.row], attribute = enabledAttributes[index.column]
        if (role === ProcessDataModel.PIDs) return row.pids
        const override = applicationOverrides[row.id] || {}
        return attribute in override ? override[attribute] : row[attribute]
    }
}
""",
    "org/kde/ksysguard/process/ProcessDataModel.qml": """import QtQuick
QtObject {
    enum AdditionalRoles { Value = 256, FormattedValue, PIDs, Minimum, Maximum, Attribute, Name, ShortName, Unit, UpdateInterval }
    property bool flatList
    property bool enabled
    property var enabledAttributes: []
    function rowCount() { return Fake.processes.length }
    function index(row, column) { return {row: row, column: column} }
    function data(index, role) { return Fake.processes[index.row][enabledAttributes[index.column]] }
}
""",
    "org/kde/ksysguard/sensors/qmldir": "module org.kde.ksysguard.sensors\nSensor 1.0 Sensor.qml\nsingleton Readings 1.0 Readings.qml\n",
    "org/kde/ksysguard/sensors/Readings.qml": "pragma Singleton\nimport QtQuick\nQtObject { property var values: ({}) }\n",
    "org/kde/ksysguard/sensors/Sensor.qml": """import QtQuick
QtObject {
    enum Status { Unknown, Loading, Ready, Error }
    property string sensorId
    property bool enabled
    property int updateRateLimit
    readonly property var value: Readings.values[sensorId]
    readonly property int status: Sensor.Ready
    readonly property string formattedValue: String(value)
}
""",
    "org/kde/taskmanager/qmldir": "module org.kde.taskmanager\nTasksModel 1.0 TasksModel.qml\nAbstractTasksModel 1.0 AbstractTasksModel.qml\n"
                                  "singleton Windows 1.0 Windows.qml\n",
    "org/kde/taskmanager/Windows.qml": "pragma Singleton\nimport QtQuick\nQtObject { property var list: [] }\n",
    "org/kde/taskmanager/AbstractTasksModel.qml": "import QtQuick\nQtObject { enum AdditionalRoles { AppId = 257, AppName, "
                                                  "IsWindow, IsActive, IsMinimized, AppPid, StackingOrder } }\n",
    "org/kde/taskmanager/TasksModel.qml": """import QtQuick
QtObject {
    id: tasks
    enum GroupMode { GroupDisabled, GroupApplications }
    property int groupMode
    signal dataChanged(var topLeft, var bottomRight, var roles)
    signal rowsInserted()
    signal rowsRemoved()
    signal modelReset()
    function rowCount() { return Windows.list.length }
    function index(row, column) { return {row: row} }
    function data(index, role) {
        const w = Windows.list[index.row]
        switch (role) {
        case Qt.DisplayRole: return w.title
        case Qt.DecorationRole: return w.icon || ""
        case AbstractTasksModel.AppId: return w.appId
        case AbstractTasksModel.AppName: return w.appName
        case AbstractTasksModel.IsWindow: return true
        case AbstractTasksModel.IsActive: return !!w.active
        case AbstractTasksModel.IsMinimized: return !!w.minimized
        case AbstractTasksModel.AppPid: return w.pid
        case AbstractTasksModel.StackingOrder: return w.order || 0
        }
        return undefined
    }
    property Connections changes: Connections { target: Windows; function onListChanged() { tasks.modelReset() } }
}
""",
    "org/kde/plasma/plasma5support/qmldir": "module org.kde.plasma.plasma5support\nDataSource 1.0 DataSource.qml\n",
    "org/kde/plasma/plasma5support/DataSource.qml": """import QtQuick
QtObject {
    id: source
    property string engine
    property var connectedSources: []
    signal newData(string sourceName, var data)
    function connectSource(name) {
        const done = shell.run(name)
        Qt.callLater(() => source.newData(name, {"exit code": done.code, "stdout": done.stdout}))
    }
    function disconnectSource(name) {}
}
""",
}

# KDE's Applications table as Monet's face finds it: its model, filtered view and cell choice.
SCENE = """import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.qmlmodels
import org.kde.ksysguard.process as Process
import org.kde.ksysguard.sensors as Sensors
import org.kde.taskmanager as TaskManager
import "APPS" as Monet

Window {
    id: scene
    width: 1000
    height: 640
    visible: true
    readonly property Item monet: apps
    readonly property Item layout: content
    function setProcesses(list) { Process.Fake.processes = list }
    function setWindows(list) { TaskManager.Windows.list = list }
    function setReadings(values) { Sensors.Readings.values = values }
    ColumnLayout {
        id: content
        anchors.fill: parent
        spacing: 0
        Item { Layout.fillWidth: true; implicitHeight: 8 }
        Item {
            id: table
            Layout.fillWidth: true
            Layout.fillHeight: true
            property var sourceModel: appModel
            property var model: proxyModel
            property var selectedApplications: []
            property var columnDisplay: ({usage: "lineScaled", vmPSS: "text"})
            property alias view: tree
            property alias delegate: tree.delegate
            TreeView {
                id: tree
                anchors.fill: parent
                model: proxyModel
                columnWidthProvider: column => column === 0 ? 400 : 150
                delegate: DelegateChooser {
                    role: "displayStyle"
                    DelegateChoice { column: 0; Label { objectName: "kdeName"; text: model.display } }
                    DelegateChoice { roleValue: "lineScaled"; Label { objectName: "kdeLine"; text: "line " + model.Value } }
                    DelegateChoice { Label { objectName: "kdeText"; text: model.display } }
                }
            }
        }
    }
    Monet.Apps {
        id: apps
        active: true
    }
}
"""

ROLES = {"Value": 256, "PIDs": 258, "Maximum": 260, "Unit": 264}
COLUMNS = ["appName", "usage", "vmPSS", "iconName", "menuId"]
HIDDEN = ["iconName", "menuId"]
UNITS = {"usage": 900, "vmPSS": 101}

if QT:
    class FakeApps(QAbstractTableModel):
        """KDE's ApplicationDataModel, as its rows read: an app's id, values and processes; its overrides."""
        overridesChanged = Signal()

        def __init__(self, rows):
            super().__init__()
            self.rows, self.overrides = rows, {}

        def rowCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(self.rows)

        def columnCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(COLUMNS)

        def roleNames(self):
            names = dict(super().roleNames())
            names.update({value: key.encode() for key, value in ROLES.items()})
            names[300] = b"displayStyle"
            return names

        def data(self, index, role=Qt.DisplayRole):
            row, attribute = self.rows[index.row()], COLUMNS[index.column()]
            if role == ROLES["PIDs"]:
                return row["pids"]
            if role == 300:
                return {"usage": "lineScaled"}.get(attribute, "text")
            if role == ROLES["Unit"]:
                return UNITS.get(attribute, 0)
            if role in (Qt.DisplayRole, ROLES["Value"]):
                override = self.overrides.get(row["id"], {})
                value = override.get(attribute, row.get(attribute, ""))
                return value if role == ROLES["Value"] or isinstance(value, str) else f"{value} kde"
            return None

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            attribute = COLUMNS[section]
            if role == ROLES["Maximum"]:
                return 2000 if attribute == "usage" else 0
            if role == ROLES["Unit"]:
                return UNITS.get(attribute, 0)
            return attribute

        def get_attributes(self):
            return COLUMNS

        def get_hidden(self):
            return HIDDEN

        def get_overrides(self):
            return self.overrides

        def set_overrides(self, value):
            self.overrides = value.toVariant() if hasattr(value, "toVariant") else dict(value)
            self.overridesChanged.emit()
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, len(COLUMNS) - 1))

        enabledAttributes = Property("QVariantList", get_attributes, constant=True)
        hiddenAttributes = Property("QVariantList", get_hidden, constant=True)
        applicationOverrides = Property("QVariantMap", get_overrides, set_overrides, notify=overridesChanged)

    class Shown(QSortFilterProxyModel):
        """KDE's filter over the model: the columns it only reads aren't shown."""

        def filterAcceptsColumn(self, column, parent):
            return COLUMNS[column] not in HIDDEN

    class Shell(QObject):
        """The plasma5support executable engine: runs the command, as KDE's does, in the test's home."""

        def __init__(self, env):
            super().__init__()
            self.env, self.commands = env, []

        @Slot(str, result="QVariantMap")
        def run(self, command):
            self.commands.append(command)
            done = subprocess.run(["bash", "-c", command], capture_output=True, text=True, env=self.env, timeout=60)
            return {"code": done.returncode, "stdout": done.stdout}

    class Words(QObject):
        """KDE's i18nd and i18ndp, in English."""

        @Slot(str, str, result=str)
        @Slot(str, str, "QVariant", result=str)
        @Slot(str, str, "QVariant", "QVariant", result=str)
        def i18nd(self, domain, text, first=None, second=None):
            for i, value in ((1, first), (2, second)):
                if value is not None:
                    text = text.replace(f"%{i}", str(value))
            return text

        @Slot(str, str, str, int, "QVariant", result=str)
        def i18ndp(self, domain, one, many, count, value):
            return (one if count == 1 else many).replace("%1", str(count)).replace("%2", str(value))


@unittest.skipUnless(QT, "requires PySide6")
class Tables(unittest.TestCase):
    """Monet's pieces in KDE's Applications table, against stand-ins for KDE's modules."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, text in STUBS.items():
            (root / "imports" / name).parent.mkdir(parents=True, exist_ok=True)
            (root / "imports" / name).write_text(text, encoding="utf-8")
        faces = root / "sensorfaces"
        for face in ("org.monet.performance", "org.monet.applications"):
            shutil.copytree(FACES / face, faces / face)
        for qml in faces.rglob("*.qml"):
            qml.write_text(qml.read_text(encoding="utf-8").replace("@LIBEXECDIR@", str(ROOT / "linux/libexec")), encoding="utf-8")
        scene = root / "scene.qml"
        scene.write_text(SCENE.replace("APPS", (faces / "org.monet.applications/contents/ui").as_uri()), encoding="utf-8")
        # Steam's game and Flatpak's Chromium, where monet-quick looks.
        home = root / "home"
        manifest(home / ".local/share/Steam", "3241660", "R.E.P.O.")
        flatpak = home / ".local/share/flatpak/exports/share/applications"
        flatpak.mkdir(parents=True)
        (flatpak / "org.chromium.Chromium.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Chromium\nIcon=org.chromium.Chromium\nExec=chromium\n")
        env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / ".local/share"), XDG_DATA_DIRS=str(root / "none"))
        self.shell, self.words = Shell(env), Words()
        self.model = FakeApps([
            {"id": "steam.desktop", "appName": "Steam", "iconName": "steam", "menuId": "steam.desktop", "usage": 16,
             "vmPSS": 500, "pids": [2001, 2002]},
            {"id": "app3241660", "appName": "app3241660", "iconName": "", "menuId": "", "usage": 137, "vmPSS": 4000,
             "pids": [3001, 3002]},
            {"id": "org.chromium.Chromium", "appName": "org.chromium.Chromium", "iconName": "", "menuId": "", "usage": 18,
             "vmPSS": 9000, "pids": [4001, 4002]},
            {"id": "org.kde.konsole.desktop", "appName": "Konsole", "iconName": "utilities-terminal",
             "menuId": "org.kde.konsole.desktop", "usage": 2, "vmPSS": 100, "pids": [5001]},
            {"id": "services", "appName": "Background Services", "iconName": "preferences-system-services", "menuId": "services",
             "usage": 45, "vmPSS": 800, "pids": [8001, 8002]}])
        self.model.overrides = {"services": {"menuId": "services", "appName": "Background Services"}}
        self.proxy = Shown()
        self.proxy.setSourceModel(self.model)
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(root / "imports"))
        self.errors = []
        self.engine.warnings.connect(lambda warnings: self.errors.extend(w.toString() for w in warnings))
        context = self.engine.rootContext()
        context.setContextObject(self.words)
        for name, value in (("appModel", self.model), ("proxyModel", self.proxy), ("shell", self.shell)):
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(self.engine.rootObjects(), "\n".join(self.errors))
        self.scene = self.engine.rootObjects()[0]
        self.addCleanup(self.close)
        self.apps = self.scene.property("monet")
        self.assertTrue(self.call(self.apps, "attach", self.scene.property("layout")), "\n".join(self.errors))
        QTest.qWait(50)

    def close(self):
        self.scene.close()
        self.engine.deleteLater()
        QTest.qWait(5)
        # Nothing Monet added may warn: in KDE's Task Manager a warning is usually a part not working.
        self.assertEqual(self.errors, [])

    def call(self, target, method, *args):
        from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
        if not args:
            return QMetaObject.invokeMethod(target, method, Q_RETURN_ARG("QVariant"))
        return QMetaObject.invokeMethod(target, method, Q_RETURN_ARG("QVariant"), *[Q_ARG("QVariant", a) for a in args])

    def items(self):
        todo, found = [self.scene.contentItem()], []
        while todo:
            item = todo.pop()
            todo.extend(item.childItems())
            found.append(item)
        return found

    def cells(self):
        """{row's name as shown: its first cell} of the rows on screen."""
        return {i.property("shownName"): i for i in self.items() if i.property("shownName") is not None and i.isVisible()}

    def wait_for(self, test, timeout=10):
        import time
        deadline = time.monotonic() + timeout
        while not test() and time.monotonic() < deadline:
            QTest.qWait(20)
        return test()

    def test_the_first_cell_is_monets_and_the_rest_kdes(self):
        cells = self.cells()
        self.assertEqual(sorted(cells), sorted(["Steam", "app3241660", "org.chromium.Chromium", "Konsole", "Background Services"]))
        kinds = {i.objectName() for i in self.items() if i.objectName() in ("kdeName", "kdeLine", "kdeText", "monetText")}
        # KDE's own line chart cells stay; its first cells are Monet's; text columns read their values.
        self.assertEqual(kinds, {"kdeLine", "monetText"})

    def test_rows_kde_couldnt_name_get_their_own_names(self):
        self.call(self.apps.property("names"), "look", [])
        self.assertTrue(self.wait_for(lambda: "R.E.P.O." in self.cells() and "Chromium" in self.cells()),
                        (sorted(self.cells()), self.shell.commands, self.errors))
        self.assertEqual(len(self.shell.commands), 1)
        self.assertIn(" app-names ", self.shell.commands[0])
        self.assertEqual(self.model.overrides["app3241660"], {"appName": "R.E.P.O.", "iconName": "applications-games"})
        self.assertEqual(self.model.overrides["services"]["appName"], "Background Services")
        # Asked once: the next look has nothing new to ask.
        self.call(self.apps.property("names"), "look", [])
        QTest.qWait(100)
        self.assertEqual(len(self.shell.commands), 1)

    def test_a_browser_says_whats_open(self):
        web = "chrome-cadlkienfkclaiaibeoongdcgmdikeeg-Default"
        self.call(self.scene, "setWindows", [
            {"pid": 4001, "title": "ChatGPT - Chromium", "appId": "org.chromium.Chromium", "appName": "Chromium", "order": 3},
            {"pid": 4001, "title": "Inbox - Chromium", "appId": "org.chromium.Chromium", "appName": "Chromium", "order": 1},
            {"pid": 4002, "title": "ChatGPT", "appId": web, "appName": "ChatGPT", "icon": "chatgpt", "order": 5},
            {"pid": 9999, "title": "Elsewhere", "appId": "x", "appName": "X", "order": 9}])
        chromium = self.cells()
        self.assertTrue(self.wait_for(lambda: "Chromium" in self.cells()
                                      and self.cells()["Chromium"].property("detail") == "ChatGPT and 1 more"),
                        {k: v.property("detail") for k, v in self.cells().items()})
        cell = self.cells()["Chromium"]
        # Named by its windows' app until monet-quick answers; the web app's window by its own icon.
        self.assertEqual(cell.property("line").toVariant()["icon"], "chatgpt")
        self.assertEqual(self.cells()["Steam"].property("detail"), "")
        self.assertIn("org.chromium.Chromium", chromium)

    def test_the_rows_add_up_to_the_cards(self):
        processes = []
        def add(pid, ppid, uid, name, usage, pss=0):
            processes.append({"pid": pid, "parentPid": ppid, "uid": uid, "name": name, "usage": usage, "vmPSS": pss})
        add(1500, 1, 1000, "systemd", 0, 10)
        for pid, ppid, name, usage, pss in ((2001, 1500, "steam", 4, 200), (2002, 2001, "steamwebhelper", 12, 300),
                                            (3001, 2001, "reaper", 0, 0), (3002, 3001, "REPO.exe", 137, 4000),
                                            (4001, 1500, "chrome", 13, 6000), (4002, 4001, "chrome", 5, 3000),
                                            (5001, 1500, "konsole", 2, 100), (5101, 5001, "bash", 0, 5), (5102, 5101, "java", 110, 900),
                                            (8001, 1500, "kwin_wayland", 31, 500), (8002, 1500, "plasmashell", 14, 300)):
            add(pid, ppid, 1000, name, usage, pss)
        for i in range(8):
            add(6001 + i, 1500, 1000, "java", 150, 1000)
        add(100, 1, 0, "rpm-ostree", 40)
        add(90, 2, 0, "kswapd0", 60)
        self.call(self.scene, "setProcesses", processes)
        self.call(self.scene, "setReadings", {"cpu/all/usage": 88.0, "memory/physical/used": 32 * 1024 ** 3})
        sums = self.apps.property("sums")
        self.call(sums, "refresh")
        QTest.qWait(50)
        # Konsole's row gained its tab's bash and java: KDE shows the sums Monet gives it.
        self.assertEqual(self.model.overrides["org.kde.konsole.desktop"], {"usage": 112, "vmPSS": 1005})
        self.assertIn("monetText", {i.objectName() for i in self.items()})
        texts = {i.property("text") for i in self.items() if i.objectName() == "monetText"}
        self.assertIn("1005 u101", texts)
        self.assertIn("line 112", {i.property("text") for i in self.items() if i.objectName() == "kdeLine"})
        # Other: the eight java processes and the account's manager, named for the java.
        rows = {i.objectName(): i for i in self.items() if i.objectName() in ("monetOtherRow", "monetSystemRow")}
        self.assertEqual(set(rows), {"monetOtherRow", "monetSystemRow"})
        titles = {i.property("text") for i in self.items() if i.objectName() == "pinnedTitle"}
        self.assertEqual(titles, {"Java (8)", "System"})
        other = sums.property("other").toVariant()
        self.assertEqual(other["usage"], 1200)
        # System: the card's 88% of 20 processors, less every row and Other.
        rows_usage = 16 + 137 + 18 + 112 + 45
        system = sums.property("system").toVariant()
        self.assertAlmostEqual(system["usage"], 0.88 * 2000 - rows_usage - 1200)
        self.assertAlmostEqual(system["vmPSS"], 32 * 1024 ** 2 - (500 + 4000 + 9000 + 1005 + 800) - 8010)
        self.assertEqual([p["name"] for p in sums.property("systemBusiest").toVariant()], ["kswapd0", "rpm-ostree"])
        shown = {i.property("text") for i in self.items() if isinstance(i.property("text"), str)}
        self.assertIn(f"{round((0.88 * 2000 - rows_usage - 1200) / 2000 * 100, 1)} u900", shown)
        # A row KDE files under an id Monet can't know (an autostart entry's own file) keeps its
        # own sums; what it started goes to Other instead, so the rows still add up.
        konsole = next(row for row in self.model.rows if row["appName"] == "Konsole")
        konsole.update(id="/home/me/.config/autostart/konsole.desktop", menuId="")
        self.call(sums, "refresh")
        QTest.qWait(50)
        self.assertEqual(sums.property("other").toVariant()["usage"], 1310)
        self.assertEqual(sums.property("otherCount"), 11)
        system = sums.property("system").toVariant()
        self.assertAlmostEqual(system["usage"], 0.88 * 2000 - (16 + 137 + 18 + 2 + 45) - 1310)


# KDE's applicationstable face, its shape as plasma-systemmonitor 6.8 has it: the table in a
# column with its toolbar, in a split view with the details sidebar.
NATIVE_FACE = """import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.qmlmodels
Item {
    property Item contentItem: SplitView {
        ColumnLayout {
            SplitView.fillWidth: true
            spacing: 0
            ToolBar { Layout.fillWidth: true }
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                property var sourceModel: appModel
                property var model: proxyModel
                property var selectedApplications: []
                property var columnDisplay: ({usage: "lineScaled"})
                property alias view: tree
                property alias delegate: tree.delegate
                TreeView {
                    id: tree
                    anchors.fill: parent
                    model: proxyModel
                    delegate: DelegateChooser {
                        role: "displayStyle"
                        DelegateChoice { column: 0; Label { objectName: "kdeName"; text: model.display } }
                        DelegateChoice { Label { text: model.display } }
                    }
                }
            }
        }
        Item { visible: false }
    }
}
"""

FACE_SCENE = """import QtQuick
import "MONET" as Monet
Window {
    width: 900
    height: 500
    visible: true
    readonly property Item face: Monet.FullRepresentation {}
    Component.onCompleted: {
        face.contentItem.parent = contentItem
        face.contentItem.anchors.fill = contentItem
    }
}
"""


@unittest.skipUnless(QT, "requires PySide6")
class Face(unittest.TestCase):
    """Monet's Applications face itself, over KDE's: it finds the table and adds its pieces."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_the_face_finds_kdes_table_and_adds_its_rows(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, text in STUBS.items():
            (root / "imports" / name).parent.mkdir(parents=True, exist_ok=True)
            (root / "imports" / name).write_text(text, encoding="utf-8")
        native = root / "native"
        native.mkdir()
        (native / "FullRepresentation.qml").write_text(NATIVE_FACE, encoding="utf-8")
        faces = root / "sensorfaces"
        for face in ("org.monet.performance", "org.monet.applications"):
            shutil.copytree(FACES / face, faces / face)
        kde = "file:///usr/share/ksysguard/sensorfaces/org.kde.ksysguard.applicationstable/contents/ui"
        for qml in faces.rglob("*.qml"):
            text = qml.read_text(encoding="utf-8").replace("@LIBEXECDIR@", str(ROOT / "linux/libexec"))
            qml.write_text(text.replace(kde, native.as_uri()), encoding="utf-8")
        scene = root / "scene.qml"
        scene.write_text(FACE_SCENE.replace("MONET", (faces / "org.monet.applications/contents/ui").as_uri()), encoding="utf-8")
        model = FakeApps([{"id": "steam.desktop", "appName": "Steam", "iconName": "steam", "menuId": "steam.desktop",
                           "usage": 16, "vmPSS": 500, "pids": [2001]}])
        proxy = Shown()
        proxy.setSourceModel(model)
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(root / "imports"))
        errors = []
        engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
        context = engine.rootContext()
        words, shell = Words(), Shell(dict(os.environ))
        context.setContextObject(words)
        for name, value in (("appModel", model), ("proxyModel", proxy), ("shell", shell)):
            context.setContextProperty(name, value)
        engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(engine.rootObjects(), "\n".join(errors))
        window = engine.rootObjects()[0]
        self.addCleanup(engine.deleteLater)
        self.addCleanup(window.close)

        def items():
            todo, found = [window.contentItem()], []
            while todo:
                item = todo.pop()
                todo.extend(item.childItems())
                found.append(item)
            return found
        import time
        deadline = time.monotonic() + 5
        while not any(i.property("shownName") == "Steam" for i in items()) and time.monotonic() < deadline:
            QTest.qWait(50)
        self.assertTrue(any(i.property("shownName") == "Steam" for i in items()), errors)
        self.assertFalse([i for i in items() if i.objectName() == "kdeName"])
        self.assertEqual({i.objectName() for i in items() if i.objectName() in ("monetOtherRow", "monetSystemRow")},
                         {"monetOtherRow", "monetSystemRow"})
        self.assertEqual(errors, [])


# KDE's Processes table as Monet's face finds it.
PROCESS_SCENE = """import QtQuick
import QtQuick.Controls
import Qt.labs.qmlmodels
import org.kde.ksysguard.process as Process
import "PROCESSES" as Monet

Window {
    id: scene
    width: 800
    height: 500
    visible: true
    readonly property Item monet: processes
    readonly property Item layout: content
    function setApps(list) { Process.Fake.apps = list }
    Item {
        id: content
        anchors.fill: parent
        Item {
            id: table
            anchors.fill: parent
            property var processModel: processList
            property bool flatList: true
            property var model: processProxy
            property alias view: tree
            property alias delegate: tree.delegate
            TreeView {
                id: tree
                anchors.fill: parent
                model: processProxy
                delegate: DelegateChooser {
                    DelegateChoice { column: 0; Label { objectName: "kdeName"; text: model.display } }
                    DelegateChoice { Label { text: model.display } }
                }
            }
        }
    }
    Monet.Processes {
        id: processes
        active: true
    }
}
"""

if QT:
    class FakeProcesses(QAbstractTableModel):
        """KDE's ProcessDataModel in a list: name, CPU and the process id it keeps out of sight."""

        def __init__(self, rows):
            super().__init__()
            self.rows = rows

        def rowCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(self.rows)

        def columnCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else 3

        def data(self, index, role=Qt.DisplayRole):
            name, pid = self.rows[index.row()]
            if role in (Qt.DisplayRole, ROLES["Value"]):
                return (name, 0, pid)[index.column()]
            return None

        def get_pid_column(self):
            return 2

        pidColumn = Property(int, get_pid_column, constant=True)

    class ProcessesShown(QSortFilterProxyModel):
        def filterAcceptsColumn(self, column, parent):
            return column != 2


@unittest.skipUnless(QT, "requires PySide6")
class ProcessTable(unittest.TestCase):
    """Under each process in KDE's Processes table, the app it belongs to, by the Applications page's name."""

    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_each_process_says_its_app(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, text in STUBS.items():
            (root / "imports" / name).parent.mkdir(parents=True, exist_ok=True)
            (root / "imports" / name).write_text(text, encoding="utf-8")
        faces = root / "sensorfaces"
        for face in ("org.monet.performance", "org.monet.processes"):
            shutil.copytree(FACES / face, faces / face)
        home = root / "home"
        manifest(home / ".local/share/Steam", "3241660", "R.E.P.O.")
        for qml in faces.rglob("*.qml"):
            qml.write_text(qml.read_text(encoding="utf-8").replace("@LIBEXECDIR@", str(ROOT / "linux/libexec")), encoding="utf-8")
        scene = root / "scene.qml"
        scene.write_text(PROCESS_SCENE.replace("PROCESSES", (faces / "org.monet.processes/contents/ui").as_uri()), encoding="utf-8")
        shell = Shell(dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / ".local/share"), XDG_DATA_DIRS=str(root / "none")))
        words = Words()
        model = FakeProcesses([("steam", 2001), ("steamwebhelper", 2002), ("REPO.exe", 3002), ("kwin_wayland", 8001), ("java", 6001)])
        proxy = ProcessesShown()
        proxy.setSourceModel(model)
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(root / "imports"))
        errors = []
        engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
        context = engine.rootContext()
        context.setContextObject(words)
        for name, value in (("processList", model), ("processProxy", proxy), ("shell", shell)):
            context.setContextProperty(name, value)
        engine.load(QUrl.fromLocalFile(str(scene)))
        self.assertTrue(engine.rootObjects(), "\n".join(errors))
        window = engine.rootObjects()[0]
        self.addCleanup(engine.deleteLater)
        self.addCleanup(window.close)
        from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
        QMetaObject.invokeMethod(window, "setApps", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", [
            {"id": "steam.desktop", "appName": "Steam", "iconName": "steam", "menuId": "steam.desktop", "pids": [2001, 2002]},
            {"id": "app3241660", "appName": "app3241660", "iconName": "", "menuId": "", "pids": [3001, 3002]}]))
        processes = window.property("monet")
        attached = QMetaObject.invokeMethod(processes, "attach", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", window.property("layout")))
        self.assertTrue(attached, errors)
        QMetaObject.invokeMethod(processes, "refresh")

        def details():
            todo, found = [window.contentItem()], {}
            while todo:
                item = todo.pop()
                todo.extend(item.childItems())
                if item.property("detail") is not None and item.isVisible():
                    found[item.property("name")] = item.property("detail")
            return found
        # Monet's name for the game comes from monet-quick, as on the Applications page.
        QTest.qWait(50)
        self.assertEqual(details(), {"steam": "", "steamwebhelper": "Steam", "REPO.exe": "app3241660", "kwin_wayland": "",
                                     "java": ""})
        import time
        deadline = time.monotonic() + 10
        QMetaObject.invokeMethod(processes, "lookNow")
        while details().get("REPO.exe") != "R.E.P.O." and time.monotonic() < deadline:
            QMetaObject.invokeMethod(processes, "refresh")
            QTest.qWait(50)
        self.assertEqual(details()["REPO.exe"], "R.E.P.O.", (shell.commands, errors))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
