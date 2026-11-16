#!/usr/bin/env python3
"""Monet's betas: a new version people can choose to try before everyone gets it.

Pushing to the branch named beta (git push origin HEAD:beta) builds the version in VERSION
and publishes it as that version's next beta, signed like a release:

    git tag and GitHub pre-release   v0.9.8-7-beta.1, "Monet 0.9.8-7 beta 1"
    each image's own tag             ghcr.io/happyhamster135/monet:0.9.8-7-beta.1 (and monet-amd's)
    the images' :beta tag            moved to it once the whole beta is out

:latest and the version's own tag never move for a beta, and an installed Monet gets one only
when someone chooses Install beta (Settings → Updates). When the same source then reaches the
default branch, its release ships the beta's images exactly as they were tested instead of
building them again; without a published beta of that source the release is built as always.

    beta-release.py reserve                         the next beta number, kept as its git tag
    beta-release.py promotion                       the beta to release as this version, if any
    beta-release.py promote IMAGE VERSION TAG       that beta's signed image as VERSION, then latest
    beta-release.py newest VERSION NUMBER           exit 3 when a newer beta or the release is out
    beta-release.py notes VERSION NUMBER NOTES.md   the beta's release notes
    beta-release.py publish VERSION NUMBER IMAGE... :beta to this beta; older betas' pages go

Outputs for the workflow go to $GITHUB_OUTPUT (or stdout without it).
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = r"\d+\.\d+\.\d+(?:-\d+)?"
BETA = re.compile(rf"v?({RELEASE})-beta\.([1-9][0-9]{{0,5}})")
PUBLIC_KEY = ROOT / "image/monet-update.pub"
# A newer beta, or this version's release, is already out: this beta stays unpublished.
SUPERSEDED = 3


def release_order(version):
    """0.9.8 < 0.9.8-5 < 0.9.9, as Monet and Bridge compare them; None for anything else."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-(\d+))?", version or "")
    return tuple(int(part or 0) for part in match.groups()) if match else None


def beta(tag):
    """("0.9.8-7", 1) for v0.9.8-7-beta.1 (or the image tag 0.9.8-7-beta.1); None otherwise."""
    match = BETA.fullmatch(tag or "")
    return (match[1], int(match[2])) if match else None


def beta_order(tag):
    version, number = beta(tag)
    return release_order(version), number


def git_betas(tags, version=None):
    """The git tags among `tags` that are betas (of `version`, if given)."""
    return [tag for tag in tags if tag.startswith("v") and beta(tag) and (version is None or beta(tag)[0] == version)]


def remote_tags(listing):
    """{tag: commit} from `git ls-remote --tags`; an annotated tag counts as its commit."""
    tags = {}
    for line in listing.splitlines():
        sha, _, ref = line.partition("\t")
        if not ref.startswith("refs/tags/"):
            continue
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = sha
        else:
            tags.setdefault(name, sha)
    return tags


def superseded(version, tags):
    """Why a beta of `version` comes too late, or None: its release, or a newer one, is out
    (a beta never goes to PCs that already have as new a Monet), or a newer beta is."""
    order = release_order(version)
    for tag in tags:
        if re.fullmatch(rf"v{RELEASE}", tag) and release_order(tag[1:]) >= order:
            return f"{tag} is already released"
    return None


def next_number(version, tags):
    return max((beta(tag)[1] for tag in git_betas(tags, version)), default=0) + 1


def reserve(version, commit, git, attempts=5):
    """The next beta number of `version`, kept by pushing its git tag at `commit`. A pushed tag
    is never replaced, so betas pushed together get different numbers, and a beta that stops
    halfway keeps its number: the next push makes the next one."""
    if not release_order(version):
        raise ValueError(f"VERSION isn't a Monet version: {version!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"Not a commit: {commit!r}")
    for _ in range(attempts):
        tags = remote_tags(git("ls-remote", "--tags", "origin").stdout)
        reason = superseded(version, tags)
        if reason:
            raise SystemExit(f"{reason}: a beta needs a newer version in VERSION.")
        number = next_number(version, tags)
        pushed = git("push", "origin", f"{commit}:refs/tags/v{version}-beta.{number}", check=False)
        if pushed.returncode == 0:
            return number
        if "already exists" not in pushed.stderr and "rejected" not in pushed.stderr:
            raise RuntimeError(f"Couldn't keep beta {number}: {pushed.stderr.strip()}")
    raise RuntimeError("Couldn't keep a beta number: other betas kept taking them")


def promotion(version, head, head_tree, tags, released, tree_of):
    """The image tag of the newest published beta of `version` made from this same source (this
    commit, or one with exactly the same files), or None: then the release is built as always.
    `released()` lists the published releases; it's asked only when there is a beta of `version`."""
    candidates = sorted(git_betas(tags, version), key=beta_order, reverse=True)
    if not candidates:
        return None
    published = released()
    for tag in candidates:
        if tag in published and (tags[tag] == head or tree_of(tag) == head_tree):
            return tag[1:]
    return None


class Registry:
    """The image registry through skopeo: a manifest's digest, and copies that keep it, each
    checked against Monet's signing key first for Monet's own repositories (as PCs check it)."""

    def __init__(self, folder, run=subprocess.run, repositories=None):
        self.folder = Path(folder)
        self.run = run
        if repositories is None:
            repositories = runpy.run_path(str(ROOT / "image/install-update-trust.py"))["REPOSITORIES"]
        self.repositories = tuple(repositories)

    def digest(self, image):
        result = self.run(["skopeo", "inspect", "--raw", "docker://" + image], capture_output=True)
        if result.returncode:
            if b"manifest unknown" in result.stderr.lower():
                return None
            raise RuntimeError(f"Unable to inspect {image}: {result.stderr.decode(errors='replace')}")
        return "sha256:" + hashlib.sha256(result.stdout).hexdigest()

    def copy(self, source, target):
        repository = re.split(r"[@:](?=[^/]*$)", source, maxsplit=1)[0]
        if repository in self.repositories and PUBLIC_KEY.is_file():
            rule = [{"type": "sigstoreSigned", "keyPath": str(PUBLIC_KEY),
                     "signedIdentity": {"type": "matchRepository"}}]
            policy = {"default": [{"type": "reject"}], "transports": {"docker": {repository: rule}}}
        else:
            policy = {"default": [{"type": "insecureAcceptAnything"}]}
        self.folder.mkdir(parents=True, exist_ok=True)
        registries = self.folder / "registries.d"
        registries.mkdir(exist_ok=True)
        (registries / "monet.yaml").write_text(f"docker:\n  {repository}:\n    use-sigstore-attachments: true\n")
        policy_file = self.folder / "policy.json"
        policy_file.write_text(json.dumps(policy))
        # The signature stays attached to the digest in the same repository: nothing to copy.
        self.run(["skopeo", "--registries.d", str(registries), "--policy", str(policy_file), "copy",
                  "--preserve-digests", "--remove-signatures", "docker://" + source, "docker://" + target],
                 check=True)


def promote(repository, version, tag, registry, released):
    """Release a tested beta's image as `version`: its exact manifest, its signature checked,
    copied to the version's tag and then to latest. Never replaces a version that's out."""
    if beta(tag) is None or beta(tag)[0] != version or tag.startswith("v"):
        raise ValueError(f"{tag} isn't a beta of {version}")
    if released(version):
        print(f"v{version} is released; keeping its qualified image.", flush=True)
        return None
    digest = registry.digest(f"{repository}:{tag}")
    if digest is None:
        raise RuntimeError(f"The tested beta isn't published: {repository}:{tag}")
    current = registry.digest(f"{repository}:{version}")
    if current not in (None, digest):
        raise RuntimeError(f"Refusing to replace an existing version: {repository}:{version}")
    for target in ([version] if current is None else []) + ["latest"]:
        registry.copy(f"{repository}@{digest}", f"{repository}:{target}")
        if registry.digest(f"{repository}:{target}") != digest:
            raise RuntimeError(f"Published manifest does not match: {repository}:{target}")
        print(f"Verified {repository}:{target}: {digest} (beta {tag})", flush=True)
    return digest


def newest(version, number, releases):
    """Whether beta `number` of `version` is still the newest: no newer beta's release and no
    release of this version or a newer one is out."""
    reason = superseded(version, releases)
    if reason:
        return False, reason
    ours = (release_order(version), number)
    for tag in git_betas(releases):
        if beta_order(tag) > ours:
            return False, f"{tag} is already out"
    return True, None


def older_betas(version, number, releases):
    """The other betas' release pages, older than this one, newest first."""
    ours = (release_order(version), number)
    return sorted((tag for tag in git_betas(releases) if beta_order(tag) < ours), key=beta_order, reverse=True)


def publish(version, number, repositories, registry, releases, delete):
    """After the beta's release: each image's :beta moves to it, then the older betas' release
    pages go (their tags and images stay). One beta page at a time keeps the releases Bridge
    looks through (the newest ten) for releases."""
    tag = f"{version}-beta.{number}"
    for repository in repositories:
        digest = registry.digest(f"{repository}:{tag}")
        if digest is None:
            raise RuntimeError(f"The beta isn't published: {repository}:{tag}")
        registry.copy(f"{repository}@{digest}", f"{repository}:beta")
        if registry.digest(f"{repository}:beta") != digest:
            raise RuntimeError(f"Published manifest does not match: {repository}:beta")
        print(f"Verified {repository}:beta: {digest} ({tag})", flush=True)
    for old in older_betas(version, number, releases):
        delete(old)
        print(f"Removed the release page of {old}; its tag and images stay.", flush=True)


def notes(version, number, text):
    this = runpy.run_path(str(ROOT / "tools/release-notes.py"))["this_release"](text)
    return (f"**Monet {version} beta {number}: not fully tested yet.** It's for people who'd like to try "
            "what's next and say what they find. A PC gets it only when someone chooses Install beta in "
            "Settings → Updates, with Show beta versions on. When Monet "
            f"{version} itself is released, a PC on this beta moves to it by itself, with its daily update.\n\n"
            f"To make a USB stick of this beta, download Monet-{version}-Setup.iso and drop it onto "
            "Make-USB-Stick.exe.\n\n" + this)


def output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(lines)
    else:
        sys.stdout.write(lines)


def git(*args, check=True):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


def published_releases():
    listing = subprocess.run(["gh", "release", "list", "--limit", "100", "--json", "tagName,isDraft"],
                             capture_output=True, text=True, check=True).stdout
    return {item["tagName"] for item in json.loads(listing) if not item["isDraft"]}


def is_released(version):
    """Whether v`version` is tagged. Git says 2 only when the tag doesn't exist: a network or
    authentication failure is never taken for an unreleased version."""
    result = subprocess.run(["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/v{version}"],
                            capture_output=True, text=True)
    if result.returncode in (0, 2):
        return result.returncode == 0
    raise RuntimeError(f"Could not determine whether v{version} is released: {result.stderr.strip()}")


def tree_of(tag):
    git("fetch", "--quiet", "--depth=1", "origin", f"refs/tags/{tag}")
    return git("rev-parse", "FETCH_HEAD^{tree}").stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("reserve")
    commands.add_parser("promotion")
    command = commands.add_parser("promote")
    command.add_argument("image")
    command.add_argument("version")
    command.add_argument("tag")
    command = commands.add_parser("newest")
    command.add_argument("version")
    command.add_argument("number", type=int)
    command = commands.add_parser("notes")
    command.add_argument("version")
    command.add_argument("number", type=int)
    command.add_argument("notes", type=Path)
    command = commands.add_parser("publish")
    command.add_argument("version")
    command.add_argument("number", type=int)
    command.add_argument("images", nargs="+")
    args = parser.parse_args(argv)

    if args.command == "reserve":
        version = (ROOT / "VERSION").read_text().strip()
        commit = os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD").stdout.strip()
        number = reserve(version, commit, git)
        print(f"Monet {version} beta {number} (v{version}-beta.{number})", flush=True)
        output(version=version, number=number, tag=f"{version}-beta.{number}", release=f"v{version}-beta.{number}")
    elif args.command == "promotion":
        version = (ROOT / "VERSION").read_text().strip()
        tags = remote_tags(git("ls-remote", "--tags", "origin").stdout)
        head = git("rev-parse", "HEAD").stdout.strip()
        found = promotion(version, head, git("rev-parse", "HEAD^{tree}").stdout.strip(), tags,
                          published_releases, tree_of)
        print(f"Releasing beta {found} as Monet {version}, as it was tested." if found
              else f"No published beta of this source: Monet {version} is built.", flush=True)
        output(promote=found or "")
    elif args.command == "promote":
        with tempfile.TemporaryDirectory(prefix="monet-promote-") as folder:
            digest = promote(args.image, args.version, args.tag, Registry(folder), is_released)
        if digest:
            output(digest=digest)
    elif args.command == "newest":
        current, reason = newest(args.version, args.number, published_releases())
        if not current:
            print(f"Monet {args.version} beta {args.number} stays unpublished: {reason}.", flush=True)
            return SUPERSEDED
    elif args.command == "notes":
        sys.stdout.write(notes(args.version, args.number, args.notes.read_text(encoding="utf-8")))
    elif args.command == "publish":
        def delete(tag):
            subprocess.run(["gh", "release", "delete", tag, "--yes"], check=True)
        with tempfile.TemporaryDirectory(prefix="monet-beta-") as folder:
            publish(args.version, args.number, args.images, Registry(folder), published_releases(), delete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
