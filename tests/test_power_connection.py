"""A battery's charging state does not establish that a charger is connected."""
from pathlib import Path
import tempfile
import unittest

from tests.test_look import quick_helper


class MainsConnection(unittest.TestCase):
    def test_disconnected_and_multiple_chargers_and_device_scope(self):
        q = quick_helper()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIsNone(q.mains_state(root))
            mains = root / 'AC'; mains.mkdir()
            (mains / 'type').write_text('Mains\n')
            (mains / 'online').write_text('0\n')
            self.assertIs(q.mains_state(root), False)
            usb = root / 'USB-C'; usb.mkdir()
            (usb / 'type').write_text('USB_PD\n'); (usb / 'online').write_text('1\n')
            self.assertIs(q.mains_state(root), True)
            (usb / 'scope').write_text('Device\n')
            self.assertIs(q.mains_state(root), False)
            (mains / 'online').write_text('unavailable\n')
            self.assertIsNone(q.mains_state(root))

    def test_full_or_pending_battery_respects_actual_connection(self):
        q = quick_helper()
        for state in (4, 5):
            props = {key: {'data': value} for key, value in
                     dict(IsPresent=True, Type=2, Percentage=100., State=state).items()}
            self.assertFalse(q.battery_state(props, plugged=False)['plugged'])
            self.assertTrue(q.battery_state(props, plugged=True)['plugged'])
