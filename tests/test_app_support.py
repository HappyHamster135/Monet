"""App support changes one preference, preserves newer choices, and can undo."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tests.test_app_logins import IDENTITY
from app_support import AppSupport, parse, KEY, LIMIT

APP = 'org.example.Desktop'


class SupportSettings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backend = AppSupport(self.root/'data', self.root/'config',
            runner=lambda *a, **kw: SimpleNamespace(returncode=0, stdout=APP+'\tExample app\norg.mozilla.firefox\tFirefox\n'))
        self.backend.overrides.mkdir(parents=True)
        self.path = self.backend.overrides/APP

    def test_enable_is_narrow_and_restore_is_byte_identical(self):
        original = b'# personal\n[Context]\nfilesystems=~/Documents:ro;\n[Environment]\nCUSTOM=mine\nACCESSIBILITY_ENABLED=0\n'
        self.path.write_bytes(original)
        self.assertTrue(self.backend.change(APP, True)['changed'])
        config = parse(self.path.read_bytes())
        self.assertEqual(config.get('Environment', KEY), '1')
        self.assertEqual(config.get('Environment', 'CUSTOM'), 'mine')
        self.assertEqual(config.get('Context', 'filesystems'), '~/Documents:ro;')
        self.assertEqual(self.backend.listed(), [dict(id=APP,name='Example app',enabled=True,managed=True)])
        self.backend.change(APP, False); self.assertEqual(self.path.read_bytes(), original)

    def test_new_override_is_removed_and_existing_opt_in_is_never_owned(self):
        self.backend.change(APP, True); self.backend.change(APP, False); self.assertFalse(self.path.exists())
        self.path.write_text('[Environment]\nACCESSIBILITY_ENABLED=1\n')
        self.assertFalse(self.backend.change(APP, True)['changed']); self.assertIsNone(self.backend.record(APP))
        self.backend.change(APP, False); self.assertEqual(parse(self.path.read_bytes()).get('Environment', KEY), '1')

    def test_restore_preserves_unrelated_edits_and_newer_accessibility_choice(self):
        self.backend.change(APP, True)
        self.path.write_bytes(self.path.read_bytes()+b'CUSTOM=new\n[Session Bus Policy]\norg.example.Existing=talk\n')
        self.backend.change(APP, False); value=parse(self.path.read_bytes())
        self.assertFalse(value.has_option('Environment', KEY))
        self.assertEqual(value.get('Environment','CUSTOM'),'new')
        self.assertEqual(value.get('Session Bus Policy','org.example.Existing'),'talk')
        self.backend.change(APP, True)
        newer=self.path.read_bytes().replace(b'ACCESSIBILITY_ENABLED=1',b'ACCESSIBILITY_ENABLED=0');self.path.write_bytes(newer)
        self.assertTrue(self.backend.change(APP, False)['preserved']);self.assertEqual(self.path.read_bytes(),newer)

    def test_unknown_apps_symlinks_corrupt_receipts_and_invalid_metadata_fail_closed(self):
        for name in ('../outside', 'org.mozilla.firefox','org.missing.App'):
            with self.assertRaises(ValueError): self.backend.change(name, True)
        other=self.root/'outside';other.write_text('private');self.path.symlink_to(other)
        with self.assertRaises(OSError): self.backend.change(APP,True)
        self.assertEqual(other.read_text(),'private');self.path.unlink()
        self.backend.change(APP,True);receipt=self.backend.receipts/(APP+'.json');receipt.write_text('{}')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):self.backend.change(APP,False)
        self.assertEqual(self.path.read_bytes(),before)

    def test_failed_enable_retains_an_undo_record_without_overwriting_original(self):
        import app_support
        original=app_support.atomic
        def write(path,data,expected):
            if path==self.path:raise OSError('full')
            return original(path,data,expected)
        with patch.object(app_support,'atomic',side_effect=write),self.assertRaises(OSError):self.backend.change(APP,True)
        self.assertFalse(self.path.exists());self.assertIsNotNone(self.backend.record(APP))
        self.backend.change(APP,False);self.assertIsNone(self.backend.record(APP))

    def test_large_preferences_remain_reversible_and_oversized_changes_are_not_written(self):
        original=b'[Environment]\nCUSTOM='+b'a'*200000+b'\n'
        self.path.write_bytes(original)
        self.backend.change(APP,True)
        self.assertGreater((self.backend.receipts/(APP+'.json')).stat().st_size,LIMIT)
        self.backend.change(APP,False);self.assertEqual(self.path.read_bytes(),original)
        original=b'[Environment]\nCUSTOM='+b'a'*(LIMIT-22)+b'\n'
        self.assertEqual(len(original),LIMIT)
        self.path.write_bytes(original)
        with self.assertRaises(ValueError):self.backend.change(APP,True)
        self.assertEqual(self.path.read_bytes(),original);self.assertIsNone(self.backend.record(APP))


@unittest.skipUnless(os.environ.get('MONET_PASSWORDS_QT_TESTS')=='1','native Qt runtime')
class SupportUI(unittest.TestCase):
    def test_native_dialog_updates_and_reports_failure_without_closing(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        from app_support_ui import SupportDialog
        app=QApplication.instance() or QApplication([])
        class Backend:
            enabled=False
            def listed(self):return [dict(id=APP,name='Example app',enabled=self.enabled,managed=self.enabled)]
            def change(self,ident,enabled):
                if not enabled:raise ValueError('App settings changed. Refresh and try again.')
                self.enabled=True;return dict(changed=True)
        dialog=SupportDialog(Backend());dialog.show()
        def settled():
            for _ in range(200):
                QTest.qWait(10)
                if dialog.worker is None:return
            self.fail('Support worker did not finish')
        settled();dialog.apps.setCurrentRow(0);self.assertTrue(dialog.enable.isEnabled())
        dialog.change(True);settled();self.assertTrue(dialog.restore.isEnabled());self.assertFalse(dialog.enable.isEnabled())
        dialog.change(False);settled();self.assertIn('changed',dialog.feedback.text());self.assertTrue(dialog.isVisible())
        dialog.reject();dialog.deleteLater();app.processEvents()
