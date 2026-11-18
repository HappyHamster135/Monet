"""Games installed with a Windows executable, without a store or launcher."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper, windows_shortcut


class LocalGames(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.prefix = self.root / "prefix"
        self.registry = self.root / "local-games.json"

    def file(self, path, data=b"MZ"):
        path = self.prefix / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def games(self, runner="proton"):
        return self.q.local_windows_games([(self.prefix, runner)], self.registry)

    def test_game_shortcuts_and_engine_files_are_found_but_tools_are_not(self):
        direct = self.file("drive_c/Program Files/Aster/Aster.exe")
        self.file("drive_c/Program Files/Aster/Aster_Data/globalgamemanagers")
        self.file("drive_c/Program Files/Aster/unins000.exe")
        shortcut = self.file("drive_c/Program Files/Bird/fly.exe")
        self.file("drive_c/users/alex/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Games/Bird.lnk",
                  windows_shortcut(r"C:\Program Files\Bird\fly.exe"))
        self.file("drive_c/Program Files/Drawing/Paint.exe")
        self.file("drive_c/Games/Camp/Setup.exe")
        found = self.games()
        self.assertEqual({(e["name"], e["path"]) for e in found.values()},
                         {("Aster", direct), ("Bird", shortcut)})
        library = self.q.library(marks={}, steam={}, heroic=[], windows=[], shared=set(), movable=False,
                                 lutris=[], liked=set(), local=found)
        self.assertTrue(all(g["id"] == g["here"] and g["plays"] == "monet" for g in library))
        self.assertEqual([g["name"] for g in library], ["Aster", "Bird"])

    def test_an_unrecognized_executable_can_be_added_played_and_forgotten(self):
        path = self.file("drive_c/Program Files/Mountain Walk/Walk.exe")
        self.assertEqual(self.games(), {})
        self.assertFalse(self.q.edit_local_game("file://another-computer/path.exe", registry=self.registry))
        self.assertTrue(self.q.edit_local_game(path.as_uri(), registry=self.registry))
        key = self.q.local_game_id(path)
        self.assertTrue(self.games()[key]["manual"])
        with patch.object(self.q, "local_windows_games", return_value=self.games()), \
                patch.object(self.q, "program_here", return_value=True) as launch:
            self.assertTrue(self.q.play_local_game(key))
            launch.assert_called_once_with(str(path))
        with patch.object(self.q, "local_windows_games", return_value=self.games("wine")), \
                patch.object(self.q.shutil, "which", return_value="/usr/bin/wine"), \
                patch.object(self.q.subprocess, "Popen") as launch:
            self.assertTrue(self.q.play_local_game(key))
            self.assertEqual(launch.call_args.args[0], ["/usr/bin/wine", str(path)])
            self.assertEqual(launch.call_args.kwargs["env"]["WINEPREFIX"], str(self.prefix))
        self.assertTrue(self.q.edit_local_game(key, remove=True, registry=self.registry))
        self.assertEqual(self.games(), {})
        self.assertTrue(path.is_file())

    def test_windows_shortcut_case_does_not_hide_an_installed_game(self):
        executable = self.file("drive_c/Program Files/Bird/fly.exe")
        self.file("drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/Games/Bird.lnk",
                  windows_shortcut(r"C:\PROGRAM FILES\BIRD\FLY.EXE"))
        self.assertEqual({game["path"] for game in self.games().values()}, {executable})
        applications = self.root / "applications"
        self.assertEqual(self.q.program_menu(self.prefix, applications), 1)
        shortcut = applications / "monet-program-bird.desktop"
        self.assertIn(str(executable).encode().hex(), shortcut.read_text())
