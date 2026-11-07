"""Render real Plasma widgets on a private bus and in a disposable home."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[2]
name = sys.argv[1]
assert name in {'stacks', 'transfers'}
assert os.environ.get('QT_QPA_PLATFORM') == 'offscreen'
home = Path(os.environ['HOME'])
assert str(home).startswith('/tmp/monet-tests-'), home
colors = ROOT / 'linux/share/color-schemes' / ('MonetDark.colors' if os.environ.get('MONET_FILES_SMOKE') else 'MonetLight.colors')
(Path(os.environ['XDG_CONFIG_HOME']) / 'kdeglobals').write_text(colors.read_text())
with tempfile.TemporaryDirectory(prefix='monet-files-widget-') as temp:
    folder = Path(temp)
    package = Path(os.environ['XDG_DATA_HOME']) / 'plasma/plasmoids' / ('org.monet.' + name)
    shutil.copytree(ROOT / 'linux/share/plasma/plasmoids' / ('org.monet.' + name), package)
    ui = package / 'contents/ui'
    for part in (ROOT / 'linux/share/monet/widgets').iterdir():
        if part.is_file(): shutil.copy2(part, ui / part.name)
    executable = folder / 'monet-files'
    sample = dict(groups=[dict(name='Images', count=2, items=[dict(name='Water lilies.jpg', folder=False,
        url=(home / 'Desktop/Water lilies.jpg').as_uri(), path=str(home / 'Desktop/Water lilies.jpg').encode().hex())])],
        limited=False, folder=(home / 'Desktop').as_uri())
    executable.write_text('#!/usr/bin/python3\nprint(' + repr(json.dumps(sample)) + ')\n'); executable.chmod(0o700)
    jobs = folder / 'monet-file-jobs'
    sample = {'files': [dict(token='a'*32, name='Summer photos.zip', kind='extract', destination=str(home / 'Desktop/Photos'),
        state='failed', progress=-1, updated=2, error='Extraction did not finish. Partial files were kept.')],
        'store': [dict(token='b'*32, name='Example application', state='running', progress=.42, updated=1, error='')]}
    jobs.write_text('#!/usr/bin/python3\nprint(' + repr(json.dumps(sample)) + ')\n'); jobs.chmod(0o700)
    for part in ui.glob('*.qml'):
        part.write_text(part.read_text().replace('@BINDIR@', str(folder)).replace('@LIBEXECDIR@', str(folder)).replace('@DATADIR@', '/usr/share'))
    main = ui / 'main.qml'; source = main.read_text()
    source = source[:source.rfind('}')] + '''
    Kirigami.Theme.inherit: false
    Kirigami.Theme.backgroundColor: BACKGROUND
    Kirigami.Theme.textColor: INK
    Timer {
        interval: 300; running: true; repeat: true
        onTriggered: {
            root.expanded = true;
            STACK
            if (root.fullRepresentationItem && root.fullRepresentationItem.width > 200) {
                root.fullRepresentationItem.grabToImage(result => result.saveToFile("SNAPSHOT"));
            }
        }
    }
}'''.replace('SNAPSHOT', str(folder / 'widget.png')).replace('STACK', 'root.openGroup = "Images";' if name == 'stacks' else '')
    source = source.replace('BACKGROUND', '"#242321"' if os.environ.get('MONET_FILES_SMOKE') else '"#F3F1EC"')
    source = source.replace('INK', '"#EFECE6"' if os.environ.get('MONET_FILES_SMOKE') else '"#1C1B19"')
    if name == 'transfers':
        source = source.replace('    Timer {\n        interval: 300;',
            '    property int fixtureNativeJobs: nativeJobs.count\n'
            '    onFixtureNativeJobsChanged: console.log("NATIVE_FILE_JOBS", fixtureNativeJobs)\n'
            '    Timer {\n        interval: 300;')
        source = source.replace('root.fullRepresentationItem.grabToImage(result => result.saveToFile("' + str(folder / 'widget.png') + '"));',
            'root.fullRepresentationItem.grabToImage(result => { result.saveToFile("' + str(folder / 'widget.png') + '"); '
            'result.saveToFile("' + str(folder / 'native-') + '" + nativeJobs.count + ".png"); });')
    main.write_text(source)
    with (folder / 'widget.log').open('w') as output:
        process = subprocess.Popen(['plasmawindowed', 'org.monet.' + name], stdout=output, stderr=output,
            env=dict(os.environ, QT_QPA_PLATFORMTHEME='kde', QT_FORCE_STDERR_LOGGING='1', QT_LOGGING_RULES='qml.debug=true'))
        try:
            if name == 'transfers':
                import dbus
                bus = dbus.SessionBus()
                deadline = time.monotonic() + 5
                while 'org.kde.JobViewServer' not in bus.list_names() and time.monotonic() < deadline:
                    time.sleep(.05)
                server = bus.get_object('org.kde.JobViewServer', '/JobViewServer')
                path = server.requestView('org.kde.dolphin', dbus.Int32(3), dbus.Dictionary({'immediate': True}, signature='sv'),
                                          dbus_interface='org.kde.JobViewServerV2')
                view = bus.get_object('org.kde.JobViewServer', path)
                view.setInfoMessage('Copying holiday photos', dbus_interface='org.kde.JobViewV2')
                view.setPercent(dbus.UInt32(35), dbus_interface='org.kde.JobViewV2')
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if (folder / 'widget.png').exists() and (name != 'transfers' or (folder / 'native-1.png').exists()):
                    time.sleep(.3); break
                if process.poll() is not None: break
                time.sleep(.1)
            log = (folder / 'widget.log').read_text()
            assert (folder / 'widget.png').exists(), log
            image = QImage(str(folder / 'widget.png'))
            assert image.width() >= 300 and image.height() >= 200, (image.size(), log)
            lightness = image.pixelColor(image.width() - 20, image.height() - 20).lightness()
            assert (lightness < 128) == bool(os.environ.get('MONET_FILES_SMOKE')), (lightness, log)
            errors = ('is not a type', 'is not installed', 'TypeError:', 'ReferenceError:', 'Cannot assign to non-existent property', 'Unable to assign')
            assert not any(error in log for error in errors), log
            if name == 'transfers': assert (folder / 'native-1.png').exists(), log
            if os.environ.get('MONET_FILES_CAPTURE'):
                dest = Path(os.environ['MONET_FILES_CAPTURE']); dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(folder / 'widget.png', dest / (name + '.png'))
                shutil.copy2(folder / 'widget.log', dest / (name + '.log'))
        finally:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
    shutil.rmtree(package)
