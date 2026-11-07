"""Temporary inhibition preserves policy and releases owned cookies on every exit."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet'))
from monet_runtime.keep_awake import Controller, DesktopBackend
from tests.test_look import quick_helper


class Backend:
    def __init__(self): self.held = 0; self.fail = False
    def acquire(self):
        if self.fail: raise RuntimeError('unavailable')
        self.held += 1
        return (self.held,)
    def release(self, cookies): self.held -= 1


class KeepAwake(unittest.TestCase):
    def test_duration_replacement_expiry_and_indefinite_do_not_accumulate_cookies(self):
        now = [100.]
        backend = Backend(); c = Controller(backend, lambda: now[0])
        self.assertTrue(c.set_duration(1800)['ok'])
        self.assertEqual(c.status()['remaining'], 1800)
        now[0] += 30
        c.set_duration(3600)
        self.assertEqual(backend.held, 1)
        self.assertEqual(c.status()['remaining'], 3600)
        now[0] += 3601
        self.assertTrue(c.expired()); self.assertEqual(backend.held, 0)
        c.set_duration(-1); now[0] += 1e7
        self.assertFalse(c.expired()); self.assertTrue(c.status()['indefinite'])
        c.set_duration(0); self.assertEqual(backend.held, 0)

    def test_backend_restart_failure_and_retry_keep_the_original_deadline(self):
        now = [50.]; backend = Backend(); c = Controller(backend, lambda: now[0])
        c.set_duration(1800); end = c.end
        backend.fail = True; c.backend_changed()
        self.assertFalse(c.status()['active']); self.assertTrue(c.status()['pending'])
        self.assertEqual(backend.held, 0)
        now[0] += 80; backend.fail = False; c.backend_changed()
        self.assertTrue(c.status()['active']); self.assertEqual(c.end, end)
        self.assertEqual(c.status()['remaining'], 1720)
        c.stop(); self.assertEqual(backend.held, 0)

    def test_invalid_requests_preserve_an_existing_hold(self):
        backend = Backend(); c = Controller(backend)
        c.set_duration(-1)
        for value in (None, True, '30', -5, 86401):
            self.assertFalse(c.set_duration(value)['ok'])
            self.assertTrue(c.status()['active'])
            self.assertEqual(backend.held, 1)
        c.stop()

    def test_partial_acquire_rolls_back_against_the_exact_unique_owner(self):
        backend = DesktopBackend(None, None, None)
        with patch.object(backend, 'owner', return_value=':1.44'), \
             patch.object(backend, 'call', side_effect=[(7,), RuntimeError('screen failed'), ()]) as call:
            with self.assertRaises(RuntimeError): backend.acquire()
        self.assertEqual(call.call_args_list[-1].args[0][0], ':1.44')
        self.assertEqual(call.call_args_list[-1].args[1:], ('ReleaseInhibition', '(u)', (7,)))

    def test_malformed_timing_is_not_reported_as_an_active_hold(self):
        q = quick_helper()
        state = dict(active=True, duration=1800, remaining=1799, end=9000, indefinite=False, pending=False)
        for key, value in [('remaining', float('nan')), ('end', float('inf')),
                           ('duration', True), ('pending', None), ('indefinite', 0)]:
            broken = dict(state, **{key:value})
            result = q.awake_reply([json.dumps(broken)])
            self.assertFalse(result['ok']); self.assertFalse(result['state']['active'])

    def test_inactive_reads_do_not_start_a_process_or_activate_the_service(self):
        q = quick_helper()
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, XDG_RUNTIME_DIR=folder), \
             patch.object(q, 'busjson') as bus, patch.object(q, 'kwrite') as write:
            self.assertFalse(q.keep_awake_status()['active'])
            bus.assert_not_called(); write.assert_not_called()
            marker = q.awake_marker(); marker.parent.mkdir()
            marker.write_text('{"owner":":1.42"}')
            bus.return_value = None
            self.assertEqual(q.keep_awake_status()['error'], 'interrupted')
            self.assertTrue(q.set_keep_awake('off')['ok']); self.assertFalse(marker.exists())
            write.assert_not_called()


@unittest.skipUnless(sys.platform == 'linux' and importlib.util.find_spec('gi'), 'requires Linux GLib D-Bus')
class NativeKeepAwake(unittest.TestCase):
    def test_native_owned_inhibitions_expiry_backend_restart_and_crash(self):
        from tools.test import private_session
        with private_session() as env:
            env['MONET_KEEP_AWAKE_PRIVATE_BUS'] = '1'
            result = subprocess.run([sys.executable, str(ROOT/'tests/fixtures/keep-awake-native.py'), 'exercise'],
                                    env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
