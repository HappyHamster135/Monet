"""EFI load options, one-shot selection and write failures without host changes."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('efi_trial', Path(__file__).resolve().parents[1] / 'tools/install-efi-boot-trial.py')
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)
ID = '20261127T150000Z'
PARTUUID = 'bfd99cf8-a424-41d7-923d-3dae7ab638f9'
LOADER = '\\EFI\\fedora\\shimx64.efi'
BASE = 'root=UUID=abc rw ostree=/ostree/boot.0/default/abc/0 rd.luks.uuid=def rd.luks.options=def=tpm2-device=auto'


def option(label='Monet', options='', loader=LOADER, partition=1):
    hd = struct.pack('<BBHIQQ', 4, 1, 42, partition, 2048, 2097152) + uuid.UUID(PARTUUID).bytes_le + b'\2\2'
    text = (loader + '\0').encode('utf-16-le')
    device = hd + struct.pack('<BBH', 4, 4, 4 + len(text)) + text + b'\x7f\xff\4\0'
    return (struct.pack('<IIH', 7, 1, len(device)) + (label + '\0').encode('utf-16-le')
            + device + ((options + '\0').encode('utf-16-le') if options else b''))


def num(value):
    return struct.pack('<IH', 7, value)


class EFITrial(unittest.TestCase):
    def setUp(self):
        self.options = trial.kernel_options('BOOT_IMAGE=/vmlinuz ' + BASE + ' monet.startup_trial=' + ID, BASE, ID)
        self.state = {'Boot0000': option(), 'BootOrder': num(0), 'BootCurrent': num(0)}
        self.before = dict(self.state)
        self.original = trial.load_option(option())
        self.calls = []
        self.fail_next = False
        self.partial_create = False
        self.wrong_partition = False

    def firmware(self, *args):
        self.calls.append(args)
        if '--create-only' in args:
            self.assertEqual(Path(args[args.index('--append-binary-args') + 1]).read_bytes(),
                             (self.options + '\0').encode('utf-16-le'))
            self.state['Boot0001'] = option(trial.LABEL, self.options, partition=2 if self.wrong_partition else 1)
            if self.partial_create:
                raise OSError('Firmware write completed but command failed')
        elif '--bootnext' in args:
            self.state['BootNext'] = num(1)
            if self.fail_next:
                raise OSError('BootNext written before command failure')
        elif '--delete-bootnext' in args:
            self.state.pop('BootNext', None)
        elif '--delete-bootnum' in args:
            self.state.pop('Boot0001', None)
        else:
            self.fail('Unexpected mutation ' + str(args))
        return ''

    def register(self, verify=lambda: None, save=lambda value: None):
        with patch.object(trial, 'variable', side_effect=lambda n: self.state.get(n)), patch.object(trial, 'run', side_effect=self.firmware):
            trial.register_once(self.before, self.original, 1, '/dev/nvme0n1', self.options, save, verify)

    def test_complete_load_option_round_trip(self):
        self.assertEqual(trial.load_option(option(trial.LABEL, self.options)),
                         dict(active=True, label=trial.LABEL, partition=1, partuuid=PARTUUID,
                              loader=LOADER, options=(self.options + '\0').encode('utf-16-le')))
        for damaged in (b'', option()[:14], option()[:-2], option()[:8] + b'\xff\xff' + option()[10:]):
            with self.assertRaises(ValueError):
                trial.load_option(damaged)

    def test_shim_receives_kernel_path_before_unchanged_unlock_arguments(self):
        loader, args = self.options.split(' ', 1)
        self.assertEqual(loader, '\\EFI\\MonetDirect\\' + ID + '\\vmlinuz.efi')
        self.assertTrue(args.startswith('initrd=\\EFI\\MonetDirect\\' + ID + '\\initramfs.img '))
        self.assertIn(BASE, args)
        self.assertNotIn('BOOT_IMAGE=', args)
        self.assertNotIn('monet.startup_trial=', args)
        for actual, expected, identifier in ((BASE + ' init=/bin/sh', BASE, ID),
                                             (BASE, BASE, '../escape'),
                                             (BASE + ' rd.luks.key=/secret', BASE + ' rd.luks.key=/secret', ID)):
            with self.assertRaises(ValueError):
                trial.kernel_options(actual, expected, identifier)

    def test_success_preserves_permanent_order_and_all_existing_entries(self):
        saved = Mock()
        self.register(save=saved)
        self.assertEqual({k:self.state[k] for k in self.before}, self.before)
        self.assertEqual(self.state['BootNext'], num(1))
        saved.assert_called_once_with(hashlib.sha256(self.state['Boot0001']).hexdigest())
        self.assertIn('--create-only', self.calls[0])
        self.assertFalse(any('--bootorder' in call or '--create' in call for call in self.calls))

    def test_existing_one_time_request_prevents_any_mutation(self):
        self.state['BootNext'] = num(2)
        with self.assertRaises(ValueError):
            self.register()
        self.assertEqual(self.calls, [])

    def test_changed_backup_entry_prevents_any_mutation(self):
        self.state['Boot0000'] = option('Changed by owner')
        with self.assertRaises(RuntimeError):
            self.register()
        self.assertEqual(self.calls, [])

    def test_failing_bootnext_write_is_disarmed_and_original_entry_preserved(self):
        self.fail_next = True
        with self.assertRaises(OSError):
            self.register()
        self.assertEqual(self.state, self.before)

    def test_partial_entry_creation_is_removed_without_arming(self):
        self.partial_create = True
        with self.assertRaises(OSError):
            self.register()
        self.assertEqual(self.state, self.before)
        self.assertFalse(any('--bootnext' in call for call in self.calls))

    def test_wrong_partition_never_becomes_bootnext(self):
        self.wrong_partition = True
        with self.assertRaises(RuntimeError):
            self.register()
        self.assertEqual(self.state, self.before)
        self.assertFalse(any('--bootnext' in call for call in self.calls))

    def test_new_deployment_during_preparation_prevents_arming(self):
        def changed():
            raise ValueError('New staged deployment')
        with self.assertRaises(ValueError):
            self.register(verify=changed)
        self.assertEqual(self.state, self.before)

    def test_concurrent_bootnext_is_preserved(self):
        def external_request():
            self.state['BootNext'] = num(2)
        with self.assertRaises(ValueError):
            self.register(verify=external_request)
        self.assertEqual(self.state, {**self.before, 'BootNext': num(2)})

    def test_rollback_leaves_repurposed_entry_alone(self):
        self.state.update(Boot0001=option('Someone else'), BootNext=num(1))
        with patch.object(trial, 'variable', side_effect=lambda n: self.state.get(n)), patch.object(trial, 'run', side_effect=self.firmware):
            trial.rollback_entry(1, self.options)
        self.assertEqual(self.calls, [])

    def test_rollback_also_removes_unterminated_efibootmgr_payload(self):
        self.state['Boot0001'] = option(trial.LABEL, self.options)[:-2]
        with patch.object(trial, 'variable', side_effect=lambda n: self.state.get(n)), patch.object(trial, 'run', side_effect=self.firmware):
            trial.rollback_entry(1, self.options)
        self.assertEqual(self.state, self.before)

    def test_kernel_must_be_x64_efi_application(self):
        data = bytearray(512)
        data[:2] = b'MZ'; struct.pack_into('<I', data, 60, 128)
        data[128:132] = b'PE\0\0'
        struct.pack_into('<H', data, 132, 0x8664)
        struct.pack_into('<H', data, 152, 0x20b)
        struct.pack_into('<H', data, 220, 10)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'kernel.efi'
            path.write_bytes(data); trial.validate_pe(path)
            struct.pack_into('<H', data, 132, 0x14c)
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                trial.validate_pe(path)


if __name__ == '__main__':
    unittest.main()
