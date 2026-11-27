"""Boot policy, recovery and transactional rollback without touching host firmware."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fast_boot', ROOT/'tools/install-fast-boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
CONFIG = '''source ${prefix}/user.cfg
### BEGIN 08_greenboot.cfg ###
if [ -n "${boot_counter}" -a "${boot_success}" = "0" ]; then
  save_env boot_counter
fi
set boot_success=0
blscfg
### BEGIN 14_menu_show_once.cfg ###
'''
EFI = 'BootCurrent: 0000\nTimeout: 2 seconds\nBootOrder: 0000,0002\nBoot0000* Monet\tHD(1)\n'


class Policy(unittest.TestCase):
    def evaluate(self, **state):
        # This profile uses the common shell/GRUB if syntax. Adapt only GRUB's
        # assignment builtin; run the actual conditions, not a Python duplicate.
        shell = '''set() { export "$1"; }
save_env() { printf 'saved_%s=%s\\n' "$1" "${!1}"; }
''' + boot.PROFILE + '''
# bootupd applies this after user.cfg and greenboot.
if [ "${menu_show_once_timeout}" ]; then
  set timeout_style=menu
  set timeout="${menu_show_once_timeout}"
fi
printf 'timeout=%s\\nstyle=%s\\ncounter=%s\\n' "$timeout" "$timeout_style" "$boot_counter"
'''
        env = dict(os.environ, boot_success='', boot_counter='', menu_show_once_timeout='', **{})
        env.update(state)
        output = subprocess.check_output(['bash', '-c', shell], env=env, text=True)
        return dict(line.split('=', 1) for line in output.splitlines())

    def test_healthy_boot_skips_menu_and_marks_attempt_incomplete(self):
        result = self.evaluate(boot_success='1')
        self.assertEqual(result['timeout'], '0')
        self.assertEqual(result['saved_boot_success'], '0')

    def test_failed_or_unknown_boot_keeps_recovery_menu(self):
        for success in ('', '0', 'unknown'):
            with self.subTest(success=success):
                self.assertEqual(self.evaluate(boot_success=success)['timeout'], '10')

    def test_all_trial_counter_states_retain_upstream_ownership(self):
        for success in ('0', '1'):
            for counter in ('3', '2', '1', '0', '-1'):
                with self.subTest(success=success, counter=counter):
                    result = self.evaluate(boot_success=success, boot_counter=counter)
                    self.assertEqual(result['timeout'], '10')
                    self.assertEqual(result['counter'], counter)
                    self.assertNotIn('saved_boot_success', result)
                    self.assertNotIn('saved_boot_counter', result)

    def test_explicit_menu_request_wins_on_healthy_and_trial_boots(self):
        for counter in ('', '3', '-1'):
            result = self.evaluate(boot_success='1', boot_counter=counter, menu_show_once_timeout='30')
            self.assertEqual(result['timeout'], '30')
            self.assertEqual(result['style'], 'menu')

    def test_grub_parser_accepts_the_real_profile(self):
        checker = shutil.which('grub2-script-check') or shutil.which('grub-script-check')
        if not checker:
            self.skipTest('GRUB parser unavailable')
        result = subprocess.run([checker], input=boot.PROFILE, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_authentication_settings_survive_repeat_install(self):
        existing = '# Local policy\nset GRUB2_PASSWORD=example-test-hash\n'
        rendered = boot.render(existing)
        self.assertIn(existing, rendered)
        self.assertEqual(boot.render(rendered), rendered)
        self.assertEqual(rendered.count(boot.BEGIN), 1)

    def test_conflicting_or_broken_boot_policies_are_rejected(self):
        for existing in ('set timeout=8\n', 'set saved_entry=windows\n', boot.BEGIN,
                         boot.END+'\n'+boot.BEGIN, boot.PROFILE+boot.PROFILE):
            with self.subTest(existing=existing):
                with self.assertRaises(ValueError): boot.render(existing)

    def test_upstream_hook_order_must_match(self):
        boot.validate_config(CONFIG)
        with self.assertRaises(ValueError): boot.validate_config(CONFIG.replace('blscfg', ''))
        with self.assertRaises(ValueError):
            boot.validate_config(CONFIG.replace('source ${prefix}/user.cfg', '')+'source ${prefix}/user.cfg')

    def test_boot_order_must_already_point_to_monet(self):
        self.assertEqual(boot.efi_state(EFI)['timeout'], 2)
        for changed in (EFI.replace('Monet', 'Windows'), EFI.replace('0000,0002', '0002,0000'),
                        EFI.replace('Timeout: 2 seconds', '')):
            with self.assertRaises(ValueError): boot.efi_state(changed)


class Installation(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for name, value in {'BIOS': self.root/'bios', 'STATE': self.root/'state',
                            'USER': self.root/'user.cfg', 'CONFIG': self.root/'grub.cfg'}.items():
            p = patch.object(boot, name, value); p.start(); self.addCleanup(p.stop)
        boot.CONFIG.write_text(CONFIG)
        self.original = '# Existing local setting\nset GRUB2_PASSWORD=test-only\n'
        boot.USER.write_text(self.original)
        for n in boot.NETWORK:
            (boot.BIOS/n).mkdir(parents=True)
            (boot.BIOS/n/'current_value').write_text('Enable\n')
        self.before = {'bios': {n: 'Enable' for n in boot.NETWORK},
                       'efi': {'timeout': 2, 'order': '0000,0002', 'current': '0000'},
                       'grubenv': 'boot_success=1\nboot_counter=3',
                       'boot_files': {'grub.cfg': boot.digest(CONFIG.encode())},
                       'pending_reboot': '0'}
        self.after = copy.deepcopy(self.before)
        self.after['bios'] = {n: 'Disable' for n in boot.NETWORK}
        self.after['efi']['timeout'] = 0
        self.after['pending_reboot'] = '1'
        self.efi_timeout = 2
        self.calls = []

    def command(self, *args):
        self.calls.append(args)
        if args == ('efibootmgr',): return EFI.replace('Timeout: 2 seconds', f'Timeout: {self.efi_timeout} seconds')
        if args[:2] == ('efibootmgr', '--timeout'): self.efi_timeout = int(args[2])
        return ''

    def install(self, *, after=None, command=None):
        with patch.object(boot, 'snapshot', side_effect=[self.before, after or self.after]), \
                patch.object(boot, 'validate_firmware'), patch.object(boot, 'run', side_effect=command or self.command), \
                contextlib.redirect_stdout(io.StringIO()):
            boot.install()

    def receipt(self):
        return json.loads(next(boot.STATE.glob('*/receipt.json')).read_text())

    def test_install_and_restore_preserve_original_config_and_firmware(self):
        self.install()
        self.assertEqual(self.receipt()['status'], 'installed')
        self.assertEqual(boot.CONFIG.read_text(), CONFIG)
        self.assertEqual(self.efi_timeout, 0)
        self.assertEqual(boot.USER.read_text(), boot.render(self.original))
        with patch.object(boot, 'run', side_effect=self.command): boot.revert(self.receipt())
        self.assertEqual(boot.USER.read_text(), self.original)
        self.assertEqual(self.efi_timeout, 2)
        for n in boot.NETWORK: self.assertEqual(boot.bios_value(n), 'Enable')
        self.assertFalse(any(c[0] == 'grub2-editenv' for c in self.calls))

    def test_rollback_when_verification_detects_changed_boot_entry(self):
        after = copy.deepcopy(self.after); after['boot_files']['grub.cfg'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'boot_files'): self.install(after=after)
        self.assertEqual(self.receipt()['status'], 'reverted-after-failure')
        self.assertEqual(boot.USER.read_text(), self.original)
        self.assertEqual(self.efi_timeout, 2)
        for n in boot.NETWORK: self.assertEqual(boot.bios_value(n), 'Enable')

    def test_rollback_when_efi_write_fails_after_bios_changes(self):
        def fail(*args):
            if args == ('efibootmgr', '--timeout', '0'): raise OSError('Simulated firmware failure')
            return self.command(*args)
        with self.assertRaises(OSError): self.install(command=fail)
        self.assertEqual(self.receipt()['status'], 'reverted-after-failure')
        self.assertEqual(boot.USER.read_text(), self.original)
        for n in boot.NETWORK: self.assertEqual(boot.bios_value(n), 'Enable')

    def test_restore_does_not_overwrite_a_later_user_edit(self):
        self.install()
        boot.USER.write_text('set timeout=42\n')
        with patch.object(boot, 'run', side_effect=self.command):
            with self.assertRaisesRegex(ValueError, 'not overwritten'): boot.revert(self.receipt())
        self.assertEqual(boot.USER.read_text(), 'set timeout=42\n')

    def test_new_file_is_removed_on_restore(self):
        boot.USER.unlink()
        self.install()
        with patch.object(boot, 'run', side_effect=self.command): boot.revert(self.receipt())
        self.assertFalse(boot.USER.exists())

    def test_symlink_is_rejected_before_any_hardware_access(self):
        boot.USER.unlink(); boot.USER.symlink_to(boot.CONFIG)
        with patch.object(boot, 'snapshot') as snap:
            with self.assertRaises(ValueError): boot.install()
            snap.assert_not_called()


if __name__ == '__main__':
    unittest.main()
