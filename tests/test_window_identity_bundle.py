"""Keep a compositor plugin built for another runtime out of the image."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("identity_bundle", ROOT / "image/window-identity/bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class WindowIdentityBundle(unittest.TestCase):
    def setUp(self):
        self.directory = Path("/usr/lib64/qt6/plugins/kwin/plugins")
        self.manifest = {"schema":1, "path":str(self.directory / bundle.PLUGIN),
            "library":"/usr/lib64/libkwin.so.6.7.5", "library_sha256":"library", "executable_sha256":"executable",
            "package_names":["kwin.x86_64","kwin-common","kwin-libs.x86_64"],
            "packages":["kwin-6.7.5-1.fc44.x86_64","kwin-common-6.7.5-1.fc44.x86_64","kwin-libs-6.7.5-1.fc44.x86_64"]}
        for name, kwargs in (
                ("plugin_directory", {"return_value":self.directory}),
                ("packages", {"return_value":self.manifest["packages"]}),
                ("digest", {"side_effect":lambda path:"executable" if str(path)==bundle.EXECUTABLE else "library"})):
            mock = patch.object(bundle,name,**kwargs)
            mock.start()
            self.addCleanup(mock.stop)

    def test_matching_runtime_is_accepted(self):
        bundle.verify(self.manifest)

    def test_updated_runtime_or_locally_changed_compositor_is_rejected(self):
        with patch.object(bundle,"packages",return_value=["kwin-6.8.0-1.fc44.x86_64"]):
            with self.assertRaisesRegex(ValueError,"packages changed"):
                bundle.verify(self.manifest)
        for file in (self.manifest["library"],bundle.EXECUTABLE):
            def digest(path):
                return "changed" if str(path)==file else "executable" if str(path)==bundle.EXECUTABLE else "library"
            with self.subTest(file=file), patch.object(bundle,"digest",side_effect=digest):
                with self.assertRaisesRegex(ValueError,"binaries changed"):
                    bundle.verify(self.manifest)

    def test_unexpected_paths_and_package_options_cannot_be_used(self):
        for key, value in (("path","/etc/passwd"), ("path",str(self.directory / "../monet_window_identity.so")),
                           ("library","/etc/passwd"), ("library","/usr/lib64/../../tmp/library"),
                           ("package_names",["--root=/tmp"]), ("package_names",[]), ("package_names",[1])):
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                bundle.verify(dict(self.manifest,**{key:value}))
        with patch.object(bundle,"plugin_directory",return_value=Path("/usr/lib/qt6/plugins/kwin/plugins")):
            with self.assertRaisesRegex(ValueError,"destination changed"):
                bundle.verify(self.manifest)

    def test_capture_tracks_the_actual_compositor_and_transitive_dependencies(self):
        owners = {bundle.EXECUTABLE:"kwin.x86_64",self.manifest["library"]:"kwin-libs.x86_64",
                  "/usr/lib64/libQt6Core.so.6.11.2":"qt6-qtbase.x86_64"}
        def run(*args):
            if args == ("ldd",bundle.EXECUTABLE):
                return ("libkwin.so.6 => /usr/lib64/libkwin.so.6.7.5 (0x1)\n"
                        "libQt6Core.so.6 => /usr/lib64/libQt6Core.so.6.11.2 (0x2)")
            return owners[args[-1]]
        with patch.object(bundle,"run",side_effect=run), patch.object(bundle.Path,"resolve",lambda path:path):
            manifest = bundle.capture()
        self.assertEqual(manifest["library"],self.manifest["library"])
        self.assertEqual(manifest["path"],self.manifest["path"])
        self.assertEqual(manifest["package_names"],sorted({"kwin-common",*owners.values()}))
        self.assertEqual(manifest["library_sha256"],"library")
        self.assertEqual(manifest["executable_sha256"],"executable")

    def test_capture_rejects_missing_or_ambiguous_compositor_libraries(self):
        for linked in ("", "libkwin.so.6 => not found", "libkwin.so.6 => /a\nlibkwin.so.7 => /b"):
            with self.subTest(linked=linked), patch.object(bundle,"run",return_value=linked):
                with self.assertRaises(ValueError):
                    bundle.capture()

    def make_bundle(self, folder):
        for name in (bundle.PLUGIN,"source.tar.xz"):
            (folder/name).write_bytes(b"original")
        manifest = dict(self.manifest,files={name:"original" for name in (bundle.PLUGIN,"source.tar.xz")})
        (folder/"runtime.json").write_text(json.dumps(manifest))

    def test_damaged_binary_or_source_never_installs_any_file(self):
        for damaged in (bundle.PLUGIN,"source.tar.xz"):
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as temporary:
                folder=Path(temporary);self.make_bundle(folder)
                (folder/damaged).write_bytes(b"damaged")
                with patch.object(bundle,"verify"), patch.object(bundle,"digest",side_effect=lambda p:Path(p).read_text()), \
                        patch.object(bundle,"atomic_copy") as copy:
                    with self.assertRaisesRegex(ValueError,"Damaged window identity bundle"):
                        bundle.install(folder)
                    copy.assert_not_called()

    def test_missing_library_or_symbol_prevents_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);self.make_bundle(folder)
            for linked in ("libkwin.so.6 => not found", "undefined symbol: changedPrivateAPI"):
                with self.subTest(linked=linked), patch.object(bundle,"verify"), \
                        patch.object(bundle,"digest",return_value="original"), patch.object(bundle,"run",return_value=linked), \
                        patch.object(bundle,"atomic_copy") as copy:
                    with self.assertRaisesRegex(ValueError,"unresolved dependencies"):
                        bundle.install(folder)
                    copy.assert_not_called()

    def test_sealing_rejects_build_time_library_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);self.make_bundle(folder)
            original=(folder/"runtime.json").read_bytes()
            for field in ("RPATH","RUNPATH"):
                with self.subTest(field=field), patch.object(bundle,"verify"), patch.object(bundle,"run",return_value=f"({field}) /work/build"):
                    with self.assertRaisesRegex(ValueError,"build-time"):
                        bundle.seal(folder)
                    self.assertEqual((folder/"runtime.json").read_bytes(),original)

    def test_failed_copy_preserves_existing_plugin(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source,target=folder/"source",folder/"plugin"
            source.write_bytes(b"new");target.write_bytes(b"installed")
            with patch.object(bundle.shutil,"copyfileobj",side_effect=OSError("disk full")):
                with self.assertRaises(OSError):bundle.atomic_copy(source,target,0o755)
            self.assertEqual(target.read_bytes(),b"installed")
            self.assertEqual(sorted(p.name for p in folder.iterdir()),["plugin","source"])
