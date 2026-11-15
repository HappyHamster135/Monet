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
import runpy
import subprocess
import sys
import tarfile


def checked(command):
    return subprocess.run(command, check=True, capture_output=True).stdout


def verify_parts(record, folder):
    prefix = re.escape(f"Monet-{record['version']}-oci.tar.part-")
    paths = []
    for part in record["parts"]:
        name = part["name"]
        if Path(name).name != name or not re.fullmatch(prefix + r"[a-z]{2}", name):
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


def publish(record, layout, signer=None, *, promote=True):
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
        print(f"Verified {image}: {digest}", flush=True)
    if not promote:
        return
    # Both versioned images must be verified before either rolling tag moves.
    for info in record["images"].values():
        image = info["image"]
        latest = image.rsplit(":", 1)[0] + ":latest"
        subprocess.run(["skopeo", "copy", "--preserve-digests",
                        "docker://" + image, "docker://" + latest], check=True)
        if remote_digest(latest) != info["manifest"]:
            raise RuntimeError(f"Rolling manifest does not match: {latest}")
        print(f"Verified {image} and {latest}: {info['manifest']}", flush=True)


def promote_existing(record, previous, folder):
    root = Path(__file__).resolve().parents[1]
    repositories = runpy.run_path(str(root / "image/install-update-trust.py"))["REPOSITORIES"]
    images = record["images"]
    old_images = previous["images"]
    if images.keys() != old_images.keys() or len(images) != len(repositories):
        raise ValueError("Both release variants are required for promotion")

    sources = {}
    policy = {}
    for variant, info in images.items():
        repository, _, tag = info["image"].rpartition(":")
        old = old_images[variant]
        if (repository not in repositories or repository in policy or tag != record["version"]
                or old["image"] != f"{repository}:{previous['version']}"
                or any(not re.fullmatch(r"sha256:[a-f0-9]{64}", item["manifest"]) for item in (info, old))):
            raise ValueError(f"Unexpected release target: {variant}")
        if remote_digest(info["image"]) != info["manifest"]:
            raise RuntimeError(f"Versioned image does not match: {info['image']}")
        sources[variant] = (f"{repository}@{info['manifest']}", f"{repository}:latest",
                            info["manifest"], old["manifest"])
        policy[repository] = [{"type": "sigstoreSigned", "keyPath": str(root / "image/monet-update.pub"),
                               "signedIdentity": {"type": "matchRepository"}}]

    def check_rolling(target, digest, old_digest):
        current = remote_digest(target)
        if current not in (digest, old_digest):
            raise RuntimeError(f"Rolling tag has changed unexpectedly: {target}")
        return current

    for _, target, digest, old_digest in sources.values():
        check_rolling(target, digest, old_digest)

    folder.mkdir(parents=True, exist_ok=True)
    registries = folder / "registries.d"
    registries.mkdir(exist_ok=True)
    (registries / "monet.yaml").write_text("docker:\n" + "".join(
        f"  {repository}:\n    use-sigstore-attachments: true\n" for repository in policy))
    policy_file = folder / "policy.json"
    policy_file.write_text(json.dumps({"default": [{"type": "reject"}], "transports": {"docker": policy}}))
    copy = ["skopeo", "--registries.d", str(registries), "--policy", str(policy_file),
            "copy", "--preserve-digests", "--remove-signatures"]

    # Verify both signatures before changing either rolling tag. The signatures
    # remain attached to these digests in the same repositories after retagging.
    for variant, (source, _, _, _) in sources.items():
        subprocess.run([*copy, f"docker://{source}", f"oci:{folder / 'verified'}:{variant}"], check=True)
        print(f"Verified signature for {source}", flush=True)
    for _, target, digest, old_digest in sources.values():
        check_rolling(target, digest, old_digest)
    for source, target, digest, old_digest in sources.values():
        if check_rolling(target, digest, old_digest) != digest:
            subprocess.run([*copy, f"docker://{source}", f"docker://{target}"], check=True)
        if remote_digest(target) != digest:
            raise RuntimeError(f"Rolling manifest does not match: {target}")
        print(f"Verified {target}: {digest}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("folder", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--versioned-only", action="store_true")
    mode.add_argument("--promote-existing-from", type=Path, metavar="PREVIOUS_RECORD")
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    version = Path("VERSION").read_text().strip()
    if record["version"] != version:
        raise ValueError("Release version mismatch")
    folder = args.folder
    if args.promote_existing_from:
        promote_existing(record, json.loads(args.promote_existing_from.read_text()), folder)
        return
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
    signer = Path(__file__).with_name("sign-release-image.py") if Path("image/monet-update.pub").is_file() else None
    publish(record, layout, signer, promote=not args.versioned_only)


if __name__ == "__main__":
    main()
