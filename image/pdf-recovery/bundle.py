#!/usr/bin/python3
"""Guard the PDF shell against its unchanged document engine and image runtime."""
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
    try:
        return sorted(run("rpm", "-q", "--qf", "%{NEVRA}\n", *names).splitlines())
    except subprocess.CalledProcessError as error:
        raise ValueError("PDF runtime changed: a required package is missing") from error


def capture():
    parts = re.findall(r"^(/usr/lib(?:64)?/qt6/plugins/kf6/parts/okularpart\.so)$",
                       run("rpm", "-ql", "okular-part"), re.M)
    if len(parts) != 1:
        raise ValueError("Expected one installed Okular document part")
    core = re.findall(r"libOkular6Core\.so\.\d+ => (/\S+)", run("ldd", parts[0]))
    if len(core) != 1:
        raise ValueError("Expected one installed Okular document engine")
    generator = Path(parts[0]).parents[2] / "okular_generators/okularGenerator_poppler.so"
    targets = ["/usr/bin/okular", parts[0], str(Path(core[0]).resolve()), str(generator)]
    names = set()
    for target in targets:
        linked = run("ldd", target)
        if "not found" in linked:
            raise ValueError("PDF runtime has missing dependencies")
        for path in {target, *re.findall(r"(?:=>\s+|^\s*)(/\S+)", linked, re.M)}:
            names.update(run("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n", str(Path(path).resolve())).splitlines())
    return {"schema": 1, "targets": [{"path": p, "original_sha256": digest(p)} for p in targets],
            "package_names": sorted(names), "packages": packages(sorted(names))}


def verify(manifest):
    targets = manifest.get("targets")
    patterns = (r"/usr/bin/okular", r"/usr/lib(?:64)?/qt6/plugins/kf6/parts/okularpart\.so",
                r"/usr/lib(?:64)?/libOkular6Core\.so\.\d+(?:\.\d+)*",
                r"/usr/lib(?:64)?/qt6/plugins/okular_generators/okularGenerator_poppler\.so")
    if (manifest.get("schema") != 1 or not isinstance(targets, list) or len(targets) != len(patterns)
            or any(not isinstance(t, dict) or not re.fullmatch(pattern, t.get("path", ""))
                   for t, pattern in zip(targets, patterns))):
        raise ValueError("Invalid PDF runtime destinations")
    names = manifest.get("package_names")
    if (not isinstance(names, list) or not 1 <= len(names) <= 512
            or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]*", n) for n in names)
            or packages(names) != manifest["packages"]):
        raise ValueError("PDF runtime changed: rebuild for this image")
    for target in targets:
        if digest(target["path"]) != target["original_sha256"]:
            raise ValueError("Base PDF binary changed: rebuild for this image")


def compatible(original, replacement):
    def needed(path):
        dynamic = run("readelf", "-d", str(path))
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
            raise ValueError("PDF shell contains a build-time library path")
        return set(re.findall(r"\(NEEDED\).*\[([^\]]+)\]", dynamic))
    dependencies = needed(original)
    if not dependencies or needed(replacement) not in (dependencies, dependencies | {"libwayland-client.so.0"}):
        raise ValueError("PDF shell build features differ from the runtime")


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
        Path(temporary).unlink(missing_ok=True)


def seal(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    compatible("/usr/bin/okular", bundle / "okular")
    manifest["files"] = {name: digest(bundle / name) for name in ("okular", "source.tar.xz")}
    (bundle / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")


def install(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    for name in ("okular", "source.tar.xz"):
        if digest(bundle / name) != manifest["files"][name]:
            raise ValueError("Damaged PDF bundle: " + name)
    compatible("/usr/bin/okular", bundle / "okular")
    linked = run("ldd", "-r", str(bundle / "okular"))
    if "not found" in linked or "undefined symbol" in linked:
        raise ValueError("PDF shell has unresolved dependencies")
    atomic_copy(bundle / "okular", Path("/usr/bin/okular"), 0o755)
    docs = Path("/usr/share/doc/monet-pdf-recovery")
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("runtime.json", "source.tar.xz", "README.md"):
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
