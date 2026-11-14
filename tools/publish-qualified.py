#!/usr/bin/env python3
"""Publish checksummed OCI exports through the repository's package credentials.

The input record is committed before the publication tag is pushed. Archives are
temporary draft-release assets, removed before the public release is opened.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


def checked(command):
    return subprocess.run(command, check=True, capture_output=True).stdout


def verify_file(path, entry):
    if path.stat().st_size != entry["bytes"]:
        raise ValueError(f"Release file failed verification: {path.name}")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
            raise ValueError(f"Release file failed verification: {path.name}")


def verify_parts(record, folder):
    paths = []
    for part in record["parts"]:
        name = part["name"]
        if Path(name).name != name or not re.fullmatch(r"Monet-[0-9.]+(?:-[0-9]+)?-oci\.tar\.part-[a-z]{2}", name):
            raise ValueError("Invalid archive part name")
        path = folder / name
        verify_file(path, part)
        paths.append(path)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("Missing or repeated archive parts")
    return paths


def release_files(record):
    version = record["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9]+)?", version):
        raise ValueError("Invalid release version")
    names = {f"Monet-{version}-{kind}" for kind in (
        "Setup.iso", "Installer.iso", "Linux.tar.gz", "Windows.zip", "Make-USB-Stick.exe",
    )}
    if set(record["assets"]) != names | {"SHA256SUMS.txt"}:
        raise ValueError("Missing or unexpected qualified release files")
    return sorted(names)


def verify_release_files(record, folder, names):
    checksums = folder / "SHA256SUMS.txt"
    verify_file(checksums, record["assets"][checksums.name])
    expected = {name: record["assets"][name]["sha256"] for name in names}
    listed = {}
    for line in checksums.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or name in listed:
            raise ValueError("Invalid release checksum list")
        listed[name] = digest
    if listed != expected:
        raise ValueError("Release checksum list does not match the qualification record")
    for name in names:
        verify_file(folder / name, record["assets"][name])


def remote_digest(image):
    result = subprocess.run(["skopeo", "inspect", "--raw", "docker://" + image],
                            capture_output=True)
    if result.returncode:
        if b"manifest unknown" in result.stderr.lower():
            return None
        raise RuntimeError(f"Unable to inspect {image}: {result.stderr.decode()}")
    return "sha256:" + hashlib.sha256(result.stdout).hexdigest()


def publish(record, layout, signer=None):
    for variant, info in record["images"].items():
        image, digest = info["image"], info["manifest"]
        current = remote_digest(image)
        if current is not None and current != digest:
            raise RuntimeError(f"Refusing to replace an existing version: {image}")
        if signer:
            # An interrupted publish may have left a manifest without its signature.
            subprocess.run([sys.executable, str(signer), f"oci:{layout}:{variant}", image], check=True)
        elif current is None:
            subprocess.run(["skopeo", "copy", "--preserve-digests",
                            f"oci:{layout}:{variant}", "docker://" + image], check=True)
        if remote_digest(image) != digest:
            raise RuntimeError(f"Published manifest does not match: {image}")
    # Both versioned images must be verified before either rolling tag moves.
    for info in record["images"].values():
        image = info["image"]
        latest = image.rsplit(":", 1)[0] + ":latest"
        subprocess.run(["skopeo", "copy", "--preserve-digests",
                        "docker://" + image, "docker://" + latest], check=True)
        if remote_digest(latest) != info["manifest"]:
            raise RuntimeError(f"Rolling manifest does not match: {latest}")
        print(f"Verified {image} and {latest}: {info['manifest']}", flush=True)


def unpack_images(parts, layout, images):
    # Stream verified parts instead of making another full-sized archive copy.
    cat = subprocess.Popen(["cat", "--", *map(str, parts)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=cat.stdout, mode="r|") as archive:
            archive.extractall(layout, filter="data")
        if cat.wait() != 0:
            raise RuntimeError("Could not read verified OCI archive")
    finally:
        if cat.poll() is None:
            cat.terminate()
            cat.wait()
    for variant, info in images.items():
        raw = checked(["skopeo", "inspect", "--raw", f"oci:{layout}:{variant}"])
        if "sha256:" + hashlib.sha256(raw).hexdigest() != info["manifest"]:
            raise ValueError(f"Unexpected archived manifest: {variant}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--verify-local", action="store_true",
                        help="Verify existing files in the folder without downloading or publishing")
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    version = Path("VERSION").read_text().strip()
    if record["version"] != version:
        raise ValueError("Release version mismatch")
    folder = args.folder
    names = release_files(record) if "assets" in record else []
    if not args.verify_local:
        folder.mkdir(parents=True, exist_ok=True)
        patterns = ["--pattern", f"Monet-{version}-oci.tar.part-*"]
        if names:
            for name in [*names, "SHA256SUMS.txt"]:
                patterns.extend(("--pattern", name))
        subprocess.run(["gh", "release", "download", "v" + version, "--dir", str(folder),
                        *patterns], check=True)
    if names:
        verify_release_files(record, folder, names)
    parts = verify_parts(record, folder)
    with tempfile.TemporaryDirectory(prefix="monet-oci-", dir=folder) as directory:
        layout = Path(directory).resolve()
        unpack_images(parts, layout, record["images"])
        if args.verify_local:
            print(f"Verified local release {version} and both image manifests.")
            return
        signer = Path(__file__).with_name("sign-release-image.py") if Path("image/monet-update.pub").is_file() else None
        publish(record, layout, signer)


if __name__ == "__main__":
    main()
