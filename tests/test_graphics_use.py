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


if __name__ == '__main__':
    unittest.main()
