#!/usr/bin/env python3
"""Align the shipped native runtime with repository headers before building plugins."""
import argparse
from pathlib import Path
import re
import runpy
import subprocess

BUNDLES = ("notifications", "dock", "editor-recovery", "task-manager", "login", "session",
           "files-recovery", "archive-recovery", "activity", "launcher", "pdf-recovery", "window-identity", "recording-clicks")


def runtime_packages(root):
    # Reuse each bundle's actual ELF dependency closure instead of maintaining
    # an incomplete hand-written list of Qt, KDE and supporting libraries.
    # libzstd is in the desktop closure, but its command-line compressor is
    # not. Keep them together: zstd requires the exact library version when
    # dracut compresses the final initramfs.
    names = {"polkit-kde", "polkit-qt6-1", "kf6-kwallet", "kf6-kwallet-libs", "zstd"}
    for name in BUNDLES:
        manifest = runpy.run_path(str(root / name / "bundle.py"))["capture"]()
        packages = manifest["package_names"]
        if not isinstance(packages, list) or not packages:
            raise ValueError("Missing runtime packages for " + name)
        if any(not isinstance(p, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]*", p)
               for p in packages):
            raise ValueError("Invalid runtime packages for " + name)
        names.update(packages)
    return sorted(names)


def refresh(root):
    names = runtime_packages(root)
    subprocess.run(["dnf5", "-y", "upgrade", *names], check=True)
    # Exercise compression now, before the expensive native build stages.
    subprocess.run(["zstd", "--quiet", "--stdout"], input=b"Monet initramfs compressor check\n",
                   stdout=subprocess.DEVNULL, check=True)
    # Native stages capture this updated runtime and still reject any later
    # dependency drift when development headers are installed.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upgrade", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.upgrade:
        refresh(root)
    else:
        print("\n".join(runtime_packages(root)))
