"""Foreground power reads retain native KConfig policy and bound their work."""
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper


class PowerReads(unittest.TestCase):
    def test_foreground_workers_are_bounded_and_results_keep_request_order(self):
        q = quick_helper()
        active = peak = 0
        gate = threading.Lock()

        def read(_file, _group, key, _default):
            nonlocal active, peak
            with gate:
                active += 1
                peak = max(active, peak)
            try:
                time.sleep(.01 * (4 - int(key) % 4))
                return key
            finally:
                with gate: active -= 1

        requests = [('powerdevilrc', 'AC', str(i), '') for i in range(13)]
        with patch.object(q, 'kread', side_effect=read):
            self.assertEqual(q.kread_values(requests), [str(i) for i in range(13)])
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 4)
        self.assertEqual(active, 0)

    @unittest.skipUnless(shutil.which('kreadconfig6'), 'native KConfig reader')
    def test_native_inheritance_locked_groups_and_changes_between_requests(self):
        q = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = root/'config'; system = root/'defaults'
            config.mkdir(); system.mkdir()
            (system/'powerdevilrc').write_text(
                '[AC][Display][$i]\nTurnOffDisplayWhenIdle=true\nTurnOffDisplayIdleTimeoutSec=888\n'
                '[AC][SuspendAndShutdown]\nAutoSuspendIdleTimeoutSec=1234\n'
                '[Battery][Display]\nTurnOffDisplayIdleTimeoutSec=432\n')
            power = config/'powerdevilrc'
            power.write_text('[AC][Display]\nTurnOffDisplayWhenIdle=false\nTurnOffDisplayIdleTimeoutSec=9\n'
                '[Battery][SuspendAndShutdown]\nAutoSuspendAction=0\n')
            locker = config/'kscreenlockerrc'
            locker.write_text('[Daemon]\nAutolock=false\nTimeout=17\nLockOnResume=false\n')
            with patch.dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_CONFIG_DIRS=str(system)), \
                    patch.object(q, 'virtual_machine', return_value=False), \
                    patch.object(q, 'power_mode', return_value=('balanced', ['balanced'])):
                first = q.power_state()
                self.assertEqual(first['ac'], dict(screen=888, sleep=1234))
                self.assertEqual(first['battery'], dict(screen=432, sleep=0))
                self.assertEqual(first['lockAfter'], 0)
                self.assertIs(first['lockOnResume'], False)
                # No process-wide snapshot: the next foreground request sees edits.
                locker.write_text('[Daemon]\nAutolock=true\nTimeout=19\nLockOnResume=true\n')
                second = q.power_state()
                self.assertEqual(second['lockAfter'], 19)
                self.assertIs(second['lockOnResume'], True)
                with patch.object(q, 'kread_values', side_effect=lambda requests: [q.kread(*r) for r in requests]):
                    self.assertEqual(q.power_state(), second)

    def test_malformed_policy_values_retain_existing_defaults(self):
        q = quick_helper()
        with patch.object(q, 'kread', return_value='invalid'), \
                patch.object(q, 'virtual_machine', return_value=False), \
                patch.object(q, 'power_mode', return_value=('', [])):
            state = q.power_state()
        for name, (_, screen, sleep) in q.POWER_STATES.items():
            self.assertEqual(state[name], dict(screen=screen, sleep=sleep))
        self.assertEqual(state['button'], q.ASK)
        self.assertEqual(state['lidAction'], q.SLEEP)
        self.assertEqual(state['lockAfter'], 5)
