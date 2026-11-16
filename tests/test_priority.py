"""Steam's shader processing at idle priority: every thread of it, nothing else, and nearly free
while Steam isn't running. A pretend /proc, and nothing's priority really changed."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('monet_priority', str(ROOT / 'linux/libexec/monet-priority'))
priority = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(priority)

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


class Idle(Fixture):
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
        self.assertEqual(self.said, ["Steam's shader processing (process 500) runs at idle priority"])

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

    def test_main_sleeps_what_each_turn_says(self):
        slept = []
        with mock.patch.object(priority, 'turn', side_effect=[30, 30, 2]), \
                mock.patch.object(priority.time, 'sleep', side_effect=lambda s: slept.append(s)):
            with self.assertRaises(StopIteration):
                priority.main()
        self.assertEqual(slept, [30, 30, 2])


class Kernel(unittest.TestCase):
    def test_the_processor_and_the_disk_are_asked_for_one_thread_each(self):
        with mock.patch.object(priority.os, 'sched_setscheduler') as setscheduler:
            priority.idle_processor(4242)
        tid, policy, param = setscheduler.call_args.args
        self.assertEqual((tid, policy, param.sched_priority), (4242, os.SCHED_IDLE, 0))
        libc = mock.Mock()
        libc.syscall.return_value = 0
        with mock.patch.object(priority, 'libc', return_value=libc), mock.patch.object(priority, 'IOPRIO_SET', 251):
            priority.idle_disk(4242)
            self.assertEqual([a.value for a in libc.syscall.call_args.args], [251, 1, 4242, 3 << 13])
            libc.syscall.return_value = -1
            with mock.patch.object(priority.ctypes, 'get_errno', return_value=3), \
                    self.assertRaises(ProcessLookupError):
                priority.idle_disk(4242)
        with mock.patch.object(priority, 'IOPRIO_SET', None), \
                mock.patch.object(priority, 'libc', side_effect=AssertionError('asked')):
            priority.idle_disk(4242)  # Elsewhere than x86-64 and Arm: the processors alone.
        if os.uname().machine == 'x86_64':
            self.assertEqual(priority.IOPRIO_SET, 251)


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
