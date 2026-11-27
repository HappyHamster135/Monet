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


class BatteryEstimate(unittest.TestCase):
    def reading(self, **changes):
        values = dict(IsPresent=True, Type=2, Percentage=70., State=2,
                      TimeToEmpty=5400, EnergyRate=22.1, Energy=33.1, EnergyFull=47.36)
        values.update(changes)
        return {key: {'data': value} for key, value in values.items()}

    def test_estimate_uses_reported_capacity_and_draw_without_inflating_time(self):
        value = quick_helper().battery_state(self.reading(), plugged=False)
        self.assertEqual(value['minutes'], 90)
        self.assertEqual(value['watts'], 22.1)
        self.assertEqual(value['energyWh'], 33.1)
        self.assertEqual(value['fullWh'], 47.4)

    def test_invalid_or_stale_direction_has_no_estimate_or_draw(self):
        q = quick_helper()
        for seconds in (float('nan'), float('inf'), -5, 0, True, '5400'):
            self.assertIsNone(q.battery_state(self.reading(TimeToEmpty=seconds), plugged=False)['minutes'])
        connected = q.battery_state(self.reading(), plugged=True)
        self.assertIsNone(connected['minutes'])
        self.assertIsNone(connected['watts'])
        for state in (4, 5):
            value = q.battery_state(self.reading(State=state), plugged=True)
            self.assertIsNone(value['minutes'])
            self.assertIsNone(value['watts'])
        charging = q.battery_state(self.reading(State=1, TimeToFull=3600), plugged=True)
        self.assertEqual(charging['minutes'], 60)
        self.assertIsNone(charging['watts'])

    def test_health_aggregates_wh_and_excludes_peripherals(self):
        q = quick_helper()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def battery(name, **attrs):
                p = root / name; p.mkdir()
                for key, value in dict(type='Battery', **attrs).items():
                    (p/key).write_text(str(value))
                return p
            battery('BAT0', energy_full=47000000, energy_full_design=52000000)
            second = battery('BAT1', charge_full=2000000, charge_full_design=3000000, voltage_min_design=10000000)
            battery('mouse', scope='Device')
            self.assertEqual(q.battery_health(root), 81.7)
            (second/'charge_full').write_text('nan')
            self.assertIsNone(q.battery_health(root))
            (second/'present').write_text('0')
            self.assertEqual(q.battery_health(root), 90.4)
