"""Hardware snapshots count shared topology accurately without probing devices."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('monet_system_info', str(ROOT / 'linux/libexec/monet-system-info'))
spec = importlib.util.spec_from_loader(loader.name, loader)
info = importlib.util.module_from_spec(spec)
loader.exec_module(info)


class HardwareSnapshot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def test_hybrid_topology_and_shared_caches_are_not_double_counted(self):
        self.put('proc/cpuinfo', 'processor : 0\nmodel name : Test Hybrid\nflags : vmx avx\n')
        base = 'sys/devices/system/cpu/'
        self.put(base + 'online', '0-2')
        self.put(base + 'present', '0-3')
        for ident, core, siblings in [(0, 0, '0-1'), (1, 0, '0-1'), (2, 1, '2'), (3, 2, '3')]:
            prefix = base + f'cpu{ident}/'
            self.put(prefix + 'topology/physical_package_id', '0')
            self.put(prefix + 'topology/core_id', str(core))
            self.put(prefix + 'topology/thread_siblings_list', siblings)
            self.put(prefix + 'cpufreq/cpuinfo_max_freq', '5200000')
            for index, level, sharing, size in [(0, '1', siblings, '48K'), (1, '3', '0-3', '24M')]:
                for key, value in dict(level=level, type='Unified', shared_cpu_list=sharing, size=size).items():
                    self.put(prefix + f'cache/index{index}/' + key, value)
        cpu = info.snapshot(self.root)['cpu']
        self.assertEqual((cpu['cores'], cpu['logical'], cpu['online'], cpu['sockets']), (3, 4, 3, 1))
        self.assertEqual(cpu['maxMHz'], 5200)
        self.assertEqual(cpu['models'], ['Test Hybrid'])
        self.assertEqual(cpu['caches'][0]['bytes'], 3 * 48 * 1024)
        self.assertEqual(cpu['caches'][1]['bytes'], 24 * 1024 ** 2)
        self.assertEqual(cpu['caches'][1]['instances'], 1)
        self.assertFalse(cpu['topology'][-1]['online'])

    def test_unknown_topology_stays_unknown(self):
        self.put('sys/devices/system/cpu/present', '0-1')
        self.put('sys/devices/system/cpu/cpu0/topology/physical_package_id', '-1')
        cpu = info.snapshot(self.root)['cpu']
        self.assertIsNone(cpu['cores'])
        self.assertIsNone(cpu['sockets'])
        self.assertIsNone(cpu['maxMHz'])
        self.assertEqual(cpu['caches'], [])

    def test_pci_driver_identity_uses_files_and_preserves_missing_versions(self):
        device = self.root / 'sys/class/drm/card0/device'
        self.put('sys/class/drm/card0/device/vendor', '0x10de')
        self.put('sys/class/drm/card0/device/device', '0x1234')
        self.put('sys/class/drm/card0/device/power/runtime_status', 'suspended')
        driver = self.root / 'sys/bus/pci/drivers/example'
        driver.mkdir(parents=True)
        (device / 'driver').symlink_to(driver)
        self.put('usr/share/hwdata/pci.ids', '10de  NVIDIA\n\t1234  Example GPU\n\t\t0000 0000  Subsystem\n')
        self.put('sys/class/drm/card0-HDMI-A-1/status', 'connected')
        gpu, = info.snapshot(self.root)['graphics']
        self.assertEqual(gpu['model'], 'Example GPU')
        self.assertEqual(gpu['driver'], 'example')
        self.assertEqual(gpu['driverVersion'], '')
        self.assertEqual(gpu['runtime'], 'suspended')

    def test_memory_disk_and_release_are_data_not_commands(self):
        self.put('proc/meminfo', 'MemTotal: 12345 kB\nSwapTotal: 0 kB\nMemFree: 900 kB\n')
        self.put('etc/os-release', 'PRETTY_NAME="Monet $(touch nope)"\nBAD="unterminated\n')
        self.put('sys/class/block/nvme0n1/device/model', 'Test drive')
        self.put('sys/class/block/nvme0n1/size', '1000')
        self.put('sys/class/block/nvme0n1/queue/rotational', '0')
        self.put('sys/class/block/nvme0n1p1/partition', '1')
        self.put('sys/class/net/eth0/carrier', '0')
        self.put('sys/class/net/eth0/speed', '-1')
        result = info.snapshot(self.root)
        self.assertEqual(result['memory'], {'MemTotal': 12345 * 1024, 'SwapTotal': 0})
        self.assertEqual(result['system']['os'], 'Monet $(touch nope)')
        self.assertEqual(len(result['disks']), 1)
        self.assertEqual(result['disks'][0]['bytes'], 512000)
        self.assertIsNone(result['networks'][0]['speedMbps'])

    def test_malformed_cpu_ranges_are_bounded(self):
        self.assertEqual(info.cpu_list('1-3,3,9,5-2,0-99999999,nope,-1'), [1, 2, 3, 9])
        self.assertEqual(info.read(self.root / 'missing'), '')

    def test_image_page_install_preserves_existing_kde_and_custom_pages(self):
        source = (ROOT / 'linux/install.sh').read_text()
        start = source.index('install -d "$DATADIR/plasma-systemmonitor"')
        end = source.index('\ntree ', start)
        directory = self.root / 'share/plasma-systemmonitor'
        directory.mkdir(parents=True)
        for name in ('applications.page', 'processes.page', 'personal.page'):
            (directory / name).write_text('Keep my original layout')
        subprocess.run(['bash', '-eu', '-c', source[start:end]], check=True,
                       env={'PATH': '/usr/bin:/bin', 'SRC': str(ROOT / 'linux'), 'DATADIR': str(self.root / 'share')})
        for name in ('applications.page', 'processes.page', 'personal.page'):
            self.assertEqual((directory / name).read_text(), 'Keep my original layout')
        self.assertTrue((directory / 'monet-system.page').exists())

    @unittest.skipUnless(shutil.which('plasma-systemmonitor'), 'native Task Manager executable')
    def test_preview_launcher_keeps_arguments_names_and_existing_interfaces(self):
        loader = importlib.machinery.SourceFileLoader('preview_test', str(ROOT / 'tools/install-desktop-preview.py'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        preview = importlib.util.module_from_spec(spec)
        loader.exec_module(preview)
        preview.DATA = self.root / 'data'
        path = preview.DATA / 'applications/org.kde.plasma-systemmonitor.desktop'
        path.parent.mkdir(parents=True)
        path.write_text('[Desktop Entry]\nName=My monitor\nExec=plasma-systemmonitor --page-id personal.page\n'
                        'Icon=my-icon\nX-KDE-Wayland-Interfaces=existing_protocol\n'
                        '[Desktop Action test]\nExec=plasma-systemmonitor --page-id processes.page\n')
        plan = preview.plan()
        contents = plan[path][0].decode()
        self.assertIn('Name=My monitor\n', contents)
        self.assertIn('Icon=my-icon\n', contents)
        self.assertIn('X-KDE-Wayland-Interfaces=existing_protocol,org_kde_plasma_window_management\n', contents)
        self.assertRegex(contents, r'Exec=/[^\n]+/plasma-systemmonitor --page-id personal.page\n')
        self.assertIn('[Desktop Action test]\nExec=plasma-systemmonitor --page-id processes.page', contents)
        self.assertIn('Exec=plasma-systemmonitor --page-id personal.page', path.read_text())  # Planning is read-only.
        # Every desktop widget must receive the same guard, not only panel apps.
        for widget in (ROOT / 'linux/share/plasma/plasmoids').glob('org.monet.*'):
            ui = preview.DATA / 'plasma/plasmoids' / widget.name / 'contents/ui'
            self.assertEqual(plan[ui / 'LayoutGuard.qml'][0], (ROOT / 'linux/share/monet/widgets/LayoutGuard.qml').read_bytes())
            self.assertIn(ui / 'GlassSettings.qml', plan)


if __name__ == '__main__':
    unittest.main()
