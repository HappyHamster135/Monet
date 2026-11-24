"""Exercise the installed KDE prompt with an empty, synthetic wallet on a private display and bus."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()
HELPER = os.environ.get("MONET_TEST_RESTORE_LAUNCH", "/usr/libexec/monet-restore-launch")
DAEMON = os.environ.get("MONET_TEST_KSECRETD", "/usr/bin/ksecretd")


def request_wallet():
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    service = dbus.Interface(bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets"),
                             "org.freedesktop.Secret.Service")
    collection = service.ReadAlias("default")
    assert collection != "/"
    _, prompt = service.Unlock(dbus.Array([collection], signature="o"))
    assert prompt != "/"
    dialog = dbus.Interface(bus.get_object("org.freedesktop.secrets", prompt), "org.freedesktop.Secret.Prompt")
    loop = GLib.MainLoop()
    dismissed = []
    def complete(cancelled, value):
        dismissed.append(bool(cancelled))
        loop.quit()
    dialog.connect_to_signal("Completed", complete)
    dialog.Prompt("")
    GLib.timeout_add(7000, lambda: (loop.quit(), False)[1])
    loop.run()
    assert dismissed == [True]


def private_session():
    import dbus
    import time
    bus = dbus.SessionBus()
    assert not bus.name_has_owner("org.freedesktop.secrets")
    data = Path(os.environ["XDG_DATA_HOME"])
    wallet = data / "kwalletd"
    wallet.mkdir(parents=True)
    # Generated with KWallet::Backend in a temporary home. Contains zero entries.
    for src in (HERE.parent / "fixtures/empty-test-wallet").iterdir():
        shutil.copyfile(src, wallet / src.name)
    server = subprocess.Popen([DAEMON])
    try:
        for _ in range(100):
            if bus.name_has_owner("org.freedesktop.secrets"):
                break
            time.sleep(.05)
        assert bus.name_has_owner("org.freedesktop.secrets")
        for restored, prompts_enabled, expect_dialog in ((True, False, False), (False, False, True), (True, True, True)):
            if prompts_enabled:
                setting = Path(os.environ["XDG_CONFIG_HOME"]) / "monet/allow-restored-wallet-prompts"
                setting.parent.mkdir(parents=True, exist_ok=True)
                setting.touch()
            command = [sys.executable, str(HERE), "request"]
            if restored:
                command = [HELPER, "--exec", *command]
            with subprocess.Popen(command) as client:
                saw_dialog = False
                deadline = time.monotonic() + 8
                while client.poll() is None and time.monotonic() < deadline:
                    windows = subprocess.run(["xdotool", "search", "--all", "--onlyvisible", "--pid", str(server.pid),
                                              "--name", "KDE Wallet Service"], capture_output=True, text=True)
                    if windows.stdout and not saw_dialog:
                        saw_dialog = True
                        subprocess.run(["xdotool", "windowfocus", "--sync", windows.stdout.splitlines()[0]], check=True)
                        subprocess.run(["xdotool", "key", "Escape"], check=True)
                    time.sleep(.04)
                assert client.wait(timeout=2) == 0 and saw_dialog == expect_dialog
    finally:
        server.terminate()
        server.wait(timeout=5)


class NativeWalletPrompts(unittest.TestCase):
    @unittest.skipUnless(Path(HELPER).is_file() and all(shutil.which(c) for c in ("xvfb-run", "xdotool", "dbus-run-session")),
                         "requires Monet's native restore launcher and a virtual X server")
    def test_prompt_depends_on_how_this_instance_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "run"
            runtime.mkdir(mode=0o700)
            env = dict(os.environ, HOME=tmp, XDG_RUNTIME_DIR=str(runtime), XDG_CONFIG_HOME=tmp + "/config",
                       XDG_DATA_HOME=tmp + "/data", XDG_CACHE_HOME=tmp + "/cache", QT_QPA_PLATFORM="xcb",
                       LC_ALL="C.UTF-8", LANGUAGE="en", MONET_WALLET_TEST_HOME=tmp)
            subprocess.run(["xvfb-run", "-a", "dbus-run-session", "--", sys.executable, str(HERE), "session"],
                           env=env, timeout=40, check=True)


if __name__ == "__main__":
    if sys.argv[1:] in (["session"], ["request"]):
        assert os.environ.get("MONET_WALLET_TEST_HOME") == os.environ["HOME"]
        assert Path(os.environ["XDG_RUNTIME_DIR"]).parent == Path(os.environ["HOME"])
        (private_session if sys.argv[1] == "session" else request_wallet)()
    else:
        unittest.main()
