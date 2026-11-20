"""Repeated app-icon maintenance avoids theme walks without keeping stale icons."""
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


@unittest.skipUnless(os.name == 'posix', 'Linux icon-theme maintenance')
class IconIndex(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.home, self.system = self.root/'home', self.root/'system'
        self.q = quick_helper()
        self.q.data_dirs = lambda: [self.home, self.system]
        self.q.ICON_FILE_CACHE = self.root/'cache/icons.json'
        self.apps = self.system/'icons/hicolor/scalable/apps'
        self.apps.mkdir(parents=True)
        self.icon = self.apps/'sample.svg'
        self.icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#111111"/></svg>')

    def test_unchanged_inputs_reuse_paths_without_enumerating_any_directory(self):
        cold = self.q.icon_files({'sample'})
        self.assertEqual(self.q.own_icon(cold['sample']), self.icon)
        with patch.object(self.q.os, 'walk', side_effect=AssertionError('Repeated theme walk')):
            self.assertEqual(self.q.icon_files({'sample'}), cold)
        self.assertEqual(self.q.ICON_FILE_CACHE.stat().st_mode & 0o777, 0o600)

    def test_no_unpainted_names_need_no_theme_walk_or_cache(self):
        with patch.object(self.q.os, 'walk', side_effect=AssertionError('Empty theme walk')):
            self.assertEqual(self.q.icon_files(set()), {})
        self.assertFalse(self.q.ICON_FILE_CACHE.exists())

    def test_new_boot_rebuilds_even_when_image_directory_metadata_is_unchanged(self):
        self.q.icon_files({'sample'})
        walk = self.q.os.walk
        with patch.object(self.q, 'icon_boot_identity', return_value='next-boot'):
            with patch.object(self.q.os, 'walk', wraps=walk) as scanned:
                self.assertIn('sample', self.q.icon_files({'sample'}))
                self.assertTrue(scanned.called)
            with patch.object(self.q.os, 'walk', side_effect=AssertionError('Repeated theme walk')):
                self.assertIn('sample', self.q.icon_files({'sample'}))

    def test_unavailable_boot_identity_still_finds_icons_without_persisting_an_index(self):
        with patch.object(self.q, 'icon_boot_identity', return_value=''):
            self.assertIn('sample', self.q.icon_files({'sample'}))
        self.assertFalse(self.q.ICON_FILE_CACHE.exists())

    def test_new_better_theme_and_resolution_are_detected(self):
        self.q.icon_files({'sample'})
        png = self.system/'icons/hicolor/256x256/apps/sample.png'
        png.parent.mkdir(parents=True)
        png.write_bytes(b'fixture')
        self.assertEqual(self.q.own_icon(self.q.icon_files({'sample'})['sample']), png)
        preferred = self.home/'icons/breeze/scalable/apps/sample.svg'
        preferred.parent.mkdir(parents=True)
        preferred.write_text('<svg/>')
        self.assertEqual(self.q.own_icon(self.q.icon_files({'sample'})['sample']), preferred)

    def test_added_and_removed_files_are_detected_even_with_restored_directory_mtime(self):
        self.q.icon_files({'sample', 'new'})
        before = self.apps.stat()
        added = self.apps/'new.svg'
        added.write_text('<svg/>')
        os.utime(self.apps, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertIn('new', self.q.icon_files({'sample', 'new'}))
        self.icon.unlink()
        self.assertNotIn('sample', self.q.icon_files({'sample', 'new'}))

    def test_reused_paths_still_read_updated_icon_pixels(self):
        found = self.q.icon_files({'sample'})
        before = self.q.frame_svg('sample', self.q.own_icon(found['sample']), ['YQ==', 'Yg=='])
        self.icon.write_text(self.icon.read_text().replace('#111111', '#222222'))
        with patch.object(self.q.os, 'walk', side_effect=AssertionError('Unnecessary theme walk')):
            found = self.q.icon_files({'sample'})
        after = self.q.frame_svg('sample', self.q.own_icon(found['sample']), ['YQ==', 'Yg=='])
        self.assertNotEqual(before, after)
        self.assertIn('#222222', after)

    def test_names_and_search_roots_invalidate_the_index(self):
        self.q.icon_files({'sample'})
        self.assertIn('sample', self.q.icon_files({'sample', 'extra'}))
        self.q.data_dirs = lambda: [self.home]
        self.assertEqual(self.q.icon_files({'sample'}), {})

    def test_corrupt_or_unwritable_cache_does_not_prevent_icons(self):
        self.q.ICON_FILE_CACHE.parent.mkdir()
        self.q.ICON_FILE_CACHE.write_bytes(b'partial JSON')
        with patch.object(self.q, 'write_private', side_effect=PermissionError('Read-only cache')):
            self.assertIn('sample', self.q.icon_files({'sample'}))
        self.assertIn('sample', self.q.icon_files({'sample'}))
        saved = json.loads(self.q.ICON_FILE_CACHE.read_text())
        saved['found']['sample'][0][2] = str(self.root/'outside.svg')
        self.q.ICON_FILE_CACHE.write_text(json.dumps(saved))
        self.assertEqual(self.q.own_icon(self.q.icon_files({'sample'})['sample']), self.icon)

    def test_a_concurrent_install_cannot_publish_an_incomplete_index(self):
        walk = self.q.os.walk
        added = self.apps/'new.svg'
        def installing(root, **kwargs):
            for folder, children, files in walk(root, **kwargs):
                if Path(folder) == self.apps and not added.exists():
                    added.write_text('<svg/>')
                yield folder, children, files
        with patch.object(self.q.os, 'walk', installing):
            self.q.icon_files({'sample', 'new'})
        self.assertFalse(self.q.ICON_FILE_CACHE.exists())
        self.assertIn('new', self.q.icon_files({'sample', 'new'}))

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX named pipes')
    def test_non_regular_cache_cannot_block_icon_maintenance(self):
        self.q.ICON_FILE_CACHE.parent.mkdir()
        os.mkfifo(self.q.ICON_FILE_CACHE)
        source = Path(__file__).resolve().parents[1]/'linux/libexec/monet-quick'
        script = '''import importlib.machinery,importlib.util,sys
from pathlib import Path
loader=importlib.machinery.SourceFileLoader('icon_fifo',sys.argv[1])
q=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(q)
q.data_dirs=lambda:[Path(sys.argv[2]),Path(sys.argv[3])]
q.ICON_FILE_CACHE=Path(sys.argv[4])
assert 'sample' in q.icon_files({'sample'})
'''
        subprocess.run([sys.executable, '-c', script, str(source), str(self.home), str(self.system),
                        str(self.q.ICON_FILE_CACHE)], check=True, timeout=5)
        self.assertTrue(self.q.ICON_FILE_CACHE.is_file())
