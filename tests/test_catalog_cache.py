"""Parsed Store metadata follows the catalog, language and filtering exactly."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from tests.test_look import STORE_CATALOG, libexec_helper


class CatalogCache(unittest.TestCase):
    def setUp(self):
        self.store = libexec_helper('monet-store')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.folder = self.root / 'catalog'; self.folder.mkdir()
        self.xml = self.folder / 'appstream.xml'; self.xml.write_text(STORE_CATALOG)
        self.cache = self.root / 'cache'

    def read(self, langs=(), blocked=frozenset(), **options):
        return self.store.cached_catalog(self.folder, langs, blocked, cache=self.cache, **options)

    def test_second_read_reuses_the_same_real_parsed_app_data(self):
        expected = self.store.read_catalog(self.folder, [])
        self.assertEqual(self.read(), expected)
        with patch.object(self.store, 'read_catalog', side_effect=AssertionError('unchanged XML reparsed')):
            self.assertEqual(self.read(), expected)
        self.assertEqual(len(list(self.cache.glob('*.json'))), 1)
        self.assertEqual(next(self.cache.glob('*.json')).stat().st_mode & 0o777, 0o600)

    def test_language_blocklist_and_schema_changes_cannot_reuse_old_values(self):
        english = self.read(); swedish = self.read(['sv'])
        self.assertNotEqual(english['org.gimp.GIMP']['summary'], swedish['org.gimp.GIMP']['summary'])
        self.assertNotIn('org.gimp.GIMP', self.read(blocked=frozenset({'org.gimp.GIMP'})))
        with patch.object(self.store, 'read_catalog', wraps=self.store.read_catalog) as parse, \
                patch.object(self.store, 'CATALOG_CACHE_SCHEMA', 99):
            self.assertEqual(self.read(), english); parse.assert_called_once()

    def test_atomic_catalog_replacement_and_in_place_changes_invalidate(self):
        self.read(); old = self.xml.stat()
        replacement = self.folder / 'replacement'; replacement.write_text(STORE_CATALOG.replace('Krita', 'Other'))
        os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns)); replacement.replace(self.xml)
        self.assertEqual(self.read()['org.kde.krita']['name'], 'Other')
        self.xml.write_text(STORE_CATALOG.replace('Krita', 'Again'))
        os.utime(self.xml, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertEqual(self.read()['org.kde.krita']['name'], 'Again')
        self.assertEqual(len(list(self.cache.glob('*.json'))), 1)

    def test_explicit_refresh_reparses_even_an_unchanged_source(self):
        self.read()
        with patch.object(self.store, 'read_catalog', wraps=self.store.read_catalog) as parse:
            self.read(refresh=True); parse.assert_called_once()

    def test_broken_or_wrong_shaped_cache_falls_back_to_the_catalog(self):
        expected = self.read(); path = next(self.cache.glob('*.json'))
        good = json.loads(path.read_text())
        for value in ('broken json', '[]', json.dumps(dict(good, apps={'org.gimp.GIMP': {'id': 'wrong'}}))):
            path.write_text(value)
            self.assertEqual(self.read(), expected)
        self.assertEqual(list(self.cache.glob('.catalog-*')), [])

    def test_write_failure_keeps_existing_cache_and_returns_current_apps(self):
        expected = self.read(); path = next(self.cache.glob('*.json')); before = path.read_bytes()
        self.xml.write_text(STORE_CATALOG.replace('Krita', 'Current'))
        with patch.object(self.store.os, 'replace', side_effect=OSError('no space')):
            self.assertEqual(self.read()['org.kde.krita']['name'], 'Current')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.cache.glob('.catalog-*')), [])

    def test_catalog_change_during_parse_is_not_saved_under_old_identity(self):
        original = self.store.read_catalog
        def changed(*args):
            apps = original(*args); self.xml.write_text(STORE_CATALOG.replace('Krita', 'Changed')); return apps
        with patch.object(self.store, 'read_catalog', side_effect=changed): self.read()
        self.assertEqual(list(self.cache.glob('*.json')), [])
        self.assertEqual(self.read()['org.kde.krita']['name'], 'Changed')

    def test_missing_catalog_does_not_return_an_older_cached_catalog(self):
        self.read(); self.xml.unlink(); self.assertEqual(self.read(), {})

    def test_deferred_saves_keep_cold_catalog_data_available_before_writing(self):
        deferred = []
        apps = self.read(deferred=deferred)
        self.assertIn('org.gimp.GIMP', apps)
        self.assertFalse(self.cache.exists()); self.assertEqual(len(deferred), 1)
        deferred[0]()
        with patch.object(self.store, 'read_catalog', side_effect=AssertionError('reparsed')):
            self.assertEqual(self.read(), apps)

    def test_source_changed_before_deferred_write_is_not_published(self):
        deferred = []; self.read(deferred=deferred)
        self.xml.write_text(STORE_CATALOG.replace('Krita', 'Newer'))
        deferred[0]()
        self.assertFalse(self.cache.exists())

    def test_nonregular_cache_does_not_block_the_catalog_worker(self):
        expected = self.read(); path = next(self.cache.glob('*.json')); path.unlink(); os.mkfifo(path)
        results = []
        worker = threading.Thread(target=lambda: results.append(self.read()), daemon=True)
        worker.start(); worker.join(1)
        self.assertFalse(worker.is_alive(), 'A rebuildable FIFO cache blocked catalog loading')
        self.assertEqual(results, [expected])
