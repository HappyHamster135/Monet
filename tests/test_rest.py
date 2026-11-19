"""Resting the apps you've left: only those, only when memory runs low, never what's in use."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('monet_rest', str(ROOT / 'linux/libexec/monet-rest'))
spec = importlib.util.spec_from_loader(loader.name, loader)
rest = importlib.util.module_from_spec(spec)
loader.exec_module(rest)

GIB, MIB = rest.GIB, rest.MIB


def memory(total_gib, available_gib, swap_free_gib=4):
    return {'MemTotal': int(total_gib * GIB), 'MemAvailable': int(available_gib * GIB),
            'SwapTotal': 8 * GIB, 'SwapFree': int(swap_free_gib * GIB)}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.apps = base / 'cgroup/app.slice'
        self.proc = base / 'proc'
        self.apps.mkdir(parents=True)
        self.proc.mkdir()
        self.asked = []
        self.cpu = {}

    def unit(self, name, pids, anon_mib, cpu_usec=0):
        folder = self.apps / name
        folder.mkdir()
        (folder / 'cgroup.procs').write_text(''.join(f'{p}\n' for p in pids))
        (folder / 'memory.stat').write_text(f'anon {anon_mib * MIB}\nfile 1000\n')
        (folder / 'memory.current').write_text(f'{(anon_mib + 10) * MIB}\n')
        (folder / 'cpu.stat').write_text(f'usage_usec {cpu_usec}\nuser_usec 0\n')
        for pid in pids:
            (self.proc / str(pid)).mkdir()
            (self.proc / str(pid) / 'cgroup').write_text(
                f'0::/user.slice/user-1000.slice/user@1000.service/app.slice/{name}\n')
        return folder

    def process(self, pid, name, **environment):
        """What /proc says of a process: its name and the environment it started with."""
        folder = self.proc / str(pid)
        folder.mkdir(exist_ok=True)
        (folder / 'comm').write_text(name + '\n')
        (folder / 'environ').write_bytes(b''.join(f'{k}={v}\0'.encode() for k, v in
                                                  {'HOME': '/home/me', **environment}.items()))

    def look(self, state, now, mem, shown, playing=(set(), set()), asker=None):
        def record(folder, amount):
            self.asked.append((folder.name, amount))
            return True
        return rest.rest(mem, False, state, now, self.apps, list_windows=lambda: shown,
                         playing=lambda: playing, asker=asker or record, proc=self.proc)


class Resting(Fixture):
    def test_screenshot_service_stays_ready_under_memory_pressure(self):
        self.unit('app-org.kde.spectacle.service', [10], 300)
        state = {}
        for now in (1000, 2000, 3000): self.look(state, now, memory(16, 1), [])
        self.assertEqual(self.asked, [])
        self.assertNotIn('app-org.kde.spectacle.service', state)

    def test_plenty_free_does_nothing_and_asks_kwin_nothing(self):
        self.unit('app-discord-1.scope', [10], 800)
        state = {}
        result = rest.rest(memory(16, 10), False, state, 1000, self.apps,
                           list_windows=lambda: self.fail('KWin asked'), playing=lambda: self.fail('sound asked'),
                           asker=lambda *a: self.fail('reclaim asked'), proc=self.proc)
        self.assertEqual(result, {})
        self.assertEqual(state, {})

    def test_only_apps_left_long_enough_rest_longest_left_first(self):
        self.unit('app-org.kde.dolphin@1.service', [10], 300)        # on screen
        self.unit('app-flatpak-com.discordapp.Discord-2.scope', [20, 21], 900)   # minimized
        self.unit('app-flatpak-com.spotify.Client-3.scope', [30], 600)   # playing, in the tray
        self.unit('app-steam@autostart.service', [40], 500)            # in the tray, no window
        self.unit('app-tiny-5.scope', [50], 20)                        # too small to bother
        self.unit('monet-rest.service', [60], 900)                     # Monet's own
        self.unit('app-zen-6.scope', [70], 2000)                       # minimized but busy
        windows = [{'pid': 10, 'minimized': False, 'active': True},
                   {'pid': 20, 'minimized': True, 'active': False},
                   {'pid': 70, 'minimized': True, 'active': False}]
        playing = ({30}, set())
        state = {}
        low = memory(8, 0.2)  # short of more than both apps can give
        # First look: noted, nothing rests yet.
        self.assertEqual(self.look(state, 1000, low, windows, playing), {})
        self.assertEqual(self.asked, [])
        # Steam was left first; Discord a minute later.
        (self.apps / 'app-zen-6.scope/cpu.stat').write_text('usage_usec 30000000\n')  # 30 s of work in 10 min
        state['apps']['app-flatpak-com.discordapp.Discord-2.scope']['idle_since'] = 1060
        result = self.look(state, 1000 + rest.IDLE + 60, low, windows, playing)
        names = [name for name, _ in self.asked]
        self.assertEqual(list(dict.fromkeys(names)), ['app-steam@autostart.service',
                                                     'app-flatpak-com.discordapp.Discord-2.scope'])
        self.assertTrue(all(amount <= rest.CHUNK for _, amount in self.asked))
        self.assertEqual(result['app-steam@autostart.service'], int(500 * MIB * 0.75))
        self.assertEqual(result['app-flatpak-com.discordapp.Discord-2.scope'], int(900 * MIB * 0.75))
        for kept in ('app-org.kde.dolphin@1.service', 'app-flatpak-com.spotify.Client-3.scope', 'app-tiny-5.scope',
                     'monet-rest.service', 'app-zen-6.scope'):
            self.assertNotIn(kept, result)
        json.dumps(state)

    def test_it_asks_only_for_what_is_missing_and_not_again_soon(self):
        self.unit('app-a-1.scope', [10], 4000)
        self.unit('app-b-2.scope', [20], 4000)
        state, low = {}, memory(16, 3.0)  # 3.2 GB wanted (20%): 0.2 GB missing
        self.look(state, 1000, low, [])
        result = self.look(state, 1000 + rest.IDLE, low, [])
        want = rest.room_wanted(low, False)
        self.assertEqual(sum(result.values()), int((want - low['MemAvailable']) * 1.5))
        self.assertEqual(list(result), ['app-a-1.scope'])
        self.asked.clear()
        # Two minutes later, still low: what rested isn't asked again; the next one is.
        result = self.look(state, 1000 + rest.IDLE + 120, low, [])
        self.assertEqual(list(result), ['app-b-2.scope'])

    def test_an_app_coming_back_starts_its_wait_again(self):
        self.unit('app-a-1.scope', [10], 1000)
        state, low = {}, memory(8, 1.0)
        self.look(state, 1000, low, [{'pid': 10, 'minimized': True, 'active': False}])
        self.look(state, 1300, low, [{'pid': 10, 'minimized': False, 'active': True}])  # opened again
        self.assertEqual(self.look(state, 1000 + rest.IDLE + 1, low, [{'pid': 10, 'minimized': True, 'active': False}]), {})
        self.assertEqual(self.asked, [])

    def test_watching_starts_before_the_line_so_apps_are_ready_when_it_is_crossed(self):
        self.unit('app-a-1.scope', [10], 1000)
        state = {}
        near = memory(16, 4.0)  # 3.2 GB wanted: 4 GB is within half again of it
        self.assertEqual(self.look(state, 1000, near, []), {})
        self.assertIn('idle_since', state['apps']['app-a-1.scope'])
        self.assertEqual(self.asked, [])
        result = self.look(state, 1000 + rest.IDLE, memory(16, 3.0), [])
        self.assertIn('app-a-1.scope', result)

    def test_flatpak_sound_by_app_id_and_unknown_windows_rest_nothing(self):
        self.unit('app-flatpak-com.spotify.Client-3.scope', [30], 900)
        state, low = {}, memory(8, 1.0)
        playing = ({999}, {'com.spotify.Client'})  # the sandbox's own process number
        self.look(state, 1000, low, [], playing)
        self.assertEqual(self.look(state, 1000 + rest.IDLE, low, [], playing), {})
        # KWin can't be asked: which app is in front is unknown.
        self.assertEqual(rest.rest(low, False, {}, 5000, self.apps, list_windows=lambda: None,
                                   playing=lambda: (set(), set()), asker=lambda *a: self.fail('asked'),
                                   proc=self.proc), {})

    def test_not_allowed_here_stops_and_is_remembered(self):
        self.unit('app-a-1.scope', [10], 1000)
        state, low = {}, memory(8, 1.0)
        self.look(state, 1000, low, [])
        self.assertEqual(self.look(state, 1000 + rest.IDLE, low, [], asker=lambda folder, amount: None), {})
        self.assertEqual(state['unsupported_at'], 1000 + rest.IDLE)

    def test_a_full_compressed_swap_rests_nothing(self):
        self.unit('app-a-1.scope', [10], 1000)
        state, full = {}, memory(8, 1.0, swap_free_gib=0.01)
        self.look(state, 1000, full, [])
        self.assertEqual(self.look(state, 1000 + rest.IDLE, full, []), {})


class Games(Fixture):
    """A game minimized with Alt+Tab is never rested: once back, it would stutter for minutes."""

    def test_steam_with_a_game_in_it_never_rests_and_starts_its_wait_when_the_game_quits(self):
        steam = self.unit('app-steam@autostart.service', [40, 41, 42], 3000)
        self.process(40, 'steam')
        self.process(41, 'reaper', SteamAppId='1091500', SteamGameId='1091500')
        self.process(42, 'Cyberpunk2077.e', SteamAppId='1091500', STEAM_COMPAT_APP_ID='1091500')
        self.unit('app-a-1.scope', [10], 1000)
        minimized = [{'pid': 42, 'minimized': True, 'active': False}]  # Alt+Tabbed out of a fullscreen game
        state, low = {}, memory(8, 0.5)
        self.look(state, 1000, low, minimized)
        self.assertNotIn('idle_since', state['apps']['app-steam@autostart.service'])
        result = self.look(state, 1000 + rest.IDLE * 2, low, minimized)
        self.assertEqual(list(result), ['app-a-1.scope'])  # Another app left: rested as before.
        self.assertNotIn('app-steam@autostart.service', [name for name, _ in self.asked])
        # The game quits; Steam, alone in the tray, is left from now on, not from before.
        (steam / 'cgroup.procs').write_text('40\n')
        for pid in (41, 42):
            shutil.rmtree(self.proc / str(pid))
        self.assertEqual(self.look(state, 2400, low, []), {})
        self.assertEqual(state['apps']['app-steam@autostart.service']['idle_since'], 2400)
        self.assertEqual(list(self.look(state, 2400 + rest.IDLE, low, [])), ['app-steam@autostart.service'])

    def test_what_counts_as_a_game(self):
        self.process(1, 'wineserver')                                  # any Windows game, whoever started it
        self.process(2, 'gamescope')
        self.process(3, 'hl2_linux', SteamAppId='0', SteamGameId='15426519127218675712')  # a non-Steam game in Steam
        self.process(4, 'Game.exe', STEAM_COMPAT_APP_ID='292030')     # Proton's own
        self.process(5, 'game.x86_64', LUTRIS_GAME_UUID='6d1e8c4e-3e64-4a5c-9b7e-1f0b4ed7ac35')
        self.process(6, 'steam', SteamAppId='0', SteamGameId='', STEAM_COMPAT_APP_ID='0')  # Steam itself
        self.process(7, 'fossilize_repla', SteamAppId='1091500')      # Steam processing shaders: not playing
        self.process(8, 'zen', MY_SteamAppId='5', NOT='SteamAppId=5')
        for pid in (1, 2, 3, 4, 5):
            self.assertTrue(rest.game(pid, self.proc), pid)
        for pid in (6, 7, 8, 99):  # 99: gone
            self.assertFalse(rest.game(pid, self.proc), pid)
        # One that quits between its name and its environment, or isn't this account's to read.
        self.process(9, 'Game.exe', SteamAppId='1091500')
        reading = Path.read_bytes
        for error in (FileNotFoundError, PermissionError, ProcessLookupError):
            def refuse(path, error=error):
                if path.parent.name == '9':
                    raise error()
                return reading(path)
            with mock.patch.object(Path, 'read_bytes', refuse):
                self.assertFalse(rest.game(9, self.proc))
                self.assertFalse(rest.game_running([6, 9], self.proc))
        self.assertTrue(rest.game_running([6, 9], self.proc))

    def test_an_environment_is_read_only_for_apps_otherwise_left(self):
        self.unit('app-on-screen-1.scope', [10], 1000)
        self.unit('app-busy-2.scope', [20], 1000, cpu_usec=60 * 10 ** 6)  # a minute's work in two
        self.unit('app-sounding-3.scope', [30], 1000)
        self.unit('app-left-4.scope', [40, 41], 1000)
        asked = []
        state, low = {'apps': {'app-busy-2.scope': {'cpu': 0, 'at': 880}}}, memory(8, 0.5)
        with mock.patch.object(rest, 'game', lambda pid, proc: asked.append(pid) or False):
            self.look(state, 1000, low, [{'pid': 10, 'minimized': False, 'active': True}], ({30}, set()))
        self.assertEqual(sorted(asked), [40, 41])
        self.assertEqual(sorted(name for name, entry in state['apps'].items() if 'idle_since' in entry),
                         ['app-left-4.scope'])

    def test_kwin_is_asked_every_ten_minutes_at_most_while_a_game_runs(self):
        self.unit('app-a-1.scope', [10], 1000)
        self.process(50, 'wineserver')  # A game, wherever it was started.
        asked = []
        windows = lambda: asked.append(True) or []
        state, low = {}, memory(8, 0.5)
        look = lambda now: rest.rest(low, False, state, now, self.apps, list_windows=windows,
                                     playing=lambda: (set(), set()), asker=lambda folder, amount: True, proc=self.proc)
        self.assertEqual(look(1000), {})
        for now in (1120, 1240, 1000 + rest.GAME_LOOK - 1):
            self.assertEqual(look(now), {})
        self.assertEqual(len(asked), 1)
        # Ten minutes on: asked, and the app left all along rests, the game or not.
        self.assertIn('app-a-1.scope', look(1000 + rest.GAME_LOOK))
        self.assertEqual(len(asked), 2)
        # The game over: every look again.
        shutil.rmtree(self.proc / '50')
        look(1000 + rest.GAME_LOOK + 120)
        look(1000 + rest.GAME_LOOK + 240)
        self.assertEqual(len(asked), 4)
        # A clock set back doesn't keep KWin from being asked.
        self.process(50, 'wineserver')
        look(500)
        self.assertEqual(len(asked), 5)

    def test_every_process_of_this_account_and_only_its_own(self):
        self.process(1, 'bash')
        self.process(2, 'wineserver')
        self.assertTrue(rest.game_running(proc=self.proc))  # These folders are this account's.
        self.assertFalse(rest.game_running(proc=self.proc, uid=os.getuid() + 1))  # Someone else's game.
        self.assertFalse(rest.game_running(proc=self.proc / 'missing'))
        (self.proc / '2').rename(self.proc / 'self')  # Not a process number.
        self.assertFalse(rest.game_running(proc=self.proc))


class Kernel(Fixture):
    def test_the_request_and_what_the_kernel_says(self):
        folder = self.unit('app-a-1.scope', [10], 100)
        (folder / 'memory.reclaim').write_text('')
        self.assertTrue(rest.ask(folder, 1234))
        self.assertEqual((folder / 'memory.reclaim').read_text(), '1234')
        with mock.patch.object(rest.os, 'write', side_effect=BlockingIOError(11, 'EAGAIN')):
            self.assertFalse(rest.ask(folder, 1))
        # Where there's no such file (an older kernel, no memory controller), none is made.
        (folder / 'memory.reclaim').unlink()
        self.assertIsNone(rest.ask(folder, 1))
        self.assertFalse((folder / 'memory.reclaim').exists())
        self.assertIsNone(rest.ask(self.apps / 'gone.scope', 1))

    def test_room_older_pcs_keep_more_free(self):
        self.assertEqual(rest.room_wanted(memory(32, 0), False), int(32 * GIB * 0.20))
        self.assertEqual(rest.room_wanted(memory(8, 0), True), int(8 * GIB * 0.30))
        self.assertEqual(rest.room_wanted(memory(4, 0), False), int(1.5 * GIB))

    def test_units_and_which_one_a_process_is_in(self):
        self.unit('app-a-1.scope', [10], 100)
        self.unit('monet-backup.service', [11], 100)
        (self.apps / 'nested.slice').mkdir()
        self.assertEqual(sorted(rest.units(self.apps)), ['app-a-1.scope'])
        self.assertEqual(rest.unit_of(10, self.proc), 'app-a-1.scope')
        self.assertEqual(rest.unit_of(12345, self.proc), '')

    def test_sound_streams_from_pactl(self):
        streams = [{'corked': False, 'properties': {'application.process.id': '42', 'application.id': 'org.example.App'}},
                   {'corked': True, 'properties': {'application.process.id': '43'}},
                   {'corked': False, 'properties': {'pipewire.sec.pid': '44', 'pipewire.access.portal.app_id': 'com.spotify.Client'}}]
        done = mock.Mock(returncode=0, stdout=json.dumps(streams))
        with mock.patch.object(rest.shutil, 'which', return_value='/usr/bin/pactl'), \
                mock.patch.object(rest.subprocess, 'run', return_value=done):
            pids, ids = rest.sounding()
        self.assertEqual(pids, {42, 44})
        self.assertEqual(ids, {'org.example.App', 'com.spotify.Client'})


class Warning(Fixture):
    def test_nearly_full_for_a_while_names_the_biggest_apps_at_most_every_half_hour(self):
        data = Path(self.temp.name) / 'data'
        (data / 'applications').mkdir(parents=True)
        (data / 'applications/app.zen_browser.zen.desktop').write_text(
            '[Desktop Entry]\nName=Zen Browser\nName[sv]=Zen-webbläsaren\n[Desktop Action new]\nName=New window\n')
        self.unit('app-flatpak-app.zen_browser.zen-1.scope', [10], 8 * 1024)
        self.unit('true-borders.service', [20], 2 * 1024)
        self.unit('app-org.kde.dolphin@3.service', [30], 100)   # too small to name
        said, state = [], {}
        full, fine = memory(16, 0.4), memory(16, 6)
        with mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(data), 'XDG_DATA_DIRS': str(data), 'LANGUAGE': '',
                                          'LC_ALL': '', 'LC_MESSAGES': '', 'LANG': 'C'}):
            look = lambda now, mem: rest.warn(mem, state, now, self.apps, say=lambda *a: said.append(a))
            self.assertFalse(look(1000, full))                 # just now: maybe a moment's peak
            self.assertFalse(look(1000 + rest.FULL_FOR - 1, full))
            self.assertTrue(look(1000 + rest.FULL_FOR, full))
            title, body = said[0]
            self.assertEqual(title, 'Memory is almost full')
            self.assertIn('Zen Browser (8.0 GB), true-borders (2.0 GB)', body)
            self.assertNotIn('dolphin', body.lower())
            self.assertFalse(look(1000 + rest.FULL_FOR + 60, full))  # not again so soon
            self.assertFalse(look(1500, fine))                       # room again: starts over
            self.assertNotIn('full_since', state)
            self.assertEqual(len(said), 1)
            with mock.patch.dict(os.environ, {'LANG': 'sv_SE.UTF-8'}):
                self.assertEqual(rest.app_name('app-flatpak-app.zen_browser.zen-1.scope'), 'Zen-webbläsaren')
        self.assertEqual(rest.app_name('app-org.example.Gone@4.service'), 'Gone')  # no menu entry any more
        self.assertEqual(rest.size(int(1.25 * GIB)), '1.2 GB')
        self.assertEqual(rest.size(300 * MIB), '300 MB')

    def test_the_notification_waits_in_its_own_unit_and_opens_task_manager(self):
        with mock.patch.object(rest.subprocess, 'run') as run:
            rest.notify('Memory is almost full', 'Using the most now: Zen (8 GB).')
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ['systemd-run', '--user', '--collect', '--quiet'])
        self.assertIn('--action=open="$1" --wait', command[6])
        self.assertIn('monet-quick launch ' + b'org.kde.plasma-systemmonitor.desktop'.hex(), command[6])
        self.assertEqual(command[-3:], ['Open Task Manager', 'Memory is almost full', 'Using the most now: Zen (8 GB).'])


class Installed(unittest.TestCase):
    def test_timer_unit_and_install(self):
        units = ROOT / 'linux/systemd/user'
        timer = (units / 'monet-rest.timer').read_text()
        self.assertIn('OnUnitActiveSec=2min', timer)
        self.assertIn('WantedBy=timers.target', timer)
        service = (units / 'monet-rest.service').read_text()
        self.assertIn('ExecStart=@LIBEXECDIR@/monet-rest', service)
        self.assertIn('Type=oneshot', service)
        install = (ROOT / 'linux/install.sh').read_text()
        self.assertIn('put 644 "$SRC/systemd/user/monet-rest.timer" "$USERUNITDIR/monet-rest.timer"', install)
        self.assertIn('systemctl --global enable monet-backup.timer monet-rest.timer\n', install)  # the image
        self.assertIn('systemctl --global enable monet-backup.timer monet-rest.timer >/dev/null', install)  # a system
        self.assertIn(' monet-rest ', install.split('for tool in ', 1)[1].split('; do', 1)[0] + ' ')
        uninstall = (ROOT / 'linux/uninstall.sh').read_text()
        self.assertIn('/etc/systemd/user/monet-rest.timer', uninstall)
        self.assertTrue(os.access(ROOT / 'linux/libexec/monet-rest', os.X_OK))


if __name__ == '__main__':
    unittest.main()
