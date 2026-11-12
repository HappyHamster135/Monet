"""Only disposable files and simulated drive metadata; never format a real disk."""
from contextlib import contextmanager, redirect_stdout
import copy
import errno
import hashlib
import io
import importlib.util
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_setup import disk, part, GB, STICK
from monet_setup import cache, checkpoint, disks, install, resources, seat, trust


def prepared(encrypted=True):
    result = disk('nvme0n1', 1000 * GB)
    result.update(serial='SYNTHETIC-A', wwn='SYNTHETIC-WWN', **{'maj:min': '259:0', 'log-sec': 512})
    result['children'] = [dict(part('nvme0n1p1', disks.EFI_TYPE, 'vfat'), partuuid='efi-id', uuid='efi-fs', size=disks.GIB, start=2048),
                          dict(part('nvme0n1p2', fstype='ext4', label='boot'), partuuid='boot-id', uuid='boot-fs', size=2*disks.GIB, start=2099200),
                          dict(part('nvme0n1p3', fstype='crypto_LUKS' if encrypted else 'btrfs'), partuuid='root-id', uuid='root-fs', size=500*disks.GIB, start=6293504)]
    return result


def make_cache(folder, image='example.invalid/monet:fixture', payload=b'SYNTHETIC LAYER'):
    root = folder / 'oci'; (root / 'blobs/sha256').mkdir(parents=True)
    def blob(data, kind):
        encoded = json.dumps(data).encode() if isinstance(data, dict) else data
        digest = hashlib.sha256(encoded).hexdigest()
        (root / 'blobs/sha256' / digest).write_bytes(encoded)
        return dict(digest='sha256:'+digest, size=len(encoded), mediaType='application/vnd.oci.image.'+kind)
    layer = blob(payload, 'layer.v1.tar')
    config = blob(dict(architecture='amd64', os='linux'), 'config.v1+json')
    manifest = blob(dict(schemaVersion=2, config=config, layers=[layer]), 'manifest.v1+json')
    manifest['annotations'] = {'org.opencontainers.image.ref.name': 'latest'}
    (root / 'index.json').write_text(json.dumps(dict(schemaVersion=2, manifests=[manifest])))
    cache.complete(folder, image)
    return root / 'blobs/sha256' / layer['digest'][7:]


class SeatSocket(unittest.TestCase):
    def test_missing_or_abandoned_socket_allows_display_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'seat.sock'
            self.assertTrue(seat.ready(path))
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path))
            self.assertTrue(path.exists())
            self.assertTrue(seat.ready(path))
            self.assertFalse(path.exists())

    def test_active_display_server_keeps_its_socket(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'seat.sock'
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path)); server.listen()
                self.assertFalse(seat.ready(path))
                self.assertTrue(path.exists())

    def test_unexpected_files_links_and_other_owners_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'seat.sock'; path.write_text('keep')
            self.assertFalse(seat.ready(path)); self.assertEqual(path.read_text(), 'keep')
            link = path.with_name('link'); link.symlink_to(path)
            self.assertFalse(seat.ready(link)); self.assertTrue(link.is_symlink())
            path.unlink()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server: server.bind(str(path))
            with patch.object(seat.os, 'geteuid', return_value=os.geteuid()+1):
                self.assertFalse(seat.ready(path))
            self.assertTrue(path.exists())

    def test_socket_replacement_during_probe_is_not_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'seat.sock'; replacement = path.with_name('replacement')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server: server.bind(str(path))
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server: server.bind(str(replacement))
            before, after = path.lstat(), replacement.lstat()
            with patch.object(Path, 'lstat', side_effect=[before, after]):
                self.assertFalse(seat.ready(path))
            self.assertTrue(path.exists()); self.assertTrue(replacement.exists())


class DriveReview(unittest.TestCase):
    def test_fast_inventory_never_mounts_or_scans_unselected_windows_files(self):
        selected = prepared()
        with patch.object(disks, 'largest_free', side_effect=AssertionError('slow probe')), \
             patch.object(disks, 'shrink_info', side_effect=AssertionError('NTFS scan')), \
             patch.object(disks, 'windows_files', side_effect=AssertionError('file scan')):
            found = disks.offer([STICK, selected, disk('sdb', 500*GB, tran='usb')], details=False)
        self.assertEqual([row['path'] for row in found], ['/dev/nvme0n1', '/dev/sdb'])
        self.assertFalse(found[0]['checked'])
        self.assertEqual(found[0]['contents'][1]['path'], '/dev/nvme0n1p2')
        self.assertTrue(found[1]['external'])

    def test_nested_live_root_and_mounts_are_protected(self):
        live = prepared()
        live['children'][2]['children'] = [dict(path='/dev/mapper/root', mountpoints=['/'])]
        self.assertEqual(disks.disks([live]), [])
        live['children'][2]['children'][0]['mountpoints'] = ['/mnt/personal']
        self.assertTrue(disks.in_use(live))
        live['children'][2]['children'][0].update(type='crypt', mountpoints=[])
        self.assertTrue(disks.in_use(live))

    def test_swapped_disk_partition_changes_and_unknown_modes_block_all_writes(self):
        current = prepared(False)
        plan = dict(disk=current['path'], mode='erase', identity=disks.identity(current),
                    layout=disks.layout(current), sizes=disks.plan_erase(current['size']))
        with patch.object(checkpoint, 'current_disk', return_value=current), patch.object(install, 'run') as run:
            install.validate_target(plan)
            for change in ('identity', 'layout', 'mode', 'sizes'):
                bad = dict(plan, **{change: 'invalid'})
                with self.subTest(change=change), self.assertRaises(install.Stop): install.validate_target(bad)
            run.assert_not_called()
        mounted = copy.deepcopy(current); mounted['children'][1]['mountpoints'] = ['/mnt/user']
        with patch.object(checkpoint, 'current_disk', return_value=mounted), self.assertRaises(install.Stop):
            install.validate_target(dict(plan, resume='receipt'))

    def test_offline_new_install_is_refused_before_probing_or_writing(self):
        with patch.object(checkpoint, 'current_disk') as probe, patch.object(install, 'run') as run:
            with self.assertRaisesRegex(install.Stop, 'internet'):
                install.validate_target(dict(offline=True, mode='erase'))
            probe.assert_not_called(); run.assert_not_called()


class Checkpoints(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.boot = self.root / 'boot'; self.boot.mkdir()
        self.key = self.root / 'ram/bootstrap'; self.key.parent.mkdir(); self.key.write_bytes(b'K'*64)
        self.disk = prepared()
        self.plan = dict(disk=self.disk['path'], mode='erase', image='example.invalid/monet:fixture',
                         identity=disks.identity(self.disk), layout=disks.layout(self.disk), sizes=disks.plan_erase(self.disk['size']),
                         password='DO NOT PERSIST', wifi='PRIVATE NETWORK', encrypt=True)
        self.parts = dict(efi='/dev/nvme0n1p1', boot='/dev/nvme0n1p2', monet='/dev/nvme0n1p3', fs='/dev/mapper/monet')
        @contextmanager
        def mounted(path, writable=False):
            self.assertEqual(path, self.parts['boot'])
            yield self.boot
        context = patch.object(checkpoint, 'boot_mount', mounted); context.start(); self.addCleanup(context.stop)
        context = patch.object(checkpoint, 'current_disk', lambda _: self.disk); context.start(); self.addCleanup(context.stop)

    def save(self):
        return checkpoint.save(self.plan, self.parts, self.key)

    def test_worker_isolation_failure_stops_before_drive_probes_or_writes(self):
        for step in ('namespace', 'propagation'):
            with self.subTest(step=step):
                plan = self.root/'isolation-plan.json'; plan.write_text(json.dumps(self.plan))
                events = []
                with patch.object(install, 'STATE', self.root/'runtime/install.json'), \
                     patch.object(install.os, 'unshare', side_effect=PermissionError('denied') if step == 'namespace' else None), \
                     patch.object(install, 'run', side_effect=install.Stop('cannot make mounts private')) as run, \
                     patch.object(install, 'validate_target') as validate, \
                     patch.object(install, 'prepare_disk') as prepare, patch.object(install, 'log'), \
                     patch.object(install, 'emit', side_effect=lambda **event: events.append(event)):
                    with self.assertRaises(SystemExit) as failed:
                        install.main(plan)
                self.assertEqual(failed.exception.code, 1)
                validate.assert_not_called(); prepare.assert_not_called()
                if step == 'namespace': run.assert_not_called()
                self.assertEqual(events[-1]['phase'], 'disk')
                self.assertIn('error', events[-1])

    def test_missing_media_digest_stops_before_drive_probes_or_writes(self):
        plan = self.root / 'missing-digest-plan.json'
        plan.write_text(json.dumps(dict(self.plan, imageDigest='sha256:' + 'a' * 64)))
        with patch.object(trust, 'expected', side_effect=FileNotFoundError), \
             patch.object(install, 'isolate_mounts') as isolate, \
             patch.object(install, 'prepare_disk') as prepare, \
             patch.object(install, 'emit') as emit, self.assertRaises(SystemExit) as failed:
            install.main(plan)
        self.assertEqual(failed.exception.code, 1)
        isolate.assert_not_called()
        prepare.assert_not_called()
        self.assertIn('verify its image information', emit.call_args.kwargs['error'])

    def test_reboot_recovers_only_the_bootstrap_key_and_same_partitions(self):
        receipt = self.save(); self.key.unlink()
        stored = (self.boot / checkpoint.DIRECTORY / checkpoint.RECEIPT).read_text()
        self.assertNotIn('DO NOT PERSIST', stored); self.assertNotIn('PRIVATE NETWORK', stored)
        self.assertEqual((self.boot / checkpoint.DIRECTORY / checkpoint.KEYFILE).stat().st_mode & 0o777, 0o600)
        plan = dict(self.plan, resume=receipt['id'])
        parts, recovered = checkpoint.resume(plan, self.key)
        self.assertEqual(self.key.read_bytes(), b'K'*64)
        self.assertEqual(parts, {k:v for k,v in self.parts.items() if k != 'fs'})
        self.assertEqual(recovered['id'], receipt['id'])

    def test_disk_replacement_reused_partitions_wrong_key_and_links_reject_resume(self):
        receipt = self.save()
        for field in ('serial', 'size'):
            changed = copy.deepcopy(self.disk); changed[field] = 'different'
            with self.subTest(field=field), self.assertRaises(ValueError): checkpoint.read(self.boot, changed)
        changed = copy.deepcopy(self.disk); changed['children'][2]['uuid'] = 'reformatted'
        with self.assertRaises(ValueError): checkpoint.read(self.boot, changed)
        for change in ({'resume': 'wrong'}, {'resume': receipt['id'], 'image': 'different'}):
            with self.assertRaises(ValueError): checkpoint.resume(dict(self.plan, **change), self.key)
        key = self.boot / checkpoint.DIRECTORY / checkpoint.KEYFILE
        key.write_bytes(b'corrupt')
        with self.assertRaises(ValueError): checkpoint.read(self.boot, self.disk)
        key.unlink(); key.symlink_to(self.key)
        with self.assertRaises(OSError): checkpoint.read(self.boot, self.disk)

    def test_success_retires_checkpoint_key_and_interrupted_atomic_writes(self):
        self.save()
        folder = self.boot / checkpoint.DIRECTORY
        (folder / 'health.json').write_text('{"temperature": 80}')
        (folder / '.checkpoint-interrupted').write_bytes(b'K'*64)
        checkpoint.clear(self.parts)
        self.assertFalse(folder.exists())
        self.assertTrue(self.key.exists())  # clear never touches unrelated/in-memory paths

    def test_unencrypted_resume_does_not_create_or_read_a_key(self):
        self.disk = prepared(False); self.parts.pop('fs'); self.key.unlink()
        receipt = self.save()
        plan = dict(self.plan, resume=receipt['id'])
        checkpoint.resume(plan, self.key)
        self.assertFalse(self.key.exists()); self.assertFalse(plan['encrypt'])

    def test_failed_install_then_lost_ram_resumes_offline_without_formatting(self):
        from contextlib import ExitStack
        receipt = self.save()
        top = self.root / 'target'; download = top / 'download'
        make_cache(download, self.plan['image'])
        untouched = self.root / 'other-drive'; untouched.write_text('personal files')
        commands, events = [], []
        with ExitStack() as context:
            for name, value in (('TOP', str(top)), ('TARGET', str(self.root/'mounted')),
                                ('DOWNLOAD', str(download)), ('KEY', self.key), ('STATE', self.root/'state/install.json')):
                context.enter_context(patch.object(install, name, value))
            context.enter_context(patch.object(install.os.path, 'ismount', return_value=False))
            context.enter_context(patch.object(install.os, 'unshare'))
            context.enter_context(patch.object(install, 'run', side_effect=lambda *args, **kwargs: commands.append(args) or ''))
            context.enter_context(patch.object(install, 'emit', side_effect=lambda **event: events.append(event)))
            context.enter_context(patch.object(install, 'prepare_disk', side_effect=AssertionError('must not format')))
            context.enter_context(patch.object(install, 'copy_once', side_effect=AssertionError('must not download')))
            context.enter_context(patch.object(install, 'configure'))
            context.enter_context(patch.object(install, 'seal', return_value='synthetic-recovery-phrase'))
            plan = dict(self.plan, resume=receipt['id'])
            path = self.root / 'plan.json'; path.write_text(json.dumps(plan))
            for failure in (install.Stop('interrupted unpacking'),
                            OSError(errno.ENOSPC, 'disk full'), OSError(errno.EDQUOT, 'quota')):
                path.write_text(json.dumps(plan))
                with patch.object(install, 'install', side_effect=failure):
                    with self.assertRaises(SystemExit) as error: install.main(path)
                self.assertEqual(error.exception.code, 1)
                self.assertFalse(path.exists())
                self.assertTrue((self.boot/checkpoint.DIRECTORY/checkpoint.RECEIPT).exists())
                self.assertTrue(cache.valid(download, self.plan['image']))
                if isinstance(failure, OSError):
                    self.assertIn('ran out of space', next(e['error'] for e in reversed(events) if 'error' in e))
            self.key.unlink()  # A restart loses /run, including the original bootstrap key.
            path.write_text(json.dumps(plan))
            with patch.object(install, 'install') as unpack:
                install.main(path)
                unpack.assert_called_once()
            self.assertEqual(untouched.read_text(), 'personal files')
            self.assertFalse((self.boot/checkpoint.DIRECTORY).exists())
            self.assertEqual(events[-1], {'done': True})
            self.assertFalse(any(args[0] in ('wipefs', 'sgdisk', 'mkfs.btrfs', 'mkfs.ext4') for args in commands))
        self.assertEqual(sum(args[:2] == ('cryptsetup', 'open') for args in commands), 4)

    def test_retry_after_cache_cleanup_recreates_only_the_download_subvolume(self):
        from contextlib import ExitStack
        receipt = self.save(); top = self.root/'target'; top.mkdir()
        download = top/'download'; commands, events = [], []
        def run(*args, **kwargs):
            commands.append(args)
            if args[:3] == ('btrfs', 'subvolume', 'create'):
                self.assertEqual(args[3], str(download)); download.mkdir()
            return ''
        with ExitStack() as context:
            for name, value in (('TOP', str(top)), ('TARGET', str(self.root/'mount')), ('DOWNLOAD', str(download)),
                                ('KEY', self.key), ('STATE', self.root/'state/install.json')):
                context.enter_context(patch.object(install, name, value))
            context.enter_context(patch.object(install.os.path, 'ismount', return_value=False))
            context.enter_context(patch.object(install.os, 'unshare'))
            context.enter_context(patch.object(install, 'run', side_effect=run))
            context.enter_context(patch.object(install, 'emit', side_effect=lambda **event: events.append(event)))
            context.enter_context(patch.object(install, 'prepare_disk', side_effect=AssertionError('must not format')))
            context.enter_context(patch.object(install, 'download', side_effect=lambda plan: make_cache(download, plan['image'])))
            for name in ('install', 'configure', 'seal', 'log'):
                context.enter_context(patch.object(install, name, return_value=None))
            path = self.root/'plan.json'; path.write_text(json.dumps(dict(self.plan, resume=receipt['id'])))
            install.main(path)
        self.assertIn(('btrfs', 'subvolume', 'create', str(download)), commands)
        self.assertFalse(any(args[0].startswith('mkfs') or args[0] in ('wipefs', 'sgdisk') for args in commands))
        self.assertEqual(events[-1], dict(done=True))


class DownloadCache(unittest.TestCase):
    def test_full_drive_stops_network_retries_and_preserves_partial_download(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); partial = folder/'partial-layer'; partial.write_bytes(b'kept')
            for available in ([0], [1024**3, 0]):
                with self.subTest(available=available), \
                     patch.object(install, 'DOWNLOAD', str(folder)), patch.object(install, 'run'), \
                     patch.object(install, 'image_size', return_value=0), patch.object(install, 'received', return_value=0), \
                     patch.object(install.shutil, 'disk_usage', side_effect=[SimpleNamespace(free=n) for n in available]), \
                     patch.object(install.time, 'sleep') as sleep, patch.object(install, 'log'), \
                     patch.object(install, 'copy_once', return_value=False) as fetch, redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(install.Stop, 'running out of space'):
                        install.download({'image': 'example.invalid/monet:fixture'})
                    self.assertEqual(fetch.call_count, len(available)-1)
                    sleep.assert_not_called()
                    self.assertEqual(partial.read_bytes(), b'kept')

    def test_low_working_space_keeps_the_current_root_and_boot_files_in_place(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp); (top/'root').mkdir(); notes=top/'root/notes'; notes.write_text('keep')
            with patch.object(install, 'TOP', str(top)), \
                 patch.object(install.shutil, 'disk_usage', return_value=SimpleNamespace(free=install.INSTALL_WORKING_BYTES-1)), \
                 patch.object(install, 'run') as commands, patch.object(install, 'preserve_boot') as boot, \
                 patch.object(install, 'unmount_target') as unmount, redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(install.Stop, '20 GiB'):
                    install.install({}, {})
                commands.assert_not_called(); boot.assert_not_called(); unmount.assert_not_called()
                self.assertEqual(notes.read_text(), 'keep')
                self.assertFalse(list(top.glob('previous-install-*')))

    def test_exact_working_budget_is_accepted(self):
        with patch.object(install.shutil, 'disk_usage', return_value=SimpleNamespace(free=install.INSTALL_WORKING_BYTES)):
            install.require_space('synthetic', install.INSTALL_WORKING_BYTES)

    def test_removed_cache_is_fetched_again_instead_of_blocking_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); (folder / cache.MARKER).write_text('{}')
            with patch.object(install, 'DOWNLOAD', str(folder)), patch.object(install, 'run'), \
                 patch.object(install, 'image_size', return_value=0), patch.object(install, 'received', return_value=0), \
                 patch.object(install, 'log'), patch.object(cache, 'complete'), \
                 patch.object(install, 'copy_once', return_value=True) as fetch, redirect_stdout(io.StringIO()):
                install.download({'image': 'example.invalid/monet:fixture'})
                fetch.assert_called_once()

    def test_completed_download_can_resume_offline_and_corruption_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); layer = make_cache(folder)
            self.assertTrue(cache.valid(folder, 'example.invalid/monet:fixture'))
            self.assertFalse(cache.valid(folder, 'different-image'))
            with patch.object(install, 'DOWNLOAD', str(folder)), patch.object(install, 'run') as run, \
                 patch.object(install, 'copy_once') as fetch, redirect_stdout(io.StringIO()):
                install.download({'image': 'example.invalid/monet:fixture', 'offline': True})
                run.assert_not_called(); fetch.assert_not_called()
            layer.write_bytes(b'CORRUPTED LAYER!')
            self.assertFalse(cache.valid(folder, 'example.invalid/monet:fixture'))

    def test_offline_resume_refuses_a_substitute_with_its_own_valid_receipt(self):
        image = 'example.invalid/monet:fixture'
        with tempfile.TemporaryDirectory() as temp:
            original, substitute = Path(temp) / 'original', Path(temp) / 'substitute'
            make_cache(original, image)
            make_cache(substitute, image, payload=b'REPLACEMENT LAYER')
            expected = json.loads((original / 'oci/index.json').read_text())['manifests'][0]['digest']
            self.assertTrue(cache.valid(original, image, expected))
            self.assertTrue(cache.valid(substitute, image))
            self.assertFalse(cache.valid(substitute, image, expected))
            with patch.object(install, 'DOWNLOAD', str(substitute)), patch.object(install, 'run') as run, \
                 patch.object(install, 'copy_once') as fetch, redirect_stdout(io.StringIO()):
                with self.assertRaises(install.Stop):
                    install.download(dict(image=image, imageDigest=expected, offline=True))
                run.assert_not_called()
                fetch.assert_not_called()
            self.assertTrue((substitute / cache.MARKER).exists())

    def test_fresh_install_downloads_the_digest_from_its_media(self):
        image = 'example.invalid/monet:fixture'
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_cache(folder, image)
            expected = json.loads((folder / 'oci/index.json').read_text())['manifests'][0]['digest']
            (folder / cache.MARKER).unlink()
            with patch.object(install, 'DOWNLOAD', str(folder)), patch.object(install, 'run'), \
                 patch.object(install, 'image_size', return_value=0), patch.object(install, 'log'), \
                 patch.object(install, 'copy_once', return_value=True) as fetch, redirect_stdout(io.StringIO()):
                install.download(dict(image=image, imageDigest=expected))
            self.assertEqual(fetch.call_args.args[0], 'example.invalid/monet@' + expected)

    def test_built_media_keeps_the_verified_source_and_tracks_the_update_channel(self):
        for repository, digest, channel, signed in (
            ('ghcr.io/happyhamster135/monet', 'sha256:' + 'a' * 64, 'latest', True),
            ('ghcr.io/happyhamster135/monet-amd', 'sha256:' + 'b' * 64, 'latest', True),
            ('example.invalid:8443/monet', 'sha256:' + 'c' * 64, 'latest', False),
            ('example.invalid:8443/monet-dev', None, '0.9.7', False),
        ):
            plan = dict(image=f'{repository}:0.9.7', imageDigest=digest, offline=True)
            with self.subTest(image=plan['image']), tempfile.TemporaryDirectory() as temp:
                download = str(Path(temp) / 'download')
                with patch.object(install, 'TOP', temp), patch.object(install, 'DOWNLOAD', download), \
                     patch.object(install, 'TARGET', str(Path(temp) / 'target')), \
                     patch.object(install, 'require_space'), patch.object(install, 'unmount_target'), \
                     patch.object(install, 'preserve_boot'), patch.object(install, 'mount_target'), \
                     patch.object(install, 'boot_entry'), patch.object(install, 'run') as run, redirect_stdout(io.StringIO()):
                    install.install(plan, {})
                command = next(call.args for call in run.call_args_list if 'bootc' in call.args)
                self.assertEqual(command[command.index('--source-imgref') + 1], f'oci:{download}/oci:latest')
                self.assertEqual(command[command.index('--target-imgref') + 1], f'{repository}:{channel}')
                self.assertEqual('--enforce-container-sigpolicy' in command, signed)
                self.assertIn('--skip-fetch-check', command)

    def test_built_media_requires_a_valid_digest_for_the_selected_variant(self):
        image = 'example.invalid/monet:fixture'
        amd = 'example.invalid/monet-amd:fixture'
        pins = {image: 'sha256:' + 'a' * 64, amd: 'sha256:' + 'b' * 64}
        with tempfile.TemporaryDirectory() as temp:
            media = Path(temp)
            self.assertIsNone(trust.expected(image, media))
            (media / 'IMAGE').write_text(image)
            with self.assertRaises(FileNotFoundError):
                trust.expected(image, media)
            source = media / 'verified-images.json'
            source.write_text(json.dumps(pins))
            trust.write_pins(image, media / trust.PINS, source)
            self.assertEqual(trust.expected(image, media), pins[image])
            self.assertEqual(trust.expected(amd, media), pins[amd])
            rendered = trust.render_kickstart('nvidia=@IMAGE@\namd=@AMD_IMAGE@', image, pins)
            self.assertEqual(rendered, f'nvidia=example.invalid/monet@{pins[image]}\n'
                                       f'amd=example.invalid/monet-amd@{pins[amd]}')
            with self.assertRaises(ValueError):
                trust.expected('example.invalid/monet:other', media)
            source.write_text(json.dumps({image: pins[image]}))
            with self.assertRaises(ValueError):
                trust.write_pins(image, media / trust.PINS, source)

    def test_offline_missing_or_corrupt_download_fails_without_network_or_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with patch.object(install, 'DOWNLOAD', str(folder)), patch.object(install, 'run') as run, \
                 patch.object(install, 'copy_once') as fetch, redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(install.Stop, 'incomplete or damaged'):
                    install.download(dict(image='example.invalid/monet:fixture', offline=True))
                layer = make_cache(folder); layer.write_bytes(b'CORRUPT')
                with self.assertRaisesRegex(install.Stop, 'incomplete or damaged'):
                    install.download(dict(image='example.invalid/monet:fixture', offline=True))
                self.assertEqual(layer.read_bytes(), b'CORRUPT')
                self.assertTrue((folder/cache.MARKER).is_file())
                run.assert_not_called(); fetch.assert_not_called()

    def test_missing_truncated_and_symlinked_blobs_are_never_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); layer = make_cache(folder)
            data = layer.read_bytes(); layer.unlink()
            self.assertFalse(cache.valid(folder, 'example.invalid/monet:fixture'))
            other = folder / 'personal'; other.write_bytes(data); layer.symlink_to(other)
            self.assertFalse(cache.valid(folder, 'example.invalid/monet:fixture'))
            self.assertEqual(other.read_bytes(), data)
            (folder / cache.MARKER).unlink()
            with patch.object(install, 'DOWNLOAD', str(folder)), patch.object(install, 'run'), \
                 patch.object(install, 'image_size', return_value=0), patch.object(install, 'log'), \
                 patch.object(install, 'copy_once') as fetch, redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(install.Stop, 'location changed'):
                    install.download({'image': 'example.invalid/monet:fixture'})
                fetch.assert_not_called()


class FinishAndResources(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Qt regional data')
    def test_city_defaults_are_written_into_the_installed_account(self):
        from PySide6.QtCore import QLocale, QTime
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'deployment'; var = Path(temp) / 'var'
            (root / 'usr/share/zoneinfo/Europe').mkdir(parents=True); var.mkdir()
            (root / 'usr/share/zoneinfo/Europe/Stockholm').write_bytes(b'fixture')
            plan = dict(account='test', name='Test', password='synthetic', language='en_US.UTF-8',
                        keyboard='us', variant='', timezone='Europe/Stockholm', mode='keep', apps=[])
            with patch.object(install, 'deployment', return_value=(root, var)), \
                 patch.object(install, 'run', return_value='') as commands, patch.object(install, 'log'), \
                 patch.object(install.glob, 'glob', return_value=[]), redirect_stdout(io.StringIO()):
                install.configure(plan)
            config = var / 'home/test/.config'
            weather = json.loads((config / 'monet/weather.json').read_text())
            self.assertEqual(weather['place'], 'Stockholm'); self.assertFalse(weather['fahrenheit'])
            import configparser
            preferences = configparser.ConfigParser(); preferences.read(config / 'plasma-localerc')
            formats = preferences['Formats']
            self.assertEqual(formats['LANG'], 'en_US.UTF-8')
            self.assertIn('18', QLocale(formats['LC_TIME']).toString(QTime(18, 20), QLocale.ShortFormat))
            self.assertIn('LC_TIME=' + formats['LC_TIME'], (root / 'etc/locale.conf').read_text())
            self.assertIn(unittest.mock.call('chroot', root, 'chown', '-R', 'test:test', '/var/home/test/.config'),
                          commands.call_args_list)

    def test_configuration_isolates_live_mounts_before_chroot_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'deployment'; var = Path(temp)/'var'
            root.mkdir(); var.mkdir()
            (root/'usr/share/zoneinfo').mkdir(parents=True)
            (root/'usr/share/zoneinfo/UTC').write_bytes(b'fixture')
            commands = []
            mounted, isolated = set(), set()
            def run(*args, **kwargs):
                commands.append(args)
                if args[:2] == ('mount', '--make-rslave'):
                    isolated.add(args[-1])
                elif args[0] == 'mount' and '-o' not in args:
                    mounted.add(args[-1])
                elif args[0] == 'chroot':
                    self.assertEqual(mounted, isolated)
                elif args[0] == 'umount':
                    self.assertIn(args[-1], isolated)
                    mounted.remove(args[-1])
                return ''
            plan = dict(account='test', name='Test', password='synthetic',
                        language='en_US.UTF-8', keyboard='us', variant='',
                        timezone='UTC', mode='keep', apps=[])
            with patch.object(install, 'deployment', return_value=(root, var)), \
                 patch.object(install, 'run', side_effect=run), patch.object(install, 'log'), \
                 patch.object(install.glob, 'glob', return_value=[]), redirect_stdout(io.StringIO()):
                install.configure(plan)
            self.assertEqual(isolated, {root/name for name in ('var', 'proc', 'sys', 'dev')})
            self.assertEqual(mounted, set())
            self.assertEqual([c[-1].name for c in commands if c[0] == 'umount'], ['dev', 'sys', 'proc', 'var'])

    def test_mount_isolation_failure_stops_configuration_and_attempts_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'deployment'; var = Path(temp)/'var'
            root.mkdir(); var.mkdir()
            def run(*args, **kwargs):
                if args[:2] == ('mount', '--make-rslave'):
                    raise install.Stop('cannot isolate mount')
                return ''
            with patch.object(install, 'deployment', return_value=(root, var)), \
                 patch.object(install, 'run', side_effect=run) as commands, redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(install.Stop, 'cannot isolate mount'):
                    install.configure({})
            self.assertFalse(any(c.args[0] == 'chroot' for c in commands.call_args_list))
            self.assertEqual(commands.call_args.args, ('umount', '-R', root/'var'))

    def test_rebuilding_an_unfinished_system_preserves_its_personal_files(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp); root = top/'root'; home = root/'ostree/deploy/default/var/home/person'
            home.mkdir(parents=True); (home/'notes').write_text('personal files from the unfinished installation')
            commands = []
            def run(*args, **kwargs):
                commands.append(args)
                if args[:3] == ('btrfs', 'subvolume', 'create'): Path(args[3]).mkdir()
                return ''
            with patch.object(install, 'TOP', str(top)), patch.object(install, 'TARGET', str(top/'mount')), \
                 patch.object(install, 'run', side_effect=run), patch.object(install, 'unmount_target'), \
                 patch.object(install, 'mount_target'), patch.object(install, 'boot_entry'), \
                 patch.object(install, 'preserve_boot'), patch.object(install, 'require_space'), \
                 patch.object(install, 'log'), redirect_stdout(io.StringIO()):
                install.install({'image': 'example.invalid/fixture'}, {'monet': 'synthetic'})
            saved = list(top.glob('previous-install-*'))
            self.assertEqual(len(saved), 1)
            self.assertEqual((saved[0]/home.relative_to(root)/'notes').read_text(), 'personal files from the unfinished installation')
            self.assertTrue(root.is_dir()); self.assertEqual(list(root.iterdir()), [])
            self.assertFalse(any(args[:3] == ('btrfs', 'subvolume', 'delete') for args in commands))
            command = next(args for args in commands if 'to-filesystem' in args)
            self.assertEqual(command[:7], ('unshare', '--mount', '--propagation', 'private',
                                           'bootc', 'install', 'to-filesystem'))
            self.assertIn('--skip-finalize', command)

    def test_late_retry_preserves_boot_files_and_removes_stale_deployment_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp); boot = top/'boot'; previous = top/'previous-install-test'
            boot.mkdir(); previous.mkdir()
            for name in (checkpoint.DIRECTORY, 'efi', 'lost+found'):
                folder = boot/name; folder.mkdir(); (folder/'untouched').write_text(name)
            entries = boot/'loader.1/entries'; entries.mkdir(parents=True)
            (entries/'old.conf').write_text('ostree=/ostree/boot.1/default/old/0\n')
            (boot/'loader').symlink_to('loader.1')
            # A boot symlink must be preserved without reading or modifying its target.
            outside = top/'other-drive'; outside.mkdir(); (outside/'personal').write_text('keep')
            (boot/'outside').symlink_to(outside, target_is_directory=True)
            @contextmanager
            def mounted(partition, writable=False):
                self.assertEqual(partition, 'synthetic-boot'); self.assertTrue(writable)
                yield boot
            def flushed(*args, **kwargs):
                if args[-1] != boot:
                    self.assertTrue((entries/'old.conf').exists())
                    self.assertTrue((args[-1]/'loader.1/entries/old.conf').exists())
                return ''
            with patch.object(install, 'TOP', str(top)), patch.object(checkpoint, 'boot_mount', mounted), \
                 patch.object(install, 'run', side_effect=flushed), patch.object(install, 'log'):
                install.preserve_boot({'boot': 'synthetic-boot'}, previous)
            backup, = previous.glob('saved-boot-*')
            self.assertEqual((backup/'loader').readlink(), Path('loader.1'))
            self.assertEqual((backup/'outside').readlink(), outside)
            self.assertEqual((backup/'loader.1/entries/old.conf').read_text(), 'ostree=/ostree/boot.1/default/old/0\n')
            self.assertEqual((outside/'personal').read_text(), 'keep')
            self.assertEqual({p.name for p in boot.iterdir()}, {checkpoint.DIRECTORY, 'efi', 'lost+found'})
            for name in (checkpoint.DIRECTORY, 'efi', 'lost+found'):
                self.assertEqual((boot/name/'untouched').read_text(), name)

    def test_failed_boot_backup_flush_leaves_originals_for_another_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp); boot = top/'boot'; boot.mkdir(); (boot/'vmlinuz').write_bytes(b'kernel')
            @contextmanager
            def mounted(*args, **kwargs): yield boot
            def run(*args, **kwargs):
                if args[:3] == ('btrfs', 'subvolume', 'create'): Path(args[-1]).mkdir()
                elif args[0] == 'sync': raise install.Stop('flush failed')
            with patch.object(install, 'TOP', str(top)), patch.object(checkpoint, 'boot_mount', mounted), \
                 patch.object(install, 'run', side_effect=run):
                with self.assertRaisesRegex(install.Stop, 'flush failed'):
                    install.preserve_boot({'boot': 'synthetic-boot'})
            self.assertEqual((boot/'vmlinuz').read_bytes(), b'kernel')
            backup, = top.glob('previous-install-*/saved-boot-*/vmlinuz')
            self.assertEqual(backup.read_bytes(), b'kernel')

    def test_first_install_does_not_create_an_empty_boot_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            boot = Path(temp); (boot/checkpoint.DIRECTORY).mkdir(); (boot/'lost+found').mkdir()
            @contextmanager
            def mounted(*args, **kwargs): yield boot
            with patch.object(checkpoint, 'boot_mount', mounted), patch.object(install, 'run') as run:
                install.preserve_boot({'boot': 'synthetic-boot'})
            run.assert_not_called()

    def test_an_existing_encryption_mapping_must_belong_to_the_selected_partition(self):
        with patch.object(install.os.path, 'exists', return_value=True), \
             patch.object(install, 'run', return_value='  device: /dev/OTHER\n') as run:
            with self.assertRaises(install.Stop): install.opened('/dev/SELECTED')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[:2], ('cryptsetup', 'status'))

    def test_failed_flush_never_unmounts_or_discards_recovery_state(self):
        def run_command(*args, **kwargs):
            if args[0] == 'sync': raise install.Stop('flush failed')
            return ''
        with patch.object(install, 'run', side_effect=run_command) as run, \
             patch.object(checkpoint, 'clear') as clear, redirect_stdout(io.StringIO()):
            with self.assertRaises(install.Stop): install.finish(dict(monet='fixture'))
            self.assertEqual(run.call_args.args[:2], ('sync', '-f'))
            clear.assert_not_called()

    def test_health_distinguishes_missing_sensors_and_bounds_invalid_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); memory = root/'meminfo'; memory.write_text('MemAvailable: 1048576 kB\n')
            self.assertEqual(resources.sample(root, memory), dict(temperature=None, available=1024**3))
            for i,value in enumerate(('85000','bad','-1000','200000')):
                sensor = root/f'thermal_zone{i}'; sensor.mkdir(); (sensor/'temp').write_text(value)
            self.assertEqual(resources.sample(root, memory)['temperature'], 85)

    @unittest.skipUnless(hasattr(os, 'sched_getaffinity'), 'Linux CPU affinity')
    def test_gentler_mode_limits_only_a_disposable_worker_and_its_children(self):
        before = os.sched_getaffinity(0)
        script = 'import os,json; from monet_setup import resources; n=resources.gentler(); print(json.dumps([n,len(os.sched_getaffinity(0)),os.getpriority(os.PRIO_PROCESS,0)]))'
        result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1]/'setup',
                                capture_output=True, text=True, check=True, timeout=10)
        count, affinity, priority = json.loads(result.stdout)
        self.assertEqual(count, min(2, len(before))); self.assertEqual(affinity, count)
        self.assertGreaterEqual(priority, 10); self.assertEqual(os.sched_getaffinity(0), before)


if __name__ == '__main__': unittest.main()
