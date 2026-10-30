"""Event-driven panel audio, tested against a private sound server."""
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import time
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (importlib.util.find_spec('PySide6') and shutil.which('pipewire') and shutil.which('pipewire-pulse') and shutil.which('pactl')
          and shutil.which('dbus-run-session') and any(Path('/usr').glob('lib*/qt6/qml/org/kde/plasma/private/volume/qmldir')))


@unittest.skipUnless(NATIVE, 'native KDE audio/Qt and private PipeWire server')
class NativeAudio(unittest.TestCase):
    def fixture(self, name):
        with tempfile.TemporaryDirectory(prefix='monet-audio-') as tmp:
            root = Path(tmp)
            for part in ['config', 'data', 'cache', 'state', 'runtime']:
                (root / part).mkdir(mode=0o700)
            env = dict(os.environ, HOME=tmp, MONET_AUDIO_FIXTURE=tmp,
                       XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'),
                       XDG_CACHE_HOME=str(root / 'cache'), XDG_STATE_HOME=str(root / 'state'),
                       XDG_RUNTIME_DIR=str(root / 'runtime'), QT_QPA_PLATFORM='offscreen',
                       QT_QUICK_BACKEND='software', QT_QUICK_CONTROLS_STYLE='Basic',
                       QT_QPA_PLATFORMTHEME='generic', XDG_CURRENT_DESKTOP='',
                       QT_FORCE_STDERR_LOGGING='1', QT_LOGGING_RULES='qml.debug=true',
                       DBUS_SYSTEM_BUS_ADDRESS='unix:path=/nonexistent', PULSE_SERVER='unix:' + str(root / 'runtime/pulse/native'),
                       PIPEWIRE_RUNTIME_DIR=str(root / 'runtime'), PIPEWIRE_REMOTE='pipewire-0',
                       PULSE_RUNTIME_PATH=str(root / 'runtime/pulse'))
            output = root / 'fixture.log'
            with output.open('w') as log:
                proc = subprocess.Popen(['dbus-run-session', '--', 'python3', str(ROOT / 'tests/fixtures/audio-native.py'), name],
                                        env=env, cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
                try:
                    code = proc.wait(timeout=50)
                except subprocess.TimeoutExpired:
                    self.fail('Audio fixture timed out: ' + output.read_text())
                finally:
                    # Native KDE hosts may activate services on this private bus.
                    # Stop the whole fixture group before removing its private home.
                    try: os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    time.sleep(.1)
                    try: os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    proc.wait(timeout=5)
            self.assertEqual(code, 0, output.read_text())


    def test_native_changes_are_immediate_and_idle_does_not_spawn_commands(self):
        self.fixture('native')

    def test_missing_native_module_falls_back_with_fresh_coalesced_requests_and_retry(self):
        self.fixture('fallback')

    def test_disconnect_reconnect_and_late_fallback_do_not_corrupt_the_display(self):
        self.fixture('recovery')

    @unittest.skipUnless(shutil.which('plasmawindowed'), 'native Plasma widget host')
    def test_full_sound_widget_tracks_native_level_and_renders(self):
        self.fixture('widget')
