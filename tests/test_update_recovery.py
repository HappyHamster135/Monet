"""Upgrade regressions using disposable caches, processes and desktop services."""
import contextlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]


class UpdateInstall(unittest.TestCase):
    def test_slow_updates_have_no_deadline_and_failed_apps_keep_pending_restart(self):
        q = quick_helper()
        held = []
        @contextlib.contextmanager
        def awake():
            held.append(True)
            try:
                yield
            finally:
                held.pop()
        def run(*args, **kwargs):
            self.assertEqual(held, [True])
            self.assertIsNone(kwargs.get('timeout'))
            return subprocess.CompletedProcess(args, 1, 'System staged\n', 'App update failed')
        with patch.object(q, 'update_display_awake', awake), patch.object(q.subprocess, 'run', side_effect=run), \
                patch.object(q, 'update_waiting', return_value=True):
            reply = q.install_updates()
        self.assertEqual(reply, dict(ok=False, staged=True, message='System staged\nApp update failed'))
        self.assertEqual(held, [])

    def test_missing_updater_still_reports_existing_staged_deployment(self):
        q = quick_helper()
        with patch.object(q, 'update_display_awake', contextlib.nullcontext), \
                patch.object(q.subprocess, 'run', side_effect=OSError('updater missing')), \
                patch.object(q, 'update_waiting', return_value=True):
            self.assertEqual(q.install_updates(), dict(ok=False, staged=True, message='updater missing'))

    def test_native_display_hold_is_connection_owned_and_does_not_inhibit_lock_screen(self):
        try:
            import dbus
            import gi
            gi.require_version('Gio', '2.0')
            from gi.repository import Gio, GLib
        except ImportError:
            self.skipTest('Linux GLib and Python D-Bus')
        from tools.test import private_session
        # Subprocesses use a private bus, never the laptop's power service.
        with private_session() as env, patch.dict(os.environ, env):
            fixture = ROOT / 'tests/fixtures/keep-awake-native.py'
            fake = subprocess.Popen([sys.executable, str(fixture), 'fake'],
                env=dict(env, MONET_KEEP_AWAKE_PRIVATE_BUS='1'), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            bus = None
            try:
                self.assertTrue(select.select([fake.stdout], [], [], 5)[0])
                self.assertEqual(fake.stdout.readline().strip(), 'READY')
                bus = dbus.SessionBus(private=True)
                proxy = bus.get_object('org.monet.KeepAwakeTest', '/org/monet/KeepAwakeTest', introspect=False)
                def snapshot():
                    return json.loads(str(proxy.Snapshot(dbus_interface='org.monet.KeepAwakeTest', timeout=3)))
                q = quick_helper()
                for fail in (False, True):
                    try:
                        with q.update_display_awake():
                            self.assertEqual([item['kind'] for item in snapshot()], ['power'])
                            if fail:
                                raise OSError('download failed')
                    except OSError:
                        pass
                    deadline = time.monotonic() + 3
                    while snapshot() and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertEqual(snapshot(), [])
            finally:
                if bus is not None:
                    bus.close()
                fake.terminate()
                fake.communicate(timeout=5)


class FreshCaches(unittest.TestCase):
    def test_upgrade_same_version_rebuild_and_rollback_clear_only_regenerable_caches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache, config, data, helpers = [root / name for name in ('cache', 'config', 'data', 'bin')]
            for p in (cache, config / 'monet', data / 'monet', helpers):
                p.mkdir(parents=True)
            for name in ('monet', 'monet-profile', 'monet-region', 'monet-quick'):
                file = helpers / name
                file.write_text('#!/bin/sh\n' + ('echo "monet 0.9.8-5"\n' if name == 'monet' else 'exit 0\n'))
                file.chmod(0o755)
            script = root / 'fresh'
            script.write_text((ROOT / 'linux/libexec/monet-fresh').read_text()
                .replace('@BINDIR@', str(helpers)).replace('@LIBEXECDIR@', str(helpers))
                .replace('@DATADIR@', str(data)))
            revision = data / 'monet/desktop-revision'
            env = dict(os.environ, XDG_CACHE_HOME=str(cache), XDG_CONFIG_HOME=str(config))
            def run():
                result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
            ordinary = cache / 'monet/settings/important'
            ordinary.parent.mkdir(parents=True)
            ordinary.write_text('keep')
            outside = root / 'outside'
            (outside / 'qmlcache').mkdir(parents=True)
            (outside / 'qmlcache/keep').write_text('keep')
            (cache / 'linked-app').symlink_to(outside, target_is_directory=True)
            for identity in ('first', 'rebuilt', 'first'):
                revision.write_text(identity)
                for name in ('plasmashell/qmlcache/code.qmlc', 'monet/settings/qmlcache/code.qmlc', 'ksycoca6_fixture'):
                    file = cache / name
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text('stale')
                run()
                self.assertFalse((cache / 'plasmashell/qmlcache').exists())
                self.assertFalse((cache / 'monet/settings/qmlcache').exists())
                self.assertFalse((cache / 'ksycoca6_fixture').exists())
                self.assertEqual(ordinary.read_text(), 'keep')
                self.assertEqual((outside / 'qmlcache/keep').read_text(), 'keep')
                regenerated = cache / 'plasmashell/qmlcache/new.qmlc'
                regenerated.parent.mkdir(parents=True)
                regenerated.write_text('valid')
                run()
                self.assertEqual(regenerated.read_text(), 'valid')

    def test_a_failing_setup_step_does_not_empty_the_caches_at_every_login(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache, config, data, helpers = [root / name for name in ('cache', 'config', 'data', 'bin')]
            for p in (cache, config / 'monet', data / 'monet', helpers):
                p.mkdir(parents=True)
            for name in ('monet', 'monet-profile', 'monet-region', 'monet-quick'):
                file = helpers / name
                # Region setup keeps failing; it retries by its own flag.
                file.write_text('#!/bin/sh\n' + {'monet': 'echo "monet 0.9.8-6"\n', 'monet-region': 'exit 1\n'}.get(name, 'exit 0\n'))
                file.chmod(0o755)
            script = root / 'fresh'
            script.write_text((ROOT / 'linux/libexec/monet-fresh').read_text()
                .replace('@BINDIR@', str(helpers)).replace('@LIBEXECDIR@', str(helpers))
                .replace('@DATADIR@', str(data)))
            env = dict(os.environ, XDG_CACHE_HOME=str(cache), XDG_CONFIG_HOME=str(config))
            compiled = cache / 'plasmashell/qmlcache/code.qmlc'
            compiled.parent.mkdir(parents=True)
            compiled.write_text('stale')
            first = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 1, 'the failed step is still reported')
            self.assertFalse(compiled.exists())
            self.assertTrue((cache / 'monet-version').exists())
            compiled.parent.mkdir(parents=True)
            compiled.write_text('valid')
            subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(compiled.read_text(), 'valid')


class SoundRepair(unittest.TestCase):
    def test_duplicate_controls_are_removed_once_without_changing_other_panels(self):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            self.skipTest('Qt JavaScript runtime')
        app = QCoreApplication.instance() or QCoreApplication([])
        engine = QJSEngine()
        engine.evaluate('''
            function panel(monet, quick) {
                var config = {extraItems:"org.kde.plasma.volume,custom", shownItems:"org.kde.plasma.volume,custom",
                              hiddenItems:"org.kde.plasma.volume,clipboard", knownItems:"custom"};
                var list = ["org.kde.plasma.volume", "org.kde.plasma.systemtray"];
                if (monet) list.push("org.monet.sound", "org.monet.sound");
                if (quick) list.push("org.monet.quick");
                var widgets = list.map(type => ({type:type, remove:function(){widgets.splice(widgets.indexOf(this),1)},
                    readConfig:key=>config[key]||"", writeConfig:(key,value)=>config[key]=value.join(","), reloadConfig:()=>{}}));
                return {widgets:type=>widgets.filter(w=>w.type===type), all:()=>widgets.map(w=>w.type), config:config};
            }
            var active=panel(true,true), noSound=panel(false,true), custom=panel(true,false);
            function panels(){return [active,noSound,custom]}
        ''')
        source = (ROOT / 'linux/share/monet/repair-sound.js').read_text()
        for _ in range(2):
            result = engine.evaluate(source)
            self.assertFalse(result.isError(), result.toString())
        result = json.loads(engine.evaluate('JSON.stringify(panels().map(p=>({widgets:p.all(),config:p.config})))').toString())
        self.assertEqual(result[0]['widgets'].count('org.monet.sound'), 1)
        self.assertNotIn('org.kde.plasma.volume', result[0]['widgets'])
        self.assertEqual(result[0]['config']['extraItems'], 'custom')
        self.assertEqual(result[0]['config']['shownItems'], 'custom')
        self.assertEqual(result[0]['config']['hiddenItems'], 'clipboard')
        self.assertIn('org.kde.plasma.volume', result[0]['config']['knownItems'])
        for panel in result[1:]:
            self.assertIn('org.kde.plasma.volume', panel['widgets'])
            self.assertIn('org.kde.plasma.volume', panel['config']['extraItems'])


if __name__ == '__main__':
    unittest.main()
