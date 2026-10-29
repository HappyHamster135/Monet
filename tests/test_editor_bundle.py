"""Prevent delivery of an editor library for a different editor/runtime."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("editor_bundle", ROOT / "image/editor-recovery/bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class EditorBundle(unittest.TestCase):
    def setUp(self):
        self.manifest = {"schema": 1,
            "path": "/usr/lib64/libkateprivate.so.26.08.1",
            "original_sha256": "original", "package_names": ["kate-libs.x86_64"],
            "packages": ["kate-libs-26.08.1-1.fc44.x86_64"]}

    def test_matching_runtime_is_accepted(self):
        with patch.object(bundle, "packages", return_value=self.manifest["packages"]), \
                patch.object(bundle, "digest", return_value="original"):
            bundle.verify(self.manifest)

    def test_loader_alias_is_canonicalised_before_destination_validation(self):
        alias = "libkateprivate.so.26.08.1 => /lib64/libkateprivate.so.26.08.1 (0x123)"
        engine = "libKF6TextEditor.so.6 => /lib64/libKF6TextEditor.so.6.31.0 (0x123)"
        def resolve(path):
            return Path("/usr" + str(path)) if str(path).startswith("/lib64/") else path
        with patch.object(bundle, "run", side_effect=[alias, engine, "x86_64", "kate-libs.x86_64", "kf6-ktexteditor.x86_64"]), \
                patch.object(bundle.Path, "resolve", resolve), patch.object(bundle, "digest", return_value="original"), \
                patch.object(bundle, "packages", return_value=self.manifest["packages"]):
            manifest = bundle.capture()
            self.assertEqual(manifest["path"], self.manifest["path"])
            self.assertIn("libwayland-client.x86_64", manifest["package_names"])
            self.assertEqual(manifest["engine"]["path"], "/usr/lib64/libKF6TextEditor.so.6.31.0")
            bundle.verify(manifest)

    def test_engine_must_match_before_either_library_is_installed(self):
        manifest = dict(self.manifest, schema=2, engine={"path": "/usr/lib64/libKF6TextEditor.so.6.31.0", "original_sha256": "engine"})
        with patch.object(bundle, "packages", return_value=self.manifest["packages"]), \
                patch.object(bundle, "digest", side_effect=lambda p: "original" if "kateprivate" in p else "changed"):
            with self.assertRaisesRegex(ValueError, "base editor library changed"):
                bundle.verify(manifest)
        for engine in (None, {}, {"path": "/etc/passwd"}, {"path": "relative.so"}, {"path": "/usr/lib64/libKF6TextEditor.so.7.0.0"}):
            with self.subTest(engine=engine), self.assertRaisesRegex(ValueError, "engine destination"):
                bundle.verify(dict(manifest, engine=engine))

    def test_engine_cannot_lose_build_features_or_public_symbols(self):
        dynamic = "(NEEDED) Shared library: [libQt6Core.so.6]"
        symbols = "editor_api T 100 10\neditor_vtable V 200 10\n_ZN11KTextEditor4View16staticMetaObjectE D 300 10"
        with patch.object(bundle, "run", side_effect=[dynamic, dynamic, symbols, symbols + "\nnew_api T 300 10"]):
            bundle.verify_engine("old", "new")
        with patch.object(bundle, "run", side_effect=[dynamic, dynamic,
                symbols + "\nqt_template D 400 10", symbols.replace("editor_vtable V", "editor_vtable D")]):
            bundle.verify_engine("old", "new")
        for output, error in (([dynamic, ""], "dependencies changed"),
                              ([dynamic, dynamic, symbols, "editor_api T 100 10"], "lost exported symbols"),
                              ([dynamic, dynamic, symbols, "editor_api T 100 10\neditor_vtable V 200 10"], "lost exported symbols"),
                              ([dynamic, dynamic, "", ""], "lost exported symbols")):
            with self.subTest(error=error), patch.object(bundle, "run", side_effect=output):
                with self.assertRaisesRegex(ValueError, error): bundle.verify_engine("old", "new")

    def test_runtime_upgrade_is_rejected_even_if_library_file_is_unchanged(self):
        with patch.object(bundle, "packages", return_value=["kate-libs-26.12.0-1.fc44.x86_64"]), \
                patch.object(bundle, "digest", return_value="original"):
            with self.assertRaisesRegex(ValueError, "packages changed"):
                bundle.verify(self.manifest)

    def test_different_library_is_rejected_even_when_package_version_matches(self):
        with patch.object(bundle, "packages", return_value=self.manifest["packages"]), \
                patch.object(bundle, "digest", return_value="locally-modified"):
            with self.assertRaisesRegex(ValueError, "base editor library changed"):
                bundle.verify(self.manifest)

    def test_unexpected_destinations_are_rejected(self):
        for path in ("/etc/passwd", "/usr/lib64/../../test.so", "relative.so"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "destination"):
                bundle.verify({**self.manifest, "path": path})

    def test_damaged_binary_or_source_never_replaces_the_installed_library(self):
        files = ("libkateprivate.so.26.08.1", "libKF6TextEditor.so.6.31.0", "source.tar.xz")
        for damaged in files:
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                for name in files:
                    (folder / name).write_bytes(b"valid content")
                manifest = {**self.manifest, "schema": 2,
                    "engine": {"path": "/usr/lib64/libKF6TextEditor.so.6.31.0", "original_sha256": "engine"},
                    "files": {name: bundle.digest(folder / name) for name in files}}
                (folder / "runtime.json").write_text(json.dumps(manifest))
                (folder / damaged).write_bytes(b"damaged")
                with patch.object(bundle, "verify"), patch.object(bundle, "atomic_copy") as copy:
                    with self.assertRaisesRegex(ValueError, "Damaged editor bundle"):
                        bundle.install(folder)
                    copy.assert_not_called()

    def test_engine_guard_runs_before_any_bundle_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            files = ("libkateprivate.so.26.08.1", "libKF6TextEditor.so.6.31.0", "source.tar.xz")
            for name in files: (folder / name).write_bytes(b"valid content")
            manifest = {**self.manifest, "schema": 2,
                "engine": {"path": "/usr/lib64/libKF6TextEditor.so.6.31.0", "original_sha256": "engine"},
                "files": {name: bundle.digest(folder / name) for name in files}}
            (folder / "runtime.json").write_text(json.dumps(manifest))
            with patch.object(bundle, "verify"), patch.object(bundle, "run", return_value="all libraries found"), \
                    patch.object(bundle, "verify_engine", side_effect=ValueError("lost exported symbols")), \
                    patch.object(bundle, "atomic_copy") as copy:
                with self.assertRaisesRegex(ValueError, "lost exported symbols"): bundle.install(folder)
                copy.assert_not_called()

    def test_native_folding_patch_is_guarded_and_includes_the_regression(self):
        spec = importlib.util.spec_from_file_location("texteditor_patch", ROOT / "image/editor-recovery/patch-texteditor.py")
        native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            engine = root / "src/buffer/katetextfolding.cpp"
            header = root / "autotests/src/katefoldingtest.h"
            test = root / "autotests/src/katefoldingtest.cpp"
            engine.parent.mkdir(parents=True); header.parent.mkdir(parents=True)
            engine.write_text("if (rawFlags & Folded) {\n            flags = Folded;\n        }")
            header.write_text("    void testUnfoldingInImportFoldingRanges();")
            test.write_text('#include "moc_katefoldingtest.cpp"')
            view = root / "src/view"
            view.mkdir()
            (view / "kateview.h").write_text('#include <QJsonDocument>\n    QList<PlainSecondaryCursor> plainSecondaryCursors() const;')
            (view / "kateview.cpp").write_text('#include "moc_kateview.cpp"')
            (header.parent / "multicursortest.h").write_text('    static void testSetGetSelections();')
            (header.parent / "multicursortest.cpp").write_text('#include "moc_multicursortest.cpp"')
            native.patch(root)
            self.assertIn("flags |= Folded;", engine.read_text())
            self.assertIn("testPersistentFoldingRoundTrip", header.read_text())
            self.assertIn("QCOMPARE(folding.foldingRange(child), inner);", test.read_text())
            self.assertIn("Q_INVOKABLE QJsonObject monetSelectionState", (view / "kateview.h").read_text())
            self.assertIn("m_viewInternal->m_selectAnchor =", (view / "kateview.cpp").read_text())
            self.assertEqual((view / "monetselection.h").read_bytes(), (ROOT / "image/editor-recovery/monetselection.h").read_bytes())
            with self.assertRaisesRegex(ValueError, "import changed"): native.patch(root)

    def test_missing_runtime_library_never_replaces_the_installed_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name in ("libkateprivate.so.26.08.1", "source.tar.xz"):
                (folder / name).write_bytes(b"valid content")
            manifest = {**self.manifest, "files": {name: bundle.digest(folder / name)
                for name in ("libkateprivate.so.26.08.1", "source.tar.xz")}}
            (folder / "runtime.json").write_text(json.dumps(manifest))
            with patch.object(bundle, "verify"), patch.object(bundle, "run", return_value="libKF6TextEditor.so.7 => not found"), \
                    patch.object(bundle, "atomic_copy") as copy:
                with self.assertRaisesRegex(ValueError, "missing dependencies"):
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
