#!/usr/bin/python3
"""Install the screencast module only against its verified KWin runtime."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def target():
    matches = [Path(line) for line in output("rpm", "-ql", "kwin-common").splitlines()
               if re.fullmatch(r"/usr/lib(?:64)?/qt6/plugins/kwin/plugins/screencast\.so", line)]
    path, = matches
    return path


def capture():
    module = target()
    deps = output("ldd", str(module))
    if "not found" in deps:
        raise ValueError("Incomplete KWin screencast runtime")
    paths = {str(module), *re.findall(r"(?:=>\s+|^\s*)(/\S+)", deps, re.M)}
    packages = set(output("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n",
                          *(str(Path(p).resolve()) for p in sorted(paths))).splitlines())
    versions = output("rpm", "-q", "--qf", "%{NEVRA}\n", *sorted(packages))
    kwin, = re.findall(r"libkwin\.so\.\S+ => (/\S+)", deps)
    return dict(original=digest(module), kwin=digest(Path(kwin)), package_names=sorted(packages),
                packages=sorted(versions.splitlines()))


def check_binary(path):
    linked = output("ldd", "-r", str(path))
    dynamic = output("readelf", "-d", str(path))
    if "undefined symbol" in linked or "not found" in linked or "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
        raise ValueError("Incompatible KWin screencast module")


def install(folder, root):
    manifest = json.loads((folder/"runtime.json").read_bytes())
    if manifest["runtime"] != capture():
        raise ValueError("KWin runtime changed since the recording module was built")
    files = {name: digest(folder/name) for name in ("source.tar.xz", "screencast.so", "README.md")}
    if manifest["files"] != files:
        raise ValueError("Damaged recording module")
    check_binary(folder/"screencast.so")
    original = target().relative_to("/")
    binary = original.parents[4] / "monet-recording-clicks" / files["screencast.so"] / original.name
    (root/binary.parent).mkdir(parents=True, exist_ok=True)
    shutil.copy2(folder/original.name, root/binary)
    (root/original.parent).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root/original.parent) as tmp:
        link = Path(tmp) / original.name
        link.symlink_to(os.path.relpath(binary, original.parent))
        os.replace(link, root/original)
    docs = root/"usr/share/doc/monet-recording-clicks"
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("runtime.json", "README.md", "source.tar.xz"):
        shutil.copy2(folder/name, docs/name)


if __name__ == "__main__":
    command, arg = sys.argv[1:]
    folder = Path(arg)
    path = folder/"runtime.json"
    if command == "install":
        install(folder, Path("/"))
    elif command == "capture":
        path.write_text(json.dumps(dict(runtime=capture()), indent=2) + "\n")
    elif command in ("seal", "verify"):
        manifest = json.loads(path.read_bytes())
        if manifest["runtime"] != capture():
            raise ValueError("KWin runtime changed since build preparation")
        if command == "seal":
            check_binary(folder/"screencast.so")
            manifest["files"] = {name: digest(folder/name) for name in ("source.tar.xz", "screencast.so", "README.md")}
            path.write_text(json.dumps(manifest, indent=2) + "\n")
    else:
        raise ValueError(command)
