"""Recovery and sign-in controls use disposable files and simulated disk commands."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper
ROOT = Path(__file__).resolve().parents[1]


def helper(name):
    loader = importlib.machinery.SourceFileLoader(name.replace('-', '_'), str(ROOT / 'linux/libexec' / name))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


class Startup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.s = helper('monet-startup')
        self.s.CONFIG = self.root/'config'; self.s.DATA = self.root/'data'
        self.s.CONFIG_DIRS = [self.root/'system']; self.s.DATA_DIRS = []
        self.user = self.s.CONFIG/'autostart'; self.system = self.root/'system/autostart'
        self.user.mkdir(parents=True); self.system.mkdir(parents=True)
        self.data = b'[Desktop Entry]\nType=Application\nName=Example\nExec=example --literal "$HOME" %U\nOnlyShowIn=KDE;\n\n[Other]\nHidden=keep\n'
        (self.system/'example.desktop').write_bytes(self.data)
        self.desktop = patch.dict(os.environ, XDG_CURRENT_DESKTOP='KDE'); self.desktop.start(); self.addCleanup(self.desktop.stop)

    def test_system_override_preserves_commands_and_conditions_and_never_launches(self):
        item, = self.s.listing()['items']
        off = self.s.change('set', item['id'], item['token'], 'off')['items'][0]
        self.assertFalse(off['enabled']); self.assertTrue(off['personal'])
        self.assertEqual((self.system/'example.desktop').read_bytes(), self.data)
        data = (self.user/'example.desktop').read_text()
        self.assertIn('Exec=example --literal "$HOME" %U', data)
        self.assertIn('[Other]\nHidden=keep', data)
        self.assertIn('OnlyShowIn=KDE;', data)
        self.assertTrue(self.s.change('set', off['id'], off['token'], 'on')['items'][0]['enabled'])

    def test_stale_review_and_managed_components_are_refused(self):
        item, = self.s.listing()['items']
        (self.system/'example.desktop').write_bytes(self.data+b'# changed\n')
        with self.assertRaises(ValueError): self.s.change('set', item['id'], item['token'], 'off')
        (self.system/'monet-session.desktop').write_bytes(self.data)
        item = next(i for i in self.s.listing()['items'] if i['managed'])
        with self.assertRaises(ValueError): self.s.change('set', item['id'], item['token'], 'off')
        self.assertFalse(list(self.user.iterdir()))

    def test_user_hidden_override_wins_and_missing_binary_remains_visible(self):
        (self.user/'example.desktop').write_bytes(self.data.replace(b'Exec=', b'Hidden=true\nExec='))
        item, = self.s.listing()['items']; self.assertFalse(item['enabled'])
        (self.user/'example.desktop').write_bytes(self.data+b'\n[Desktop Entry]\nTryExec=/nonexistent/monet-test-app\n')
        item, = self.s.listing()['items']; self.assertFalse(item['available'])

    def test_add_an_installed_app_with_no_execution(self):
        apps = self.s.DATA/'applications'; apps.mkdir(parents=True)
        (apps/'second.desktop').write_bytes(self.data.replace(b'Example', b'Second'))
        item, = self.s.listing(True)['items']
        result = self.s.change('add', item['id'], item['token'])
        self.assertEqual(len(result['items']), 2)
        self.assertTrue((self.user/'second.desktop').exists())
        self.assertEqual(self.s.listing(True)['items'], [])

    def test_symlink_entry_is_replaced_without_editing_its_target(self):
        source = self.root/'launcher'; source.write_bytes(self.data)
        (self.user/'example.desktop').symlink_to(source)
        item, = self.s.listing()['items']; self.s.change('set', item['id'], item['token'], 'off')
        self.assertFalse((self.user/'example.desktop').is_symlink())
        self.assertEqual(source.read_bytes(), self.data)

    def test_corrupt_oversized_and_fifo_entries_do_not_block_reading(self):
        (self.user/'bad.desktop').write_text('not an entry')
        (self.user/'huge.desktop').write_bytes(b'a'*65537)
        os.mkfifo(self.user/'pipe.desktop')
        result = self.s.listing(); self.assertEqual(result['unreadable'], 3)
        self.assertEqual(len(result['items']), 1)

    def test_failed_atomic_write_keeps_the_old_entry(self):
        item, = self.s.listing()['items']
        with patch.object(self.s.os, 'replace', side_effect=OSError('full')):
            with self.assertRaises(OSError): self.s.change('set', item['id'], item['token'], 'off')
        self.assertFalse(list(self.user.iterdir()))

    def test_path_injection_and_stale_add_are_refused(self):
        with self.assertRaises(ValueError): self.s.change('set', '../other.desktop'.encode().hex(), 'a'*64, 'off')
        item, = self.s.listing()['items']
        with self.assertRaises(ValueError): self.s.change('add', item['id'], item['token'])

    def test_an_app_creating_an_override_during_review_keeps_its_new_choice(self):
        item, = self.s.listing()['items']
        original = self.s.entry
        newer = self.data + b'\n# App saved a newer choice\n'
        def intervening(name, path):
            result = original(name, path)
            (self.user/'example.desktop').write_bytes(newer)
            return result
        with patch.object(self.s, 'entry', side_effect=intervening):
            with self.assertRaises(ValueError): self.s.change('set', item['id'], item['token'], 'off')
        self.assertEqual((self.user/'example.desktop').read_bytes(), newer)

    def test_unreadable_startup_directory_does_not_look_like_an_empty_list(self):
        def denied(folder, **kwargs):
            kwargs['onerror'](PermissionError('unreadable'))
            return iter(())
        with patch.object(self.s.os, 'walk', side_effect=denied):
            with self.assertRaises(PermissionError): self.s.listing()


class Retained(unittest.TestCase):
    def setUp(self):
        self.r = helper('monet-storage-recovery')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.top = Path(self.temp.name); self.name = 'previous-install-'+'a'*16
        self.saved = self.top/self.name; self.saved.mkdir()
        self.user = SimpleNamespace(pw_name='person', pw_uid=os.getuid(), pw_gid=os.getgid())
        self.item = dict(id=self.name, token='b'*64, time=1234, homes=0, bytes=None)

    def test_active_subvolumes_bind_mounts_and_different_btrfs_device_numbers_are_protected(self):
        text = f'7 1 0:99 /{self.name}/ostree/deploy/default/var /var rw - btrfs /dev/vda3 rw\n'
        roots = self.r.mounted_roots(text, '0:42')
        with patch.object(self.r, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'in-use'): self.r.identity(self.top, self.name, roots)
            run.assert_not_called()

    def test_regular_directories_symlinks_and_nonretained_names_are_refused(self):
        for name in ('root', '../root', self.name):
            with self.assertRaises(RuntimeError): self.r.identity(self.top, name, [])
        self.saved.rmdir(); self.saved.symlink_to(self.top)
        with self.assertRaises(RuntimeError): self.r.identity(self.top, self.name, [])

    def test_stale_confirmation_never_deletes(self):
        with patch.object(self.r, 'inspect', return_value=self.item), patch.object(self.r, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                self.r.operate(self.top, 'delete', [self.name, 'c'*64], [], self.user)
            run.assert_not_called()

    def test_delete_requires_verified_absence_and_failure_is_not_success(self):
        with patch.object(self.r, 'inspect', return_value=self.item), patch.object(self.r, 'run'):
            with self.assertRaises(RuntimeError): self.r.operate(self.top, 'delete', [self.name, 'b'*64], [], self.user)
        def remove(*args, **kwargs): self.saved.rmdir(); return ''
        with patch.object(self.r, 'inspect', return_value=self.item), patch.object(self.r, 'run', side_effect=remove) as run:
            self.assertTrue(self.r.operate(self.top, 'delete', [self.name, 'b'*64], [], self.user)['ok'])
            self.assertIn('--commit-after', run.call_args.args)
            self.assertEqual(run.call_args.args[-1], self.saved)

    def test_export_is_limited_to_the_matching_owned_home_and_drops_privileges(self):
        home = self.saved/'ostree/deploy/default/var/home/person'; home.mkdir(parents=True)
        self.assertEqual(self.r.homes(self.top, self.name, self.user), [home])
        with patch.object(self.r, 'inspect', return_value=self.item), patch.object(self.r.os, 'getgrouplist', return_value=[]), \
                patch.object(self.r.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.r.operate(self.top, 'export', [self.name, 'b'*64], [], self.user)
            self.assertEqual(run.call_args.kwargs['user'], self.user.pw_uid)
            self.assertIn('--directory='+str(home), run.call_args.args[0])
            self.assertNotIn('--dereference', run.call_args.args[0])
            self.assertNotIn('--one-file-system', run.call_args.args[0])
        home.rmdir(); home.symlink_to(self.top)
        with self.assertRaises(RuntimeError): self.r.homes(self.top, self.name, self.user)

    def test_failed_export_does_not_leave_an_apparently_complete_archive(self):
        q = quick_helper()
        with patch.object(q, 'HOME', self.top), patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            self.assertFalse(q.storage_recovery(['export', self.name, 'b'*64])['ok'])
        self.assertFalse(list(self.top.rglob('*.tar')))

    def test_export_destination_is_unprivileged_and_published_only_after_success(self):
        q = quick_helper(); destination = self.top/'another drive'; destination.mkdir()
        def export(command, **kwargs):
            self.assertEqual(command[-3:], ['export', self.name, 'b'*64])
            self.assertNotIn(str(destination), command)
            self.assertFalse(list(destination.glob('*.tar')))
            kwargs['stdout'].write(b'archive sentinel')
            return subprocess.CompletedProcess(command, 0)
        with patch.object(q.subprocess, 'run', side_effect=export):
            result = q.storage_recovery(['export', self.name, 'b'*64, str(destination).encode().hex()])
        self.assertTrue(result['ok'])
        self.assertEqual(Path(result['path']).read_bytes(), b'archive sentinel')
        self.assertEqual(Path(result['path']).stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(destination.glob('*.partial')))

    def test_invalid_export_destination_never_requests_privileges(self):
        q = quick_helper()
        with patch.object(q.subprocess, 'run') as run:
            for value in ('oops', 'relative'.encode().hex(), str(self.top/'absent').encode().hex()):
                self.assertFalse(q.storage_recovery(['export', self.name, 'b'*64, value])['ok'])
            run.assert_not_called()

    def test_archive_publication_never_overwrites_an_existing_file(self):
        q = quick_helper(); source = self.top/'new.partial'; target = self.top/'existing.tar'
        source.write_text('new'); target.write_text('keep')
        with self.assertRaises(OSError): q.publish_recovery_archive(source, target)
        self.assertEqual(target.read_text(), 'keep'); self.assertEqual(source.read_text(), 'new')

    def test_transport_rejects_invalid_arguments_and_false_success(self):
        q = quick_helper()
        with patch.object(q.subprocess, 'run') as run:
            self.assertFalse(q.storage_recovery(['delete', 'root', 'b'*64])['ok']); run.assert_not_called()
        with patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '{"ok":true}', '')):
            self.assertFalse(q.storage_recovery(['list'])['ok'])

    def test_unmount_failure_never_recursively_removes_the_mount(self):
        libc = SimpleNamespace(unshare=lambda _: 0)
        def run(*args, **kwargs):
            if args[0] == 'umount': raise RuntimeError('failure')
        with patch.object(self.r.ctypes, 'CDLL', return_value=libc), patch.object(self.r.tempfile, 'mkdtemp', return_value=str(self.saved)), patch.object(self.r, 'run', side_effect=run):
            with self.assertRaises(RuntimeError):
                with self.r.top_mount('/dev/fixture', True) as top:
                    (top/'keep').write_text('important')
        self.assertEqual((self.saved/'keep').read_text(), 'important')


class Diagnostics(unittest.TestCase):
    def test_unprivileged_rollback_query_uses_read_only_deployment_service(self):
        q = quick_helper()
        for deployments, expected in (([dict(booted=True), dict(booted=False)], True),
                                      ([dict(booted=True), dict(booted=False, staged=True)], False),
                                      ([dict(booted=True)], False), ([], None), ([{}], None),
                                      ([dict(booted='false')], None), (None, None)):
            def run(*args, **kwargs):
                return json.dumps(dict(deployments=deployments)) if args[0] == 'rpm-ostree' else None
            with self.subTest(deployments=deployments), patch.object(q, 'run', side_effect=run), \
                    patch.object(q, 'storage_capacity', return_value=dict(total=100, free=50)), \
                    patch.object(q, 'update_history', return_value=dict(ok=False, items=[])), \
                    patch.object(q, 'snapshot_names', return_value=[]):
                self.assertIs(q.troubleshooting()['rollback'], expected)

    def test_report_is_allowlisted_and_failure_states_have_next_actions(self):
        q = quick_helper()
        def run(*args, **kwargs):
            if args[0] == 'bootc': return json.dumps({'status': {'rollback': {'image': 'private/registry'}, 'secret': 'private-user'}})
            return 'LoadState=loaded\nActiveState=failed\nResult=exit-code\nDescription=private path /home/person\n'
        with patch.object(q, 'storage_capacity', return_value=dict(total=100*1024**3, free=1024**3)), \
                patch.object(q, 'update_history', return_value=dict(ok=True, items=[dict(result='failed')])), \
                patch.object(q, 'snapshot_names', return_value=['private-path']), patch.object(q, 'run', side_effect=run):
            result = q.troubleshooting()
        self.assertTrue(result['low']); self.assertTrue(result['rollback'])
        self.assertNotIn('private', result['report']); self.assertNotIn('/home/', result['report'])
        self.assertEqual({s['state'] for s in result['services']}, {'failed'})

    def test_missing_services_and_rollback_are_unknown_not_healthy(self):
        q = quick_helper()
        with patch.object(q, 'storage_capacity', return_value=dict(total=100, free=50)), \
                patch.object(q, 'update_history', return_value=dict(ok=False, items=[])), \
                patch.object(q, 'snapshot_names', return_value=[]), patch.object(q, 'run', return_value=None):
            result = q.troubleshooting()
        self.assertIsNone(result['rollback'])
        self.assertEqual({s['state'] for s in result['services']}, {'unavailable'})


class StorageScan(unittest.TestCase):
    def test_drive_layout_keeps_windows_and_unallocated_space_separate(self):
        q = quick_helper()
        gb = 10**9
        parts = [
            dict(type='part', kname='sda1', size=gb, parttype='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'),
            dict(type='part', kname='sda2', size=653*gb,
                 children=[dict(type='crypt', kname='dm-0', path='/dev/mapper/monet')]),
            dict(type='part', kname='sda3', size=100*gb, label='Windows'),
            dict(type='part', kname='sda4', size=gb, parttype='de94bba4-06d1-4d40-a16a-bfd50179d6ac'),
            dict(type='part', kname='sda5', size=20*gb, fstype='ntfs'),
        ]
        devices = [
            dict(type='disk', kname='zram0', size=16*gb),
            dict(type='disk', kname='sda', size=1000*gb, pttype='gpt', children=parts),
        ]
        mounts = [dict(target='/', source='composefs'), dict(target='/sysroot', source='/dev/mapper/monet')]
        with patch.object(q, 'run', side_effect=[json.dumps(dict(blockdevices=devices)),
                                                json.dumps(dict(filesystems=mounts))]):
            drive, = q.storage_drives()
        self.assertTrue(drive['monet'])
        self.assertEqual(drive['size'], 1000*gb)
        self.assertEqual(drive['unallocated'], 225*gb)
        self.assertEqual([part['kind'] for part in drive['partitions']],
                         ['efi', 'monet', 'windows', 'windowsRecovery', 'windowsData'])

    def test_shared_extents_cannot_overfill_the_capacity_chart(self):
        q = quick_helper()
        with patch.object(q, 'storage_capacity', return_value=dict(total=100, free=50, occupied=50)), \
                patch.object(q, 'storage_drives', return_value=[]), \
                patch.object(q, 'storage_scan', return_value=dict(home=70, games=40, apps=20, userApps=0, trash=None,
                    downloads=0, limited=True, unreadable=False, visited=2, scopes=[dict(state='measured')])):
            result = q.storage()
        self.assertFalse(result['breakdown'])
        self.assertTrue(result['overcounted'])
        self.assertEqual(result['occupied'], 50)
        self.assertIsNone(result['trash'])

    def test_single_walk_counts_categories_and_hardlinks_without_following_links(self):
        q = quick_helper()
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)/'home'; games = home/'Games'; games.mkdir(parents=True)
            downloads = home/'Downloads'; downloads.mkdir()
            (games/'game').write_bytes(b'g'*8192)
            (downloads/'file').write_bytes(b'd'*4096)
            os.link(downloads/'file', downloads/'hardlink')
            outside = Path(folder)/'outside'; outside.mkdir(); (outside/'huge').write_bytes(b'x'*32768)
            (home/'external').symlink_to(outside)
            with patch.object(q, 'HOME', home), patch.object(q, 'DATA_HOME', home/'.local/share'), patch.object(q, 'downloads_dir', return_value=downloads):
                result = q.storage_scan(system_apps=Path(folder)/'absent')
                self.assertFalse(result['limited']); self.assertFalse(result['unreadable'])
                self.assertEqual(result['games'], games.stat().st_blocks*512 + (games/'game').stat().st_blocks*512)
                self.assertEqual(result['downloads'], downloads.stat().st_blocks*512 + (downloads/'file').stat().st_blocks*512)
                self.assertLess(result['home'], 32768)
                limited = q.storage_scan(limit=2, system_apps=Path(folder)/'absent')
                self.assertTrue(limited['limited']); self.assertLessEqual(limited['visited'], 2)
                self.assertTrue(q.storage_scan(seconds=0)['limited'])
