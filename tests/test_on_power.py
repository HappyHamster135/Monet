"""Heavy background work waits for the charger, as macOS keeps it for when the battery can take it."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / 'linux/libexec/monet-on-power'


class OnPower(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sys/class/power_supply').mkdir(parents=True)

    def supply(self, name, **values):
        folder = self.root / 'sys/class/power_supply' / name
        folder.mkdir()
        for key, value in values.items():
            (folder / key).write_text(f'{value}\n')

    def may(self, profile='balanced'):
        env = dict(os.environ, MONET_POWER_ROOT=str(self.root), MONET_POWER_PROFILE=profile)
        return subprocess.run(['sh', str(CHECK)], env=env, timeout=10).returncode == 0

    def test_a_desktop_without_a_battery_may(self):
        self.assertTrue(self.may())
        self.assertFalse(self.may('power-saver'))  # but never in Power Saver

    def test_a_laptop_on_battery_waits_unless_half_full(self):
        self.supply('AC', type='Mains', online=0)
        self.supply('BAT0', type='Battery', capacity=35, status='Discharging')
        self.assertFalse(self.may())
        (self.root / 'sys/class/power_supply/BAT0/capacity').write_text('50\n')
        self.assertTrue(self.may())
        self.assertFalse(self.may('s "power-saver"'))  # as busctl reports it

    def test_plugged_in_or_charging_may(self):
        self.supply('AC', type='Mains', online=1)
        self.supply('BAT0', type='Battery', capacity=12, status='Charging')
        self.assertTrue(self.may())
        (self.root / 'sys/class/power_supply/AC/online').write_text('0\n')
        self.assertTrue(self.may())  # still charging (USB-C through another supply)
        self.supply('ucsi-source-psy-USBC000:001', type='USB', online=0)
        (self.root / 'sys/class/power_supply/BAT0/status').write_text('Discharging\n')
        self.assertFalse(self.may())
        (self.root / 'sys/class/power_supply/ucsi-source-psy-USBC000:001/online').write_text('1\n')
        self.assertTrue(self.may())

    def test_a_mouse_battery_is_not_the_pcs(self):
        self.supply('hidpp_battery_0', type='Battery', scope='Device', capacity=5, status='Discharging')
        self.assertTrue(self.may())  # a desktop with a wireless mouse

    def test_the_update_waits_for_it_and_memory_stays_responsive(self):
        service = (ROOT / 'linux/systemd/monet-update.service').read_text()
        self.assertIn('ExecCondition=@LIBEXECDIR@/monet-on-power\n', service)
        tmpfiles = (ROOT / 'linux/tmpfiles/monet-memory.conf').read_text()
        self.assertIn('w- /sys/kernel/mm/lru_gen/min_ttl_ms - - - - 1000\n', tmpfiles)
        install = (ROOT / 'linux/install.sh').read_text()
        self.assertIn('put 644 "$SRC/tmpfiles/monet-memory.conf" "$TMPFILESDIR/monet-memory.conf"', install)
        self.assertIn('TMPFILESDIR=/usr/lib/tmpfiles.d', install)
        self.assertIn(' monet-on-power ', install)
        self.assertIn('/etc/tmpfiles.d/monet-memory.conf', (ROOT / 'linux/uninstall.sh').read_text())
        self.assertTrue(os.access(CHECK, os.X_OK))


if __name__ == '__main__':
    unittest.main()
