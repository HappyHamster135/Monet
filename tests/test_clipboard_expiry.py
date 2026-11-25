"""Clipboard expiry must fail safely across invalid settings and service failures."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
import clipboard_expiry as expiry


class ClipboardExpiry(unittest.TestCase):
    def setUp(self):
        config = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, XDG_CONFIG_HOME=config))

    def test_default_off_and_independent_triggers(self):
        self.assertFalse(expiry.read_policy().enabled())
        for policy in (expiry.Policy(15), expiry.Policy(lock=True), expiry.Policy(sleep=True)):
            with self.subTest(policy=policy):
                self.assertTrue(policy.enabled())
                with patch.object(expiry, "control", return_value=Mock(returncode=0, stdout="disabled")) as ctl:
                    expiry.configure(policy)
                self.assertEqual(expiry.read_policy(), policy)
                self.assertEqual([c.args[0] for c in ctl.call_args_list], ["is-enabled", "enable", "reload-or-restart"])

    def test_invalid_inputs_cannot_activate_timers_or_lock_triggers(self):
        for args in ((True,), (1,), (-15,), (60, "false"), (0, False, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                expiry.Policy(*args)

    def test_failed_activation_restores_previous_config_and_unit(self):
        previous = expiry.Policy(60, True)
        expiry.config_path().parent.mkdir()
        expiry.write_policy(previous)
        with patch.object(expiry, "control", return_value=Mock(stdout="enabled")), \
             patch.object(expiry, "configure_unit", side_effect=[RuntimeError("failed"), None]) as apply:
            with self.assertRaisesRegex(RuntimeError, "failed"):
                expiry.configure(expiry.Policy())
        self.assertEqual(expiry.read_policy(), previous)
        self.assertEqual([call.args[0] for call in apply.call_args_list], [False, True])

    def test_unreadable_policy_is_preserved(self):
        path = expiry.config_path()
        path.parent.mkdir()
        path.write_text("{")
        with patch.object(expiry, "control") as ctl, self.assertRaises(json.JSONDecodeError):
            expiry.configure(expiry.Policy(15))
        ctl.assert_not_called()
        self.assertEqual(path.read_text(), "{")
