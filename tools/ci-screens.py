#!/usr/bin/env python3
"""Screenshots from CI's virtual-machine tests, kept in the image registry.

    python3 tools/ci-screens.py push DIR ghcr.io/OWNER/monet:ci-screens     (CI: GITHUB_TOKEN, GITHUB_ACTOR)
    python3 tools/ci-screens.py pull ghcr.io/OWNER/monet:ci-screens DIR

The pictures (shrunk to JPEG) ride in the annotations of a small OCI
manifest, so they can be read back with nothing but the registry's manifest
API: a quick way to look at what the VM showed without downloading CI
artifacts.
"""

import base64
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EMPTY = b"{}"
EMPTY_DIGEST = "sha256:" + hashlib.sha256(EMPTY).hexdigest()
EMPTY_DESC = {"mediaType": "application/vnd.oci.empty.v1+json", "digest": EMPTY_DIGEST, "size": len(EMPTY)}
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
PREFIX = "org.monet.screen."
LIMIT = 3 * 1024 * 1024


def split(ref):
    registry, rest = ref.split("/", 1)
    repo, tag = rest.rsplit(":", 1)
    return registry, repo, tag


def token(registry, repo, scope, auth=None):
    url = f"https://{registry}/token?service={registry}&scope=repository:{repo}:{scope}"
    request = urllib.request.Request(url)
    if auth:
        request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(request, timeout=30) as r:
        return json.load(r)["token"]


def shrink(path, width=1100, quality=72):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality, optimize=True)
    return out.getvalue()


def push(folder, ref):
    registry, repo, tag = split(ref)
    auth = f"{os.environ.get('GITHUB_ACTOR', 'ci')}:{os.environ['GITHUB_TOKEN']}"
    bearer = {"Authorization": "Bearer " + token(registry, repo, "push,pull", auth)}
    base = f"https://{registry}/v2/{repo}"

    # The manifest's one blob: "{}".
    try:
        urllib.request.urlopen(urllib.request.Request(f"{base}/blobs/{EMPTY_DIGEST}", method="HEAD", headers=bearer),
                               timeout=30).close()
    except urllib.error.HTTPError:
        start = urllib.request.urlopen(urllib.request.Request(f"{base}/blobs/uploads/", data=b"", method="POST",
                                                              headers=bearer), timeout=30)
        location = urllib.parse.urljoin(base + "/", start.headers["Location"])
        sep = "&" if "?" in location else "?"
        urllib.request.urlopen(urllib.request.Request(
            f"{location}{sep}digest={EMPTY_DIGEST}", data=EMPTY, method="PUT",
            headers={**bearer, "Content-Type": "application/octet-stream"}), timeout=30).close()

    annotations, total = {}, 0
    # The minute-by-minute install shots go last: when the manifest is full,
    # they're the ones left out, not Monet itself.
    for path in sorted(Path(folder).glob("*.png"), key=lambda p: ("installing" in p.stem, p.name)):
        data = base64.b64encode(shrink(path)).decode()
        if total + len(data) > LIMIT:
            print(f"skipping {path.name}: the manifest is full")
            continue
        annotations[PREFIX + path.stem + ".jpg"] = data
        total += len(data)
    manifest = {"schemaVersion": 2, "mediaType": MANIFEST, "artifactType": "application/vnd.monet.screens.v1",
                "config": EMPTY_DESC, "layers": [EMPTY_DESC], "annotations": annotations}
    body = json.dumps(manifest).encode()
    urllib.request.urlopen(urllib.request.Request(f"{base}/manifests/{tag}", data=body, method="PUT",
                                                  headers={**bearer, "Content-Type": MANIFEST}), timeout=60).close()
    print(f"pushed {len(annotations)} screens ({len(body) // 1024} KiB) to {ref}")


def pull(ref, folder):
    registry, repo, tag = split(ref)
    bearer = {"Authorization": "Bearer " + token(registry, repo, "pull"), "Accept": MANIFEST}
    with urllib.request.urlopen(urllib.request.Request(f"https://{registry}/v2/{repo}/manifests/{tag}",
                                                       headers=bearer), timeout=60) as r:
        manifest = json.load(r)
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    for key, value in manifest.get("annotations", {}).items():
        if key.startswith(PREFIX):
            (out / key[len(PREFIX):]).write_bytes(base64.b64decode(value))
            print(out / key[len(PREFIX):])


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("push", "pull"):
        sys.exit(__doc__)
    {"push": push, "pull": pull}[sys.argv[1]](sys.argv[2], sys.argv[3])
