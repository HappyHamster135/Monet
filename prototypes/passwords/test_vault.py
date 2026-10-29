#!/usr/bin/env python3
"""VM fixture only: make a disposable vault and register its native browser host.

Requires the preview in ~/monet-passwords-build/out and its runtime libraries.
Restore the VM checkpoint after testing. Never place real credentials here.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE = Path.home() / "monet-passwords-build"
VAULT = BASE / "fixtures/Passwords.kdbx"
MASTER = "Monet-demo-vault-only-1028!"
ENV = dict(os.environ, LD_LIBRARY_PATH=str(BASE / "runtime"),
           DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{os.getuid()}/bus",
           XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}", WAYLAND_DISPLAY="wayland-0",
           QT_QPA_PLATFORM="wayland", QT_QPA_PLATFORMTHEME="kde", QT_STYLE_OVERRIDE="kvantum",
           XDG_CONFIG_HOME=str(BASE / "config"), QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1")


def cli(args, supplied):
    return subprocess.run([str(BASE / "out/bin/keepassxc-cli"), *args], input=supplied,
                          text=True, env=ENV, capture_output=True, check=True).stdout


def setup():
    os.umask(0o077)
    if VAULT.exists():
        raise SystemExit("The fixture vault already exists; refusing to replace it.")
    config = BASE / "config/monet/passwords-preview"
    config.mkdir(parents=True, exist_ok=True)
    source = Path.home() / ".config/Kvantum"
    link = BASE / "config/Kvantum"
    if source.exists() and not link.exists():
        link.symlink_to(source)
    (config / "settings.ini").write_text(f"[Browser]\nEnabled=true\nUseCustomProxy=true\nCustomProxyLocation={BASE}/fixture-browser-proxy\n")
    cli(["db-create", "-q", "-p", str(VAULT)], MASTER + "\n" + MASTER + "\n")
    cli(["add", "-q", "-u", "monet-demo", "--url", "http://127.0.0.1:8765/", "-p",
         str(VAULT), "Local sign-in test"], MASTER + "\nMonet-demo-only-1028!\n")
    proxy = BASE / "fixture-browser-proxy"
    proxy.write_text(f'#!/bin/sh\nexec env LD_LIBRARY_PATH="{BASE}/runtime" "{BASE}/out/bin/keepassxc-proxy" "$@"\n')
    proxy.chmod(0o700)
    hosts = Path.home() / ".mozilla/native-messaging-hosts"
    hosts.mkdir(parents=True, exist_ok=True)
    with (hosts / "org.keepassxc.keepassxc_browser.json").open("x") as out:
        json.dump({"name": "org.keepassxc.keepassxc_browser", "description": "Monet disposable test",
                   "path": str(proxy), "type": "stdio",
                   "allowed_extensions": ["keepassxc-browser@keepassxc.org"]}, out)
    print("Fixture vault and browser host ready. Pairing still requires approval in Passwords.")


def launch():
    with (BASE / "app.log").open("w") as log:
        process = subprocess.Popen([str(BASE / "out/bin/monet-passwords-preview"), str(VAULT)],
                                   env=ENV, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
    (BASE / "app.pid").write_text(str(process.pid))
    print("Preview started", process.pid)


def verify_disk():
    before = VAULT.read_bytes()
    backup = VAULT.with_name("Passwords.old.kdbx")
    assert backup.is_file(), "Native encrypted backup was not created"
    for path in (VAULT, backup):
        data = path.read_bytes()
        assert all(value not in data for value in (MASTER.encode(), b"Monet-demo-only-1028!", b"monet-demo"))
        assert path.stat().st_mode & 0o077 == 0, "Vault must be private to this user"
        assert cli(["show", "-q", "-a", "Password", str(path), "Local sign-in test"], MASTER + "\n").rstrip("\n") == "Monet-demo-only-1028!"
    recovered = VAULT.with_name("Recovered.kdbx")
    with recovered.open("xb") as out:
        out.write(backup.read_bytes())
    assert cli(["show", "-q", "-a", "UserName", str(recovered), "Local sign-in test"], MASTER + "\n").strip() == "monet-demo"
    corrupted = bytearray(before)
    corrupted[len(corrupted) // 2] ^= 0x80
    damaged = VAULT.with_name("Damaged.kdbx")
    with damaged.open("xb") as out:
        out.write(corrupted)
    try:
        cli(["db-info", "-q", str(damaged)], MASTER + "\n")
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError("The damaged vault was accepted")
    assert VAULT.read_bytes() == before
    print("PASS: private encrypted vault/backup, independent recovery, and corruption rejection.")


def verify_browser_save(state):
    database = ET.fromstring(cli(["export", "-q", str(VAULT)], MASTER + "\n"))
    entries = [entry for group in database.iter("Group") for entry in group.findall("Entry")]
    def fields(entry):
        return {field.findtext("Key"): field.findtext("Value") for field in entry.findall("String")}
    saved = [entry for entry in entries if fields(entry).get("UserName") == "monet-new"]
    if state == "unsaved":
        assert not saved, "A submitted form must not be stored without approval"
        assert len(entries) == 1, "Only the original fixture account should exist"
        print("PASS: no account saved without approval.")
        return
    assert len(saved) == 1, "Browser save must create one account; update must not duplicate it"
    updated = state == "updated"
    expected = "Monet-updated-only-1028!" if updated else "Monet-new-only-1028!"
    assert fields(saved[0])["Password"] == expected
    assert fields(saved[0])["URL"].startswith("http://127.0.0.1:8765")
    if updated:
        assert any(fields(entry).get("Password") == "Monet-new-only-1028!"
                   for entry in saved[0].findall("History/Entry")), "Previous password must remain in vault history"
    print("PASS: browser " + ("update preserved history without duplicates." if updated else "save persisted in the encrypted vault."))


if __name__ == "__main__":
    os.umask(0o077)
    if sys.argv[1] == "setup":
        setup()
    elif sys.argv[1] == "launch":
        launch()
    elif sys.argv[1] == "verify-disk":
        verify_disk()
    elif sys.argv[1] in ("verify-unsaved", "verify-saved", "verify-updated"):
        verify_browser_save(sys.argv[1][7:])
