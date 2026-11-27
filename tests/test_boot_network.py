"""Health checks may skip a network wait, never the checks themselves."""
import hashlib
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.test_boot_graphics import boot

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('monet_boot_network', str(ROOT/'linux/libexec/monet-boot-network'))
guard = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(guard)


class BootNetwork(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root/'etc/ostree/remotes.d').mkdir(parents=True)
        self.checks = self.root/'usr/lib/greenboot/check/required.d'; self.checks.mkdir(parents=True)
        self.script = self.checks/'02_watchdog.sh'; self.script.write_text('local check')
        known = patch.object(guard, 'KNOWN', {self.script.name: hashlib.sha256(self.script.read_bytes()).hexdigest()})
        known.start(); self.addCleanup(known.stop)

    def test_local_checks_skip_wait_and_remote_configuration_restores_it(self):
        self.assertFalse(guard.needs_network(self.root))
        (self.root/'etc/ostree/remotes.d/repo.conf').write_text('[remote example]')
        self.assertTrue(guard.needs_network(self.root))

    def test_changed_or_new_health_check_keeps_network_dependency(self):
        self.script.write_text('new upstream code')
        self.assertTrue(guard.needs_network(self.root))
        self.script.write_text('local check')
        (self.checks/'custom-check').write_text('curl example.invalid')
        self.assertTrue(guard.needs_network(self.root))

    def test_optional_and_local_scripts_are_not_assumed_offline(self):
        for directory in ('etc/greenboot/check/required.d', 'etc/greenboot/check/wanted.d', 'usr/lib/greenboot/check/wanted.d'):
            with self.subTest(directory=directory):
                p = self.root/directory; p.mkdir(parents=True, exist_ok=True)
                check = p/'custom'; check.write_text('custom check')
                self.assertTrue(guard.needs_network(self.root)); check.unlink()
                self.assertFalse(guard.needs_network(self.root))

    def test_shell_in_configuration_retains_network_ordering(self):
        config = self.root/'etc/greenboot/greenboot.conf'; config.parent.mkdir(parents=True)
        config.write_text('GREENBOOT_WATCHDOG_GRACE_PERIOD=1\nGREENBOOT_WATCHDOG_CHECK_ENABLED=true\nDISABLED_HEALTHCHECKS=("01_repository_dns_check.sh")\n')
        self.assertFalse(guard.needs_network(self.root))
        config.write_text('source /etc/custom-script\n')
        self.assertTrue(guard.needs_network(self.root))

    def test_explicitly_disabled_optional_check_does_not_hold_boot(self):
        directory = self.root/'usr/lib/greenboot/check/wanted.d'; directory.mkdir()
        (directory/'network-check').write_text('network')
        config = self.root/'etc/greenboot/greenboot.conf'; config.parent.mkdir(parents=True)
        config.write_text('DISABLED_HEALTHCHECKS=("network-check")')
        self.assertFalse(guard.needs_network(self.root))
        config.write_text('DISABLED_HEALTHCHECKS=()')
        self.assertTrue(guard.needs_network(self.root))

    def test_preparation_keeps_healthcheck_and_rollback_unit_untouched(self):
        unit = self.root/'usr/lib/systemd/system/greenboot-healthcheck.service'
        unit.parent.mkdir(parents=True); unit.write_text('Before=boot-complete.target\nExecStart=/usr/libexec/greenboot/greenboot health-check\n')
        dropin = unit.with_name(unit.name+'.d')/'10-network-online.conf'; dropin.parent.mkdir()
        vendor = '[Unit]\nAfter=network-online.target\nWants=network-online.target\n'; dropin.write_text(vendor)
        original = unit.read_bytes()
        boot.prepare_healthcheck(self.root)
        self.assertEqual(unit.read_bytes(), original)
        self.assertIn('ExecStartPre=/usr/libexec/monet-boot-network', dropin.read_text())
        self.assertNotIn('Wants=', dropin.read_text())
        boot.prepare_healthcheck(self.root)  # idempotent
        dropin.write_text(vendor)
        boot.prepare_healthcheck(self.root, '/usr/local/libexec', local=True)
        self.assertEqual(dropin.read_text(), vendor)
        override = self.root/'etc/systemd/system/greenboot-healthcheck.service.d/10-network-online.conf'
        self.assertIn('/usr/local/libexec', override.read_text())
        override.write_text('custom')
        with self.assertRaises(ValueError): boot.prepare_healthcheck(self.root, local=True)
