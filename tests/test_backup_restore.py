"""Restoration never publishes incomplete copies or overwrites another file."""
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper


class Restore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.q = quick_helper()
        self.original = self.root / 'letter.txt'; self.original.write_text('current')
        self.source = self.root / 'saved'; self.source.write_text('earlier')
        self.item = dict(path=str(self.source), name='2026-11-04 09.00')
        self.target = self.root / 'letter (2026-11-04 09.00).txt'

    def test_concurrent_collision_and_dangling_link_preserve_every_copy(self):
        publish = self.q.publish_recovery_archive
        def collision(source, target):
            if target == self.target:
                target.symlink_to(self.root / 'missing')
            return publish(source, target)
        with patch.object(self.q, 'publish_recovery_archive', side_effect=collision):
            copied = self.q.put_back(self.item, self.original)
        self.assertEqual(copied.name, 'letter (2026-11-04 09.00) (2).txt')
        self.assertEqual(copied.read_text(), 'earlier')
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(self.original.read_text(), 'current')

    def test_disk_full_leaves_no_partial_result(self):
        def fail(source, target, **kwargs):
            Path(target).write_text('partial')
            raise OSError(errno.ENOSPC, 'fixture full')
        with patch.object(self.q.shutil, 'copy2', side_effect=fail), self.assertRaises(OSError):
            self.q.put_back(self.item, self.original)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.root.glob('.monet-restore-*')), [])
        self.assertEqual(self.original.read_text(), 'current')

    def test_folder_contents_and_links_restore_without_following_links(self):
        self.source.unlink(); self.source.mkdir()
        (self.source/'nested').mkdir(); (self.source/'nested'/'file').write_text('saved')
        (self.source/'outside').symlink_to(self.original)
        copied = self.q.put_back(self.item, self.root/'folder')
        self.assertEqual((copied/'nested'/'file').read_text(), 'saved')
        self.assertTrue((copied/'outside').is_symlink())

    def test_selected_snapshot_does_not_change_when_a_new_one_arrives(self):
        marker = self.root/'earlier'; marker.write_text(str(self.original))
        with patch.object(self.q, 'EARLIER', marker), \
                patch.object(self.q, 'versions', return_value=[dict(self.item, name='new'), self.item]), \
                patch.object(self.q, 'show_in_files') as show:
            result = self.q.earlier_action('put-back', str(self.original).encode().hex(), self.item['name'].encode().hex())
        self.assertEqual(result, dict(ok=True, state='restored'))
        self.assertEqual(self.target.read_text(), 'earlier')
        show.assert_called_once_with(self.target)

    def test_changed_selection_and_pruned_snapshot_are_reported(self):
        marker = self.root/'earlier'; marker.write_text('another file')
        with patch.object(self.q, 'EARLIER', marker), patch.object(self.q, 'show_in_files') as show:
            args = ('put-back', str(self.original).encode().hex(), self.item['name'].encode().hex())
            self.assertEqual(self.q.earlier_action(*args), dict(ok=False, state='changed'))
            marker.write_text(str(self.original))
            with patch.object(self.q, 'versions', return_value=[]):
                self.assertEqual(self.q.earlier_action(*args), dict(ok=False, state='changed'))
            show.assert_not_called()

    def test_permission_failure_returns_a_retryable_result(self):
        marker = self.root/'earlier'; marker.write_text(str(self.original))
        with patch.object(self.q, 'EARLIER', marker), patch.object(self.q, 'versions', return_value=[self.item]), \
                patch.object(self.q, 'put_back', side_effect=PermissionError()), patch.object(self.q, 'show_in_files') as show:
            result = self.q.earlier_action('put-back', str(self.original).encode().hex(), self.item['name'].encode().hex())
        self.assertEqual(result, dict(ok=False, state='failed')); show.assert_not_called()
