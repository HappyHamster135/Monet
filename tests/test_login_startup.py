"""Login prerequisites stay correct while unrelated boot work no longer holds them up."""
from contextlib import ExitStack
from contextlib import redirect_stdout
import importlib.machinery
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

from tests.test_boot_graphics import boot

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('login_windows_drive', str(ROOT / 'linux/libexec/monet-windows-drive'))
drive = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(drive)

# Bazzite's receipt comparison is left intact by the image transformation.
HARDWARE = '''#!/bin/bash
IMAGE_NAME=monet
IMAGE_BRANCH=stable
FEDORA_VERSION=45
HWS_VER=90
KNOWN_IMAGE_NAME="${TEST_IMAGE:-monet}"
KNOWN_IMAGE_BRANCH="${TEST_BRANCH:-stable}"
KNOWN_FEDORA_VERSION="${TEST_FEDORA:-45}"
HWS_VER_RAN="${TEST_HWS:-90}"
if [[ "$KNOWN_IMAGE_NAME" == "$IMAGE_NAME" && \\
    "$KNOWN_IMAGE_BRANCH" == "$IMAGE_BRANCH" && \\
    "$KNOWN_FEDORA_VERSION" == "$FEDORA_VERSION" && \\
    "$HWS_VER_RAN" == "$HWS_VER" ]]; then
  echo "Hardware setup already ran for version $HWS_VER_RAN, skipping"
  exit 0
fi

# GLOBAL
echo migrated >> "$TEST_LOG"
'''
UNIT = '''[Unit]
Description=Hardware setup
After=rpm-ostreed.service tuned.service
Before=systemd-user-sessions.service jupiter-biosupdate.service jupiter-controller-update.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
'''


@unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Linux startup scripts')
class HardwareStartup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.script = self.root / 'hardware'
        self.script.write_text(boot.hardware_config(HARDWARE, UNIT)[0])
        tools = self.root / 'bin'; tools.mkdir()
        ctl = tools / 'systemctl'
        ctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_LOG"\nexit "${TEST_CTL_CODE:-0}"\n')
        ctl.chmod(0o755)
        self.log = self.root / 'log'
        self.env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], TEST_LOG=str(self.log))

    def invoke(self, **env):
        self.log.unlink(missing_ok=True)
        subprocess.run(['bash', str(self.script)], env=dict(self.env, **env), check=True, capture_output=True, timeout=5)
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_a_current_hardware_receipt_needs_no_daemons(self):
        self.assertEqual(self.invoke(), [])

    def test_each_changed_identity_still_waits_before_running_hardware_setup(self):
        for changed in ({'TEST_IMAGE': 'different'}, {'TEST_BRANCH': 'beta'}, {'TEST_FEDORA': '46'}, {'TEST_HWS': '91'}):
            with self.subTest(changed=changed):
                self.assertEqual(self.invoke(**changed), ['start rpm-ostreed.service tuned.service', 'migrated'])

    def test_a_failed_dependency_keeps_the_original_after_ordering_semantics(self):
        self.assertEqual(self.invoke(TEST_HWS='old', TEST_CTL_CODE='1'),
                         ['start rpm-ostreed.service tuned.service', 'migrated'])

    def test_unknown_vendor_layout_is_rejected_before_any_image_write(self):
        script = self.root / 'usr/libexec/bazzite-hardware-setup'
        unit = self.root / 'usr/lib/systemd/system/bazzite-hardware-setup.service'
        script.parent.mkdir(parents=True); unit.parent.mkdir(parents=True)
        script.write_text(HARDWARE.replace('exit 0', 'exit 1')); unit.write_text(UNIT)
        original = script.read_bytes(), unit.read_bytes()
        with self.assertRaises(ValueError): boot.prepare_hardware(self.root)
        self.assertEqual((script.read_bytes(), unit.read_bytes()), original)

    def test_image_preparation_is_idempotent_and_keeps_other_prerequisites(self):
        script = self.root / 'usr/libexec/bazzite-hardware-setup'
        unit = self.root / 'usr/lib/systemd/system/bazzite-hardware-setup.service'
        script.parent.mkdir(parents=True); unit.parent.mkdir(parents=True)
        script.write_text(HARDWARE); script.chmod(0o755); unit.write_text(UNIT)
        boot.prepare_hardware(self.root)
        first = script.read_bytes(), unit.read_bytes()
        boot.prepare_hardware(self.root)
        self.assertEqual((script.read_bytes(), unit.read_bytes()), first)
        self.assertEqual(script.stat().st_mode & 0o777, 0o755)
        self.assertIn('Before=systemd-user-sessions.service jupiter-biosupdate.service jupiter-controller-update.service', unit.read_text())
        self.assertIn('After=local-fs.target', unit.read_text())

    def test_bootc_installs_the_global_hardware_default_only_on_matching_images(self):
        import tomllib
        script = self.root / 'usr/libexec/bazzite-hardware-setup'
        unit = self.root / 'usr/lib/systemd/system/bazzite-hardware-setup.service'
        script.parent.mkdir(parents=True)
        unit.parent.mkdir(parents=True)
        unit.write_text(UNIT)
        script.write_text(HARDWARE + boot.BLUETOOTH_DEFAULT + '\n')
        config = self.root / 'usr/lib/bootc/install/00-monet-bluetooth.toml'
        for _ in range(2):
            boot.prepare_hardware(self.root)
            self.assertEqual(tomllib.loads(config.read_text()), {'install': {'kargs': ['bluetooth.disable_ertm=1']}})
            self.assertIn(boot.BLUETOOTH_DEFAULT, script.read_text())
        self.assertFalse((self.root / 'usr/lib/bootc/kargs.d').exists())
        script.write_text(script.read_text().replace('disable_ertm=1', 'disable_ertm=0'))
        boot.prepare_hardware(self.root)
        self.assertFalse(config.exists())

    def test_native_systemd_accepts_the_resulting_units(self):
        hardware = self.root / 'hardware.service'
        hardware.write_text(boot.hardware_config(HARDWARE, UNIT)[1])
        network = self.root / 'monet-windows-network.service'
        network.write_text((ROOT / 'linux/systemd/monet-windows-network.service').read_text()
                           .replace('@LIBEXECDIR@/monet-windows-drive wifi', '/bin/true'))
        (self.root / 'monet-windows-drive.service').write_text(
            (ROOT / 'linux/systemd/monet-windows-drive.service').read_text()
            .replace('@LIBEXECDIR@/monet-windows-drive', '/bin/true'))
        env = dict(self.env, SYSTEMD_UNIT_PATH=str(self.root) + ':')
        result = subprocess.run(['systemd-analyze', '--user', '--man=no', 'verify', str(hardware), str(network)],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class WindowsStartup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state.json'

    def open_with_inventory(self, responses):
        with patch.object(drive, 'owner', return_value=('person', 1000, 1000, self.root)), \
                patch.object(drive, 'run', side_effect=responses) as run, \
                patch.object(drive, 'unlock_saved', return_value=0) as unlock, \
                patch.object(drive, 'write_state') as state:
            drive.open_drive()
        return run, unlock, state

    def test_plain_disk_needs_only_one_device_listing(self):
        tree = {'blockdevices': [{'path': '/dev/disk', 'fstype': 'btrfs'}]}
        run, unlock, state = self.open_with_inventory([(0, json.dumps(tree))])
        self.assertEqual(run.call_count, 1)
        unlock.assert_called_once_with([])
        self.assertEqual(state.call_args.args, ('no-windows',))

    def test_unlock_is_followed_by_a_fresh_listing_that_can_see_the_mapper(self):
        device = {'path': '/dev/locked', 'fstype': 'BitLocker', 'uuid': '1234-abcd'}
        mapper = {'path': '/dev/mapper/opened', 'fstype': 'ntfs'}
        responses = [(0, json.dumps({'blockdevices': [row]}))
                     for row in (device, {**device, 'children': [mapper]})]
        with patch.object(drive, 'find_windows', return_value=(None, 'no-windows')) as find:
            run, unlock, _ = self.open_with_inventory(responses)
        unlock.assert_called_once_with([('/dev/locked', '1234-abcd')])
        self.assertEqual(run.call_count, 2)
        find.assert_called_once_with([('/dev/locked', 'bitlocker'), ('/dev/mapper/opened', 'ntfs')])

    def test_a_failed_first_listing_does_not_hide_the_next_one(self):
        tree = {'blockdevices': [{'path': '/dev/recovered', 'fstype': 'btrfs'}]}
        with patch.object(drive, 'find_windows', return_value=(None, 'no-windows')) as find:
            run, _, _ = self.open_with_inventory([(1, ''), (0, json.dumps(tree))])
        self.assertEqual(run.call_count, 2)
        find.assert_called_once_with([('/dev/recovered', 'btrfs')])

    def test_only_background_network_exchange_waits_for_network_and_the_login_manager(self):
        import configparser
        units = []
        for name in ('monet-windows-drive', 'monet-windows-network'):
            unit = configparser.ConfigParser(interpolation=None)
            unit.read(ROOT / ('linux/systemd/' + name + '.service'))
            units.append(unit)
        disk, network = units
        self.assertNotIn('NetworkManager.service', disk['Unit']['After'].split())
        self.assertIn('display-manager.service', disk['Unit']['Before'].split())
        self.assertTrue({'NetworkManager.service', 'display-manager.service', 'monet-windows-drive.service'}
                        <= set(network['Unit']['After'].split()))
        self.assertNotIn('display-manager.service', network['Unit'].get('Before', '').split())

    def test_login_path_publishes_shared_storage_and_key_without_waiting_for_wifi(self):
        events = []
        with ExitStack() as stack:
            for name, value in {'STATE': self.state, 'DRIVE': self.root / 'windows'}.items():
                stack.enter_context(patch.object(drive, name, value))
            for name, value in {'owner': ('person', 1000, 1000, self.root), 'unlock_saved': 0,
                    'block_inventory': {'blockdevices': []}, 'find_windows': ('/dev/mock', 'open'), 'hide': None,
                    'steam_root': self.root / 'steam', 'prepare_games': self.root / 'games',
                    'mount': True, 'share': True, 'share_files': True, 'windows_launchers': {}, 'windows_faceit': False}.items():
                stack.enter_context(patch.object(drive, name, return_value=value))
            stack.enter_context(patch.object(drive.os.path, 'ismount', return_value=True))
            lock = stack.enter_context(patch.object(drive, 'give_lock', side_effect=lambda _: events.append('key')))
            export = stack.enter_context(patch.object(drive, 'give_wifi'))
            imports = stack.enter_context(patch.object(drive, 'take_wifi'))
            original = drive.write_state
            def publish(*args, **kwargs):
                events.append('state'); return original(*args, **kwargs)
            stack.enter_context(patch.object(drive, 'write_state', side_effect=publish))
            self.assertEqual(drive.open_drive(), 0)
            lock.assert_called_once(); export.assert_not_called(); imports.assert_not_called()
        self.assertEqual(events, ['key', 'state'])
        self.assertEqual(json.loads(self.state.read_text())['state'], 'open')

    def test_wifi_waits_for_a_confirmed_mounted_windows_drive(self):
        with patch.object(drive, 'STATE', self.state), patch.object(drive.os.path, 'ismount') as mounted, \
                patch.object(drive, 'give_wifi') as export, patch.object(drive, 'take_wifi') as imports:
            for content in ('', 'bad json', '[]', '{"state":"asleep"}', '{"state":"failed"}'):
                self.state.write_text(content); self.assertEqual(drive.sync_wifi(), 0)
            self.state.write_text('{"state":"open"}'); mounted.return_value = False
            self.assertEqual(drive.sync_wifi(), 0)
            export.assert_not_called(); imports.assert_not_called()
            mounted.return_value = True
            self.assertEqual(drive.sync_wifi(), 0)
            export.assert_called_once_with(drive.DRIVE); imports.assert_called_once_with(drive.DRIVE)

    def test_wifi_failure_cannot_break_the_completed_mount(self):
        self.state.write_text('{"state":"open"}')
        with patch.object(drive, 'STATE', self.state), patch.object(drive.os.path, 'ismount', return_value=True), \
                patch.object(drive, 'give_wifi', side_effect=OSError('network unavailable')), patch.object(drive, 'log'):
            self.assertEqual(drive.sync_wifi(), 0)
        self.assertEqual(self.state.read_text(), '{"state":"open"}')

    def test_settings_unlock_starts_import_and_network_exchange_without_waiting(self):
        self.state.write_text('{"state":"open"}')
        with patch.object(drive, 'STATE', self.state), patch.object(drive.sys, 'stdin', io.StringIO('test-key')), \
                patch.object(drive, 'unlock', return_value='open'), patch.object(drive, 'open_drive') as opened, \
                patch.object(drive, 'run', return_value=(0, '')) as run, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(drive.unlock_from_settings(), 0)
            opened.assert_called_once()
            self.assertEqual(run.call_args_list[-1].args,
                ('systemctl', 'start', '--no-block', 'monet-windows-files.service', 'monet-windows-network.service'))
        self.assertEqual(json.loads(output.getvalue()), {'result': 'open', 'state': 'open'})
