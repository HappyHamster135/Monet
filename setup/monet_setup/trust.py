"""The OS manifests recorded on a built Setup stick."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from . import cache, pc

MEDIA = Path(__file__).resolve().parent.parent
INSTALLED_MEDIA = Path("/usr/share/monet-setup")
PINS = "IMAGE_DIGESTS.json"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
RELEASE_REPOSITORIES = {"ghcr.io/happyhamster135/monet", "ghcr.io/happyhamster135/monet-amd"}


def read_pins(path):
    pins = json.loads(path.read_text())
    if not isinstance(pins, dict) or not pins or not all(
            isinstance(value, str) and DIGEST.fullmatch(value) for value in pins.values()):
        raise ValueError("Invalid Monet image digests")
    return pins


def expected(image, media=None):
    media = MEDIA if media is None else media
    try:
        pins = read_pins(media / PINS)
    except FileNotFoundError:
        # Running Setup from source for development has no built-media metadata.
        if media != INSTALLED_MEDIA and not (media / "IMAGE").exists():
            return None
        raise
    if image not in pins:
        raise ValueError("The installer has no digest for this Monet image")
    return pins[image]


def image_repository(image):
    repo, separator, tag = image.rpartition(":")
    if not separator or not tag or "/" in tag or "/" not in repo or "@" in repo:
        raise ValueError("Setup requires a tagged Monet image")
    return repo


def pinned_reference(image, digest):
    repo = image_repository(image)
    if not DIGEST.fullmatch(digest):
        raise ValueError("Invalid Monet image digest")
    return f"{repo}@{digest}"


def update_reference(image):
    return f"{image_repository(image)}:latest"


def registry_digest(image):
    manifest = subprocess.run(["skopeo", "inspect", "--raw", f"docker://{image}"],
                              check=True, capture_output=True, timeout=120).stdout
    data = json.loads(manifest)
    # Each graphics variant is a single OCI image for x86-64. Preserve its
    # manifest bytes when copying into the installer's OCI cache.
    if not isinstance(data, dict) or data.get("schemaVersion") != 2 or data.get("mediaType") != cache.OCI_MANIFEST:
        raise ValueError(f"{image} is not a single OCI image manifest")
    return "sha256:" + hashlib.sha256(manifest).hexdigest()


def image_pins(image, source=None):
    variants = {image, pc.image_for(image, {"newNvidia": False})}
    pins = read_pins(source) if source is not None else {ref: registry_digest(ref) for ref in sorted(variants)}
    if pins.keys() != variants:
        raise ValueError("The digest list must match the installer's image variants")
    for ref, digest in pins.items():
        pinned_reference(ref, digest)
    return pins


def write_pins(image, destination, source=None):
    pins = image_pins(image, source)
    destination.write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n")


def render_kickstart(template, image, pins):
    amd = pc.image_for(image, {"newNvidia": False})
    return template.replace("@IMAGE@", pinned_reference(image, pins[image])).replace(
        "@AMD_IMAGE@", pinned_reference(amd, pins[amd]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("destination", type=Path)
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--kickstart", type=Path)
    args = parser.parse_args()
    if args.kickstart:
        args.destination.write_text(render_kickstart(args.kickstart.read_text(), args.image,
                                                     image_pins(args.image, args.source)))
    else:
        write_pins(args.image, args.destination, args.source)
