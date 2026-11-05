#!/usr/bin/env python3
"""Publish checksummed OCI exports through the repository's package credentials.

The input record is committed before the publication tag is pushed. Archives are
temporary draft-release assets, removed before the public release is opened.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def checked(command):
    return subprocess.run(command, check=True, capture_output=True).stdout


def verify_parts(record, folder):
    paths = []
    for part in record["parts"]:
        name = part["name"]
        if Path(name).name != name or not re.fullmatch(r"Monet-[0-9.]+-oci\.tar\.part-[a-z]{2}", name):
            raise ValueError("Invalid archive part name")
        path = folder / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != part["bytes"] or digest != part["sha256"]:
            raise ValueError(f"Archive part failed verification: {name}")
        paths.append(path)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("Missing or repeated archive parts")
    return paths


def remote_digest(image):
    result = subprocess.run(["skopeo", "inspect", "--raw", "docker://" + image],
                            capture_output=True)
    if result.returncode:
        if b"manifest unknown" in result.stderr.lower():
            return None
        raise RuntimeError(f"Unable to inspect {image}: {result.stderr.decode()}")
    return "sha256:" + hashlib.sha256(result.stdout).hexdigest()


def publish(record, layout):
    for variant, info in record["images"].items():
        image, digest = info["image"], info["manifest"]
        current = remote_digest(image)
        if current is not None and current != digest:
            raise RuntimeError(f"Refusing to replace an existing version: {image}")
        if current is None:
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


def main():
    record = json.loads(Path(sys.argv[1]).read_text())
    version = Path("VERSION").read_text().strip()
    if record["version"] != version:
        raise ValueError("Release version mismatch")
    folder = Path(sys.argv[2])
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "release", "download", "v" + version, "--dir", str(folder),
                    "--pattern", f"Monet-{version}-oci.tar.part-*"], check=True)
    parts = verify_parts(record, folder)
    layout = folder / "oci"
    layout.mkdir()
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
    for variant, info in record["images"].items():
        raw = checked(["skopeo", "inspect", "--raw", f"oci:{layout}:{variant}"])
        if "sha256:" + hashlib.sha256(raw).hexdigest() != info["manifest"]:
            raise ValueError(f"Unexpected archived manifest: {variant}")
    publish(record, layout)


if __name__ == "__main__":
    main()
