"""Game top-row routing without grabbing the host keyboard or sending real input."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('game_keys', str(ROOT / 'linux/libexec/monet-game-keys'))
keys = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(keys)


class Routing(unittest.TestCase):
    def test_all_twelve_keys_and_fn_reverse_only_in_games(self):
        for standard, special in zip(keys.FUNCTION, keys.SPECIAL):
            for active in (False, True):
                mapper = keys.Keys()
                for code, expected in ((special, standard if active else special),
                                       (standard, special if active else standard)):
                    self.assertEqual(mapper.event(code, 1, active), [(expected, 1)])
                    self.assertEqual(mapper.event(code, 2, active), [(expected, 2)])
                    self.assertEqual(mapper.event(code, 0, active), [(expected, 0)])

    def test_alt_tab_while_holding_a_key_keeps_its_release_matched(self):
        for before in (True, False):
            mapper = keys.Keys()
            code = keys.SPECIAL[2]
            out = keys.FUNCTION[2] if before else code
            self.assertEqual(mapper.event(code, 1, before), [(out, 1)])
            self.assertEqual(mapper.event(code, 2, not before), [(out, 2)])
            self.assertEqual(mapper.event(code, 0, not before), [(out, 0)])
            self.assertEqual(mapper.event(code, 1, not before), [(code if before else keys.FUNCTION[2], 1)])

    def test_regular_typing_modifiers_and_other_shortcuts_pass_through(self):
        mapper = keys.Keys()
        for code in (1, 30, 57, 29, 42, 56, 125, 166, 163, 228, 240):
            self.assertEqual(mapper.event(code, 1, True), [(code, 1)])
            self.assertEqual(mapper.event(code, 0, False), [(code, 0)])
        self.assertEqual(mapper.release(), [])

    def test_same_output_does_not_release_a_second_held_key(self):
        mapper = keys.Keys()
        self.assertEqual(mapper.event(115, 1, True), [(61, 1)])
        self.assertEqual(mapper.event(61, 1, False), [])
        self.assertEqual(mapper.event(115, 0, False), [])
        self.assertEqual(mapper.event(61, 0, False), [(61, 0)])

    def test_overflow_releases_every_held_output_once(self):
        mapper = keys.Keys()
        mapper.event(115, 1, True)
        mapper.event(61, 1, False)
        mapper.event(30, 1, True)
        self.assertEqual(sorted(mapper.release()), [(30, 0), (61, 0)])
        self.assertEqual(mapper.event(115, 0, False), [])
        self.assertEqual(mapper.release(), [])


class Foreground(unittest.TestCase):
    def setUp(self):
        self.events, self.identities = [], {10: 'game-start', 20: 'steam-start', 30: 'browser-start'}
        self.games = {10}
        self.enabled = True
        self.focus = keys.Focus(lambda pid: pid in self.games, self.identities.get,
                                self.events.append, lambda: self.enabled)

    def front(self, active, full=()):
        self.focus.report(json.dumps(dict(active=active, full=list(full))))

    def test_focus_alt_tab_and_return(self):
        self.front(10)
        self.assertEqual(self.events, [True])
        self.front(30, [10])  # Full-screen game on another monitor is not focused.
        self.assertEqual(self.events, [True, False])
        self.front(10)
        self.focus.close()
        self.assertEqual(self.events, [True, False, True, False])

    def test_steam_library_sharing_game_unit_is_not_a_game(self):
        self.front(20, [10])
        self.assertEqual(self.events, [])

    def test_exit_and_pid_reuse_end_the_lease(self):
        self.front(10)
        self.identities[10] = 'new-process'
        self.focus.tick()
        self.assertEqual(self.events, [True, False])
        self.focus.tick()
        self.assertEqual(self.events, [True, False])

    def test_preference_changes_and_heartbeat(self):
        self.front(10)
        self.focus.tick()
        self.enabled = False
        self.focus.tick()
        self.assertEqual(self.events, [True, True, False])

    def test_malformed_foreground_always_restores(self):
        for text in ('bad', '[]', '{}', '{"active":true}', '{"active":-1}', '{"active":"10"}'):
            self.front(10)
            self.focus.report(text)
            self.assertFalse(self.focus.active, text)


class Boundaries(unittest.TestCase):
    def test_local_session_only_and_lease_expires_after_crash(self):
        lease = keys.Lease()
        lease.request(b'game', 1001, 1000, 0)
        self.assertFalse(lease.active(1000, 1))
        lease.request(b'game', 1000, 1000, 10)
        self.assertTrue(lease.active(1000, 11))
        self.assertFalse(lease.active(None, 11))  # locked / signed out
        self.assertFalse(lease.active(1001, 11))  # fast user switch
        self.assertFalse(lease.active(1000, 10 + keys.LEASE))
        lease.request(b'game', 1000, 1000, 20)
        lease.request(b'normal', 1000, 1000, 21)
        self.assertFalse(lease.active(1000, 21))

    def test_only_the_verified_laptop_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            dmi = Path(folder)
            self.assertFalse(keys.supported(dmi))
            (dmi / 'sys_vendor').write_text('LENOVO\n')
            for model in keys.MODELS:
                (dmi / 'product_version').write_text(model + '\n')
                self.assertTrue(keys.supported(dmi))
            (dmi / 'product_version').write_text('Some other ThinkPad')
            self.assertFalse(keys.supported(dmi))

    def test_external_and_virtual_devices_never_remapped(self):
        self.assertTrue(keys.built_in('AT Translated Set 2 keyboard', 'isa0060/serio0/input0'))
        self.assertTrue(keys.built_in('ThinkPad Extra Buttons', 'thinkpad_acpi/input0'))
        self.assertTrue(keys.built_in('Video Bus', 'LNXVIDEO/video/input0'))
        for name, phys in [('AT Translated Set 2 keyboard', 'usb/input0'), ('USB keyboard', 'usb/input0'),
                           ('Monet game keys: AT Translated Set 2 keyboard', 'monet/game-keys'),
                           ('Logitech MX Anywhere 3S', 'usb/input1')]:
            self.assertFalse(keys.built_in(name, phys))

    def test_keyboard_attachment_does_not_grab_while_keys_are_held(self):
        device = Mock()
        device.name = 'AT Translated Set 2 keyboard'
        device.capabilities.return_value = {1: [30, 59]}
        device.active_keys.return_value = [56]
        with patch('evdev.UInput') as output:
            with self.assertRaises(OSError):
                keys.Keyboard(device)
            device.ungrab.assert_called_once()
            output.return_value.close.assert_called_once()

    def test_no_profile_or_bios_setting_written(self):
        service = (ROOT / 'linux/systemd/monet-game-keys.service').read_text()
        self.assertIn('ProtectSystem=strict', service)
        self.assertIn('ProtectHome=yes', service)
        self.assertIn('NoNewPrivileges=yes', service)

    def test_virtual_keyboard_never_advertises_the_hardware_radio_switch(self):
        from evdev import ecodes as e, InputDevice
        device = Mock(spec=InputDevice)
        device.name = 'ThinkPad Extra Buttons'
        device.capabilities.return_value = {e.EV_KEY: [e.KEY_WLAN], e.EV_SW: [e.SW_RFKILL_ALL]}
        device.active_keys.return_value = []
        with patch('evdev.UInput') as output:
            keyboard = keys.Keyboard(device)
            caps = output.call_args.args[0]
            self.assertNotIn(e.EV_SW, caps)
            self.assertTrue(set(keys.SWAP).issubset(caps[e.EV_KEY]))
            output.return_value.write.assert_not_called()
            output.return_value.write_event.assert_not_called()
            keyboard.close()

    def test_real_switch_changes_return_to_the_original_kernel_handler(self):
        from evdev import ecodes as e, InputEvent, InputDevice
        device = Mock(spec=InputDevice)
        device.name = 'ThinkPad Extra Buttons'
        device.capabilities.return_value = {e.EV_KEY: [e.KEY_WLAN], e.EV_SW: [e.SW_RFKILL_ALL]}
        device.active_keys.return_value = []
        with patch('evdev.UInput') as output:
            keyboard = keys.Keyboard(device)
            device.read.return_value = [InputEvent(0, 0, e.EV_SW, e.SW_RFKILL_ALL, 0)]
            with self.assertRaisesRegex(OSError, 'Physical wireless switch'):
                keyboard.read(False)
            output.return_value.write_event.assert_not_called()
            keyboard.close()
            device.ungrab.assert_called_once()

    def test_dropped_events_also_resync_the_physical_switch(self):
        from evdev import ecodes as e, InputEvent, InputDevice
        device = Mock(spec=InputDevice)
        device.name = 'ThinkPad Extra Buttons'
        device.capabilities.return_value = {e.EV_KEY: [e.KEY_WLAN], e.EV_SW: [e.SW_RFKILL_ALL]}
        device.active_keys.return_value = []
        with patch('evdev.UInput'):
            keyboard = keys.Keyboard(device)
            device.read.return_value = [InputEvent(0, 0, e.EV_SYN, e.SYN_DROPPED, 0),
                                       InputEvent(0, 0, e.EV_SYN, e.SYN_REPORT, 0)]
            with self.assertRaisesRegex(OSError, 'Physical wireless switch'):
                keyboard.read(True)
            keyboard.close()

    def test_other_hardware_switches_are_not_grabbed_or_cloned(self):
        from evdev import ecodes as e
        device = Mock()
        device.capabilities.return_value = {e.EV_KEY: [e.KEY_F1], e.EV_SW: [e.SW_LID]}
        with patch('evdev.UInput') as output:
            with self.assertRaises(OSError): keys.Keyboard(device)
            output.assert_not_called()
            device.grab.assert_not_called()


if __name__ == '__main__':
    unittest.main()
