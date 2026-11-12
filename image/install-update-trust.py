#!/usr/bin/env python3
"""Trust Monet's release signer for its two public update repositories."""

import json
import os
from pathlib import Path
import sys
import tempfile


REPOSITORIES = ("ghcr.io/happyhamster135/monet", "ghcr.io/happyhamster135/monet-amd")
KEY_PATH = Path("/etc/containers/keys/monet-update.pub")


def replace(path, contents):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(contents)
            stream.flush()
            temporary.chmod(0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def install(root, public_key):
    policy_path = root / "etc/containers/policy.json"
    policy = json.loads(policy_path.read_text())
    docker = policy.setdefault("transports", {}).setdefault("docker", {})
    for repository in REPOSITORIES:
        docker[repository] = [{
            "type": "sigstoreSigned",
            "keyPath": str(KEY_PATH),
            "signedIdentity": {"type": "matchRepository"},
        }]
    target = root / KEY_PATH.relative_to("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    replace(target, public_key.read_bytes())
    registries = root / "etc/containers/registries.d"
    registries.mkdir(parents=True, exist_ok=True)
    config = "docker:\n" + "".join(f"  {repository}:\n    use-sigstore-attachments: true\n"
                                   for repository in REPOSITORIES)
    replace(registries / "monet.yaml", config.encode())
    replace(policy_path, (json.dumps(policy, indent=2) + "\n").encode())


if __name__ == "__main__":
    install(Path("/"), Path(sys.argv[1]))
