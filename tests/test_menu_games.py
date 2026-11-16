"""The menu's All apps leaves out the entry Steam, Heroic and Lutris each add for a game: games
are in Games. Monet's helper finds those entries by how they start."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


class LauncherGames(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name) / "home/applications"
        self.system = Path(folder.name) / "system/applications"
        self.q = quick_helper()

    def entry(self, folder, name, command, extra=""):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[Desktop Entry]\nType=Application\nName=" + Path(name).stem + "\nExec=" + command + "\n" + extra)

    def test_the_games_launchers_add_and_nothing_else(self):
        self.entry(self.home, "Counter-Strike 2.desktop", "steam steam://rungameid/730", "Categories=Game;\n")
        self.entry(self.home, "Transport Fever 3.desktop", "flatpak run com.valvesoftware.Steam steam://rungameid/2850")
        self.entry(self.home, "Hades.desktop", "xdg-open heroic://launch/legendary/Min")
        self.entry(self.home, "Celeste.desktop", "env LUTRIS_SKIP_INIT=1 lutris lutris:rungameid/12")
        self.entry(self.home, "Old.desktop", "lutris lutris:rungame/old-game")
        # Steam itself, a game's own installer and a native game stay: they aren't in Games.
        self.entry(self.system, "steam.desktop", "/usr/bin/steam %U", "Categories=Network;FileTransfer;Game;\n")
        self.entry(self.system, "org.kde.kpat.desktop", "kpat -qwindowtitle %c", "Categories=Qt;KDE;Game;CardGame;\n")
        self.entry(self.system, "kde/org.kde.dolphin.desktop", "dolphin %u")
        found = self.q.launcher_games([self.home, self.system])
        self.assertEqual(sorted(found), ["Celeste.desktop", "Counter-Strike 2.desktop", "Hades.desktop",
                                         "Old.desktop", "Transport Fever 3.desktop"])

    def test_menu_ids_of_subfolders_and_the_nearer_folder_wins(self):
        self.entry(self.system, "games/Portal 2.desktop", "steam steam://rungameid/620")
        # Someone's own copy of an entry, which no longer starts a game, hides the system's.
        self.entry(self.home, "Celeste.desktop", "celeste-native")
        self.entry(self.system, "Celeste.desktop", "lutris lutris:rungameid/12")
        self.assertEqual(self.q.launcher_games([self.home, self.system]), ["games-Portal 2.desktop"])

    def test_a_missing_folder_or_unreadable_entry_is_skipped(self):
        self.entry(self.home, "Broken.desktop", "steam steam://rungameid/1")
        (self.home / "Broken.desktop").chmod(0)
        self.addCleanup((self.home / "Broken.desktop").chmod, 0o644)
        found = self.q.launcher_games([self.home, Path("/nonexistent/applications")])
        self.assertIn(found, ([], ["Broken.desktop"]))  # root may still read it

    def test_the_helper_prints_them_for_the_menu(self):
        shown = subprocess.run([sys.executable, str(ROOT / "linux/libexec/monet-quick"), "menu-games"],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        result = json.loads(shown.stdout)
        self.assertIs(result["ok"], True)
        self.assertIsInstance(result["ids"], list)

    def test_the_menu_shows_all_apps_without_them(self):
        menu = (ROOT / "linux/share/plasma/plasmoids/org.monet.menu/contents/ui/main.qml").read_text()
        self.assertIn("model: root.appsWithoutGames", menu)
        self.assertIn("readonly property string launcherGamesSource: \"'@LIBEXECDIR@/monet-quick' menu-games\"", menu)
        self.assertIn("helper.connectSource(root.launcherGamesSource)", menu)
        self.assertIn("root.appsWithoutGames.invalidateFilter()", menu)
        self.assertNotIn("root.launch(allApps.model, index)", menu)
        # From All apps, Apps: every app in a library of its own.
        self.assertIn("helper.connectSource(\"'@LIBEXECDIR@/monet-quick' launch %s\")" % "monet-apps.desktop".encode().hex(), menu)


if __name__ == "__main__":
    unittest.main()
