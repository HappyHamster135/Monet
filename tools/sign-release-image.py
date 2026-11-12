#!/usr/bin/env python3
"""Publish an OCI manifest with the release signer trusted by Monet."""

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = runpy.run_path(str(ROOT / "image/install-update-trust.py"))["REPOSITORIES"]
PUBLIC_KEY = ROOT / "image/monet-update.pub"


def sign(source, destination, digest_output):
    repository = destination.rsplit(":", 1)[0]
    if repository not in REPOSITORIES or not source.startswith(("oci:", "containers-storage:")):
        raise ValueError("Signing requires a local OCI image and an official Monet repository.")
    key = os.environ.pop("MONET_SIGNING_KEY", "")
    passphrase = os.environ.pop("MONET_SIGNING_PASSPHRASE", "")
    if not key or not passphrase:
        raise ValueError("The Monet release signing credentials are missing.")

    with tempfile.TemporaryDirectory(prefix="monet-sign-") as temporary:
        folder = Path(temporary)
        private = folder / "signing.key"
        password = folder / "passphrase"
        private.write_text(key)
        password.write_text(passphrase)
        private.chmod(0o600)
        password.chmod(0o600)
        derived = subprocess.check_output(["cosign", "public-key", "--key", str(private)],
                                          env=dict(os.environ, COSIGN_PASSWORD=passphrase))
        if derived.strip() != PUBLIC_KEY.read_bytes().strip():
            raise ValueError("The release signer does not match the public key shipped in Monet.")

        registries = folder / "registries.d"
        registries.mkdir()
        (registries / "monet.yaml").write_text(
            f"docker:\n  {repository}:\n    use-sigstore-attachments: true\n")
        prefix = ["sudo"] if source.startswith("containers-storage:") else []
        skopeo = [*prefix, "skopeo", "--registries.d", str(registries)]
        recorded = folder / "digest"
        exact = source.startswith("oci:")
        copy_format = ["--preserve-digests"] if exact else ["--format", "oci"]
        subprocess.run([*skopeo, "copy", *copy_format,
                        "--sign-by-sigstore-private-key", str(private), "--sign-passphrase-file", str(password),
                        "--digestfile", str(recorded), source, "docker://" + destination], check=True)
        digest = recorded.read_text().strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise RuntimeError("The registry did not return a valid manifest digest.")

        if exact:
            # Verify using the same pull-time signature rule installed in Monet.
            # The OCI destination already has these blobs, so no duplicate export is needed.
            policy = folder / "policy.json"
            policy.write_text(json.dumps({"default": [{"type": "reject"}], "transports": {"docker": {
                repository: [{"type": "sigstoreSigned", "keyPath": str(PUBLIC_KEY),
                              "signedIdentity": {"type": "matchRepository"}}]}}}))
            layout = source.rsplit(":", 1)[0]
            subprocess.run([*skopeo, "--policy", str(policy), "copy", "--preserve-digests", "--remove-signatures",
                            f"docker://{repository}@{digest}", f"{layout}:verified-{digest[7:19]}"], check=True)
        if digest_output:
            digest_output.write_text(digest + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("digest_output", nargs="?", type=Path)
    args = parser.parse_args()
    sign(args.source, args.destination, args.digest_output)
