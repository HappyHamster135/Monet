"""Refresh only declared desktop runtime dependencies; never waive ABI checks."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_runtime_refresh", ROOT / "image/refresh-native-runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class NativeRuntimeRefresh(unittest.TestCase):
    def test_all_bundle_dependency_closures_are_upgraded_once(self):
        def bundle(path):
            name = Path(path).parent.name
            return {"capture": lambda: {"package_names": ["shared.x86_64", name + ".x86_64"]}}
        with patch.object(runtime.runpy, "run_path", side_effect=bundle) as capture, \
                patch.object(runtime.subprocess, "run") as run:
            runtime.refresh(ROOT / "image")
        self.assertEqual(capture.call_count, len(runtime.BUNDLES))
        expected = sorted({"shared.x86_64", "polkit-kde", "polkit-qt6-1",
                           *(name + ".x86_64" for name in runtime.BUNDLES)})
        run.assert_called_once_with(["dnf5", "-y", "upgrade", *expected], check=True)

    def test_missing_or_invalid_dependency_capture_never_runs_a_transaction(self):
        for packages in ([], "all", ["--allowerasing"], ["package; command"], [None]):
            with self.subTest(packages=packages), \
                    patch.object(runtime.runpy, "run_path", return_value={"capture": lambda: {"package_names": packages}}), \
                    patch.object(runtime.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    runtime.refresh(ROOT / "image")
                run.assert_not_called()

    def test_failed_upgrade_stops_the_build(self):
        with patch.object(runtime, "runtime_packages", return_value=["libplasma.x86_64"]), \
                patch.object(runtime.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "dnf5")):
            with self.assertRaises(subprocess.CalledProcessError):
                runtime.refresh(ROOT / "image")
