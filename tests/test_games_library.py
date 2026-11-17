"""Games shows every game you own in the launchers you're signed in to, installed or not:
Steam's (its own files for what's installed and downloading, Steam's Web API with a key you
make once for what the account owns, kept for offline), Heroic's (its library caches and its
download queue) and Lutris' (the games its services list), each with Install, Play or its
download, as one library with Windows' games.

    python3 tools/test.py tests.test_games_library
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "linux/share/monet/games/Games.qml"
PAGE = ROOT / "linux/share/monet/games/GamePage.qml"
ANNA, BEN = "76561198000000001", "76561198000000002"
KEY = "0123456789ABCDEF0123456789abcdef"


def manifest(library, appid, name, flags="4", **more):
    folder = library / "steamapps"
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f'\t"appid"\t\t"{appid}"', f'\t"name"\t\t"{name}"', f'\t"StateFlags"\t\t"{flags}"',
             f'\t"installdir"\t\t"{name}"'] + [f'\t"{k}"\t\t"{v}"' for k, v in more.items()]
    (folder / f"appmanifest_{appid}.acf").write_text('"AppState"\n{\n' + "\n".join(lines) + "\n}\n", encoding="utf-8")


def login_users(steam, *accounts):
    """accounts: (steamid, persona, most recent, timestamp)."""
    body = "".join(f'\t"{sid}"\n\t{{\n\t\t"AccountName"\t\t"{name.lower()}"\n\t\t"PersonaName"\t\t"{name}"\n'
                   f'\t\t"MostRecent"\t\t"{int(recent)}"\n\t\t"Timestamp"\t\t"{stamp}"\n\t}}\n'
                   for sid, name, recent, stamp in accounts)
    (steam / "config").mkdir(parents=True, exist_ok=True)
    (steam / "config/loginusers.vdf").write_text('"users"\n{\n' + body + "}\n", encoding="utf-8")


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class Fixture(unittest.TestCase):
    """A home with Steam, Heroic and Lutris in it, and monet-quick looking only there."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        self.q = quick_helper()
        self.steam = self.tmp / "Steam"
        (self.steam / "steamapps").mkdir(parents=True)
        self.heroic = self.tmp / "heroic"
        self.lutris = self.tmp / "lutris"
        for name, value in {"STEAM_ROOTS": (self.steam,), "OWNED": self.tmp / "cache/owned",
                            "STEAM_KEY": self.tmp / "config/monet/steam-key",
                            "STEAM_KEY_HINT_OFF": self.tmp / "config/monet/steam-key-hint-off",
                            "HEROIC_ROOTS": (self.heroic,), "LUTRIS_ROOTS": (self.lutris,),
                            "WINDOWS_GAMES": (self.tmp / "games.json",), "SHARED": self.tmp / "Windows games",
                            "OWN_STEAM": self.steam, "PROTONDB": self.tmp / "cache/protondb.json",
                            "FAVORITES": self.tmp / "config/monet/favorite-games.json"}.items():
            patcher = mock.patch.object(self.q, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in {"anticheat": lambda fetch=False: {"1172470": "windows"}, "heroic_running": lambda: False}.items():
            patcher = mock.patch.object(self.q, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def owned_list(self, steamid, games, state="ok", fetched=None):
        put(self.q.OWNED / f"steam-{steamid}.json", {"state": state, "fetched": fetched or int(time.time()),
                                                     "tried": fetched or int(time.time()), "games": games})


class SteamAccounts(Fixture):
    def test_the_account_signed_in_last(self):
        login_users(self.steam, (ANNA, "Anna", False, 1700000000), (BEN, "Ben", True, 1600000000))
        self.assertEqual([a["id"] for a in self.q.steam_accounts(self.steam)], [BEN, ANNA])
        self.assertEqual(self.q.steam_account()[1]["name"], "Ben")
        # Without MostRecent anywhere, the latest sign-in.
        login_users(self.steam, (ANNA, "Anna", False, 1700000000), (BEN, "Ben", False, 1600000000))
        self.assertEqual(self.q.steam_account()[1]["id"], ANNA)

    def test_flathubs_steam_and_valves_own(self):
        flatpak = self.tmp / "flatpak/Steam"
        login_users(self.steam, (ANNA, "Anna", True, 1600000000))
        login_users(flatpak, (BEN, "Ben", True, 1700000000))
        steam, account = self.q.steam_account((self.steam, flatpak, self.tmp / "missing"))
        self.assertEqual((steam, account["id"]), (flatpak, BEN))
        # ~/.steam/steam is often a link to the same Steam: looked at once.
        (self.tmp / "link").symlink_to(self.steam)
        self.assertEqual(self.q.steam_account((self.steam, self.tmp / "link"))[1]["id"], ANNA)

    def test_missing_or_broken_files_mean_nobody(self):
        self.assertEqual(self.q.steam_account(), (None, None))
        (self.steam / "config").mkdir()
        (self.steam / "config/loginusers.vdf").write_bytes(b"\x00\xff{{{ not vdf")
        self.assertEqual(self.q.steam_accounts(self.steam), [])
        (self.steam / "config/loginusers.vdf").write_text('"users" { "not an id" { "MostRecent" "1" } "76561198000000003" "x" }')
        self.assertEqual(self.q.steam_accounts(self.steam), [])
        self.assertFalse(self.q.steam_owned_refresh()["steam"])


class SteamKey(Fixture):
    def test_kept_where_only_you_can_read_it(self):
        self.assertEqual(self.q.steam_key(), "")
        self.assertFalse(self.q.save_steam_key("not a key"))
        self.assertFalse(self.q.save_steam_key(KEY + "00"))
        self.assertFalse(self.q.STEAM_KEY.exists())
        self.assertTrue(self.q.save_steam_key(f"  {KEY}\n"))
        self.assertEqual(self.q.steam_key(), KEY.upper())
        self.assertEqual(stat.S_IMODE(self.q.STEAM_KEY.stat().st_mode), 0o600)
        self.q.STEAM_KEY.write_text("junk")
        self.assertEqual(self.q.steam_key(), "")

    def test_forgetting_it_forgets_the_lists_it_fetched(self):
        self.q.save_steam_key(KEY)
        self.owned_list(BEN, [{"appid": "620", "name": "Portal 2"}])
        self.assertTrue(self.q.save_steam_key(""))
        self.assertFalse(self.q.STEAM_KEY.exists())
        self.assertEqual(list(self.q.OWNED.glob("steam-*.json")), [])

    def test_the_key_comes_on_stdin_never_the_command_line(self):
        login_users(self.steam, (BEN, "Ben", True, 1))
        asked = []
        out = io.StringIO()
        with mock.patch.object(self.q, "steam_owned_fetch", lambda key, steamid: asked.append((key, steamid)) or ("ok", [])), \
                mock.patch.object(sys, "stdin", io.StringIO(KEY + "\n")), contextlib.redirect_stdout(out):
            self.q.main(["steam-key"])
        said = json.loads(out.getvalue())
        self.assertEqual((said["saved"], said["key"], said["state"], said["name"]), (True, True, "ok", "Ben"))
        self.assertEqual(asked, [(KEY.upper(), BEN)])          # asked straight away
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('saved = save_steam_key(sys.stdin.read(4096))', quick)
        games = GAMES.read_text(encoding="utf-8")
        self.assertIn('feed(["helper", "steam-key"], key, out => {', games)
        host = (ROOT / "linux/libexec/monet-games").read_text(encoding="utf-8")
        self.assertIn("process.write(str(text).encode(\"utf-8\"))\n            process.closeWriteChannel()", host)
        # Something else on stdin: not kept, and Steam isn't asked.
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("hello")), contextlib.redirect_stdout(out):
            self.q.main(["steam-key"])
        self.assertFalse(json.loads(out.getvalue())["saved"])
        self.assertEqual(len(asked), 1)


class OwnedOnSteam(Fixture):
    def test_what_steam_answers(self):
        answer = self.q.steam_owned_answer
        self.assertEqual(answer({"response": {"game_count": 3, "games": [
            {"appid": 620, "name": "Portal 2", "playtime_forever": 125, "rtime_last_played": 1700000000},
            {"appid": 1493710, "name": "Proton Experimental"}, {"appid": "x", "name": "Odd"}, {"appid": 10, "name": " "},
            {"appid": 1091500, "name": "Cyberpunk   2077", "playtime_forever": "lots"}]}}),
            ("ok", [{"appid": "620", "name": "Portal 2", "minutes": 125, "last": 1700000000},
                    {"appid": "1091500", "name": "Cyberpunk 2077", "minutes": 0, "last": 0}]))
        # An account whose games Steam keeps to itself answers with nothing at all.
        self.assertEqual(answer({"response": {}}), ("private", []))
        self.assertEqual(answer({"response": {"game_count": 0}}), ("ok", []))
        self.assertEqual(answer({"error": "?"}), ("offline", None))
        self.assertEqual(answer([]), ("offline", None))

    def test_asked_at_most_every_quarter_hour_and_kept_for_offline(self):
        login_users(self.steam, (ANNA, "Anna", False, 1700000000), (BEN, "Ben", True, 1600000000))
        asked = []
        answers = iter([("ok", [{"appid": "620", "name": "Portal 2", "minutes": 5, "last": 0}]),
                        ("offline", None), ("key", None),
                        ("ok", [{"appid": "620", "name": "Portal 2", "minutes": 5, "last": 0}]), ("private", [])])

        def fetch(key, steamid):
            asked.append((key, steamid))
            return next(answers)

        # No key: nothing asked, and Games offers to add one.
        said = self.q.steam_owned_refresh(fetch=fetch, now=1000)
        self.assertEqual((said["steam"], said["key"], said["name"], said["hint"], asked), (True, False, "Ben", True, []))
        self.q.save_steam_key(KEY)
        said = self.q.steam_owned_refresh(fetch=fetch, now=1000)
        self.assertEqual((said["state"], said["count"], said["changed"], said["fetched"]), ("ok", 1, True, 1000))
        self.assertEqual(asked, [(KEY.upper(), BEN)])          # the account signed in last
        kept = self.q.OWNED / f"steam-{BEN}.json"
        self.assertEqual(stat.S_IMODE(kept.stat().st_mode), 0o600)
        self.assertNotIn(KEY.upper(), kept.read_text())
        # Within a quarter of an hour: not again, unless asked to.
        self.assertFalse(self.q.steam_owned_refresh(fetch=fetch, now=1000 + 60)["changed"])
        self.assertEqual(len(asked), 1)
        # Offline: the list is kept, and said so.
        said = self.q.steam_owned_refresh(fetch=fetch, now=1000 + 16 * 60)
        self.assertEqual((said["state"], said["count"], said["fetched"]), ("offline", 1, 1000))
        self.assertEqual(self.q.steam_owned()["620"]["name"], "Portal 2")
        # A key Steam turns away: kept list, and Games says what to do.
        said = self.q.steam_owned_refresh(force=True, fetch=fetch, now=1000 + 17 * 60)
        self.assertEqual((said["state"], said["count"]), ("key", 1))
        said = self.q.steam_owned_refresh(force=True, fetch=fetch, now=1000 + 18 * 60)
        self.assertEqual((said["state"], said["changed"]), ("ok", True))
        # Another account's key with this one's games private: none kept for it.
        said = self.q.steam_owned_refresh(force=True, fetch=fetch, now=1000 + 19 * 60)
        self.assertEqual((said["state"], said["count"]), ("private", 0))
        self.assertEqual(self.q.steam_owned(), {})

    def test_two_accounts_each_their_own_list(self):
        login_users(self.steam, (ANNA, "Anna", True, 1700000000), (BEN, "Ben", False, 1600000000))
        self.owned_list(ANNA, [{"appid": "620", "name": "Portal 2"}])
        self.owned_list(BEN, [{"appid": "570", "name": "Dota 2"}])
        self.assertEqual(list(self.q.steam_owned()), ["620"])
        login_users(self.steam, (ANNA, "Anna", False, 1700000000), (BEN, "Ben", True, 1800000000))
        self.assertEqual(list(self.q.steam_owned()), ["570"])

    def test_play_time_from_the_accounts_own_files_too(self):
        login_users(self.steam, (BEN, "Ben", True, 1))
        self.owned_list(BEN, [{"appid": "620", "name": "Portal 2", "minutes": 10, "last": 5}, {"appid": "7", "name": "Bad", "minutes": "x"}])
        config = self.steam / "userdata/41734274/config/localconfig.vdf"
        config.parent.mkdir(parents=True)
        config.write_text('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" {'
                          ' "620" { "LastPlayed" "1700000000" "Playtime" "125" } } } } } }')
        self.assertEqual(self.q.steam_owned(), {"620": {"name": "Portal 2", "minutes": 125, "last": 1700000000},
                                                "7": {"name": "Bad", "minutes": 0, "last": 0}})

    def test_a_broken_list_is_no_list(self):
        login_users(self.steam, (BEN, "Ben", True, 1))
        (self.q.OWNED).mkdir(parents=True)
        (self.q.OWNED / f"steam-{BEN}.json").write_text("{not json")
        self.assertEqual(self.q.steam_owned(), {})
        put(self.q.OWNED / f"steam-{BEN}.json", {"games": [{"appid": "620"}, "x", {"appid": "1;rm", "name": "x"}]})
        self.assertEqual(self.q.steam_owned(), {})

    def test_steam_unreachable_or_saying_no(self):
        import urllib.error
        fetch = self.q.steam_owned_fetch
        errors = io.StringIO()

        def failing(error):
            def urlopen(request, timeout):
                # The key goes to Steam's own API, over https, and nowhere else.
                self.assertTrue(request.full_url.startswith("https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key="))
                self.assertIn("&steamid=" + BEN, request.full_url)
                self.assertIn("include_played_free_games=true", request.full_url)
                raise error
            return urlopen

        with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(errors):
            for error, said in ((urllib.error.URLError("no network"), "offline"), (TimeoutError(), "offline"),
                                (urllib.error.HTTPError("u", 403, "Forbidden", {}, None), "key"),
                                (urllib.error.HTTPError("u", 401, "Unauthorized", {}, None), "key"),
                                (urllib.error.HTTPError("u", 429, "Too many", {}, None), "offline"),
                                (urllib.error.HTTPError("u", 500, "Oops", {}, None), "offline")):
                with mock.patch("urllib.request.urlopen", failing(error)):
                    self.assertEqual(fetch(KEY, BEN), (said, None))

            class Answer(io.BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            with mock.patch("urllib.request.urlopen", lambda request, timeout: Answer(b"<html>busy</html>")):
                self.assertEqual(fetch(KEY, BEN), ("offline", None))
            with mock.patch("urllib.request.urlopen", lambda request, timeout: Answer(
                    json.dumps({"response": {"game_count": 1, "games": [{"appid": 620, "name": "Portal 2"}]}}).encode())):
                self.assertEqual(fetch(KEY, BEN)[1][0]["name"], "Portal 2")
        self.assertEqual(errors.getvalue(), "")                 # never printed, the key least of all


class SteamDownloads(Fixture):
    def test_what_steam_is_doing_with_each_game(self):
        state = self.q.steam_state
        self.assertEqual(state({"StateFlags": "4"}), "ready")
        self.assertEqual(state({"StateFlags": "6"}), "update")                  # an update waits
        self.assertEqual(state({"StateFlags": "1026", "BytesDownloaded": "45", "BytesToDownload": "100"}), "downloading")
        self.assertEqual(state({"StateFlags": str(2 | 1048576)}), "downloading")
        self.assertEqual(state({"StateFlags": "1538"}), "paused")                # 2 | 512 | 1024
        self.assertEqual(state({"StateFlags": "2"}), "waiting")                  # wants a download, not started
        self.assertEqual(state({"StateFlags": "junk"}), "ready")
        self.assertEqual(state({}), "ready")


class TheWholeLibrary(Fixture):
    """Everything on a PC at once, from its own files: no network asked."""

    def setUp(self):
        super().setUp()
        q = self.q
        login_users(self.steam, (ANNA, "Anna", False, 1700000000), (BEN, "Ben", True, 1600000000))
        manifest(self.steam, 620, "Portal 2", SizeOnDisk="12000000000")
        manifest(self.steam, 570, "Dota 2", "1026", BytesDownloaded="45", BytesToDownload="100")
        manifest(self.steam, 730, "Counter-Strike 2", "6")
        manifest(self.steam, 440, "Team Fortress 2", "1538", BytesDownloaded="10", BytesToDownload="100")
        manifest(self.steam, 10, "Counter-Strike", "2")
        manifest(self.steam, 1493710, "Proton Experimental")
        (self.steam / "steamapps/appmanifest_99.acf").write_bytes(b"\xff\xfe\x00 broken")
        art = self.steam / "appcache/librarycache"
        (art / "1091500/abc").mkdir(parents=True)
        (art / "1091500/abc/library_600x900.jpg").write_bytes(b"jpg")
        (art / "620_library_600x900.jpg").write_bytes(b"jpg")
        self.owned_list(BEN, [{"appid": "620", "name": "Portal 2", "minutes": 300, "last": 1700000000},
                              {"appid": "1091500", "name": "Cyberpunk 2077", "minutes": 60, "last": 1650000000},
                              {"appid": "1172470", "name": "Apex Legends"},
                              {"appid": "359550", "name": "Tom Clancy's Rainbow Six Siege"},
                              {"appid": "1493710", "name": "Proton Experimental"}])
        self.owned_list(ANNA, [{"appid": "12345", "name": "Anna's Game"}])
        put(self.tmp / "games.json", {"v": 1, "games": [{"id": "steam:359550", "name": "Rainbow Six Siege"},
                                                         {"id": "riot:valorant", "name": "VALORANT"},
                                                         {"id": "epic:Kinglet", "name": "Kinglet"}]})
        put(self.heroic / "legendaryConfig/legendary/installed.json", {
            "Sugar": {"app_name": "Sugar", "title": "Rocket League", "install_path": "/games/Sugar", "install_size": 1000}})
        put(self.heroic / "store_cache/legendary_library.json", {"library": [
            {"app_name": "Sugar", "title": "Rocket League", "art_cover": "https://cdn.epic/sugar.jpg"},
            {"app_name": "Kinglet", "title": "Kinglet", "art_cover": "https://cdn.epic/kinglet.jpg"},
            {"app_name": "Quail", "title": "Quail", "art_square": "https://cdn.epic/quail-tall.jpg", "namespace": "q"},
            {"app_name": "Fish", "title": "Fish", "is_dlc": True},
            {"app_name": "bad name;rm", "title": "Sneaky"}]})
        put(self.heroic / "store_cache/legendary_install_info.json", {"Quail": {"manifest": {"disk_size": 5000000000}},
                                                                        "__timestamp": {"Quail": "2026-01-01"}})
        put(self.heroic / "store_cache/gog_library.json", {"games": [{"app_name": "1207658924", "title": "Unreal Tournament 2004"}]})
        put(self.heroic / "store_cache/gog_install_info.json", {"1207658924_windows": {"manifest": {"disk_size": 2000}}})
        put(self.heroic / "store/download-manager.json", {"queue": [
            {"params": {"appName": "1207658924", "runner": "gog", "size": "2 GiB"}, "type": "install", "startTime": 5}],
            "finished": []})
        self.lutris.mkdir()
        with sqlite3.connect(self.lutris / "pga.db") as db:
            db.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, slug TEXT, runner TEXT, installed INTEGER,"
                       " service TEXT, service_id TEXT, lastplayed INTEGER, playtime REAL)")
            db.execute("CREATE TABLE service_games (id INTEGER PRIMARY KEY, service TEXT, appid TEXT, name TEXT, slug TEXT,"
                       " icon TEXT, logo TEXT, url TEXT, details TEXT, lutris_slug TEXT)")
            db.executemany("INSERT INTO games (id, name, slug, runner, installed, service, service_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           [(1, "Celeste", "celeste", "linux", 1, "humblebundle", "celeste")])
            db.executemany("INSERT INTO service_games (service, appid, name) VALUES (?, ?, ?)",
                           [("humblebundle", "celeste", "Celeste"), ("humblebundle", "machinarium", "Machinarium"),
                            ("steam", "620", "Portal 2"), ("lutris", "x", "Lutris website game"),
                            ("egs", "Quail", "Quail"), ("itchio", "../../etc", "Sneaky")])
        db.close()

    def library(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("the library never waits on the network")):
            return {g["id"]: g for g in self.q.library(lasts={}, minutes={}, now=1700000100)}

    def test_every_game_you_own_once_marked_installed_or_not(self):
        found = self.library()
        g = found["steam:620"]
        self.assertEqual((g["state"], g["here"], g["install"], g["size"], g["minutes"]), ("ready", "steam:620", "", 12000000000, 300))
        self.assertTrue(g["tall"].endswith("/620_library_600x900.jpg"))
        self.assertEqual((found["steam:570"]["state"], found["steam:570"]["progress"]), ("downloading", 45))
        self.assertEqual(found["steam:730"]["state"], "update")
        self.assertEqual((found["steam:440"]["state"], found["steam:440"]["progress"]), ("paused", 10))
        self.assertEqual(found["steam:10"]["state"], "waiting")
        # Owned, not installed: Install hands it to Steam's own install dialog; plays here once it's there.
        cyberpunk = found["steam:1091500"]
        self.assertEqual((cyberpunk["state"], cyberpunk["install"], cyberpunk["plays"], cyberpunk["here"], cyberpunk["launcher"]),
                         ("owned", "steam:1091500", "monet", "", "steam"))
        self.assertEqual((cyberpunk["minutes"], cyberpunk["last"]), (60, 1650000000))
        self.assertTrue(cyberpunk["tall"].endswith("/1091500/abc/library_600x900.jpg"))
        # Its anti-cheat wants Windows: nothing to install here, and Play asks to go to Windows.
        apex = found["steam:1172470"]
        self.assertEqual((apex["state"], apex["install"], apex["plays"], apex["windows"], apex["move"]), ("owned", "", "windows", "", False))
        self.assertTrue(apex["tall"].startswith("https://"))
        # Owned on Steam and installed in Windows: one game, ready there, installable here too.
        siege = found["steam:359550"]
        self.assertEqual((siege["state"], siege["windows"], siege["plays"], siege["install"]),
                         ("ready", "steam:359550", "windows", "steam:359550"))
        self.assertEqual(sum(1 for key in found if key.endswith(":359550")), 1)
        self.assertNotIn("steam:1493710", found)                  # Proton: a tool, not a game
        self.assertNotIn("steam:12345", found)                    # Anna's, not the account signed in now
        self.assertNotIn("steam:99", found)
        # Heroic: installed, owned (with its size once installed when Heroic said), and downloading.
        self.assertEqual((found["epic:Sugar"]["state"], found["epic:Sugar"]["here"]), ("ready", "heroic:legendary:Sugar"))
        quail = found["epic:Quail"]
        self.assertEqual((quail["state"], quail["install"], quail["size"], quail["tall"], quail["launcher"]),
                         ("owned", "heroic:legendary:Quail", 5000000000, "https://cdn.epic/quail-tall.jpg", "heroic"))
        unreal = found["gog:1207658924"]
        self.assertEqual((unreal["state"], unreal["install"], unreal["size"]), ("waiting", "heroic:gog:1207658924", 2000))
        self.assertNotIn("epic:Fish", found)                      # a DLC
        self.assertFalse(any("Sneaky" == g["name"] for g in found.values()))
        # Owned in Heroic, installed in Windows: one game, ready there, with Heroic's cover.
        kinglet = found["epic:Kinglet"]
        self.assertEqual((kinglet["state"], kinglet["windows"], kinglet["install"], kinglet["art"]),
                         ("ready", "epic:Kinglet", "heroic:legendary:Kinglet", "https://cdn.epic/kinglet.jpg"))
        # Lutris: what its services list but it hasn't installed; not Steam's, not its website's.
        machinarium = found["lutris:humblebundle.machinarium"]
        self.assertEqual((machinarium["state"], machinarium["install"], machinarium["store"]),
                         ("owned", "lutris:humblebundle:machinarium", "lutris"))
        self.assertEqual(found["lutris:1"]["state"], "ready")
        self.assertNotIn("lutris:humblebundle.celeste", found)
        self.assertFalse(any(g["name"] == "Lutris website game" for g in found.values()))
        self.assertEqual(found["riot:valorant"]["state"], "ready")
        for g in found.values():
            self.assertTrue(g["install"] == "" or self.q.INSTALLABLE.fullmatch(g["install"]), g)
            self.assertTrue(self.q.GAME_ID.fullmatch(g["id"]), g["id"])

    def test_installed_first_then_the_rest(self):
        order = [g["id"] for g in self.q.library(lasts={}, minutes={}, now=1700000100)]
        first_owned = min(i for i, key in enumerate(order) if key in ("steam:1091500", "steam:1172470", "epic:Quail"))
        self.assertTrue(all(order.index(key) < first_owned for key in ("steam:620", "steam:570", "epic:Sugar", "riot:valorant")))
        self.assertEqual(order[0], "steam:620")                    # played lately

    def test_offline_and_without_a_key_from_whats_kept(self):
        self.assertEqual(self.q.steam_key(), "")                  # no key; the list kept from before still counts
        found = self.library()
        self.assertEqual(found["steam:1091500"]["state"], "owned")
        # And without that list: what's installed, as before.
        for kept in self.q.OWNED.glob("steam-*.json"):
            kept.unlink()
        found = self.library()
        self.assertNotIn("steam:1091500", found)
        self.assertEqual(found["steam:620"]["state"], "ready")

    def test_heroic_downloading_while_its_open(self):
        found = self.q.heroic_downloads(running=True)
        self.assertEqual(found, {("gog", "1207658924"): ("downloading", 2 * 1024 ** 3)})
        put(self.heroic / "store/download-manager.json", {"queue": [
            {"params": {"appName": "A", "runner": "legendary"}, "startTime": 1, "status": "paused"},
            {"params": {"appName": "B", "runner": "nile"}, "startTime": 0},
            {"params": {"appName": "x;y", "runner": "gog"}}, {"params": {"appName": "C", "runner": "wine"}}, "junk"]})
        self.assertEqual(self.q.heroic_downloads(running=True), {("legendary", "A"): ("paused", 0), ("nile", "B"): ("waiting", 0)})
        (self.heroic / "store/download-manager.json").write_text("{broken")
        self.assertEqual(self.q.heroic_downloads(running=True), {})

    def test_lutris_without_its_database(self):
        (self.lutris / "pga.db").write_bytes(b"not a database")
        self.assertEqual(self.q.lutris_owned(), [])
        self.assertEqual(self.q.lutris_owned((self.tmp / "missing",)), [])

    def test_the_library_command(self):
        out = io.StringIO()
        with mock.patch.object(self.q.subprocess, "Popen", lambda *a, **k: None), contextlib.redirect_stdout(out), \
                mock.patch.object(self.q, "RUNTIME", self.tmp), mock.patch.object(self.q, "PROTONDB_LOCK", self.tmp / "protondb.lock"), \
                mock.patch.object(self.q, "HEROIC_ROOTS", (self.heroic,)), mock.patch.object(self.q, "LUTRIS_ROOTS", (self.lutris,)):
            self.q.main(["library"])
        found = {g["id"]: g for g in json.loads(out.getvalue())}
        self.assertEqual(found["steam:1091500"]["state"], "owned")
        self.assertEqual(found["epic:Quail"]["install"], "heroic:legendary:Quail")


class Installing(Fixture):
    def test_each_launchers_own_installer(self):
        started = []
        with mock.patch.object(self.q.shutil, "which", lambda name: name in ("steam", "xdg-open")), \
                mock.patch.object(self.q.subprocess, "Popen", lambda command, **kw: started.append(command)):
            for game in ("steam:1091500", "heroic:legendary:Quail", "heroic:gog:1207658924", "lutris:humblebundle:machinarium"):
                self.assertTrue(self.q.INSTALLABLE.fullmatch(game), game)
                self.q.main(["install", game])
            self.q.main(["downloads", "steam"])
        self.assertEqual(started, [["steam", "steam://install/1091500"],
                                   ["xdg-open", "heroic://launch?appName=Quail&runner=legendary"],
                                   ["xdg-open", "heroic://launch?appName=1207658924&runner=gog"],
                                   ["xdg-open", "lutris:install/humblebundle:machinarium"],
                                   ["steam", "steam://open/downloads"]])
        started.clear()
        with mock.patch.object(self.q.shutil, "which", lambda name: name in ("heroic", "lutris")), \
                mock.patch.object(self.q.subprocess, "Popen", lambda command, **kw: started.append(command)):
            self.q.main(["install", "heroic:nile:amzn1.adg.product.abc-123"])
            self.q.main(["install", "lutris:egs:Quail"])
            self.q.main(["downloads", "heroic"])
        # With its window: Heroic asks whether to install it, then shows its install dialog.
        self.assertEqual(started, [["heroic", "heroic://launch?appName=amzn1.adg.product.abc-123&runner=nile"],
                                   ["lutris", "lutris:install/egs:Quail"], ["heroic"]])
        started.clear()
        with mock.patch.object(self.q.shutil, "which", lambda name: True), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(self.q.subprocess, "Popen", lambda command, **kw: started.append(command)):
            for game in ("steam:12a", "steam:1;rm -rf", "heroic:sideload:x", "heroic:legendary:a&b=c", "heroic:gog:..",
                         "lutris:steam:620", "lutris:egs:a/b", "lutris:xdg:x", "epic:Quail", "lutris:1"):
                self.assertIsNone(self.q.INSTALLABLE.fullmatch(game), game)
                self.q.main(["install", game])
            self.q.main(["downloads", "elsewhere"])
        self.assertEqual(started, [])


class TheWindow(unittest.TestCase):
    """What Games shows of it."""

    def test_all_installed_or_not_installed(self):
        games = GAMES.read_text(encoding="utf-8")
        self.assertIn('model: [["all", i18n("All")], ["installed", i18n("Installed")], ["notinstalled", i18n("Not installed")]]', games)
        self.assertIn('return which === "all" || (which === "notinstalled") === notInstalled(g)', games)
        # Recent: downloading first, then installed, then the rest, each by when it was played.
        self.assertIn("const rank = g => busy(g) ? 0 : notInstalled(g) ? 2 : 1", games)
        self.assertIn("games.filter(g => g.last > 0 && !notInstalled(g))", games)
        for words in ('i18n("%1 · Not installed", storeName(game.store))', 'i18n("%1 · Download paused", storeName(game.store))',
                      'i18n("%1 · Waiting to download", storeName(game.store))',
                      'i18n("%1 · Downloading, %2%", storeName(game.store), game.progress)'):
            self.assertIn(words, games)
        # Keys reach the choices, with a ring.
        block = games[games.index("id: showChoice"):games.index("id: showLabel")]
        for line in ("activeFocusOnTab: true", "Keys.onReturnPressed: root.show = modelData[0]", "border.color: look.lily"):
            self.assertIn(line, block)

    def test_install_play_or_the_download(self):
        games = GAMES.read_text(encoding="utf-8")
        self.assertIn("if (notInstalled(game) && game.install)\n            install(game)", games)
        self.assertIn('run(["helper", "install", game.install])', games)
        self.assertIn('run(["helper", "downloads", game.launcher])', games)
        self.assertIn('items.push(["install", i18n("Install in Monet")])', games)
        self.assertIn('path: tile.toInstall ? "M12 4v11M7 10.5l5 5 5-5M5 19.5h14" : "M8 5.5L18 12 8 18.5z"', games)
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn('text: page.toInstall ? i18n("Install with %1", page.app.launcherName(page.game))', page)
        self.assertIn('i18n("Size once installed")', page)

    def test_downloads_looked_at_only_while_on_screen(self):
        games = GAMES.read_text(encoding="utf-8")
        self.assertIn('readonly property bool watching: visible && visibility !== Window.Minimized\n'
                      '        && (typeof windowActivity === "undefined" || windowActivity.active)', games)
        self.assertIn("running: root.watching && root.games.some(g => typeof g.progress === \"number\" || root.busy(g))", games)
        host = (ROOT / "linux/libexec/monet-games").read_text(encoding="utf-8")
        self.assertIn('engine.rootContext().setContextProperty("windowActivity", activity)', host)
        self.assertIn("activity.watch(engine.rootObjects()[0])", host)
        # Steam's list: asked in the background, never waited on.
        self.assertIn('run(["helper", "owned-refresh"], out => {', games)

    def test_the_steam_key_once(self):
        games = GAMES.read_text(encoding="utf-8")
        self.assertIn('onClicked: Qt.openUrlExternally("https://steamcommunity.com/dev/apikey")', games)
        self.assertIn("echoMode: TextInput.PasswordEchoOnEdit", games)
        self.assertIn('root.run(["helper", "steam-key-hint-off"])', games)
        self.assertNotIn('run(["helper", "steam-key", ', games)  # never on the command line


try:
    from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


def game(ident, name, state, **more):
    return dict({"id": ident, "name": name, "store": ident.split(":")[0], "plays": "monet", "why": "", "here": "",
                 "windows": "", "shared": False, "move": False, "progress": None, "locate": "", "art": "", "last": 0,
                 "minutes": 0, "size": 0, "favorite": False, "tall": "", "hero": "", "state": state, "install": "",
                 "launcher": "steam"}, **more)


LIBRARY = [game("steam:620", "Portal 2", "ready", here="steam:620", last=1700000000, minutes=90),
           game("steam:570", "Dota 2", "downloading", here="steam:570", progress=45),
           game("steam:1091500", "Cyberpunk 2077", "owned", install="steam:1091500"),
           game("epic:Quail", "Quail", "owned", install="heroic:legendary:Quail", launcher="heroic", size=5000000000)]


if QT:
    class FakeHelper(QObject):
        done = Signal(int, str, int, str)
        wanted = Signal(str)

        def __init__(self, owned):
            super().__init__()
            self.ticket, self.calls, self.fed, self.owned = 0, [], [], owned

        @Slot("QVariantList", result=int)
        def run(self, command):
            return self.feed(command, None)

        @Slot("QVariantList", str, result=int)
        def feed(self, command, text):
            self.ticket += 1
            ticket = self.ticket
            self.calls.append(list(command))
            if text is not None:
                self.fed.append(text)
            verb = command[1] if len(command) > 1 else ""
            out = {"library": LIBRARY, "owned-refresh": self.owned, "shared": {},
                   "steam-key": dict(self.owned, key=True, state="ok", count=4, saved=True)}.get(verb, {})
            QTimer.singleShot(1, lambda: self.done.emit(ticket, json.dumps(out), 0, ""))
            return ticket


@unittest.skipUnless(QT, "Qt/Kirigami runtime")
class TheWindowItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setOrganizationName("monet-games-tests")
        cls.app.setOrganizationDomain("tests.invalid")
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("library_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    def open(self, owned):
        self.engine, self.errors = QQmlApplicationEngine(), []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        self.helper, self.words = FakeHelper(owned), self.games.Words()
        context = self.engine.rootContext()
        context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "blurBehind": False,
                            "art": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(GAMES)))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.addCleanup(self.close)
        self.window.setWidth(1140)
        self.window.setHeight(760)
        deadline = time.monotonic() + 3
        while not self.window.property("loaded") and time.monotonic() < deadline:
            QTest.qWait(10)
        QTest.qWait(100)

    def close(self):
        self.window.close()
        self.engine.deleteLater()
        QTest.qWait(5)

    def items(self):
        todo, found = [self.window.contentItem()], []
        while todo:
            item = todo.pop()
            todo.extend(item.childItems())
            found.append(item)
        return found

    def visible_texts(self):
        return [i.property("text") for i in self.items() if i.isVisible() and isinstance(i.property("text"), str)]

    def shown(self):
        return [g["id"] for g in self.window.property("shown").toVariant()]

    def test_all_installed_and_not_installed(self):
        self.open({"steam": True, "name": "Ben", "key": True, "hint": True, "state": "ok", "count": 2, "changed": False})
        self.assertEqual(self.shown(), ["steam:570", "steam:620", "steam:1091500", "epic:Quail"])
        texts = self.visible_texts()
        for words in ("All", "Installed", "Not installed", "Steam · Not installed", "Epic · Not installed, 5.0 GB",
                      "Steam · Downloading, 45%", "Steam key"):
            self.assertIn(words, texts)
        self.assertNotIn("Add Steam key", texts)
        self.window.setProperty("show", "notinstalled")
        QTest.qWait(50)
        self.assertEqual(self.shown(), ["steam:1091500", "epic:Quail"])
        self.window.setProperty("show", "installed")
        QTest.qWait(50)
        self.assertEqual(self.shown(), ["steam:570", "steam:620"])
        # Continue playing has only what's installed.
        self.assertEqual([g["id"] for g in self.window.property("lately").toVariant()], ["steam:620"])
        self.assertEqual(self.errors, [])

    def test_install_and_the_download_from_the_covers(self):
        self.open({"steam": True, "name": "Ben", "key": True, "hint": True, "state": "ok", "count": 2, "changed": False})
        from PySide6.QtCore import Q_ARG, QMetaObject, Qt
        for ident in ("steam:1091500", "epic:Quail", "steam:570", "steam:620"):
            chosen = next(g for g in LIBRARY if g["id"] == ident)
            QMetaObject.invokeMethod(self.window, "play", Qt.DirectConnection, Q_ARG("QVariant", chosen))
        QTest.qWait(20)
        self.assertEqual([c for c in self.helper.calls if c[1:2] in (["install"], ["downloads"], ["play"])],
                         [["helper", "install", "steam:1091500"], ["helper", "install", "heroic:legendary:Quail"],
                          ["helper", "downloads", "steam"], ["helper", "play", "steam:620"]])
        # A game's page: Install with its launcher.
        self.window.setProperty("pageId", "epic:Quail")
        QTest.qWait(50)
        self.assertIn("Install with Heroic", self.visible_texts())
        self.assertIn("Size once installed", self.visible_texts())

    def test_add_game_registers_the_chosen_local_file(self):
        self.open({"steam": False, "hint": False})
        self.assertIn("Add game", self.visible_texts())
        from PySide6.QtCore import Q_ARG, QMetaObject, Qt
        chosen = "file:///home/test/Outer%20World.exe"
        self.assertTrue(QMetaObject.invokeMethod(self.window, "addLocalGame", Qt.DirectConnection,
                                                 Q_ARG("QVariant", chosen)))
        QTest.qWait(100)
        self.assertIn(["helper", "add-local-game", chosen], self.helper.calls)
        self.assertEqual(self.window.property("show"), "installed")
        self.assertEqual(self.errors, [])

    def test_the_steam_key_goes_on_stdin(self):
        self.open({"steam": True, "name": "Ben", "key": False, "hint": True, "state": "", "count": 0, "changed": False})
        self.assertIn("Add Steam key", self.visible_texts())
        self.window.setProperty("keyOpen", True)
        QTest.qWait(450)
        self.assertIn("Open Steam's key page and sign in as Ben. Type monet as the domain name, agree, and approve it in the "
                      "Steam app on your phone. Then copy the key and paste it here.", self.visible_texts())
        from PySide6.QtCore import Q_ARG, QMetaObject, Qt
        QMetaObject.invokeMethod(self.window, "saveKey", Qt.DirectConnection, Q_ARG("QVariant", "nope"))
        self.assertIn("That doesn't look like a Steam key", self.window.property("keyProblem"))
        self.assertEqual(self.helper.fed, [])
        QMetaObject.invokeMethod(self.window, "saveKey", Qt.DirectConnection, Q_ARG("QVariant", KEY))
        deadline = time.monotonic() + 2
        while self.window.property("keyOpen") and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.window.property("keyOpen"))
        self.assertEqual(self.helper.fed, [KEY])
        self.assertIn(["helper", "steam-key"], self.helper.calls)
        self.assertFalse(any(KEY in " ".join(c) for c in self.helper.calls))
        self.assertTrue(self.window.property("owned").toVariant()["key"])
        self.assertEqual(self.errors, [])

    def test_the_helper_hands_it_over_on_stdin(self):
        said = []
        with mock.patch.dict(self.games.PROGRAMS, {"helper": "/bin/cat"}):
            helper = self.games.Helper()
            helper.done.connect(lambda ticket, out, code, err: said.append((out, code)))
            helper.feed(["helper"], KEY)
            deadline = time.monotonic() + 3
            while not said and time.monotonic() < deadline:
                QTest.qWait(10)
        self.assertEqual(said, [(KEY, 0)])

    def test_no_steam_no_note(self):
        self.open({"steam": False, "name": "", "key": False, "hint": True, "state": "", "count": 0, "changed": False})
        texts = self.visible_texts()
        self.assertNotIn("Add Steam key", texts)
        self.assertFalse(any(t.startswith("Games shows the Steam games installed here") for t in texts))


if __name__ == "__main__":
    unittest.main()
