"""Prevent delivery of a notification plugin for a different Plasma/runtime."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("notification_bundle", ROOT / "image/notifications/bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class NotificationBundle(unittest.TestCase):
    def setUp(self):
        self.manifest = {"schema": 1,
            "path": "/usr/lib64/qt6/plugins/plasma/applets/" + bundle.PLUGIN,
            "original_sha256": "original", "package_names": ["plasma-workspace-libs.x86_64"],
            "packages": ["plasma-workspace-libs-6.7.5-1.fc44.x86_64"]}

    def test_matching_runtime_is_accepted(self):
        with patch.object(bundle, "packages", return_value=self.manifest["packages"]), \
                patch.object(bundle, "digest", return_value="original"):
            bundle.verify(self.manifest)

    def test_runtime_upgrade_is_rejected_even_if_plugin_file_is_unchanged(self):
        with patch.object(bundle, "packages", return_value=["plasma-workspace-libs-6.8.0-1.fc44.x86_64"]), \
                patch.object(bundle, "digest", return_value="original"):
            with self.assertRaisesRegex(ValueError, "packages changed"):
                bundle.verify(self.manifest)

    def test_different_plugin_is_rejected_even_when_package_version_matches(self):
        with patch.object(bundle, "packages", return_value=self.manifest["packages"]), \
                patch.object(bundle, "digest", return_value="locally-modified"):
            with self.assertRaisesRegex(ValueError, "base notification applet changed"):
                bundle.verify(self.manifest)

    def test_unexpected_destinations_are_rejected(self):
        for path in ("/etc/passwd", "/usr/lib64/qt6/plugins/plasma/applets/../../test.so", "relative.so"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "destination"):
                bundle.verify({**self.manifest, "path": path})

    def test_damaged_binary_or_source_never_replaces_the_installed_plugin(self):
        for damaged in (bundle.PLUGIN, "source.tar.xz"):
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                for name in (bundle.PLUGIN, "source.tar.xz"):
                    (folder / name).write_bytes(b"valid content")
                manifest = {**self.manifest, "files": {name: bundle.digest(folder / name)
                    for name in (bundle.PLUGIN, "source.tar.xz")}}
                (folder / "runtime.json").write_text(json.dumps(manifest))
                (folder / damaged).write_bytes(b"damaged")
                with patch.object(bundle, "verify"), patch.object(bundle, "atomic_copy") as copy:
                    with self.assertRaisesRegex(ValueError, "Damaged notification bundle"):
                        bundle.install(folder)
                    copy.assert_not_called()

    def test_missing_runtime_library_never_replaces_the_installed_plugin(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name in (bundle.PLUGIN, "source.tar.xz"):
                (folder / name).write_bytes(b"valid content")
            manifest = {**self.manifest, "files": {name: bundle.digest(folder / name)
                for name in (bundle.PLUGIN, "source.tar.xz")}}
            (folder / "runtime.json").write_text(json.dumps(manifest))
            with patch.object(bundle, "verify"), patch.object(bundle, "run", return_value="libPlasma.so.7 => not found"), \
                    patch.object(bundle, "atomic_copy") as copy:
                with self.assertRaisesRegex(ValueError, "missing libraries"):
                    bundle.install(folder)
                copy.assert_not_called()

    def test_failed_copy_preserves_original_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, target = folder / "source", folder / "target"
            source.write_bytes(b"replacement")
            target.write_bytes(b"original")
            with patch.object(bundle.shutil, "copyfileobj", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    bundle.atomic_copy(source, target, 0o755)
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["source", "target"])
