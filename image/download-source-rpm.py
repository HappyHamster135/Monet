#!/usr/bin/env python3
"""Fetch the installed Fedora package's exact, signed source from Koji."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request


def query(*args):
    return subprocess.check_output(["rpm", *args], text=True,
                                   env=dict(os.environ, LC_ALL="C")).strip()


def signing_key(signature):
    match = re.search(r"Key ID ([0-9a-fA-F]{16,40})$", signature)
    if not match:
        raise ValueError("The installed Fedora package has no supported signing key")
    return match[1].lower()


def source_info(package):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]*", package):
        raise ValueError("Invalid installed package name")
    source, vendor, signature = query("-q", "--qf", "%{SOURCERPM}\n%{VENDOR}\n%{RSAHEADER:pgpsig}", package).splitlines()
    match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9+_.-]*)-([A-Za-z0-9+_.~]+)-([A-Za-z0-9+_.~]+)\.src\.rpm", source)
    if not match or vendor != "Fedora Project":
        raise ValueError("Expected an installed Fedora source package")
    key = signing_key(signature)
    name, version, release = match.groups()
    url = f"https://kojipkgs.fedoraproject.org/packages/{name}/{version}/{release}/data/signed/{key[-8:]}/src/{source}"
    return source, key, url


def verify(path, source, key):
    # Requiring both digest and signature rejects unsigned archives too.
    subprocess.run(["rpmkeys", "--define", "_pkgverify_level all", "--checksig", str(path)], check=True)
    identity, is_source, signature = query("-qp", "--qf",
        "%{NAME}-%{VERSION}-%{RELEASE}.src.rpm\n%{SOURCEPACKAGE}\n%{RSAHEADER:pgpsig}", str(path)).splitlines()
    if identity != source or is_source != "1" or signing_key(signature) != key:
        raise ValueError("Source archive does not match the installed Fedora package and signer")


def download(package, destination):
    source, key, url = source_info(package)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".source-", dir=destination) as temporary:
        path = Path(temporary) / source
        # Koji retains exact builds after repository metadata drops older sources.
        # Only read source archives: no package exclusions or installed RPMs change.
        with urllib.request.urlopen(url, timeout=60) as response, path.open("wb") as output:
            shutil.copyfileobj(response, output)
        verify(path, source, key)
        path.replace(destination / source)
    print("Verified Fedora source:", source, flush=True)
    return destination / source


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    download(args.package, args.destination)
