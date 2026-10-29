"""Transient native metadata misses must not silently discard a supported window."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
editor, files, pdf = [SourceFileLoader('retry_'+name, str(ROOT/'linux/libexec'/('monet-'+name+'-session'))).load_module()
                      for name in ('editor','files','pdf')]


class CaptureRetry(unittest.TestCase):
    def test_reads_retry_transient_failures_but_stop_at_the_first_response(self):
        for module, method in ((editor,'capture_native'), (files,'capture_tree'), (pdf,'native')):
            with self.subTest(module=module.__name__), patch.object(module,method,side_effect=[OSError('busy'),None,{'metadata':True}]) as read:
                self.assertEqual(module.capture_ready(123),{'metadata':True})
                self.assertEqual(read.call_count,3)
            with patch.object(module,method,return_value=[]) as read:
                self.assertEqual(module.capture_ready(123),[])
                read.assert_called_once()

    def test_persistent_unknown_state_stays_unknown_and_is_bounded(self):
        for module, method in ((editor,'capture_native'), (files,'capture_tree'), (pdf,'native')):
            with self.subTest(module=module.__name__), patch.object(module,method,return_value=None) as read:
                self.assertIsNone(module.capture_ready(123))
                self.assertEqual(read.call_count,3)

    def test_editor_cursor_writes_are_never_replayed(self):
        for response in (None,OSError('reply lost')):
            with patch.object(editor,'capture_native',side_effect=[response,{'unexpected':'replay'}]) as read:
                self.assertIsNone(editor.capture_ready(123,{'cursor':2},windows=True))
                read.assert_called_once_with(123,{'cursor':2},windows=True)

    def test_files_window_capture_keeps_native_identity_and_never_falls_back(self):
        windows=[{'id':'exact-window'}]
        with patch.object(files,'capture_native',side_effect=[(True,None),(True,windows)]) as native, patch.object(files,'capture_tree') as tree:
            self.assertEqual(files.capture_ready(123,windows=True),windows)
            self.assertEqual(native.call_count,2)
            tree.assert_not_called()


if __name__=='__main__': unittest.main()
