"""Exercise the public monet-quick launcher as both a command and an imported helper."""
import importlib.util
import marshal
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader


LINUX = Path(__file__).resolve().parents[1] / "linux"


class QuickLauncher(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.command = self.root / "monet-quick"
        self.source = self.root / "monet_quick.py"
        shutil.copyfile(LINUX / "launchers/monet-quick", self.command)

    def compile_cache(self):
        return Path(py_compile.compile(str(self.source), doraise=True,
                                       invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH))

    def invoke(self, *args):
        return subprocess.check_output([sys.executable, "-I", "-B", self.command, *args],
                                       text=True, timeout=15).strip()

    def test_cli_and_module_share_the_public_entry_point_and_module_globals(self):
        shutil.copyfile(LINUX / "libexec/monet-quick", self.source)
        self.compile_cache()
        self.assertEqual(self.invoke("say", "Ready %1", "now"), "Ready now")
        loader = SourceFileLoader("monet_quick", str(self.command))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(module)
        self.assertEqual(module.__file__, str(self.command))
        module.PREFS = self.root / "prefs.json"
        module.PREFS.write_text('{"snap": false, "glass": "solid"}')
        self.assertFalse(module.prefs()["snap"])

    def test_updated_source_with_same_timestamp_and_size_is_used(self):
        self.source.write_text('print("old")\n')
        cache = self.compile_cache()
        before = self.source.stat()
        self.source.write_text('print("new")\n')
        os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertTrue(cache.exists())
        self.assertEqual(self.invoke(), "new")

    def test_missing_or_incomplete_cache_runs_the_source(self):
        self.source.write_text('print("ready")\n')
        cache = self.compile_cache()
        header = cache.read_bytes()[:16]
        for payload in (b"", marshal.dumps(None)):
            with self.subTest(payload=payload):
                cache.write_bytes(header + payload)
                self.assertEqual(self.invoke(), "ready")
        cache.unlink()
        self.assertEqual(self.invoke(), "ready")
