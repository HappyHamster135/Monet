"""Validate safe GRUB trial inputs, selection, and cancellation behavior."""
import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('startup_trial', ROOT / 'tools/install-startup-image.py')
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)
ENTRY = '''title Monet
version 3
linux /boot/ostree/default-abc/vmlinuz-7
initrd /boot/ostree/default-abc/initramfs-7.img
options root=UUID=abc rw ostree=/ostree/boot.0/default/abc/0 rd.luks.options=tpm2-device=auto
'''
ID = '20261127T125857Z'


class StartupTrial(unittest.TestCase):
    def test_grub_syntax_and_existing_custom_entry_are_preserved(self):
        old = "set fallback=monet-trust\nmenuentry 'Recovery' --id monet-trust { true; }\n"
        out = trial.render(old, trial.boot_entry(ENTRY), ID)
        self.assertTrue(out.startswith(old))
        self.assertIn('rd.luks.options=tpm2-device=auto', out)
        self.assertIn('set fallback=0', out)
        self.assertIn('if [ -z "${boot_counter}" ]; then', out)
        self.assertLess(out.index('unset monet_initrd_trial'), out.index('set default=monet-initrd-trial'))
        self.assertIn('if save_env monet_initrd_trial; then', out)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg') as f:
            f.write(out); f.flush()
            checker = shutil.which('grub2-script-check') or shutil.which('grub-script-check')
            self.assertIsNotNone(checker, 'GRUB syntax checker is required')
            subprocess.run([checker, f.name], check=True, capture_output=True)

    def test_incomplete_ambiguous_and_executable_boot_options_are_rejected(self):
        for text in (ENTRY.replace('initrd ', '#initrd '), ENTRY + 'initrd /other\n',
                     ENTRY.replace('root=UUID=abc', 'root=$(reboot)'),
                     ENTRY.replace(' rw ', ' rw; reboot '),
                     ENTRY.replace('/default-abc/', '/../'),
                     ENTRY.replace('ostree=/ostree/boot.0', 'ostree=/arbitrary')):
            with self.assertRaises(ValueError):
                trial.boot_entry(text)

    def test_trial_ids_and_existing_trial_blocks_are_validated(self):
        entry = trial.boot_entry(ENTRY)
        for identifier in ('../other', 'trial;reboot', '123', ID + '\n'):
            with self.assertRaises(ValueError):
                trial.render('', entry, identifier)
        for old in (trial.BEGIN, trial.END, 'set monet_initrd_trial=other'):
            with self.assertRaises(ValueError):
                trial.render(old, entry, ID)

    def test_cancel_disarms_but_does_not_overwrite_later_grub_edits(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            custom = root/'custom.cfg'; custom.write_text('later user edit\n')
            (root/'custom.cfg.before').write_text('before\n')
            receipt = {'custom_after_sha256': 'different'}
            with patch.object(trial, 'CUSTOM', custom), patch.object(trial, 'env', return_value={}), patch.object(trial, 'run') as run:
                with self.assertRaises(ValueError):
                    trial.cancel(root/'receipt.json', receipt)
                run.assert_called_once_with('grub2-editenv', '-', 'unset', trial.FLAG)
            self.assertEqual(custom.read_text(), 'later user edit\n')

    def test_cancel_refuses_to_disarm_someone_elses_trial(self):
        with patch.object(trial, 'env', return_value={trial.FLAG: 'another'}), patch.object(trial, 'run') as run:
            with self.assertRaises(ValueError):
                trial.cancel(Path('/somewhere')/ID/'receipt.json', {'custom_after_sha256': 'unused'})
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
