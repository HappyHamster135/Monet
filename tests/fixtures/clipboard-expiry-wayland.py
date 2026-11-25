"""Check clipboard expiry against a private KWin, Plasma history and login1."""
import argparse
import ctypes as C
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from screen_selection_session import run_selection_test


def wait(check, label, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.04)
    raise AssertionError(label)


def exercise(installed):
    import dbus
    home = Path(os.environ["HOME"])
    assert home.parent.name.startswith("monet-tests-") and os.environ["WAYLAND_DISPLAY"] == "monet-clipboard-expiry"
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    config = Path(os.environ["XDG_CONFIG_HOME"])
    (config / "klipperrc").write_text("[General]\nNoEmptyClipboard=true\nSyncClipboards=false\nIgnoreSelection=true\n")
    (config / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "[Containments][1]\nformfactor=2\nlocation=4\nplugin=org.kde.panel\n\n"
        "[Containments][1][Applets][2]\nplugin=org.kde.plasma.systemtray\n\n[Containments][1][General]\nAppletOrder=2\n")
    modules = Path("/usr/share/monet/utilities")
    if not installed:
        modules = home / "modules"
        modules.mkdir()
        for file in ("clipboard_expiry.py", "clipboard_expiry_service.py"):
            shutil.copy2(ROOT / "linux/share/monet/utilities" / file, modules)
        library = os.getenv("MONET_TEST_CLIPBOARD_LIBRARY")
        if library:
            shutil.copy2(library, modules / "libmonetclipboard.so")
        else:
            subprocess.run(["sh", ROOT / "linux/clipboard/build.sh", modules / "libmonetclipboard.so"], check=True)
    sys.path.insert(0, str(modules))
    from clipboard_expiry import Policy, config_path, write_policy
    config_path().parent.mkdir(exist_ok=True)
    write_policy(Policy(15, lock=True, sleep=True))
    bus = dbus.SessionBus()
    children = []

    def launch(*args):
        child = subprocess.Popen(args)
        children.append(child)
        return child

    def copy(data, *args):
        subprocess.run(["wl-copy", "--type", "text/plain", *args], input=data, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)

    def paste(*args):
        return subprocess.run(["wl-paste", "-n", "--type", "text/plain", *args], capture_output=True, timeout=2).stdout

    try:
        launch("/usr/libexec/kactivitymanagerd")
        wait(lambda: bus.name_has_owner("org.kde.ActivityManager"), "ActivityManager")
        launch("plasmashell", "--no-respawn")
        wait(lambda: bus.name_has_owner("org.kde.klipper"), "Klipper")
        launch(sys.executable, ROOT / "tests/passwords_bus_fixture.py")
        log = home / "inhibitors"
        launch(sys.executable, ROOT / "tests/fixtures/bluetooth-sleep-bus.py", log)
        wait(lambda: bus.name_has_owner("org.freedesktop.login1") and
             bus.name_has_owner("org.freedesktop.ScreenSaver"), "test buses")
        screen = dbus.Interface(bus.get_object("org.freedesktop.ScreenSaver", "/ScreenSaver"), "org.monet.Test")
        login = dbus.Interface(bus.get_object("org.freedesktop.login1", "/org/freedesktop/login1"), "org.monet.Test")
        history = bus.get_object("org.kde.klipper", "/klipper").getClipboardHistoryMenu
        watcher = launch(sys.executable, modules / "clipboard_expiry_service.py")
        wait(lambda: log.exists() and "inhibit" in log.read_text(), "sleep-delay inhibitor")
        copy(b"middle click", "--primary")
        copy(b"before locking")
        wait(lambda: "before locking" in history(), "history saved")
        screen.SetActive(True)
        wait(lambda: not paste(), "clear on lock")
        screen.SetActive(False)
        copy(b"before sleeping")
        wait(lambda: "before sleeping" in history(), "second history entry")
        login.Action("sleep")
        wait(lambda: login.Action("released") == "yes", "sleep acknowledged")
        assert not paste() and paste("--primary") == b"middle click"
        assert {"before locking", "before sleeping"} <= set(history())
        login.Action("wake")
        wait(lambda: log.read_text().count("inhibit") == 2, "resume")
        # Queue a newer selection between the observer's last event and expiration.
        lib = C.CDLL(str(modules / "libmonetclipboard.so"))
        callback_type = C.CFUNCTYPE(None, C.c_int)
        callback = callback_type(lambda _: None)
        lib.clip_open_observer.argtypes = [callback_type]
        assert lib.clip_open_observer(callback) >= 0
        copy(b"new copy")
        wait(lambda: "new copy" in history(), "new selection")
        assert lib.clip_expire() == 0 and paste() == b"new copy"
        wait(lambda: not paste(), "15-second timer", seconds=17)
        write_policy(Policy())
        watcher.send_signal(signal.SIGHUP)
        wait(lambda: login.Action("released") == "yes", "disabled")
        assert not paste() and watcher.poll() is None
        copy(b"after disabling")
        assert watcher.wait(timeout=3) == 0 and paste() == b"after disabling"
        (home / "passed").touch()
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if args.worker:
        exercise(args.installed)
    else:
        run_selection_test(Path(__file__), args.installed, "monet-clipboard-expiry")
