"""Pair the media controller with the Plasma runtime and install it for hot reload."""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bundle import atomic_copy, digest, packages, run

PLUGIN = "mprisservice.so"


def target():
    files = run("rpm", "-ql", "plasma-workspace-libs").splitlines()
    return Path(next(f for f in files if re.fullmatch(r"/usr/lib(?:64)?/qt6/plugins/kf6/kded/mprisservice\.so", f)))


def runtime():
    original = target()
    lib = original.parents[4]
    playerlib = (lib / "libkmpris.so.6").resolve(strict=True)
    inputs = {original, playerlib, lib / "libKF6KIOGui.so.6", lib / "libKF6Service.so.6"}
    linked = run("ldd", *map(str, sorted(inputs)))
    if "not found" in linked:
        raise ValueError("Media controller runtime is incomplete")
    deps = {Path(p) for p in re.findall(r"(?:=>\s+|^\s*)(/\S+)", linked, re.M) if not p.endswith(":")}
    names = set()
    for file in deps | inputs:
        names.update(run("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n", str(file.resolve())).splitlines())
    return {"original": digest(original), "player_library": digest(playerlib), "packages": packages(names)}


def check_binary(binary):
    dynamic = run("readelf", "-d", str(binary))
    linked = run("ldd", "-r", str(binary))
    if "(RUNPATH)" in dynamic or "(RPATH)" in dynamic or "not found" in linked or "undefined symbol" in linked:
        raise ValueError("Incompatible media controller")


def install(folder, dest=Path("/")):
    manifest = json.loads((folder / "runtime.json").read_text())
    if manifest["runtime"] != runtime():
        raise ValueError("The media controller or its runtime changed")
    for name in (PLUGIN, "source.tar.xz", "README.md"):
        if digest(folder / name) != manifest["files"][name]:
            raise ValueError("Damaged media controller file " + name)
    check_binary(folder / PLUGIN)
    original = target().relative_to("/")
    actual = original.parents[4] / "monet-media-keys" / manifest["files"][PLUGIN] / PLUGIN
    (dest / actual.parent).mkdir(parents=True, exist_ok=True)
    atomic_copy(folder / PLUGIN, dest / actual)
    # Qt caches factories by canonical filename for a running KDED process.
    # Change that filename with the binary, retaining the upstream module ID.
    (dest / original.parent).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest / original.parent) as tmp:
        link = Path(tmp) / PLUGIN
        link.symlink_to(os.path.relpath(actual, original.parent))
        os.replace(link, dest / original)
    docs = dest / "usr/share/doc/monet-media-keys"
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("README.md", "source.tar.xz", "runtime.json"):
        shutil.copy2(folder / name, docs / name)


if __name__ == "__main__":
    command, dirname = sys.argv[1:]
    folder = Path(dirname)
    path = folder / "runtime.json"
    if command == "capture":
        path.write_text(json.dumps({"runtime": runtime()}, indent=2) + "\n")
    elif command == "seal":
        manifest = json.loads(path.read_text())
        if manifest["runtime"] != runtime():
            raise ValueError("Media controller runtime changed during the build")
        check_binary(folder / PLUGIN)
        manifest["files"] = {name: digest(folder / name) for name in (PLUGIN, "source.tar.xz", "README.md")}
        path.write_text(json.dumps(manifest, indent=2) + "\n")
    elif command == "install":
        install(folder)
    else:
        raise ValueError("Expected capture, seal or install")
