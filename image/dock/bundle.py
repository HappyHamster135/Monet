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

PLUGIN = "org.kde.plasma.taskmanager.so"
TRASH = "org.kde.plasma.trash.so"
PLUGINS = (PLUGIN, TRASH)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plugin_path(name=PLUGIN):
    paths = [p for p in run("rpm", "-ql", "plasma-desktop").splitlines()
             if p.endswith("/plasma/applets/" + name)]
    if len(paths) != 1:
        raise ValueError("Expected one installed Plasma dock applet")
    return Path(paths[0])


def packages(names):
    return sorted(run("rpm", "-q", "--qf", "%{NEVRA}\n", *names).splitlines())


def capture():
    plugin = plugin_path()
    originals = [plugin_path(name) for name in PLUGINS]
    linked = '\n'.join(run('ldd', str(p)) for p in originals)
    if "not found" in linked:
        raise ValueError("The base dock applet has missing libraries")
    paths = {*map(str, originals), *re.findall(r"(?:=>\s+|^\s*)(/\S+)", linked, re.M)}
    names = {"plasma-desktop", "plasma-workspace-libs", "libplasma"}
    for path in paths:
        names.update(run("rpm", "-qf", "--qf", "%{NAME}.%{ARCH}\n", str(Path(path).resolve())).splitlines())
    return {"schema": 2, "path": str(plugin), "original_sha256": digest(plugin),
            "originals": {str(p): digest(p) for p in originals},
            "package_names": sorted(names), "packages": packages(sorted(names))}


def verify(manifest):
    if manifest.get("schema") not in (1, 2):
        raise ValueError("Unsupported dock bundle")
    target = manifest.get("path", "")
    if not re.fullmatch(r"/usr/lib(?:64)?/qt6/plugins/plasma/applets/" + re.escape(PLUGIN), target):
        raise ValueError("Unexpected dock plugin destination")
    if packages(manifest["package_names"]) != manifest["packages"]:
        raise ValueError("Plasma/runtime packages changed: rebuild the dock applet for this image")
    if digest(target) != manifest["original_sha256"]:
        raise ValueError("The base dock applet changed: rebuild against this image")
    if manifest['schema'] == 2:
        expected = {str(plugin_path(name)) for name in PLUGINS}
        if set(manifest.get('originals', {})) != expected:
            raise ValueError('Incomplete dock source fingerprints')
        for path, fingerprint in manifest['originals'].items():
            if digest(path) != fingerprint: raise ValueError('A base dock applet changed')


def plugin_names(manifest):
    return PLUGINS if manifest.get('schema') == 2 else (PLUGIN,)


def install(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    # Validate every delivered file before replacing anything in the image.
    for name in (*plugin_names(manifest), "source.tar.xz"):
        if digest(bundle / name) != manifest["files"][name]:
            raise ValueError(f"Damaged dock bundle: {name}")
    linked = '\n'.join(run('ldd', str(bundle / name)) for name in plugin_names(manifest))
    if "not found" in linked:
        raise ValueError("The replacement dock applet has missing libraries")
    for name in plugin_names(manifest): atomic_copy(bundle / name, Path(manifest['path']).with_name(name), 0o755)
    docs = Path("/usr/share/doc/monet-dock")
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("source.tar.xz", "runtime.json", "README.md"):
        atomic_copy(bundle / name, docs / name, 0o644)


def verified_binary(bundle):
    return verified_binaries(bundle)[0]


def verified_binaries(bundle):
    manifest = json.loads((bundle / "runtime.json").read_text())
    verify(manifest)
    plugins = [bundle / name for name in plugin_names(manifest)]
    for plugin in plugins:
        if digest(plugin) != manifest['files'][plugin.name]: raise ValueError('Damaged dock plugin')
        if 'not found' in run('ldd', str(plugin)): raise ValueError('The dock plugin has missing libraries')
    return plugins


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
        dynamic = '\n'.join(run('readelf', '-d', str(path / name)) for name in plugin_names(manifest))
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
            raise ValueError("The dock applet must not contain a build-time library path")
        manifest["files"] = {name: digest(path / name) for name in (*plugin_names(manifest), "source.tar.xz")}
        (path / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
    elif command == "install":
        install(path)
    else:
        raise ValueError("Expected capture, verify, seal or install")


if __name__ == "__main__":
    main()
