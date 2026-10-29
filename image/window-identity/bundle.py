#!/usr/bin/python3
"""Build/install guard for KWin's private-ABI window identity plugin."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = "monet_window_identity.so"
EXECUTABLE = "/usr/bin/kwin_wayland"


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plugin_directory():
    paths = {p for p in run("rpm", "-ql", "kwin-common").splitlines()
             if re.fullmatch(r"/usr/lib(?:64)?/qt6/plugins/kwin/plugins", p)}
    if len(paths) != 1:
        raise ValueError("Expected one installed KWin plugin directory")
    return Path(paths.pop())


def packages(names):
    return sorted(run("rpm", "-q", "--qf", "%{NEVRA}\n", *names).splitlines())


def capture():
    linked = run("ldd", EXECUTABLE)
    matches = re.findall(r"libkwin\.so\.\S+ => (/\S+)", linked)
    if len(matches) != 1 or "not found" in linked:
        raise ValueError("Expected one installed KWin library with all its dependencies")
    library = Path(matches[0]).resolve()
    names = {"kwin-common"}
    for path in {EXECUTABLE, str(library), *re.findall(r"(?:=>\s+|^\s*)(/\S+)", linked, re.M)}:
        names.update(run("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n", str(Path(path).resolve())).splitlines())
    return {"schema": 1, "path": str(plugin_directory() / PLUGIN), "library": str(library),
            "library_sha256": digest(library), "executable_sha256": digest(EXECUTABLE),
            "package_names": sorted(names), "packages": packages(sorted(names))}


def verify(manifest):
    if manifest.get("schema") != 1 or not re.fullmatch(
            r"/usr/lib(?:64)?/qt6/plugins/kwin/plugins/" + re.escape(PLUGIN), manifest.get("path", "")):
        raise ValueError("Invalid window identity plugin destination")
    if not re.fullmatch(r"/usr/lib(?:64)?/libkwin\.so\.\d+(?:\.\d+)*", manifest.get("library", "")):
        raise ValueError("Invalid KWin library path")
    names = manifest.get("package_names")
    if (not isinstance(names, list) or not 1 <= len(names) <= 512
            or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]*", n) for n in names)):
        raise ValueError("Invalid KWin runtime package list")
    if packages(names) != manifest["packages"]:
        raise ValueError("KWin/runtime packages changed: rebuild the window identity plugin for this image")
    if Path(manifest["path"]) != plugin_directory() / PLUGIN:
        raise ValueError("KWin plugin destination changed")
    if digest(manifest["library"]) != manifest["library_sha256"] or digest(EXECUTABLE) != manifest["executable_sha256"]:
        raise ValueError("KWin binaries changed: rebuild the window identity plugin for this image")


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


def seal(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    dynamic = run("readelf", "-d", str(bundle / PLUGIN))
    if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
        raise ValueError("Window identity plugin must not contain build-time library paths")
    manifest["files"] = {name: digest(bundle / name) for name in (PLUGIN, "source.tar.xz")}
    (bundle / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")


def install(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    for name in (PLUGIN, "source.tar.xz"):
        if digest(bundle / name) != manifest["files"][name]:
            raise ValueError("Damaged window identity bundle: " + name)
    linked = run("ldd", "-r", str(bundle / PLUGIN))
    if "not found" in linked or "undefined symbol" in linked:
        raise ValueError("Window identity plugin has unresolved dependencies")
    atomic_copy(bundle / PLUGIN, Path(manifest["path"]), 0o755)
    docs = Path("/usr/share/doc/monet-window-identity")
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("source.tar.xz", "runtime.json", "README.md"):
        atomic_copy(bundle / name, docs / name, 0o644)


if __name__ == "__main__":
    command, path = sys.argv[1], Path(sys.argv[2])
    if command == "capture":
        path.write_text(json.dumps(capture(), indent=2) + "\n")
    elif command == "verify":
        verify(json.loads(path.read_text()))
    elif command == "seal":
        seal(path)
    elif command == "install":
        install(path)
    else:
        raise ValueError("Expected capture, verify, seal or install")
