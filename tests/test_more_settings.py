"""More Settings launches its private Qt layout style without changing other apps."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_accessible_desktop import helper


@unittest.skipIf(os.name == "nt", "Linux helper imports")
class MoreSettings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.quick = helper("monet-quick")
        self.quick.LIBEXECDIR = str(Path(self.temp.name) / "libexec")
        self.plugins = Path(self.temp.name) / "lib/monet/qt"

    def test_private_plugin_path_preserves_existing_paths(self):
        plugin = self.plugins / "styles/libmonetsettings.so"
        plugin.parent.mkdir(parents=True)
        plugin.touch()
        with mock.patch.dict(os.environ, {"QT_PLUGIN_PATH": "/other/plugins"}):
            command, env = self.quick.kde_settings_command("kcm_networkmanagement")
            self.assertEqual(command, ["systemsettings", "-style", "MonetSettings", "kcm_networkmanagement"])
            self.assertEqual(env["QT_PLUGIN_PATH"], str(self.plugins) + ":/other/plugins")
            self.assertEqual(os.environ["QT_PLUGIN_PATH"], "/other/plugins")

    def test_source_checkout_without_compiled_plugin_remains_usable(self):
        command, env = self.quick.kde_settings_command("kcm_audiocd")
        self.assertEqual(command, ["systemsettings", "kcm_audiocd"])
        self.assertEqual(env, dict(os.environ))

    def test_kde_action_passes_environment_and_page_to_process(self):
        with mock.patch.object(self.quick.subprocess, "Popen") as start:
            self.assertEqual(self.quick.main(["kde", "wifi"]), 0)
        command = start.call_args.args[0]
        self.assertEqual(command[-1], "kcm_networkmanagement")
        self.assertIn("env", start.call_args.kwargs)
        self.assertTrue(start.call_args.kwargs["start_new_session"])
