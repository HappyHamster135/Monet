#!/usr/bin/python3
"""Install, load and undo the complete native preview in a disposable account.

Run in a matching desktop container, never with the host display or buses.
The wrapper smoke checks inspect the actual child executable and loaded library.
"""
import contextlib
import importlib.util
import io
import json
import os
import select
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main(bundles, output, regression=''):
    bundles = Path(bundles)
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    report = {}
    with private_session() as env, patch.dict(os.environ, {}, clear=True):
        os.environ.update(env)
        p = load('native_preview_installer', ROOT / 'tools/install-desktop-preview.py')
        files = p.plan(native_bundles=bundles)
        report['planned_files'] = len(files)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream): p.apply(files)
        installed = json.loads(stream.getvalue()); receipt = Path(installed['receipt'])
        report['installed_files'] = installed['installed_files']
        assert receipt.stat().st_mode & 0o777 == 0o600
        native = load('monet_native_preview', p.HELPERS / 'monet_native_preview.py')
        manifest = native.read()
        assert set(manifest['components']) == {'activity', 'launcher', 'dock', 'dolphin', 'ark'}
        assert all(native.valid(component) for component in manifest['components'].values())
        native.prepare(include_dock=True)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtTest import QTest
        app = QGuiApplication([])
        engine = QQmlApplicationEngine()
        engine.loadData(b'''import QtQuick
import org.monet.activity 1.0
import org.monet.launcher 1.0
QtObject {
    property QtObject activity: Activity {}
    property QtObject launcher: Launcher {}
    property QtObject folder: FolderOpener {}
}''', QUrl('file:///native-preview-install.qml'))
        assert engine.rootObjects(), 'Account native QML modules did not load'
        QTest.qWait(50)
        maps = Path('/proc/self/maps').read_text()
        for name, plugin in (('activity', 'libmonetactivityplugin.so'), ('launcher', 'libmonetlauncherplugin.so')):
            expected = p.PRIVATE / 'native' / name / 'qml/org/monet' / name / plugin
            assert str(expected) in maps, ('Loaded the wrong native module', name)
        report['account_qml_modules'] = ['activity', 'launcher', 'FolderOpener']
        report['app_entry_points'] = {}
        for name in ('settings','store','games'):
            process = subprocess.Popen([sys.executable,str(p.HELPERS/('monet-'+name))],
                env=dict(os.environ, TMPDIR=env['XDG_RUNTIME_DIR'], MONET_STARTUP_TIMING='1', QT_FORCE_STDERR_LOGGING='1'),
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
            collected='';first=False
            try:
                deadline=time.monotonic()+15
                while time.monotonic()<deadline and process.poll() is None:
                    if select.select([process.stderr],[],[],.1)[0]:
                        raw=os.read(process.stderr.fileno(),65536)
                        if not raw:break
                        collected+=raw.decode('utf-8','replace')
                        first=any(line.startswith('MONET_STARTUP ') and '"phase": "first-frame"' in line for line in collected.splitlines())
                        if first:break
                assert first,(name,process.poll(),collected)
                report['app_entry_points'][name]='actual installed helper painted its first frame'
            finally:stop(process);process.stderr.close()
        # Prove this entry-point check catches the actual packaging omission,
        # rather than merely loading a plugin on a different import path.
        shared = p.PRIVATE / 'monet/widgets'; destination = shared.readlink(); shared.unlink()
        try:
            negative_cache = Path(env['XDG_CACHE_HOME']) / 'missing-shared-import'; negative_cache.mkdir()
            negative = subprocess.run([sys.executable,str(p.HELPERS/'monet-settings')],
                env=dict(os.environ,TMPDIR=env['XDG_RUNTIME_DIR'],XDG_CACHE_HOME=str(negative_cache),QT_FORCE_STDERR_LOGGING='1'),
                capture_output=True,text=True,timeout=10)
            assert negative.returncode == 1 and '"../widgets": no such directory' in negative.stderr, negative.stderr
            report['missing_shared_import_negative'] = 'removing only the private sibling link reproduces the app-loading failure'
        finally: shared.symlink_to(destination)
        report['wrappers'] = {}
        for name in ('dolphin', 'ark'):
            executable = p.PRIVATE / 'native' / name / name
            log = output.with_name(output.stem + '-' + name + '.log')
            with log.open('w') as handle:
                process = subprocess.Popen([str(Path.home() / '.local/bin' / name)],
                    env=dict(os.environ, TMPDIR=env['XDG_RUNTIME_DIR']), stdout=handle,
                    stderr=handle, start_new_session=True)
                try:
                    deadline = time.monotonic() + 10
                    loaded = False
                    while time.monotonic() < deadline and process.poll() is None:
                        try:
                            actual = Path('/proc') / str(process.pid) / 'exe'
                            mappings = (actual.parent / 'maps').read_text()
                            loaded = actual.resolve() == executable and (name != 'dolphin' or
                                str(p.PRIVATE / 'native/dolphin/libdolphinprivate.so.') in mappings)
                            if loaded: break
                        except (FileNotFoundError, PermissionError): pass
                        time.sleep(.02)
                    assert loaded, (name, process.poll(), log.read_text())
                    QTest.qWait(300)
                    assert process.poll() is None, (name, log.read_text())
                    report['wrappers'][name] = 'paired account executable loaded'
                finally: stop(process)
        if regression:
            summary = output.with_name(output.stem + '-regression.json')
            modules = regression.split(',')
            tested = dict(os.environ,
                MONET_ACTIVITY_FIXTURE=str(bundles / 'activity/tests/activity-test'),
                MONET_LAUNCHER_FIXTURE=str(bundles / 'launcher/tests/launcher-test'),
                MONET_TRANSFER_CAPTURE=str(output.with_name(output.stem + '-transfers')))
            subprocess.run([sys.executable, str(ROOT / 'tools/test.py'), '--require-desktop',
                '--summary', str(summary), *modules], env=tested, check=True, timeout=600)
            result = json.loads(summary.read_text())
            assert not result['failed'] and result['skipped'] == 0, result
            report['regression'] = {'summary': str(summary), 'checks': result['tests'], 'skipped': result['skipped']}
        # A later user change survives undo; every other installed path returns
        # to its recorded pre-install value, including native wrappers/modules.
        personal = p.CONFIG / 'systemd/user/monet-fresh.service'
        personal.write_text('later personal edit')
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream): p.restore(receipt)
        restored = json.loads(stream.getvalue())
        assert restored['preserved_edits'] == [str(personal)], restored
        for row in json.loads(receipt.read_text())['files']:
            path = Path(row['path'])
            if path != personal: assert p.digest(path) == row['before'], path
        report['undo'] = 'all unchanged paths restored; later personal edit preserved'
        report['native_fallback_unit_checks'] = 'tests.test_native_preview'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main(*sys.argv[1:])
