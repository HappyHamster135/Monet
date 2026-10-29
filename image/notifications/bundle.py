#!/usr/bin/python3
"""Check the native applet's runtime before building or installing its replacement."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = "org.kde.plasma.notifications.so"


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plugin_path():
    paths = [p for p in run("rpm", "-ql", "plasma-workspace-libs").splitlines()
             if p.endswith("/plasma/applets/" + PLUGIN)]
    if len(paths) != 1:
        raise ValueError("Expected one installed Plasma notification applet")
    return Path(paths[0])


def packages(names):
    return sorted(run("rpm", "-q", "--qf", "%{NEVRA}\n", *names).splitlines())


def capture():
    plugin = plugin_path()
    linked = run("ldd", str(plugin))
    if "not found" in linked:
        raise ValueError("The base notification applet has missing libraries")
    paths = {str(plugin), *re.findall(r"(?:=>\s+|^\s*)(/\S+)", linked, re.M)}
    names = {"plasma-workspace", "plasma-workspace-libs", "libplasma"}
    for path in paths:
        names.update(run("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n", str(Path(path).resolve())).splitlines())
    return {"schema": 1, "path": str(plugin), "original_sha256": digest(plugin),
            "package_names": sorted(names), "packages": packages(sorted(names))}


def verify(manifest):
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported notification bundle")
    target = manifest.get("path", "")
    if not re.fullmatch(r"/usr/lib(?:64)?/qt6/plugins/plasma/applets/" + re.escape(PLUGIN), target):
        raise ValueError("Unexpected notification plugin destination")
    if packages(manifest["package_names"]) != manifest["packages"]:
        raise ValueError("Plasma/runtime packages changed: rebuild the notification applet for this image")
    if digest(target) != manifest["original_sha256"]:
        raise ValueError("The base notification applet changed: rebuild against this image")


def install(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    # Validate every delivered file before replacing anything in the image.
    for name in (PLUGIN, "source.tar.xz"):
        if digest(bundle / name) != manifest["files"][name]:
            raise ValueError(f"Damaged notification bundle: {name}")
    linked = run("ldd", str(bundle / PLUGIN))
    if "not found" in linked:
        raise ValueError("The replacement notification applet has missing libraries")
    atomic_copy(bundle / PLUGIN, Path(manifest["path"]), 0o755)
    docs = Path("/usr/share/doc/monet-notifications")
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("source.tar.xz", "runtime.json", "README.md"):
        atomic_copy(bundle / name, docs / name, 0o644)


def atomic_copy(source, target, mode):
    fd, temporary = tempfile.mkstemp(prefix=".monet-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
            output.flush()
            os.fchmod(output.fileno(), mode)
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    command, path = sys.argv[1], Path(sys.argv[2])
    if command == "capture":
        path.write_text(json.dumps(capture(), indent=2) + "\n")
    elif command == "verify":
        verify(json.loads(path.read_text()))
    elif command == "seal":
        manifest = json.loads((path / "runtime.json").read_text())
        verify(manifest)
        dynamic = run("readelf", "-d", str(path / PLUGIN))
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
            raise ValueError("The notification applet must not contain a build-time library path")
        manifest["files"] = {name: digest(path / name) for name in (PLUGIN, "source.tar.xz")}
        (path / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
    elif command == "install":
        install(path)
    else:
        raise ValueError("Expected capture, verify, seal or install")


if __name__ == "__main__":
    main()
