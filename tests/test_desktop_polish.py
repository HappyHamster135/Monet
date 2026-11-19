"""0.9.8-8 migrations and destructive actions use disposable profiles only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


def runtime(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ('linux/share/monet/monet_runtime/' + name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Profile(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / 'config'; self.config.mkdir()
        self.data = self.home / 'data'; self.data.mkdir()
        self.q = quick_helper()
        for key, value in dict(HOME=self.home, CONFIG=self.config, DATA_HOME=self.data).items():
            p = patch.object(self.q, key, value); p.start(); self.addCleanup(p.stop)


class AudioNames(Profile):
    def test_port_and_hardware_names_distinguish_connection_types(self):
        for listed, props, port, expected in (
            ('Built-in Audio Analog Stereo', {}, {'name':'analog-output-speaker', 'description':'Speakers'}, ('Speakers','Built-in audio')),
            ('Built-in Audio', {}, {'name':'analog-output-headphones', 'description':'Headphones'}, ('Headphones','Headphone jack')),
            ('WH-1000XM5', {'device.bus':'bluetooth','device.form_factor':'headset'}, {}, ('WH-1000XM5','Bluetooth headphones')),
            ('USB DAC Analog Stereo', {'device.bus':'usb'}, {}, ('USB DAC','USB audio')),
            ('Navi 21 HDMI/DP Audio', {'node.name':'alsa_output.pci-hdmi'}, {'name':'hdmi-output-2'}, ('Display audio · 3','HDMI / DisplayPort')),
        ):
            with self.subTest(expected=expected): self.assertEqual(self.q.output_name(listed, props, port), expected)

    def test_rename_is_persistent_and_blank_restores_original(self):
        key = 'alsa_output.usb-device'.encode().hex()
        self.assertTrue(self.q.set_audio_name(key, '  Desk speakers  ')['ok'])
        self.assertEqual(self.q.audio_names(), {key:'Desk speakers'})
        self.assertTrue(self.q.set_audio_name(key, '')['ok'])
        self.assertEqual(self.q.audio_names(), {})
        before = list(self.config.rglob('*'))
        for key, name in (('../outside', 'bad'), ('a', 'bad'), ('aa', 'line\nbreak'), ('aa','x'*81)):
            self.assertFalse(self.q.set_audio_name(key, name)['ok'])
        self.assertEqual(list(self.config.rglob('*')), before)


class TaskManagerReset(Profile):
    def test_custom_pages_are_backed_up_and_graphics_is_a_standard_page(self):
        config = self.config / 'systemmonitorrc'; config.write_text('[General]\npageOrder=my-own.page\n')
        pages = self.data / 'plasma-systemmonitor'; pages.mkdir(); (pages/'my-own.page').write_text('my chart')
        old = config.read_bytes()
        result = self.q.task_manager_reset(); self.assertTrue(result['ok']); self.assertTrue(result['changed'])
        backup = Path(result['backup'])
        self.assertEqual((backup/'systemmonitorrc').read_bytes(), old)
        self.assertEqual((backup/'pages/my-own.page').read_text(), 'my chart')
        self.assertIn('monet-graphics.page', config.read_text())
        self.assertIn('old-overview.page,old-history.page', config.read_text())
        config.write_text('new customization'); pages.mkdir(); (pages/'new.page').write_text('after update')
        self.assertFalse(self.q.task_manager_reset()['changed'])
        self.assertEqual(config.read_text(), 'new customization')
        self.assertTrue((pages/'new.page').exists())

    def test_retry_preserves_original_backup_and_linked_profile_is_not_moved(self):
        config = self.config/'systemmonitorrc'; config.write_text('original')
        with patch.object(self.q.Path, 'replace', side_effect=OSError('interrupted')):
            self.assertFalse(self.q.task_manager_reset()['ok'])
        config.write_text('partial')
        result = self.q.task_manager_reset(); self.assertTrue(result['ok'])
        self.assertEqual((Path(result['backup'])/'systemmonitorrc').read_text(), 'original')
        (Path(result['backup'])/'complete.json').unlink()
        config.unlink(); config.symlink_to(self.home/'outside')
        self.assertFalse(self.q.task_manager_reset()['ok']); self.assertTrue(config.is_symlink())


class AppRemoval(Profile):
    def setUp(self):
        super().setUp(); self.m = runtime('app_management')
        self.apps = self.data/'applications'; self.apps.mkdir()

    def portable(self):
        program = self.home/'My application.AppImage'
        program.write_bytes(b'\x7fELF'+b'\0'*4+b'AI\x02'); program.chmod(0o755)
        sidecar = Path(str(program)+'.home'); sidecar.mkdir(); (sidecar/'save').write_text('saved')
        ident = hashlib.sha256(str(program).encode()).hexdigest()[:24]
        entry = dict(Name='My app', Exec=f'/usr/libexec/monet-quick native-run {str(program).encode().hex()}')
        path = self.apps/f'monet-local-{ident}.desktop'; path.write_text('[Desktop Entry]\n'+'\n'.join(k+'='+v for k,v in entry.items()))
        return program, sidecar, path, entry

    def test_portable_deletes_only_reviewed_program_and_data_default_or_keeps_data(self):
        for erase in (False, True):
            program, sidecar, path, entry = self.portable()
            neighbor = self.home/'another program'; neighbor.write_text('keep')
            plan = self.m.review(path, entry, self.home, self.data)
            self.assertEqual(plan['kind'], 'portable'); self.assertTrue(plan['eraseSupported'])
            with patch.object(self.m, 'portable_running', return_value=False):
                result = self.m.uninstall(plan, plan['token'], erase, Mock())
            self.assertTrue(result['removed']); self.assertFalse(program.exists()); self.assertFalse(path.exists())
            self.assertEqual(sidecar.exists(), not erase); self.assertEqual(neighbor.read_text(), 'keep')
            if sidecar.exists(): (sidecar/'save').unlink(); sidecar.rmdir()

    def test_changed_or_running_apps_are_not_deleted(self):
        program, sidecar, path, entry = self.portable(); plan = self.m.review(path, entry, self.home, self.data)
        self.assertEqual(self.m.uninstall(plan, 'stale', True, Mock())['problem'], 'changed')
        with patch.object(self.m, 'portable_running', return_value=True):
            self.assertEqual(self.m.uninstall(plan, plan['token'], True, Mock())['problem'], 'running')
        path.write_text(path.read_text()+'\nComment=changed')
        fresh = self.m.review(path, entry, self.home, self.data)
        self.assertNotEqual(fresh['token'], plan['token']); self.assertTrue(program.exists()); self.assertTrue(sidecar.exists())
        program.write_bytes(program.read_bytes()+b'new version')
        with patch.object(self.m, 'portable_running', return_value=False):
            self.assertEqual(self.m.uninstall(plan, plan['token'], True, Mock())['problem'], 'changed')

    def test_flatpak_removal_uses_actual_uninstall_and_requires_readback(self):
        plan = dict(kind='flatpak', token='review', app='org.example.App', installation='user', entry=str(self.apps/'test.desktop'))
        for erase in (True, False):
            run = Mock(side_effect=['', '', ''])
            self.assertTrue(self.m.uninstall(plan, 'review', erase, run)['removed'])
            command = run.call_args_list[1].args
            self.assertEqual(command[:5], ('flatpak','uninstall','--user','--noninteractive','-y'))
            self.assertEqual('--delete-data' in command, erase)
        for replies, problem in ((['org.example.App\n'], 'running'), (['',None], 'uninstall'),
                                  (['','','org.example.App\n'], 'unconfirmed')):
            self.assertEqual(self.m.uninstall(plan, 'review', True, Mock(side_effect=replies))['problem'], problem)

    def test_named_installations_are_resolved_and_ambiguous_aliases_are_refused(self):
        path = self.apps/'org.example.App.desktop'
        installed = Mock(return_value='org.example.App\textra-disk\n')
        self.assertEqual(self.m.flatpak_installation(path,'org.example.App',self.data,installed),'extra-disk')
        installed.return_value = 'org.example.App\tuser\norg.example.App\tsystem\n'
        with self.assertRaises(ValueError): self.m.flatpak_installation(path,'org.example.App',self.data,installed)
        export = self.data/'flatpak/exports/share/applications/org.example.App.desktop'
        self.assertEqual(self.m.flatpak_installation(export,'org.example.App',self.data,installed),'user')

    def test_monet_windows_programs_use_their_proton_prefix_even_without_system_wine(self):
        prefix=self.home/'programs'; target=prefix/'drive_c/windows/system32/uninstaller.exe'
        target.parent.mkdir(parents=True); target.write_bytes(b'not executed')
        entry=self.apps/'monet-program-tool.desktop'; entry.write_text('[Desktop Entry]\nExec=monet-quick program-start 61\n')
        with patch.object(self.q,'app_management',return_value=dict(ok=True,kind='wine',entry=str(entry))), \
                patch.object(self.q,'PROGRAMS_PREFIX',prefix),patch.object(self.q,'steam_proton',return_value=None), \
                patch.object(self.q.shutil,'which',side_effect=lambda name:'/bin/umu-run' if name=='umu-run' else None), \
                patch.object(self.q.subprocess,'Popen') as launch:
            self.assertTrue(self.q.app_wine_uninstaller(entry.name)['ok'])
        self.assertEqual(launch.call_args.args[0],['umu-run',str(target)])
        self.assertEqual(launch.call_args.kwargs['env']['WINEPREFIX'],str(prefix))
        self.assertEqual(launch.call_args.kwargs['env']['GAMEID'],'0')


class PanelSizing(Profile):
    def test_fitting_does_not_race_an_in_progress_layout_migration(self):
        import fcntl
        runtime = self.home/'runtime'; (runtime/'monet').mkdir(parents=True)
        with patch.object(self.q,'RUNTIME',runtime), patch.object(self.q,'_fit_bars') as fit:
            with (runtime/'monet/panel-layout.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                self.q.fit_bars(); fit.assert_not_called()
            self.q.fit_bars(); fit.assert_called_once()


class TaskManagerBundle(Profile):
    def test_original_page_library_and_bundled_page_library_are_both_verified(self):
        spec=importlib.util.spec_from_file_location('monitor_bundle',ROOT/'image/task-manager/bundle.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        manifest=dict(package_names=['native'],packages=['native-1'],original='binary',originalPage='page')
        with patch.object(module,'packages',return_value=['native-1']), \
                patch.object(module,'digest',side_effect=['binary','page']): module.verify(manifest)
        with patch.object(module,'packages',return_value=['native-1']), \
                patch.object(module,'digest',side_effect=['binary','different page']),self.assertRaises(ValueError): module.verify(manifest)
        for name in ('plasma-systemmonitor','libPlasmaSystemMonitorPage.so','source.tar.xz'): (self.home/name).write_text(name)
        manifest.update(binary=module.digest(self.home/'plasma-systemmonitor'),page=module.digest(self.home/'libPlasmaSystemMonitorPage.so'),source=module.digest(self.home/'source.tar.xz'))
        (self.home/'runtime.json').write_text(json.dumps(manifest))
        with patch.object(module,'verify'):
            self.assertEqual(module.verified_binary(self.home),self.home/'plasma-systemmonitor')
            (self.home/'libPlasmaSystemMonitorPage.so').write_text('modified')
            with self.assertRaises(ValueError): module.verified_binary(self.home)


class StorageDetails(Profile):
    def setUp(self): super().setUp(); self.m = runtime('storage_details')

    def test_scan_reports_large_old_downloads_without_deleting_files(self):
        downloads = self.home/'Downloads'; downloads.mkdir(); cache = self.home/'cache'; cache.mkdir()
        old = downloads/'old.iso'; old.write_bytes(b'x'*12); os.utime(old, (100,100))
        new = downloads/'new.zip'; new.write_bytes(b'x'); os.utime(new, (100000000,100000000))
        (downloads/'linked').symlink_to(old)
        with patch.object(self.m, 'unused_refs', return_value=[]):
            result = self.m.scan(self.home, downloads, cache, now=100000000)
        self.assertEqual([item['name'] for item in result['oldDownloads']], ['old.iso'])
        self.assertTrue(result['unusedKnown']); self.assertEqual(old.stat().st_size, 12)

    def test_cleanup_refuses_stale_review_and_flatpak_rechecks_usage(self):
        rows = [dict(installation='user',ref='runtime/org.example.Platform/x86_64/1',name='Platform',size=12)]
        run = Mock(return_value='')
        with patch.object(self.m, 'unused_refs', return_value=rows):
            self.assertEqual(self.m.cleanup('old', run)['problem'], 'changed'); run.assert_not_called()
        with patch.object(self.m, 'unused_refs', side_effect=[rows, []]):
            self.assertTrue(self.m.cleanup(self.m.token(rows), run)['ok'])
        run.assert_called_once_with('flatpak','uninstall','--user','--unused','--noninteractive','-y',timeout=600)
        with patch.object(self.m, 'unused_refs', return_value=rows):
            self.assertFalse(self.m.cleanup(self.m.token(rows), Mock(return_value=None))['ok'])


if __name__ == '__main__': unittest.main()
