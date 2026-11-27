"""Policy regeneration remains intact and precedes the deployment marker."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boot_prepare', ROOT / 'image/boot/prepare.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)

UNIT = '''[Unit]
DefaultDependencies=no
Requires=local-fs.target
After=local-fs.target
Before=sysinit.target
ConditionPathIsMountPoint=/sysroot
ConditionPathExists=/usr/bin/update-crypto-policies
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -ec 'policy=$(/usr/bin/update-crypto-policies --show); exec /usr/bin/update-crypto-policies --set "$$policy"'
'''


class CryptoPolicyLifecycle(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.unit = self.root / 'usr/lib/systemd/system/bootc-update-crypto-policies.service'
        self.unit.parent.mkdir(parents=True)
        self.unit.write_text(UNIT)
        self.dropin = self.unit.with_name(self.unit.name + '.d') / '50-monet-deployment.conf'

    def test_preserves_policy_command_and_prerequisites_on_repeated_preparation(self):
        for _ in range(2):
            boot.prepare_crypto_policy(self.root)
            self.assertEqual(self.unit.read_text(), UNIT)
            self.assertIn('ConditionNeedsUpdate=/etc\n', self.dropin.read_text())
            self.assertIn('Before=systemd-update-done.service\n', self.dropin.read_text())

    def test_upstream_command_and_ordering_changes_require_review(self):
        for changed in (UNIT.replace('--show', '--check'),
                        UNIT.replace('After=local-fs.target\n', ''),
                        UNIT + 'ExecStartPost=/usr/bin/true\n'):
            self.unit.write_text(changed)
            with self.assertRaises(ValueError):
                boot.prepare_crypto_policy(self.root)
            self.assertFalse(self.dropin.exists())

    def test_custom_overrides_are_not_overwritten(self):
        self.dropin.parent.mkdir()
        self.dropin.write_text('[Unit]\nConditionNeedsUpdate=/var\n')
        with self.assertRaises(ValueError):
            boot.prepare_crypto_policy(self.root)
        self.assertIn('/var', self.dropin.read_text())

    def test_symlinked_destinations_are_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.dropin.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            boot.prepare_crypto_policy(self.root)
        self.assertEqual(list(outside.parent.glob('outside/*')), [])

    def test_images_without_the_legacy_service_are_unchanged(self):
        self.unit.unlink()
        boot.prepare_crypto_policy(self.root)
        self.assertFalse(self.dropin.parent.exists())


if __name__ == '__main__':
    unittest.main()
