"""Who gets the PC first (monet-priority): Steam's shader processing at background priority, every
thread of it and nothing else, nearly free while Steam isn't running; and a game in front ahead
of the apps behind it, put back exactly as they were. A pretend /proc, cgroup tree and systemd:
nothing's priority really changes here."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('monet_priority', str(ROOT / 'linux/libexec/monet-priority'))
priority = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(priority)
rest = priority.load('monet-rest')

ME, SOMEONE = 1000, 1001
STEAM = '/home/me/.local/share/Steam'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.proc = Path(self.temp.name) / 'proc'
        self.proc.mkdir()
        self.cpu, self.io, self.said = [], [], []
        self.watch = priority.Shaders(self.proc, uid=ME, processor=self.cpu.append, disk=self.io.append,
                                     say=self.said.append)

    def process(self, pid, name, threads=(), uid=ME, exe=None, parent=1, start=1000, command=None):
        """What /proc says of a process: its name, parent, start, user, program and threads."""
        folder = self.proc / str(pid)
        folder.mkdir()
        fields = ['S', str(parent)] + ['0'] * 17 + [str(start)] + ['0'] * 30
        (folder / 'stat').write_text(f'{pid} ({name}) {" ".join(fields)}\n')
        (folder / 'status').write_text(f'Name:\t{name}\nUmask:\t0022\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n')
        os.symlink(exe or f'{STEAM}/ubuntu12_64/fossilize_replay', folder / 'exe')
        (folder / 'cmdline').write_bytes(b'\0'.join(w.encode() for w in command or [exe or name]) + b'\0')
        (folder / 'task').mkdir()
        for tid in threads or (pid,):
            (folder / 'task' / str(tid)).mkdir()
        return folder

    def done(self):
        cpu, io = sorted(self.cpu), sorted(self.io)
        self.cpu.clear()
        self.io.clear()
        self.assertEqual(cpu, io)  # The processors and the disk, always both.
        return cpu


class Background(Fixture):
    def test_every_thread_of_steams_shader_processes_and_nothing_else(self):
        self.process(400, 'steam', [400, 401], exe=f'{STEAM}/ubuntu12_32/steam')
        self.process(500, 'fossilize_repla', [500, 501, 502], parent=400)
        self.process(510, 'fossilize_repla', [510, 511], parent=500)            # a helper it started
        self.process(520, 'fossilize_repla', [520], parent=500)
        self.process(600, 'fossilize_repla', [600, 601], uid=SOMEONE)            # another account's
        self.process(700, 'kate', [700], exe='/usr/bin/kate')
        self.process(710, 'fossilize_repla', [710], exe='/opt/other/fossilize_repla')  # only the name
        self.process(720, 'Game.exe', [720], exe='/usr/bin/wine64-preloader')
        self.watch.look()
        self.assertEqual(self.done(), [500, 501, 502, 510, 511, 520])
        self.assertEqual(sorted(self.watch.known), [500, 510, 520])
        self.assertEqual(self.said, ["Steam's shader processing (process 500) runs at background priority"])

    def test_nothing_is_done_twice_and_threads_started_later_are_caught(self):
        self.process(500, 'fossilize_repla', [500, 501])
        self.watch.look()
        self.assertEqual(self.done(), [500, 501])
        self.watch.look()
        self.assertEqual(self.done(), [])
        (self.proc / '500/task/503').mkdir()   # A new thread,
        self.process(510, 'fossilize_repla', [510], parent=500)  # and a new helper.
        self.watch.look()
        self.assertEqual(self.done(), [503, 510])
        (self.proc / '500/task/501').rmdir()   # A thread ends: forgotten, not asked again.
        self.watch.look()
        self.assertEqual(self.done(), [])
        self.assertEqual(self.watch.known[500][1], {500, 503})
        self.assertEqual(len(self.said), 1)

    def test_a_number_given_to_another_process_is_looked_at_again(self):
        self.process(500, 'fossilize_repla', [500], start=1000)
        self.watch.look()
        self.assertEqual(self.done(), [500])
        # It ends, and its number goes to Kate: not touched, and forgotten.
        (self.proc / '500').rename(self.proc / 'gone')
        self.process(500, 'kate', [500, 504], exe='/usr/bin/kate', start=2000)
        self.watch.look()
        self.assertEqual(self.done(), [])
        self.assertNotIn(500, self.watch.known)
        # Then to the next shader run, whose threads have the same numbers as the first's.
        (self.proc / '500').rename(self.proc / 'gone-too')
        self.process(500, 'fossilize_repla', [500], start=3000)
        self.watch.look()
        self.assertEqual(self.done(), [500])
        self.assertEqual(self.watch.known[500][0], 3000)
        # Same number, a later start, never seen ending in between: looked at again all the same.
        (self.proc / '500/stat').write_text((self.proc / '500/stat').read_text().replace(' 3000 ', ' 3100 '))
        self.watch.look()
        self.assertEqual(self.done(), [500])
        self.assertEqual(len(self.said), 3)

    def test_a_process_that_ends_while_it_is_looked_at(self):
        self.process(500, 'fossilize_repla', [500, 501, 502])
        self.process(510, 'fossilize_repla', [510])
        self.process(520, 'fossilize_repla', [520])
        (self.proc / '510/stat').unlink()                    # gone before its name was read
        (self.proc / '520/exe').unlink()                     # gone before its program was
        thread_ended = ProcessLookupError(3, 'No such process')

        def processor(tid):
            if tid == 501:
                raise thread_ended                           # a thread gone before it was set
            self.cpu.append(tid)
        self.watch.processor = processor
        self.watch.look()
        self.assertEqual(sorted(self.cpu), [500, 502])
        self.assertEqual(sorted(self.io), [500, 502])
        self.assertEqual(sorted(self.watch.known), [500])
        self.assertEqual(self.watch.known[500][1], {500, 502})  # 501 not counted as done
        # The whole process gone between its name and its threads: forgotten, nothing asked.
        self.process(530, 'fossilize_repla', [530])
        os.rename(self.proc / '530/task', self.proc / '530/ended')
        self.cpu.clear()
        self.io.clear()
        self.watch.look()
        self.assertNotIn(530, self.watch.known)
        self.assertEqual(self.cpu, [])
        # And gone altogether: forgotten too.
        (self.proc / '500').rename(self.proc / 'gone')
        self.watch.look()
        self.assertEqual(self.watch.known, {})

    def test_what_the_kernel_refuses_is_said_once_and_not_asked_again(self):
        self.process(500, 'fossilize_repla', [500])

        def refuse(tid):
            raise PermissionError(1, 'Operation not permitted')
        self.watch.disk = refuse
        self.watch.look()
        self.watch.look()
        self.assertEqual(self.cpu, [500])
        self.assertEqual(self.said[-1], "Steam's shader processing (thread 500) stays as it is: "
                                        "[Errno 1] Operation not permitted")
        self.assertEqual(len(self.said), 2)

    def test_names_with_spaces_and_brackets_are_read_whole(self):
        self.process(500, 'my (odd) fossilize_repla', [500])
        self.process(510, 'fossilize_repla', [510])
        self.assertEqual(priority.process(500, self.proc), ('my (odd) fossilize_repla', 1, 1000))
        self.watch.look()
        self.assertEqual(self.done(), [510])
        self.assertIsNone(priority.process(999, self.proc))
        (self.proc / '510/stat').write_text('510 (fossilize_repla) S\n')  # cut short
        self.assertIsNone(priority.process(510, self.proc))


class OnlyWhileSteamRuns(Fixture):
    def setUp(self):
        super().setUp()
        self.pid_file = Path(self.temp.name) / 'steam.pid'

    def test_steam_is_the_process_its_pid_file_names(self):
        running = lambda: priority.steam_running(self.pid_file, self.proc, uid=ME)
        self.assertFalse(running())                                     # never started
        self.pid_file.write_text('4321\n')
        self.assertFalse(running())                                     # ended without saying so
        self.process(4321, 'steam.sh', command=['/usr/bin/bash', f'{STEAM}/steam.sh', '-silent'])
        self.assertTrue(running())
        (self.proc / '4321').rename(self.proc / 'gone')
        self.process(4321, 'steam', exe=f'{STEAM}/ubuntu12_32/steam')   # the client itself
        self.assertTrue(running())
        (self.proc / '4321').rename(self.proc / 'gone-too')
        self.process(4321, 'kate', exe='/usr/bin/kate')                 # its number given to another
        self.assertFalse(running())
        self.pid_file.write_text('4322\n')
        self.process(4322, 'steam', exe=f'{STEAM}/ubuntu12_32/steam', uid=SOMEONE)  # someone else's
        self.assertFalse(running())
        for junk in ('', 'steam\n', '-1\n'):
            self.pid_file.write_text(junk)
            self.assertFalse(running())

    def test_without_steam_it_sleeps_and_looks_at_nothing(self):
        self.process(500, 'fossilize_repla', [500])
        self.watch.known[1] = (5, {1})
        with mock.patch.object(self.watch, 'look', side_effect=AssertionError('looked')):
            self.assertEqual(priority.turn(self.watch, steam=lambda: False), priority.REST)
        self.assertEqual(self.watch.known, {})  # What Steam ran is over.
        self.assertEqual(self.cpu, [])
        self.assertEqual(priority.turn(self.watch, steam=lambda: True), priority.LOOK)
        self.assertEqual(self.done(), [500])
        self.assertEqual((priority.LOOK, priority.REST), (2, 30))



class Kernel(unittest.TestCase):
    def test_the_processor_and_the_disk_are_asked_for_one_thread_each(self):
        for current, expected in ((0, 5), (5, 5), (12, 12)):
            with self.subTest(current=current), mock.patch.object(priority.os, 'getpriority', return_value=current), \
                    mock.patch.object(priority.os, 'setpriority') as setpriority:
                priority.background_processor(4242)
                setpriority.assert_called_once_with(os.PRIO_PROCESS, 4242, expected)
        libc = mock.Mock()
        libc.syscall.return_value = 0
        with mock.patch.object(priority, 'libc', return_value=libc), mock.patch.object(priority, 'IOPRIO_SET', 251):
            priority.background_disk(4242)
            self.assertEqual([a.value for a in libc.syscall.call_args.args], [251, 1, 4242, (2 << 13) | 7])
            libc.syscall.return_value = -1
            with mock.patch.object(priority.ctypes, 'get_errno', return_value=3), \
                    self.assertRaises(ProcessLookupError):
                priority.background_disk(4242)
        with mock.patch.object(priority, 'IOPRIO_SET', None), \
                mock.patch.object(priority, 'libc', side_effect=AssertionError('asked')):
            priority.background_disk(4242)  # Elsewhere than x86-64 and Arm: the processors alone.
        if os.uname().machine == 'x86_64':
            self.assertEqual(priority.IOPRIO_SET, 251)


STEAM_UNIT, CHROMIUM, ZEN = 'app-steam@autostart.service', 'app-flatpak-org.chromium.Chromium-4242.scope', 'app-zen-7.scope'


class Systemd:
    """systemctl --user, pretend: each unit's weights as `show` prints them."""

    def __init__(self):
        self.units, self.calls = {}, []

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == 'show':
            names = args[args.index('--') + 1:]
            return '\n\n'.join(f'Id={n}\n' + '\n'.join(f'{k}={self.units.get(n, {}).get(k, "[not set]")}'
                                                         for k in ('CPUWeight', 'IOWeight')) for n in names) + '\n'
        if args[:2] == ('set-property', '--runtime') and args[2] in self.units:
            for setting in args[3:]:
                key, _, value = setting.partition('=')
                self.units[args[2]][key] = value or '[not set]'
            return ''
        return None

    def sets(self):
        found = [c[2:] for c in self.calls if c[0] == 'set-property']
        self.calls.clear()
        return found


class GamesFirstFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.apps, self.proc, self.saved = base / 'cgroup/app.slice', base / 'proc', base / 'run/monet/priority.json'
        self.apps.mkdir(parents=True)
        self.proc.mkdir()
        self.systemd, self.said, self.playing = Systemd(), [], (set(), set())
        self.first = self.games_first()
        self.unit(STEAM_UNIT, {40: 'steam', 41: 'reaper', 42: 'REPO.exe'}, game=(41, 42))
        self.unit(CHROMIUM, {10: 'chromium', 11: 'chromium'})
        self.unit(ZEN, {30: 'zen'})

    def games_first(self):
        return priority.GamesFirst(rest, apps=self.apps, proc=self.proc, run=self.systemd, saved=self.saved,
                                   playing=lambda: self.playing, say=self.said.append)

    def unit(self, name, processes, game=(), weights=None):
        folder = self.apps / name
        folder.mkdir()
        (folder / 'cgroup.procs').write_text(''.join(f'{p}\n' for p in processes))
        for pid, comm in processes.items():
            (self.proc / str(pid)).mkdir()
            (self.proc / str(pid) / 'cgroup').write_text(f'0::/user.slice/user-1000.slice/user@1000.service/app.slice/{name}\n')
            (self.proc / str(pid) / 'comm').write_text(comm + '\n')
            (self.proc / str(pid) / 'environ').write_bytes(b'HOME=/home/me\0' + (b'SteamAppId=3241660\0' if pid in game else b''))
        self.systemd.units[name] = dict(weights or {})

    def front(self, now, active=0, full=()):
        return self.first.report(json.dumps({'active': active, 'full': list(full)}), now)

    def lowered(self, *names):
        return [(n, f'CPUWeight={priority.SHARE}', f'IOWeight={priority.SHARE}') for n in names]


class GamesFirst(GamesFirstFixture):
    def test_a_game_in_front_has_the_others_give_way_after_a_moment_and_back_after(self):
        self.assertEqual(self.front(0, active=42), priority.SETTLE)  # Alt+Tab may only pass by.
        self.assertEqual(self.systemd.calls, [])
        self.assertEqual(self.first.step(priority.SETTLE), priority.RECHECK)
        self.assertEqual(self.systemd.sets(), self.lowered(CHROMIUM, ZEN))  # Never Steam's: the game is in it.
        self.assertEqual(self.systemd.units[CHROMIUM], {'CPUWeight': '20', 'IOWeight': '20'})
        self.assertTrue(self.saved.exists())
        # Zen to the front: everything back at once, as it was.
        self.assertIsNone(self.front(5, active=30))
        self.assertEqual(sorted(self.systemd.sets()), [(CHROMIUM, 'CPUWeight=', 'IOWeight='), (ZEN, 'CPUWeight=', 'IOWeight=')])
        self.assertEqual(self.systemd.units[ZEN], {'CPUWeight': '[not set]', 'IOWeight': '[not set]'})
        self.assertFalse(self.saved.exists())
        self.assertIsNone(self.front(6, active=30))
        self.assertEqual(self.systemd.calls, [])  # Nothing to put back twice.
        # And back in the game: another moment first.
        self.assertEqual(self.front(10, active=42), priority.SETTLE)
        self.assertEqual(self.systemd.calls, [])

    def test_a_game_full_screen_on_another_screen_counts_until_it_quits(self):
        self.front(0, active=30, full=[42])
        self.first.step(priority.SETTLE)
        self.assertEqual(self.systemd.sets(), self.lowered(CHROMIUM))  # Zen is the one in front.
        self.assertEqual(self.first.step(priority.SETTLE + priority.RECHECK), priority.RECHECK)
        self.assertEqual(self.systemd.calls, [])  # Looked at again: nothing new to do.
        # The game quits; its window's process is gone before KWin says so.
        (self.apps / STEAM_UNIT / 'cgroup.procs').write_text('40\n')
        self.assertIsNone(self.first.step(30))
        self.assertEqual(self.systemd.sets(), [(CHROMIUM, 'CPUWeight=', 'IOWeight=')])

    def test_who_never_gives_way(self):
        self.unit('app-com.discordapp.Discord-1.scope', {20: 'Discord'})                        # in a call
        self.unit('app-flatpak-com.spotify.Client-2.scope', {50: 'spotify'})                     # playing music
        self.unit('app-polkit\\x2dkde\\x2dauthentication\\x2dagent\\x2d1@autostart.service', {60: 'polkit-kde'})
        self.unit('app-org.kde.plasma\\x2dbrowser\\x2dintegration\\x2dhost-3.scope', {61: 'host'})
        self.unit('app-xdg\\x2duser\\x2ddirs@autostart.service', {62: 'xdg-user-dirs'})
        self.unit('monet-backup.service', {63: 'monet-quick'})                                     # Monet's own
        self.unit('app-gone-4.scope', {})                                                         # nothing left in it
        self.unit('app-quiet-5.scope', {64: 'calm'}, weights={'CPUWeight': '10', 'IOWeight': 'idle'})  # lower already
        self.unit('app-half-6.scope', {65: 'half'}, weights={'CPUWeight': '10', 'IOWeight': '80'})
        self.playing = ({20}, {'com.spotify.Client'})
        self.front(0, active=42)
        self.first.step(priority.SETTLE)
        self.assertEqual(sorted(self.systemd.sets()), sorted(self.lowered(CHROMIUM, ZEN) + [('app-half-6.scope', 'IOWeight=20')]))
        self.first.restore()
        self.assertEqual(sorted(self.systemd.sets()), sorted([('app-half-6.scope', 'IOWeight=80'),
                                                              (CHROMIUM, 'CPUWeight=', 'IOWeight='), (ZEN, 'CPUWeight=', 'IOWeight=')]))
        self.assertEqual(self.systemd.units['app-half-6.scope'], {'CPUWeight': '10', 'IOWeight': '80'})

    def test_apps_that_start_end_or_make_a_sound_while_the_game_is_in_front(self):
        self.front(0, active=42)
        self.first.step(priority.SETTLE)
        self.systemd.sets()
        self.unit('app-discord-8.scope', {80: 'Discord'})  # started
        shutil.rmtree(self.apps / ZEN)                     # closed
        del self.systemd.units[ZEN]
        self.first.step(12)
        self.assertEqual(self.systemd.sets(), self.lowered('app-discord-8.scope'))
        self.assertNotIn(ZEN, self.first.lowered)
        self.playing = ({80}, set())  # a call begins: back at once
        self.first.step(22)
        self.assertEqual(self.systemd.sets(), [('app-discord-8.scope', 'CPUWeight=', 'IOWeight=')])
        self.first.restore()
        self.assertEqual(self.systemd.sets(), [(CHROMIUM, 'CPUWeight=', 'IOWeight=')])

    def test_steam_gives_way_to_a_game_of_its_own_unit(self):
        self.unit('app-net.lutris.Lutris-9.scope', {90: 'lutris', 91: 'wineserver', 92: 'Game.exe'})
        self.front(0, active=92)
        self.first.step(priority.SETTLE)
        self.assertIn(self.lowered(STEAM_UNIT)[0], self.systemd.sets())  # Steam's, with no game in front in it.
        # Steam's own window in front while its game runs: still the game's unit.
        self.front(5, active=40, full=[])
        self.assertEqual(self.first.games(), {STEAM_UNIT})

    def test_a_stop_or_a_crash_puts_everything_back(self):
        self.systemd.units[ZEN] = {'CPUWeight': '50'}
        self.front(0, active=42)
        self.first.step(priority.SETTLE)
        self.systemd.sets()
        self.assertEqual(json.loads(self.saved.read_text())[ZEN], {'CPUWeight': '50', 'IOWeight': ''})
        # Crashed: the next start finds what was lowered and puts it back.
        after = self.games_first()
        after.recover()
        self.assertEqual(sorted(self.systemd.sets()), [(CHROMIUM, 'CPUWeight=', 'IOWeight='), (ZEN, 'CPUWeight=50', 'IOWeight=')])
        self.assertFalse(self.saved.exists())
        self.assertEqual(self.systemd.units[ZEN], {'CPUWeight': '50', 'IOWeight': '[not set]'})
        # Nothing to put back, or a note that isn't one: nothing asked.
        for text in ('', 'not json', '[1, 2]', json.dumps({'-x.service': {'CPUWeight': '5'}, '../x': {}, ZEN: 'no'})):
            self.saved.parent.mkdir(parents=True, exist_ok=True)
            self.saved.write_text(text)
            self.games_first().recover()
            self.assertEqual(self.systemd.calls, [], text)
            self.assertFalse(self.saved.exists(), text)

    def test_kwins_word_and_systemds(self):
        for text in ('', 'nonsense', '[]', '{"active": "42"}', '{"active": 42.0, "full": 7}', '{"full": ["x", -1, 0]}'):
            self.first.report(text, 0)
            self.assertEqual(self.first.front, [], text)
        self.first.report('{"active": 30, "full": [42, 0]}', 0)
        self.assertEqual(self.first.front, [30, 42])
        self.assertEqual([priority.weight(t) for t in ('[not set]', '18446744073709551615', 'idle', '50', ' 100\n', '0', None)],
                         ['', '', 'idle', '50', '100', '', ''])
        self.assertTrue(priority.unit_name('app-polkit\\x2dkde@autostart.service'))
        for bad in ('-.slice', '--runtime.service', 'a b.scope', 'x/../y.scope', 'app.slice', ''):
            self.assertFalse(priority.unit_name(bad), bad)


@unittest.skipIf(os.name == 'nt' or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'), 'a private session bus')
class OnTheBus(unittest.TestCase):
    """KWin's word reaches games first through the session bus; and the service, stopped, puts
    back what an earlier run left lowered, before and as it goes."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtDBus import QDBusConnection
        except ImportError:
            raise unittest.SkipTest('Qt D-Bus required')
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.Bus = QDBusConnection

    def wait(self, condition, seconds=5):
        from PySide6.QtCore import QCoreApplication, QEventLoop
        deadline = time.monotonic() + seconds
        while not condition() and time.monotonic() < deadline:
            QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
            time.sleep(0.01)
        return condition()

    def test_front_on_the_bus(self):
        from PySide6.QtDBus import QDBusMessage
        address = os.environ['DBUS_SESSION_BUS_ADDRESS']
        bus, kwin = (self.Bus.connectToBus(address, name) for name in ('priority-under-test', 'pretend-kwin-priority'))
        self.addCleanup(lambda: [self.Bus.disconnectFromBus(n) for n in ('priority-under-test', 'pretend-kwin-priority')])
        first = mock.Mock()
        first.report.return_value = 0.1
        first.step.return_value = None
        shaders, turns = priority.Shaders('/nonexistent', processor=lambda tid: None, disk=lambda tid: None), []
        with mock.patch.object(priority, 'turn', side_effect=lambda s: turns.append(s) or 0.05):
            alive = priority.serve(shaders, first, bus=bus)
            self.assertIsNotNone(alive)
            self.assertTrue(self.wait(lambda: len(turns) >= 3))  # Each look after the time the last one said.
        self.assertTrue(all(s is shaders for s in turns))
        alive['looks'].stop()
        message = QDBusMessage.createMethodCall(priority.NAME_ON_BUS, priority.PATH_ON_BUS, priority.NAME_ON_BUS, 'Front')
        message.setArguments(['{"active": 42, "full": []}'])
        pending = kwin.asyncCall(message, 2000)
        self.assertTrue(self.wait(pending.isFinished))
        self.assertFalse(pending.isError(), pending.error().message())
        self.assertEqual(first.report.call_args.args[0], '{"active": 42, "full": []}')
        self.assertTrue(self.wait(lambda: first.step.called))  # As report asked, a moment later.
        again = self.Bus.connectToBus(address, 'second-priority')
        self.addCleanup(lambda: self.Bus.disconnectFromBus('second-priority'))
        self.assertIsNone(priority.serve(shaders, first, bus=again))  # One per sign-in.

    def test_stopped_it_puts_back_what_was_left_lowered(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        (folder / 'bin').mkdir()
        log = folder / 'systemctl.log'
        fake = folder / 'bin/systemctl'
        fake.write_text(f'#!/bin/sh\necho "$*" >> "{log}"\n')
        fake.chmod(0o755)
        saved = Path(os.environ['XDG_RUNTIME_DIR']) / 'monet/priority.json'
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps({ZEN: {'CPUWeight': '50', 'IOWeight': ''}}))
        self.addCleanup(saved.unlink, True)
        env = dict(os.environ, PATH=f'{folder / "bin"}:{os.environ.get("PATH", "")}')
        process = subprocess.Popen([sys.executable, str(ROOT / 'linux/libexec/monet-priority')], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.assertTrue(self.wait(lambda: log.exists() and not saved.exists() or process.poll() is not None, 15),
                        'the service never started')
        self.assertIsNone(process.poll(), process.stdout.read() if process.poll() is not None else '')
        self.assertEqual(log.read_text(), f'--user set-property --runtime {ZEN} CPUWeight=50 IOWeight=\n')
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.wait(5), 0)
        self.assertIn('the other apps are back as they were', process.stdout.read())


class Installed(unittest.TestCase):
    def test_a_user_service_on_for_everyone(self):
        unit = (ROOT / 'linux/systemd/user/monet-priority.service').read_text()
        for line in ('ExecStart=@LIBEXECDIR@/monet-priority', 'PartOf=graphical-session.target',
                     'WantedBy=graphical-session.target', 'Restart=on-failure', 'Slice=background.slice'):
            self.assertIn(line, unit)
        install = (ROOT / 'linux/install.sh').read_text()
        self.assertIn(' monet-priority ', install.split('for tool in ', 1)[1].split('; do', 1)[0] + ' ')
        self.assertIn('put 644 "$SRC/systemd/user/monet-priority.service" "$USERUNITDIR/monet-priority.service"', install)
        self.assertIn('    systemctl --global enable monet-priority.service\n', install)  # the image
        self.assertIn('    systemctl --global enable monet-priority.service >/dev/null 2>&1 || true\n', install)  # a system
        uninstall = (ROOT / 'linux/uninstall.sh').read_text()
        self.assertIn(' monet-priority ', uninstall.split('for tool in ', 1)[1].split('; do', 1)[0] + ' ')
        self.assertIn('systemctl --global disable monet-priority.service', uninstall)
        self.assertIn('/etc/systemd/user/monet-priority.service', uninstall)
        self.assertTrue(os.access(ROOT / 'linux/libexec/monet-priority', os.X_OK))
        self.assertIn('linux/libexec/monet-priority ', (ROOT / '.github/workflows/build.yml').read_text())


if __name__ == '__main__':
    unittest.main()
