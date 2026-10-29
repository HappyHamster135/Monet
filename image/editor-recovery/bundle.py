#!/usr/bin/python3
"""Verify the editor library's runtime, binary and corresponding source before install."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packages(names):
    return sorted(run("rpm", "-q", "--qf", "%{NEVRA}\n", *names).splitlines())


def capture():
    linked = run("ldd", "/usr/bin/kate")
    matches = re.findall(r"libkateprivate\.so\.\S+ => (/\S+)", linked)
    if len(matches) != 1 or "not found" in linked:
        raise ValueError("Expected one installed editor library with all its dependencies")
    library = Path(matches[0]).resolve()
    linked = run("ldd", str(library))
    if "not found" in linked:
        raise ValueError("The base editor library has missing dependencies")
    engines = re.findall(r"libKF6TextEditor\.so\.6 => (/\S+)", linked)
    if len(engines) != 1:
        raise ValueError("Expected one installed text editor engine")
    engine = Path(engines[0]).resolve()
    names = {"kate", "kwrite", "libwayland-client." + run("rpm", "-qf", "--qf", "%{ARCH}", str(library))}
    for path in {str(library), *re.findall(r"(?:=>\s+|^\s*)(/\S+)", linked, re.M)}:
        names.update(run("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n", str(Path(path).resolve())).splitlines())
    return {"schema": 2, "path": str(library), "original_sha256": digest(library),
            "engine": {"path": str(engine), "original_sha256": digest(engine)},
            "package_names": sorted(names), "packages": packages(sorted(names))}


def libraries(manifest):
    if manifest.get("schema") not in (1, 2) or not re.fullmatch(r"/usr/lib(?:64)?/libkateprivate\.so\.\d+\.\d+\.\d+", manifest.get("path", "")):
        raise ValueError("Invalid editor library destination")
    result = [manifest]
    if manifest["schema"] == 2:
        engine = manifest.get("engine")
        if not isinstance(engine, dict) or not re.fullmatch(r"/usr/lib(?:64)?/libKF6TextEditor\.so\.6\.\d+\.\d+", engine.get("path", "")):
            raise ValueError("Invalid editor engine destination")
        result.append(engine)
    return result


def verify(manifest):
    targets = libraries(manifest)
    if packages(manifest["package_names"]) != manifest["packages"]:
        raise ValueError("Editor/runtime packages changed: rebuild the editor library for this image")
    for target in targets:
        if digest(target["path"]) != target["original_sha256"]:
            raise ValueError("The base editor library changed: rebuild against this image")


def verify_engine(original, replacement):
    def needed(path):
        dynamic = run("readelf", "-d", str(path))
        return set(re.findall(r"\((?:NEEDED|SONAME)\).*\[([^\]]+)\]", dynamic))
    dependencies = needed(original)
    if not dependencies or dependencies != needed(replacement):
        raise ValueError("Editor engine dependencies changed: preserve the runtime's build features")
    def symbols(path):
        return {parts[0]: parts[1] for line in run("nm", "--dynamic", "--defined-only", "--format=posix", str(path)).splitlines()
                if len(parts := line.split()) >= 2}
    # Qt/std template data can change with headers; retain engine functions, vtables and owned data.
    exports = {name for name, kind in symbols(original).items()
               if kind in {"T", "V"} or name.startswith(("_ZN11KTextEditor", "_ZNK11KTextEditor", "_ZTVN11KTextEditor", "_ZTIN11KTextEditor", "_ZTSN11KTextEditor"))}
    if not exports or not exports <= symbols(replacement).keys():
        raise ValueError("Editor engine lost exported symbols: rebuild with the runtime's ABI")


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
    names = [Path(target["path"]).name for target in libraries(manifest)]
    for name in names:
        dynamic = run("readelf", "-d", str(bundle / name))
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
            raise ValueError("Editor library must not contain build-time library paths")
    if "engine" in manifest:
        verify_engine(manifest["engine"]["path"], bundle / Path(manifest["engine"]["path"]).name)
    manifest["files"] = {file: digest(bundle / file) for file in (*names, "source.tar.xz")}
    (bundle / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")


def install(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    targets = libraries(manifest)
    names = [Path(target["path"]).name for target in targets]
    for file in (*names, "source.tar.xz"):
        if digest(bundle / file) != manifest["files"][file]:
            raise ValueError("Damaged editor bundle: " + file)
    for name in names:
        if "not found" in run("ldd", str(bundle / name)):
            raise ValueError("Replacement editor library has missing dependencies")
    if "engine" in manifest:
        verify_engine(manifest["engine"]["path"], bundle / Path(manifest["engine"]["path"]).name)
    for target in targets:
        atomic_copy(bundle / Path(target["path"]).name, Path(target["path"]), 0o755)
    docs = Path("/usr/share/doc/monet-editor-recovery")
    docs.mkdir(parents=True, exist_ok=True)
    for file in ("source.tar.xz", "runtime.json", "README.md"):
        atomic_copy(bundle / file, docs / file, 0o644)


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
