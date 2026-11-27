"""Unit-aware Command Bar results and their reusable desktop-session answer."""
from pathlib import Path
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/share/monet/utilities'))
import measurements as measure


class Measurements(unittest.TestCase):
    def test_native_search_keeps_simple_conversions_and_plain_searches(self):
        for text in ('10 km in miles', '2026 budget', '1 + 2', 'calendar', '3 m', 'ans * 2'):
            self.assertIsNone(measure.expression(text))
        self.assertEqual(measure.expression('10 km in miles', scoped=True), '(10 km) to miles')

    def test_quantities_bind_before_arithmetic_and_mixed_amounts_share_a_sign(self):
        self.assertEqual(measure.expression('100 km / 2 h to km/h'), '(100 km) / (2 h) to km/h')
        self.assertEqual(measure.expression('-5′ 11 1/2″ in cm'), '- (5 ft + (11+1/2) inches) to cm')
        self.assertEqual(measure.expression('1/2 kg in grams'), '((1/2) kg) to grams')
        self.assertEqual(measure.expression('1 / 2 kg'), '1 / (2 kg)')
        self.assertEqual(measure.expression('٠٫٥ m + 25 cm', decimal='٫'), '(0.5 m) + (25 cm)')
        self.assertEqual(measure.localized('0.75 m', ','), '0,75 m')

    def test_incomplete_and_unbounded_input(self):
        for text in ('3 m; 4 h', '3e99999 km / 2 h', '2 m^9999', '2^9^9 m',
                     '1/0 kg in g', '1 m + ' * 80):
            self.assertIsNone(measure.expression(text), text)
        self.assertIsNone(measure.expression('ans * 2', answer='4 m; 2 m'))

    def test_last_answer_is_atomic_and_local_to_this_desktop_session(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            self.assertEqual(measure.session_answer(), '')
            measure.session_answer('approx. 0.4 m s^-1 kg^-1')
            self.assertEqual(measure.session_answer(), '0.4 m s^-1 kg^-1')
            self.assertEqual(measure.expression('ans * 2', answer=measure.session_answer()),
                             '( (0.4 m*s^-1*kg^-1) ) * 2')
            file = Path(directory) / 'monet/measurement-answer'
            self.assertEqual(file.stat().st_mode & 0o077, 0)

    def test_packaged_calculator(self):
        helper = next((path for path in (Path(os.environ.get('MONET_TEST_MEASURE', '/nonexistent')),
                                         ROOT/'target/release/monet-measure',
                                         ROOT/'target/debug/monet-measure', measure.HELPER)
                       if path.is_file()), None)
        if helper is None:
            self.skipTest('requires the built monet-measure binary')
        for query, expected in [('100 km / 2 h to km/h', '50 km / h'), ('5 ft 11 in in cm', '180.34 cm'),
                                ('2 h 30 min + 45 min', '3.25 h'), ('3 m × 4 m', '12 m^2'),
                                ('8 GiB / 2 s to MiB/s', '4096 MiB / s'), ('5′ 11 1/2″ in cm', '181.61 cm'),
                                ('2 m + 3 s', ''), ('1 m / 0 s', '')]:
            with self.subTest(query=query):
                self.assertEqual(measure.evaluate(measure.expression(query), helper), expected)

    @unittest.skipUnless(importlib.util.find_spec('PySide6') and importlib.util.find_spec('dbus'),
                         'requires the native desktop runner')
    def test_activation_reuses_the_displayed_answer_and_respects_tool_visibility(self):
        from PySide6.QtCore import QLocale
        import command_search as search
        locale = QLocale()
        QLocale.setDefault(QLocale('sv_SE'))
        self.addCleanup(QLocale.setDefault, locale)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory), \
                patch.object(measure, 'evaluate', return_value='75.25 cm') as evaluate, \
                patch.object(search, 'copy_text', return_value=True) as copy:
            measure.session_answer('150.5 cm')
            hit = search.measurement_match('ans / 2', scoped=False)
            self.assertEqual(hit[1], '75,25 cm')
            measure.session_answer('30 m')
            search.copy_result(hit[0], {'command-bar'}, {}, None)
            copy.assert_not_called()
            self.assertEqual(measure.session_answer(), '30 m')
            search.copy_result(hit[0], set(), {}, None)
            self.assertEqual(evaluate.call_args.args[0], '( (150.5 cm) ) / 2')
            copy.assert_called_once_with(None, '75,25 cm')
            self.assertEqual(measure.session_answer(), '75.25 cm')
