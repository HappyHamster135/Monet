#!/usr/bin/env python3
"""Rebuild the pinned browser connector and test its form code, without installing it."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path, help="official KeePassXC-Browser 1.10.4.1 XPI (hash checked by the builder)")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("connector_build", ROOT / "browser/monet-passwords/build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    spec = importlib.util.spec_from_file_location("connector_package", ROOT / "browser/monet-passwords/package.py")
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    with tempfile.TemporaryDirectory(prefix="monet-browser-tests-") as temp:
        root = Path(temp)
        candidate = root / "candidate.xpi"
        build.build(args.upstream, candidate)
        package.verify(candidate=candidate)
        # The builder verifies the exact upstream digest before producing this archive.
        with zipfile.ZipFile(candidate) as archive:
            archive.extractall(root / "extension")
        return subprocess.run(["node", str(ROOT / "tests/test_browser_forms.cjs"), str(root / "extension")],
                              cwd=ROOT, timeout=60).returncode


if __name__ == "__main__":
    raise SystemExit(main())
