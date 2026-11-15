"""Task Manager's graphics use per app: every driver's report, read and named right."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('monet_graphics_use', str(ROOT / 'linux/libexec/monet-graphics-use'))
spec = importlib.util.spec_from_loader(loader.name, loader)
use = importlib.util.module_from_spec(spec)
loader.exec_module(use)

# nvidia-smi pmon before 2023, and since: two more columns (jpg, ofa) before the name.
OLD_PMON = '''# gpu        pid  type    sm   mem   enc   dec   command
# Idx          #   C/G     %     %     %     %   name
    0       1201     G     6     1     -     -   kwin_wayland
    0       2400     G     -     -     -     -   zen
'''
NEW_PMON = '''# gpu         pid   type     sm    mem    enc    dec    jpg    ofa    command
# Idx           #    C/G      %      %      %      %      %      %    name
    0       1201     G      7      2      -      -      -      -    kwin_wayland
    0       3300     G     41     12      -      -      -      -    Cyberpunk2077.e
    1       3300     G     12      3      -      -      -      -    Cyberpunk2077.e
'''


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.proc = Path(self.temp.name) / 'proc'
        self.proc.mkdir()
        data = Path(self.temp.name) / 'data'
        (data / 'applications').mkdir(parents=True)
        (data / 'applications/app.zen_browser.zen.desktop').write_text(
            '[Desktop Entry]\nName=Zen Browser\nName[sv]=Zen-webbläsaren\nExec=zen\n[Desktop Action new]\nName=New window\n')
        (data / 'applications/steam.desktop').write_text('[Desktop Entry]\nName=Steam\n')
        environment = mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(data), 'XDG_DATA_DIRS': str(data),
                                                   'LANGUAGE': '', 'LC_ALL': '', 'LC_MESSAGES': '', 'LANG': 'C'})
        environment.start()
        self.addCleanup(environment.stop)

    def process(self, pid, comm, cmdline, unit, ppid=1, fds=()):
        """A process in the fake /proc: its names, systemd unit, parent, and open DRM clients."""
        folder = self.proc / str(pid)
        (folder / 'fd').mkdir(parents=True)
        (folder / 'fdinfo').mkdir()
        (folder / 'comm').write_text(comm + '\n')
        (folder / 'cmdline').write_text('\0'.join(cmdline) + '\0')
        (folder / 'cgroup').write_text(f'0::/user.slice/user-1000.slice/user@1000.service/app.slice/{unit}\n')
        (folder / 'stat').write_text(f'{pid} ({comm}) S {ppid} {pid} {pid} 0 -1\n')
        for number, (target, info) in enumerate(fds, start=3):
            os.symlink(target, folder / 'fd' / str(number))
            (folder / 'fdinfo' / str(number)).write_text(info)
        return folder

    def client(self, client, engines, pdev='0000:03:00.0', driver='amdgpu'):
        lines = [f'pos:\t0', f'drm-driver:\t{driver}', f'drm-pdev:\t{pdev}', f'drm-client-id:\t{client}']
        lines += [f'{key}:\t{value}' for key, value in engines.items()]
        return '\n'.join(lines) + '\n'


class Drivers(Fixture):
    def test_nvidia_columns_are_found_by_name_in_old_and_new_reports(self):
        self.assertEqual(use.nvidia_use(OLD_PMON), {1201: 6.0})  # "-": no work in this sample
        # The busiest card counts for a program on two.
        self.assertEqual(use.nvidia_use(NEW_PMON), {1201: 7.0, 3300: 41.0})
        self.assertEqual(use.nvidia_use(''), {})
        self.assertEqual(use.nvidia_use('No running processes found\n'), {})

    def test_amd_and_intel_engine_counters(self):
        # amdgpu and i915: nanoseconds busy; i915 has two video engines that are busy together.
        amd = use.drm_client(self.client(7, {'drm-engine-gfx': '2000000000 ns', 'drm-engine-compute': '0 ns',
                                             'drm-memory-vram': '1024 KiB'}))
        self.assertEqual(amd, ('0000:03:00.0', '7', {'gfx': (2000000000, None, 1), 'compute': (0, None, 1)}))
        intel = use.drm_client(self.client(9, {'drm-engine-video': '500 ns', 'drm-engine-capacity-video': '2'},
                                           driver='i915'))
        self.assertEqual(intel[2], {'video': (500, None, 2)})
        # xe: cycles of work against cycles passed.
        xe = use.drm_client(self.client(3, {'drm-cycles-rcs': '100', 'drm-total-cycles-rcs': '1000'}, driver='xe'))
        self.assertEqual(xe[2], {'rcs': (100, 1000, 1)})
        self.assertIsNone(use.drm_client('pos:\t0\nflags:\t02\n'))  # not a DRM client

        before = {('a', '7'): (10, {'gfx': (1_000_000_000, None, 1), 'compute': (0, None, 1)}),
                  ('a', '9'): (20, {'video': (0, None, 2)}),
                  ('a', '3'): (30, {'rcs': (100, 1000, 1)})}
        after = {('a', '7'): (10, {'gfx': (1_250_000_000, None, 1), 'compute': (100_000_000, None, 1)}),
                 ('a', '9'): (20, {'video': (1_000_000_000, None, 2)}),
                 ('a', '3'): (30, {'rcs': (400, 2000, 1)}),
                 ('a', '5'): (40, {'gfx': (9_000_000_000, None, 1)})}  # new since the first reading: not counted
        found = use.drm_use(before, after, 1.0)
        self.assertEqual(found, {10: 25.0, 20: 50.0, 30: 30.0})

    def test_a_client_open_in_a_parent_and_its_child_counts_once(self):
        info = self.client(7, {'drm-engine-gfx': '5 ns'})
        self.process(100, 'zen', ['/app/bin/zen'], 'app-flatpak-app.zen_browser.zen-1234.scope',
                     fds=[('/dev/dri/renderD128', info), ('/home/me/notes.txt', 'pos:\t0\n')])
        self.process(101, 'zen', ['/app/bin/zen', '-contentproc'], 'app-flatpak-app.zen_browser.zen-1234.scope',
                     ppid=100, fds=[('/dev/dri/renderD128', info)])
        self.process(102, 'zen', ['/app/bin/zen', '-contentproc'], 'app-flatpak-app.zen_browser.zen-1234.scope',
                     ppid=100, fds=[('/dev/dri/card1', self.client(8, {'drm-engine-gfx': '9 ns'}))])
        found = use.drm_clients(self.proc)
        self.assertEqual(found, {('0000:03:00.0', '7'): (100, {'gfx': (5, None, 1)}),
                                 ('0000:03:00.0', '8'): (102, {'gfx': (9, None, 1)})})

    def test_two_readings_a_second_apart_and_nvidia_in_the_same_second(self):
        folder = self.process(100, 'zen', ['/app/bin/zen'], 'app-flatpak-app.zen_browser.zen-1234.scope',
                              fds=[('/dev/dri/renderD128', self.client(7, {'drm-engine-gfx': '0 ns'}))])
        times, waited = iter([10.0, 10.2, 11.0]), []

        def nvidia():
            # The DRM reading is a second old by the time the second one is taken.
            (folder / 'fdinfo/3').write_text(self.client(7, {'drm-engine-gfx': '400000000 ns'}))
            return NEW_PMON

        self.process(1201, 'kwin_wayland', ['/usr/bin/kwin_wayland', '--wayland-fd', '7'],
                     'plasma-kwin_wayland.service')
        self.process(3300, 'Cyberpunk2077.e', ['C:\\Games\\Cyberpunk 2077\\bin\\x64\\Cyberpunk2077.exe'],
                     'app-steam@autostart.service')
        result = use.measure(self.proc, nvidia=nvidia, clock=lambda: next(times), wait=waited.append)
        self.assertEqual(waited, [near(0.8)])
        self.assertEqual(result, {'version': 1, 'ok': True, 'apps': [
            {'name': 'Cyberpunk2077', 'part': '', 'percent': 41.0},
            {'name': 'Zen Browser', 'part': '', 'percent': 40.0},
            {'name': 'kwin_wayland', 'part': 'windows', 'percent': 7.0}]})
        json.dumps(result)

    def test_without_any_report_it_says_so(self):
        self.process(100, 'zen', ['/app/bin/zen'], 'app-flatpak-app.zen_browser.zen-1234.scope')
        result = use.measure(self.proc, nvidia=lambda: '', clock=lambda: 0.0, wait=self.fail)
        self.assertEqual(result, {'version': 1, 'ok': False, 'apps': []})


class Watching(Fixture):
    def test_nvidia_stream_keeps_each_programs_newest_share(self):
        now = [100.0]
        stream = use.NvidiaStream(command=('/nonexistent/nvidia-smi',), clock=lambda: now[0])
        self.assertIsNone(stream.process)  # no NVIDIA driver: nothing started
        stream.read(iter(OLD_PMON.splitlines(True)))
        self.assertEqual(stream.use(), {1201: 6.0})
        now[0] = 102.0
        stream.read(iter(NEW_PMON.splitlines(True)))  # the newer format, from a later driver
        self.assertEqual(stream.use(), {1201: 7.0, 3300: 41.0})
        now[0] = 106.0  # nothing since: those programs have stopped or closed
        self.assertEqual(stream.use(), {})
        stream.stop()

    def test_watch_prints_each_process_share_every_round_until_reading_stops(self):
        folder = self.process(100, 'zen', ['/app/bin/zen'], 'app-flatpak-app.zen_browser.zen-1234.scope',
                              fds=[('/dev/dri/renderD128', self.client(7, {'drm-engine-gfx': '0 ns'}))])
        times = iter([0.0, 2.0, 4.0])
        busy = iter(['500000000 ns', '1500000000 ns'])

        class Stream:
            process, stopped = True, False
            def use(self):
                return {3300: 41.0, 4400: 0.01}  # too small to show
            def stop(self):
                Stream.stopped = True

        def wait(seconds):
            (folder / 'fdinfo/3').write_text(self.client(7, {'drm-engine-gfx': next(busy)}))

        lines = []
        use.watch(lines.append, self.proc, Stream(), clock=lambda: next(times), wait=wait, rounds=2)
        self.assertEqual([json.loads(line) for line in lines], [
            {'version': 1, 'ok': True, 'pids': {'100': 25.0, '3300': 41.0}},
            {'version': 1, 'ok': True, 'pids': {'100': 50.0, '3300': 41.0}}])
        self.assertTrue(Stream.stopped)

        def gone(line):
            raise BrokenPipeError()
        Stream.stopped = False
        times, busy = iter([0.0, 2.0]), iter(['0 ns'])
        use.watch(gone, self.proc, Stream(), clock=lambda: next(times), wait=wait)  # returns, never raises
        self.assertTrue(Stream.stopped)


def near(value):
    """Equal to a float within a millionth."""
    class Near(float):
        def __eq__(self, other):
            return abs(other - value) < 1e-6
        __hash__ = float.__hash__
    return Near(value)


class Names(Fixture):
    def test_apps_by_their_menu_name_in_the_session_language(self):
        self.process(100, 'zen', ['/app/bin/zen'], 'app-flatpak-app.zen_browser.zen-1234.scope')
        self.assertEqual(use.owner(100, self.proc), ('app.zen_browser.zen.desktop', 'Zen Browser', ''))
        with mock.patch.dict(os.environ, {'LANG': 'sv_SE.UTF-8'}):
            self.assertEqual(use.owner(100, self.proc)[1], 'Zen-webbläsaren')

    def test_monets_desktop_parts_and_steam_games_and_helpers(self):
        self.process(1201, 'kwin_wayland', ['/usr/bin/kwin_wayland'], 'plasma-kwin_wayland.service')
        self.process(1300, 'plasmashell', ['/usr/bin/plasmashell'], 'plasma-plasmashell.service')
        self.process(1400, 'Xwayland', ['/usr/bin/Xwayland', ':0'], 'plasma-kwin_wayland.service', ppid=1201)
        self.assertEqual(use.owner(1201, self.proc), ('part:windows', 'kwin_wayland', 'windows'))
        self.assertEqual(use.owner(1300, self.proc)[2], 'desktop')
        self.assertEqual(use.owner(1400, self.proc)[2], 'xwayland')
        # Steam itself is Steam; a game it started is named for itself, a Windows one without .exe.
        self.process(500, 'steam', ['/home/me/.local/share/Steam/ubuntu12_32/steam'], 'app-steam@autostart.service')
        self.process(600, 'GameThread', ['/home/me/Games/Hollow Knight/hollow_knight.x86_64'],
                     'app-steam@autostart.service', ppid=500)
        self.process(700, 'Cyberpunk2077.e', ['Z:\\home\\me\\Cyberpunk2077.EXE', '--launcher-skip'],
                     'app-steam@autostart.service', ppid=500)
        self.assertEqual(use.owner(500, self.proc)[1], 'Steam')
        self.assertEqual(use.owner(600, self.proc)[1], 'hollow_knight.x86_64')
        self.assertEqual(use.owner(700, self.proc)[1], 'Cyberpunk2077')
        # A web view's renderer counts as the app that opened it, here a service of its own.
        self.process(800, 'TrueBorders', ['/home/me/True Borders/TrueBorders'], 'true-borders.service')
        self.process(801, 'QtWebEngineProc', ['/usr/lib64/qt6/libexec/QtWebEngineProcess', '--type=zygote'],
                     'true-borders.service', ppid=800)
        self.process(802, 'QtWebEngineProc', ['/usr/lib64/qt6/libexec/QtWebEngineProcess', '--type=gpu-process'],
                     'true-borders.service', ppid=801)
        self.assertEqual(use.owner(802, self.proc), ('program:TrueBorders', 'TrueBorders', ''))
        # Gone already: still a name, never an error.
        self.assertEqual(use.owner(9999, self.proc), ('program:9999', '9999', ''))

    def test_the_helper_prints_its_json_contract(self):
        done = subprocess.run([sys.executable, str(ROOT / 'linux/libexec/monet-graphics-use')], capture_output=True,
                              text=True, timeout=30, env=dict(os.environ, PATH='/nonexistent'))
        self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result['version'], 1)
        self.assertIsInstance(result['ok'], bool)
        self.assertIsInstance(result['apps'], list)


@unittest.skipUnless(os.environ.get('MONET_GRAPHICS_FIXTURE'), 'compiled Graphics column (the desktop test image)')
class NativeColumn(unittest.TestCase):
    def test_kdes_own_process_model_shows_each_processs_share(self):
        fixture = Path(os.environ['MONET_GRAPHICS_FIXTURE'])
        done = subprocess.run(['sh', str(fixture.with_name('run.sh')), str(fixture)], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class GraphicsColumn(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('graphics_bundle', ROOT / 'image/graphics/bundle.py')
        self.bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bundle)

    def test_the_process_library_is_found_by_whichever_major_version_is_here(self):
        with tempfile.TemporaryDirectory() as folder:
            lib = Path(folder)
            for name in ('libprocesscore.so.10', 'libprocesscore.so.10.6.8', 'libprocesscore.so'):
                (lib / name).write_text('')
            self.assertEqual(self.bundle.libraries(lib), ('libQt6Core.so.6', 'libKF6CoreAddons.so.6', 'libKF6I18n.so.6',
                                                          'libprocesscore.so.10'))
            (lib / 'libprocesscore.so.11').write_text('')
            with self.assertRaises(ValueError):
                self.bundle.libraries(lib)  # two at once: which one the plugin was built for is unclear
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            self.bundle.libraries(Path(folder))

    def test_pages_show_it_beside_cpu_and_memory_and_it_is_built_and_tested(self):
        pages = ROOT / 'linux/share/plasma-systemmonitor'
        for page, face, first in (('monet-applications.page', '94920553440704', 'appName'),
                                  ('monet-processes.page', '94051759765872', 'name')):
            text = (pages / page).read_text()
            # KDE's table reads a face's columns from [Face-ID][FaceConfig][General].
            group = text.split(f'[Face-{face}][FaceConfig][General]\n', 1)[1].split('\n[', 1)[0]
            settings = dict(line.split('=', 1) for line in group.splitlines() if '=' in line)
            columns = settings['sortedColumns'].split(',')
            self.assertEqual(columns[:4], [first, 'usage', 'vmPSS', 'monetGraphics'], page)
            widths = [float(w) for w in settings['columnWidths'].split(',')]
            self.assertEqual(len(widths), len(columns), page)
            self.assertAlmostEqual(sum(widths), 1.0, places=6)
            self.assertEqual(set(json.loads(settings['columnDisplay'])), set(columns), page)
        source = (ROOT / 'image/graphics/monetgraphics.cpp').read_text()
        self.assertIn('QStringLiteral("monetGraphics"), i18nd("monet", "Graphics")', source)
        self.assertIn('m_watch->setArguments({QStringLiteral("--watch")});', source)
        self.assertIn('"/usr/libexec/monet-graphics-use"', (ROOT / 'image/graphics/CMakeLists.txt').read_text())
        image = (ROOT / 'image/Containerfile').read_text()
        self.assertIn('FROM runtime AS graphics\nCOPY image/graphics /src/graphics', image)
        self.assertIn('python3 /tmp/monet-graphics/bundle.py install /tmp/monet-graphics', image)
        tests = (ROOT / 'tests/Containerfile').read_text()
        self.assertIn('RUN MONET_GRAPHICS_TESTING=1 sh /src/graphics/build.sh /out', tests)
        self.assertIn('ENV MONET_GRAPHICS_FIXTURE=/opt/monet-test-graphics/graphics-column-test', tests)
        self.assertIn('image/graphics', (ROOT / 'tools/make-translations.py').read_text())


class TaskManager(unittest.TestCase):
    def test_the_graphics_page_lists_apps_only_while_in_view(self):
        ui = ROOT / 'linux/share/ksysguard/sensorfaces/org.monet.performance/contents/ui'
        page = (ui / 'Performance.qml').read_text()
        self.assertIn('GraphicsApps {', page)
        self.assertIn('visible: dashboard.section === 2', page)
        self.assertIn('sampling: visible && dashboard.monitoringActive && !dashboard.paused', page)
        apps = (ui / 'GraphicsApps.qml').read_text()
        self.assertIn('property string helper: "@LIBEXECDIR@/monet-graphics-use"', apps)
        self.assertIn('Timer { interval: 2000; repeat: true; running: use.sampling; onTriggered: use.refresh() }', apps)
        self.assertIn('if (busy || !sampling) return', apps)
        for part in ('"windows"', '"desktop"', '"xwayland"'):
            self.assertIn('app.part === ' + part, apps)
        install = (ROOT / 'linux/install.sh').read_text()
        uninstall = (ROOT / 'linux/uninstall.sh').read_text()
        self.assertRegex(install, r'for tool in [^\n]* monet-graphics-use [^\n]*; do\n    put 755 "\$SRC/libexec/\$tool"')
        self.assertRegex(uninstall, r'for tool in [^\n]* monet-graphics-use ')
        self.assertTrue(os.access(ROOT / 'linux/libexec/monet-graphics-use', os.X_OK))
        self.assertIn("'monet-graphics-use'", (ROOT / 'tools/install-desktop-preview.py').read_text())
        self.assertTrue(re.search(r'fill "\$DATADIR"/ksysguard/sensorfaces/org\.monet\.\*/contents/ui/\*\.qml', install))


PCI_IDS = """# The PCI ID list's own form: vendors, their devices indented, subsystems twice.
1002  Advanced Micro Devices, Inc. [AMD/ATI]
\t13c0  Granite Ridge [Radeon Graphics]
\t164e  Raphael
\t15bf  Phoenix1 [Radeon 780M]
\t744c  Navi 31 [Radeon RX 7900 XT/7900 XTX/7900M]
\t\t1002 0e3b  Radeon RX 7900 GRE
10de  NVIDIA Corporation
\t2c02  GB203 [GeForce RTX 5080]
\t1e87  TU104M [GeForce RTX 2080 Mobile]
8086  Intel Corporation
\t3e9b  CoffeeLake-H GT2 [UHD Graphics 630]
\t56a0  DG2 [Arc A770]
C 03  Display controller
"""


class Devices(unittest.TestCase):
    """Task Manager's device list names each graphics device as KDE counts them, so the graphics
    built into the processor isn't just "GPU 2"."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.ids = self.root / 'pci.ids'
        self.ids.write_text(PCI_IDS)
        (self.root / 'bus').mkdir()

    def device(self, path, vendor, device, kind='0x030000'):
        folder = self.root / 'devices' / path
        folder.mkdir(parents=True)
        for name, value in (('vendor', vendor), ('device', device), ('class', kind)):
            (folder / name).write_text(value + '\n')
        (self.root / 'bus' / folder.name).symlink_to(folder)

    def named(self):
        return use.devices(self.root / 'bus', (self.ids,))

    def test_a_desktop_with_an_nvidia_card_and_the_processors_own_graphics(self):
        # KDE's order is the devices' place in /sys/devices: the card on 00:01.1 before 00:08.1.
        self.device('pci0000:00/0000:00:08.1/0000:7c:00.0', '0x1002', '0x164e')
        self.device('pci0000:00/0000:00:01.1/0000:01:00.0', '0x10de', '0x2c02')
        self.device('pci0000:00/0000:00:14.3', '0x8086', '0x51f0', '0x028000')  # Wi-Fi: not graphics
        self.assertEqual(self.named(), [
            {'id': 'gpu0', 'maker': 'NVIDIA', 'name': 'NVIDIA GeForce RTX 5080', 'builtIn': False},
            {'id': 'gpu1', 'maker': 'AMD', 'name': 'AMD Radeon Graphics', 'builtIn': True}])

    def test_a_laptop_with_intel_graphics_and_an_nvidia_chip(self):
        self.device('pci0000:00/0000:00:02.0', '0x8086', '0x3e9b')
        self.device('pci0000:00/0000:00:01.0/0000:01:00.0', '0x10de', '0x1e87', '0x030200')
        self.assertEqual(self.named(), [
            {'id': 'gpu0', 'maker': 'NVIDIA', 'name': 'NVIDIA GeForce RTX 2080 Mobile', 'builtIn': False},
            {'id': 'gpu1', 'maker': 'Intel', 'name': 'Intel UHD Graphics 630', 'builtIn': True}])

    def test_cards_and_built_in_graphics_are_told_apart(self):
        self.device('pci0000:00/0000:00:01.1/0000:01:00.0/0000:02:00.0/0000:03:00.0', '0x1002', '0x744c')
        self.device('pci0000:00/0000:00:01.2/0000:04:00.0', '0x8086', '0x56a0')
        self.device('pci0000:00/0000:00:08.1/0000:c5:00.0', '0x1002', '0x15bf')
        self.device('pci0000:00/0000:00:08.1/0000:c6:00.0', '0x1002', '0x13c0')
        self.device('pci0000:00/0000:00:09.0/0000:07:00.0', '0x1a03', '0x2000')  # a server's own: KDE skips it
        self.assertEqual([(d['name'], d['builtIn']) for d in self.named()], [
            ('AMD Radeon RX 7900 XT/7900 XTX/7900M', False), ('Intel Arc A770', False),
            ('AMD Radeon 780M', True), ('AMD Radeon Graphics', True)])

    def test_a_device_the_list_does_not_know_is_named_for_its_maker(self):
        self.device('pci0000:00/0000:00:08.1/0000:7c:00.0', '0x1002', '0x9999')
        self.ids.unlink()
        self.assertEqual(self.named(), [{'id': 'gpu0', 'maker': 'AMD', 'name': 'AMD Radeon Graphics', 'builtIn': True}])

    def test_the_helper_prints_them(self):
        shown = subprocess.run([sys.executable, str(ROOT / 'linux/libexec/monet-graphics-use'), '--devices'],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        result = json.loads(shown.stdout)
        self.assertEqual(result['version'], 1)
        self.assertIsInstance(result['devices'], list)


class DeviceList(unittest.TestCase):
    """The device list leaves out KDE's sum of all devices and names each from the helper."""

    page = (ROOT / 'linux/share/ksysguard/sensorfaces/org.monet.performance/contents/ui/Performance.qml').read_text()

    def test_the_sum_of_all_devices_is_not_a_device(self):
        self.assertIn(r'/^gpu\/(?!all\/)[^/]+\/usage$/', self.page)
        self.assertIn('namer.connectSource("\'" + helper.replace(', self.page)
        self.assertIn("' --devices\")", self.page)
        self.assertIn('displayText: dashboard.graphicsLabel(currentIndex, gpuName.value)', self.page)
        self.assertIn('text: dashboard.graphicsLabel(index, deviceName.value)', self.page)

    def test_each_device_is_labelled_as_people_know_it(self):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            self.skipTest('requires PySide6')
        self.app = QCoreApplication.instance() or QCoreApplication([])
        body = re.search(r'    function graphicsLabel\(index, kdeName\) \{\n.*?\n    \}\n', self.page, re.S)[0]
        engine = QJSEngine()
        engine.evaluate('function i18nd(domain, text, value) { return text.replace("%1", value) }')
        def label(graphics, named, index, kde):
            script = ('(function() { const graphics = %s; const graphicsNamed = %s;\n%s\nreturn graphicsLabel(%d, %s) })()'
                      % (json.dumps(graphics), json.dumps(named), body, index, json.dumps(kde)))
            value = engine.evaluate(script)
            self.assertFalse(value.isError(), value.toString())
            return value.toString()
        desktop = ['gpu/gpu0/usage', 'gpu/gpu1/usage']
        named = [{'id': 'gpu0', 'maker': 'NVIDIA', 'name': 'NVIDIA GeForce RTX 5080', 'builtIn': False},
                 {'id': 'gpu1', 'maker': 'AMD', 'name': 'AMD Radeon Graphics', 'builtIn': True}]
        self.assertEqual(label(desktop, named, 0, 'NVIDIA GeForce RTX 5080'), 'NVIDIA GeForce RTX 5080')
        self.assertEqual(label(desktop, named, 1, 'GPU 2'), 'AMD Radeon Graphics (built into the processor)')
        self.assertEqual(label(desktop, named, 1, 'Raphael'), 'AMD Radeon Graphics (built into the processor)')
        # Until the helper answers, or where it counted another way, KDE's own names stand.
        self.assertEqual(label(desktop, [], 1, 'GPU 2'), 'GPU 2')
        self.assertEqual(label(desktop, named[:1], 1, 'GPU 2'), 'GPU 2')
        swapped = [dict(named[1], id='gpu0'), dict(named[0], id='gpu1')]
        self.assertEqual(label(desktop, swapped, 0, 'NVIDIA GeForce RTX 5080'), 'NVIDIA GeForce RTX 5080')
        self.assertEqual(label(desktop, [], 0, ''), 'Graphics device 1')


if __name__ == '__main__':
    unittest.main()
