"""The patched PDF shell must keep the image's exact native document engine."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pdf_bundle", ROOT / "image/pdf-recovery/bundle.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class PDFBundle(unittest.TestCase):
    def setUp(self):
        paths = ["/usr/bin/okular", "/usr/lib64/qt6/plugins/kf6/parts/okularpart.so",
                 "/usr/lib64/libOkular6Core.so.4.0.0", "/usr/lib64/qt6/plugins/okular_generators/okularGenerator_poppler.so"]
        self.manifest = {"schema": 1, "targets": [{"path": p, "original_sha256": str(i)} for i, p in enumerate(paths)],
                         "package_names": ["okular.x86_64", "okular-part.x86_64", "okular-libs.x86_64"],
                         "packages": ["okular-26.08.1-1.fc44.x86_64"]}

    def test_shell_part_engine_and_pdf_backend_are_all_guarded(self):
        with patch.object(b, "packages", return_value=self.manifest["packages"]) as packages, \
                patch.object(b, "digest", side_effect=["0", "1", "2", "3"]) as digest:
            b.verify(self.manifest)
            for i in range(4):
                hashes = [str(n) for n in range(4)]; hashes[i] = "changed"
                digest.side_effect = hashes
                with self.assertRaisesRegex(ValueError, "binary changed"):
                    b.verify(self.manifest)
            packages.return_value = ["upgraded-runtime"]
            with self.assertRaisesRegex(ValueError, "runtime changed"):
                b.verify(self.manifest)

    def test_invalid_destination_and_package_names_never_reach_files_or_rpm(self):
        for index in range(4):
            bad = copy.deepcopy(self.manifest)
            bad["targets"][index]["path"] = "/etc/passwd"
            with patch.object(b, "packages") as packages, patch.object(b, "digest") as digest:
                with self.assertRaises(ValueError): b.verify(bad)
                packages.assert_not_called(); digest.assert_not_called()
        for targets in ([], None, [None]*4):
            with self.assertRaises(ValueError): b.verify(dict(self.manifest, targets=targets))
        for names in ([], ["--config=/tmp/injected"], ["a\nb"], ["valid"]*513):
            with patch.object(b, "packages") as packages:
                with self.assertRaises(ValueError): b.verify(dict(self.manifest, package_names=names))
                packages.assert_not_called()

    def test_only_the_existing_wayland_dependency_may_be_added(self):
        native = "(NEEDED) Shared library: [libQt6Core.so.6]"
        with patch.object(b, "run", side_effect=[native, native]): b.compatible("old", "new")
        with patch.object(b, "run", side_effect=[native, native+"\n(NEEDED) [libwayland-client.so.0]"]):
            b.compatible("old", "new")
        for changed in ("", "(NEEDED) [libUnexpected.so]", native+"\n(RUNPATH) [/work]", native+"\n(RPATH) [/tmp]"):
            with patch.object(b, "run", side_effect=[native, changed]), self.assertRaises(ValueError):
                b.compatible("old", "new")

    def test_all_binary_source_and_link_checks_precede_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("okular", "source.tar.xz"): (root/name).write_bytes(b"bundle")
            manifest = copy.deepcopy(self.manifest)
            manifest["files"] = {name: b.digest(root/name) for name in ("okular", "source.tar.xz")}
            (root/"runtime.json").write_text(json.dumps(manifest))
            for name in ("okular", "source.tar.xz"):
                (root/name).write_bytes(b"damaged")
                with patch.object(b, "verify"), patch.object(b, "atomic_copy") as write:
                    with self.assertRaisesRegex(ValueError, "Damaged PDF"): b.install(root)
                    write.assert_not_called()
                (root/name).write_bytes(b"bundle")
            for linked in ("library => not found", "undefined symbol: missing_api"):
                with patch.object(b, "verify"), patch.object(b, "compatible"), patch.object(b, "run", return_value=linked), \
                        patch.object(b, "atomic_copy") as write:
                    with self.assertRaisesRegex(ValueError, "unresolved"): b.install(root)
                    write.assert_not_called()

    def test_failed_copy_preserves_original_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/"source", Path(folder)/"target"
            source.write_bytes(b"new"); target.write_bytes(b"old")
            with patch.object(b.shutil, "copyfileobj", side_effect=OSError("disk full")):
                with self.assertRaises(OSError): b.atomic_copy(source, target, 0o755)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ["source", "target"])


if __name__ == "__main__":
    unittest.main()
