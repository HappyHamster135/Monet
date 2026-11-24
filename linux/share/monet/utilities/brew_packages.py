"""Homebrew package identities and metadata shared by the Utilities package views."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil

PART = r"[a-zA-Z0-9][a-zA-Z0-9_.+@-]*"
TOKEN = re.compile(rf"(?:{PART}/{PART}/)?{PART}\Z")


def locate(configured=""):
    if configured and not isinstance(configured, str):
        return "", "missing"
    paths = [configured] if configured else [
        shutil.which("brew"), str(Path(os.environ["HOMEBREW_PREFIX"]) / "bin/brew")
        if os.path.isabs(os.environ.get("HOMEBREW_PREFIX", "")) else None,
        "/home/linuxbrew/.linuxbrew/bin/brew", str(Path.home() / ".linuxbrew/bin/brew")]
    incomplete = False
    for value in filter(None, paths):
        path = Path(value)
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            continue
        repo = path.resolve().parent.parent
        if (repo.name == "Homebrew" or (repo / "Library/Homebrew").is_dir()) and not (repo / "Library/Homebrew/brew.sh").is_file():
            incomplete = True
            continue
        return str(path), ""
    return "", "incomplete" if incomplete else "missing"


@dataclass(frozen=True)
class Package:
    kind: str
    name: str
    installed: str = ""
    available: str = ""
    description: str = ""
    pinned: bool = False
    outdated: bool = False
    dependency: bool = False
    dependencies: tuple = ()

    @property
    def key(self):
        return self.kind, self.name

    @property
    def upgradable(self):
        return bool(self.installed) and self.outdated and not self.pinned


def package_info(raw):
    data = json.loads(raw)
    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ("formulae", "casks")):
        raise ValueError("Unexpected Homebrew inventory")
    packages = {}
    for field, kind in (("formulae", "formula"), ("casks", "cask")):
        for item in data[field]:
            if not isinstance(item, dict):
                raise ValueError("Invalid Homebrew record")
            if kind == "formula":
                name = item.get("full_name") or item.get("name")
                history = [r for r in item.get("installed") or [] if isinstance(r, dict)]
                versions = [r["version"] for r in history if isinstance(r.get("version"), str)]
                installed = ", ".join(dict.fromkeys(versions))
                available = (item.get("versions") or {}).get("stable") or ""
                revision = item.get("revision")
                if available and type(revision) is int and revision > 0:
                    available = f"{available}_{revision}"
                dependency = bool(history) and all(r.get("installed_on_request") is False for r in history)
                deps = item.get("dependencies") or []
            else:
                name = item.get("full_token") or item.get("token")
                installed = item.get("installed") or ""
                available = item.get("version") or ""
                dependency = False
                deps = (item.get("depends_on") or {}).get("formula") or []
            if not isinstance(name, str) or not TOKEN.fullmatch(name):
                continue
            pkg = Package(kind, name, str(installed), str(available), str(item.get("desc") or ""),
                          item.get("pinned") is True, item.get("outdated") is True, dependency,
                          tuple(n for n in deps if isinstance(n, str)))
            packages[pkg.key] = pkg
    return packages


def search_results(raw, kind, installed):
    hits = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        name = line.strip()
        if TOKEN.fullmatch(name):
            key = kind, name
            hits[key] = installed.get(key) or Package(kind, name)
    return hits
