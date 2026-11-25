"""Conditional wake holds follow hardware and app identity without extending timers."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet'))
from monet_runtime.awake_apps import desktop_id
from monet_runtime.awake_rules import RuleMonitor, external_connected, preferences, reasons, watching
from monet_runtime.keep_awake import Controller


class Rules(unittest.TestCase):
    def test_app_units_handle_launchers_escaped_names_and_multiple_instances(self):
        for name in ('app-org.kde.example-51.scope', 'app-flatpak-org.kde.example-72.scope',
                     'app-org.kde.example@e35.service', 'app-KDE-org.kde.example.service'):
            self.assertEqual(desktop_id(name), 'org.kde.example.desktop')
        self.assertEqual(desktop_id(r'app-example\x2dreader@autostart.service'), 'example-reader.desktop')
        self.assertEqual(desktop_id(r'app-les\xc3\xa9@1.service'), 'lesé.desktop')
        for name in ('background.slice', 'org.kde.example.service', 'app-invalid-2.target'):
            self.assertEqual(desktop_id(name), '')

    def test_matching_is_per_app_and_independent_of_other_conditions(self):
        rules = dict(visible=True, enabled=True, power=True, external=True,
                     apps={'Reader.desktop': ['ebook'], 'Music.desktop': []})
        self.assertEqual(reasons(rules, True, True, {'ebook'}, {'Music.desktop'}),
                         ['Music.desktop', 'Reader.desktop', 'external', 'power'])
        self.assertEqual(reasons(rules, False, False, {'reader-tools'}, {'Different.desktop'}), [])
        self.assertEqual(reasons(dict(rules, visible=False), True, True, {'reader'}), [])

    @unittest.skipUnless(importlib.util.find_spec("PySide6"), "requires Qt preferences")
    def test_preferences_ignore_incomplete_rules_and_preserve_choices_while_hidden(self):
        from PySide6.QtCore import QSettings
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'user.ini'), QSettings.IniFormat)
            settings.setValue('awakeRules', json.dumps(dict(enabled=True, apps={'/bad.desktop': [], 'ok.desktop': []})))
            self.assertTrue(watching(preferences(settings)))
            settings.setValue('hidden', '["awake"]')
            saved = preferences(settings)
            self.assertEqual(saved['apps'], {'ok.desktop': []})
            self.assertFalse(watching(saved))
            settings.setValue('awakeRules', 'null')
            self.assertFalse(watching(preferences(settings)))

    @unittest.skipUnless(sys.platform == 'linux' and importlib.util.find_spec('gi'), 'requires the Linux DRM hotplug monitor')
    def test_display_hotplug_ignores_internal_panel_and_coalesces_notifications(self):
        import gi
        try:
            gi.require_version('GUdev', '1.0')
        except ValueError:
            self.skipTest('requires GUdev')
        from gi.repository import Gio, GLib

        class Backend:
            held = False
            def acquire(self, keep_display=True):
                self.held = True
                return ('cookie',)
            def release(self, cookies):
                self.held = False
        backend = Backend()
        monitor = RuleMonitor(backend, Controller(backend), Gio, GLib)
        rules = dict(enabled=True, visible=True, power=False, external=True, display=False, apps={})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, state in [('card1-eDP-1', 'connected'), ('card0-Writeback-1', 'connected'),
                                ('card0-DP-1-2', 'disconnected'), ('card0-Virtual-1', 'connected')]:
                (root / name).mkdir()
                (root / name / 'status').write_text(state)
            with patch('monet_runtime.awake_rules.preferences', return_value=rules), \
                 patch('monet_runtime.awake_rules.external_connected', side_effect=lambda: external_connected(root)) as scan:
                monitor.reload()
                try:
                    self.assertFalse(backend.held)
                    for status, held in [('connected', True), ('disconnected', False)]:
                        (root / 'card0-DP-1-2/status').write_text(status)
                        monitor.udev.emit('uevent', 'change', None)
                        monitor.udev.emit('uevent', 'change', None)
                        deadline = time.monotonic() + 2
                        while backend.held != held and time.monotonic() < deadline:
                            GLib.MainContext.default().iteration(False)
                            time.sleep(.01)
                        self.assertIs(backend.held, held)
                    self.assertEqual(scan.call_count, 3)
                finally:
                    monitor.close()
                self.assertIsNone(monitor.udev)
                self.assertIsNone(monitor.rescan)

    @unittest.skipUnless(shutil.which('kwin_wayland') and all(importlib.util.find_spec(p) for p in
                         ('PySide6', 'dbus', 'gi')), 'requires native KWin and Qt')
    def test_selected_wayland_app_lifetime(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/keep-awake-kwin.py')],
                                capture_output=True, text=True, timeout=50)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
