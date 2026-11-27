"""Account updates preserve rollback and cannot load stale image QML bytecode."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('power_install', ROOT/'tools/install-power-preview.py')
install = importlib.util.module_from_spec(spec); spec.loader.exec_module(install)


class PowerInstall(unittest.TestCase):
    def test_updates_keep_original_backup_and_remove_aot_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); backup = root/'backup'; backup.mkdir()
            path = root/'main.qml'; path.write_bytes(b'original source')
            cache = root/'main.qmlc'; cache.write_bytes(b'old compiled source')
            records = []
            install.put(path, b'first update', backup, records)
            install.put(path, b'final update', backup, records)
            self.assertEqual(path.read_bytes(), b'final update')
            self.assertFalse(cache.exists())
            sources = [r for r in records if r['path'] == str(path)]
            self.assertEqual(len(sources), 1)
            self.assertEqual(Path(sources[0]['before']).read_bytes(), b'original source')
            caches = [r for r in records if r['path'] == str(cache)]
            self.assertEqual(Path(caches[0]['before']).read_bytes(), b'old compiled source')
            self.assertIsNone(caches[0]['sha256'])

    def test_install_does_not_write_through_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); original = root/'original'; original.write_bytes(b'keep')
            target = root/'main.qml'; target.symlink_to(original)
            with self.assertRaises(RuntimeError): install.put(target, b'replace', root, [])
            self.assertEqual(original.read_bytes(), b'keep')
