"""Native launch ownership, helper fallback boundaries and actual KIO jobs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from tests.test_look import quick_helper


class LaunchHelpers(unittest.TestCase):
    def setUp(self): self.q = quick_helper()

    def fake_dbus(self, *, discovery_error=False, call_error=False, result=None):
        class Error(Exception): pass
        proxy = Mock(); proxy.Open.return_value = result
        if call_error: proxy.Open.side_effect = Error('lost reply')
        bus = Mock(); bus.get_name_owner.return_value = ':1.12'; bus.get_object.return_value = proxy
        if discovery_error: bus.get_name_owner.side_effect = Error('no owner')
        module = types.SimpleNamespace(DBusException=Error, Boolean=bool, SessionBus=Mock(return_value=bus))
        return module, bus, proxy

    def test_request_uses_the_unique_owner_without_introspection_and_preserves_activation(self):
        module, bus, proxy = self.fake_dbus(result={'accepted': True})
        with patch.dict(sys.modules, dbus=module), patch.dict(os.environ, XDG_ACTIVATION_TOKEN='fixture-token'):
            self.assertTrue(self.q.desktop_launch('monet-store.desktop'))
        bus.get_object.assert_called_once_with(':1.12', '/Launcher', introspect=False)
        proxy.Open.assert_called_once_with('monet-store.desktop', False, 'fixture-token', dbus_interface='org.monet.Launcher1', timeout=3)

    def test_no_owner_can_fall_back_but_lost_reply_or_rejection_cannot(self):
        for setup, expected in (({'discovery_error': True}, None), ({'call_error': True}, False),
                                ({'result': {'accepted': False}}, False), ({'result': {'accepted': 'true'}}, False)):
            module, bus, proxy = self.fake_dbus(**setup)
            with patch.dict(sys.modules, dbus=module): self.assertIs(self.q.desktop_launch('fixture.desktop'), expected)
            if setup.get('discovery_error'): proxy.Open.assert_not_called()

    def test_missing_python_dbus_retains_the_legacy_native_launcher(self):
        with patch.dict(sys.modules, dbus=None): self.assertIsNone(self.q.desktop_launch('fixture.desktop'))

    def test_known_native_result_never_spawns_another_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); (folder/'fixture.desktop').write_text('[Desktop Entry]\nType=Application\nExec=fixture\n')
            with patch.object(self.q, 'app_dirs', return_value=(folder,)), patch.object(self.q.subprocess, 'Popen') as start:
                for result in (True, False):
                    with patch.object(self.q, 'desktop_launch', return_value=result):
                        self.assertIs(self.q.launch('fixture.desktop'), result)
                start.assert_not_called()
                with patch.object(self.q, 'desktop_launch', return_value=None), patch.object(self.q.shutil, 'which', return_value='/usr/bin/kioclient'):
                    self.assertTrue(self.q.launch('fixture.desktop'))
                self.assertEqual(start.call_args.args[0], ['kioclient', 'exec', str(folder/'fixture.desktop')])

    def test_invalid_or_missing_entries_are_not_sent_to_the_endpoint(self):
        with patch.object(self.q, 'app_dirs', return_value=()), patch.object(self.q, 'desktop_launch') as native:
            for name in ('../outside.desktop', 'missing.desktop', 'fixture.desktop;touch /tmp/x'):
                self.assertFalse(self.q.launch(name))
            native.assert_not_called()


@unittest.skipUnless(os.environ.get('MONET_LAUNCHER_FIXTURE'), 'native launcher test image')
class NativeLauncher(unittest.TestCase):
    def test_actual_kio_launches_pending_jobs_activation_and_recovery(self):
        fixture = Path(os.environ['MONET_LAUNCHER_FIXTURE'])
        subprocess.run(['sh', str(fixture.with_name('run.sh')), str(fixture)], check=True, timeout=100)

    def test_actual_menu_models_start_feedback_and_notification_retry(self):
        subprocess.run([sys.executable, str(Path(__file__).resolve().parent/'fixtures/launch-menu.py')], check=True, timeout=35)

    @unittest.skipUnless(os.environ.get('MONET_DOCK_LAUNCH_FIXTURE'), 'compiled candidate dock test image')
    def test_compiled_dock_pointer_launches_feedback_and_explicit_new_windows(self):
        fixture = Path(os.environ['MONET_DOCK_LAUNCH_FIXTURE'])
        wrapper = Path(os.environ['MONET_LAUNCHER_FIXTURE']).with_name('run.sh')
        subprocess.run(['sh', str(wrapper), str(fixture)], check=True, timeout=35,
                       env=dict(os.environ, QT_FORCE_STDERR_LOGGING='1'))
