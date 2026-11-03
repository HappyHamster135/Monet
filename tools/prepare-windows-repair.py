#!/usr/bin/env python3
"""Build an offline Windows repair bundle from pinned OEM drivers. Never boots or mounts.

Example: tools/prepare-windows-repair.py --output target/windows-repair \
    --innoextract /path/to/innoextract --cache /path/to/downloaded/installers
Only the reviewed ThinkPad P16s Gen 2 Intel profile is supported so far.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STEAM_URL = "https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(url, path, sha256=None, size=None):
    if not path.is_file() or (sha256 and digest(path) != sha256):
        partial = path.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        partial.replace(path)
    if (sha256 and digest(path) != sha256) or (size and path.stat().st_size != size):
        raise ValueError(f"Downloaded package does not match the OEM catalog: {path.name}")


def build(output, extractor, cache):
    profile = json.loads((ROOT / "windows/hardware/lenovo-21hl.json").read_text())
    output.mkdir(parents=True, exist_ok=False)
    cache.mkdir(parents=True, exist_ok=True)
    manifest = {key: profile[key] for key in ("version", "vendor", "models", "catalog", "checked")}
    manifest["drivers"] = []
    for package in profile["packages"]:
        installer = cache / package["file"]
        fetch(package["url"], installer, package["sha256"], package["size"])
        with tempfile.TemporaryDirectory(prefix="monet-oem-") as temp:
            subprocess.run([str(extractor), "--silent", "--extract", "--output-dir", temp, str(installer)], check=True)
            extracted = Path(temp) / "code$GetExtractPath$"
            if not extracted.is_dir():
                raise ValueError(f"Unexpected OEM package layout: {installer.name}")
            target = output / "drivers" / installer.stem
            shutil.copytree(extracted, target)
        files = []
        infs = []
        for path in sorted(target.rglob("*")):
            if path.is_symlink():
                raise ValueError("Driver packages must not contain symlinks")
            if path.is_file():
                relative = path.relative_to(output).as_posix()
                files.append({"path": relative, "sha256": digest(path)})
                if path.suffix.lower() == ".inf":
                    infs.append(relative)
        if not infs:
            raise ValueError(f"No driver INF in {installer.name}")
        manifest["drivers"].append({"name": package["name"], "version": package["version"],
                                    "source_sha256": package["sha256"], "infs": infs, "files": files})
        print(f"Prepared {package['name']} ({len(infs)} driver INFs)")
    steam = cache / "SteamSetup.exe"
    fetch(STEAM_URL, steam)
    shutil.copy2(steam, output / steam.name)
    # Valve's installer changes over time. Windows checks its Authenticode signature
    # and publisher too; this hash detects changes after this bundle was prepared.
    manifest["steam"] = {"path": steam.name, "sha256": digest(steam), "url": STEAM_URL}
    (output / "repair-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for name in ("Repair-Windows.ps1", "Setup-Functions.ps1", "Install-Launcher.ps1", "GameProfile.ps1"):
        shutil.copy2(ROOT / "windows" / name, output / name)
    (output / "Repair Windows.cmd").write_bytes(
        b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-Windows.ps1"\r\n')
    (output / "README.txt").write_text(
        "Monet Windows repair - ThinkPad P16s Gen 2 Intel (21HK/21HL)\n\n"
        "Open Repair Windows.cmd and accept Windows' administrator prompt.\n"
        "Installs signed OEM drivers offline, installs Steam, imports saved Wi-Fi,\n"
        "and removes optional preinstalled apps. Never restarts automatically.\n"
        "Afterwards, restart Windows normally and check input, Wi-Fi, Ethernet and Bluetooth.\n"
        "Steam needs internet for its first client update and sign-in.\n"
        "Pair Bluetooth devices once in Windows. Monet imports supported Windows\n"
        "pairings on return for devices already paired in Monet. FACEIT/Riot are not installed.\n"
        "Results: C:\\ProgramData\\Monet\\repair-report.json and repair-*.log.\n"
        "Edge/WebView2, Gaming Services, Defender and boot security are preserved.\n")
    print(f"Offline repair ready: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--innoextract", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    build(args.output.resolve(), args.innoextract.resolve(), args.cache.resolve())


if __name__ == "__main__":
    main()
