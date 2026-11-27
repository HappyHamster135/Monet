"""Opt-in Bluetooth suspend policy for the active local desktop session."""
from contextlib import contextmanager
import fcntl
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time

UNIT = "monet-bluetooth-sleep.service"
BLUEZ = "org.bluez"
ADAPTER = BLUEZ + ".Adapter1"
DEVICE = BLUEZ + ".Device1"
PROPS = "org.freedesktop.DBus.Properties"
OBJECTS = "org.freedesktop.DBus.ObjectManager"
LOGIN = "org.freedesktop.login1"
LOGIN_PATH = "/org/freedesktop/login1"
MANAGER = LOGIN + ".Manager"
ADDRESS = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


def config_path():
    return Path(os.getenv("XDG_CONFIG_HOME") or Path.home()/".config") / "monet/bluetooth-sleep"


def pending_path():
    return Path(os.getenv("XDG_STATE_HOME") or Path.home()/".local/state") / "monet/bluetooth-restore"


def read_mode(path):
    try:
        value = path.read_text().strip()
    except FileNotFoundError:
        return "off"
    return value if value in ("restore", "stay-off") else "off"


@contextmanager
def locked(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.with_name("." + path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def store(path, value):
    if value:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
            try:
                tmp.write(value + "\n")
                tmp.flush()
                os.fsync(tmp.fileno())
                os.replace(tmp.name, path)
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            return
    directory = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_pending(path):
    try:
        return {s for s in path.read_text().splitlines() if ADDRESS.fullmatch(s)}
    except FileNotFoundError:
        return set()


def cancel_restore():
    # Serialize with a pending sleep/wake D-Bus write. The user's explicit
    # power command is issued after this returns and takes precedence.
    path = pending_path()
    if path.exists() or read_mode(config_path()) != "off":
        with locked(path):
            store(path, "")


def service(mode):
    action = "disable" if mode == "off" else "enable"
    subprocess.run(["systemctl", "--user", action, "--now", UNIT], capture_output=True, timeout=15, check=True)


def configure(path, mode):
    if mode not in ("off", "restore", "stay-off"):
        raise ValueError("Unknown sleep setting")
    with locked(path):
        old = read_mode(path)
        store(path, "" if mode == "off" else mode)
        try:
            service(mode)
        except (OSError, subprocess.SubprocessError):
            store(path, "" if old == "off" else old)
            service(old)
            raise
        if mode != "restore" and pending_path().exists():
            cancel_restore()


def rfkill_blocked(path, root=Path("/sys/class/rfkill")):
    hci = path.rsplit("/", 1)[-1]
    for entry in root.glob("rfkill*"):
        try:
            if (entry/"type").read_text().strip() != "bluetooth":
                continue
            name = (entry/"name").read_text().strip()
            if re.fullmatch(r"hci\d+", name) and name != hci:
                continue
            if any((entry/key).read_text().strip() == "1" for key in ("hard", "soft")):
                return True
        except OSError:
            continue
    return False


def address(props):
    value = str(props.get("Address", "")).upper()
    return value if ADDRESS.fullmatch(value) else ""


class SleepPolicy:
    def __init__(self, bus, pending, known_input, blocked=rfkill_blocked):
        self.bus = bus
        self.pending = pending
        self.known_input = known_input
        self.blocked = blocked
        self.inputs = {}
        self.owed = read_pending(pending)

    def remember(self, addresses):
        if self.owed != addresses:
            store(self.pending, "\n".join(sorted(addresses)))
            self.owed = set(addresses)

    def prepare(self, mode):
        if mode == "off" or not self.bus.active():
            return
        with locked(self.pending):
            self.owed = read_pending(self.pending)
            self._prepare(mode)

    def _prepare(self, mode):
        owner, objects = self.bus.objects()
        if not owner:
            return
        self.inputs.clear()
        # A fresh sleep starts with the state the user actually chose.
        self.remember(set())
        deadline = time.monotonic() + 1.5
        for path, interfaces in objects.items():
            adapter = interfaces.get(ADAPTER, {})
            ident = address(adapter)
            if not ident or not adapter.get("Powered") or time.monotonic() >= deadline:
                continue
            if mode == "restore":
                # Journal before sending: a crash or late D-Bus reply can follow the change.
                self.remember(self.owed | {ident})
                self.inputs[ident] = {address(dev) for obj in objects.values() if (dev := obj.get(DEVICE))
                                      and dev.get("Adapter") == path and dev.get("Connected") and self.known_input(dev)
                                      and address(dev)}
            result = self.bus.power(owner, path, ident, False, deadline)
            if result in ("changed", "blocked", "failed"):
                self.remember(self.owed - {ident})
                self.inputs.pop(ident, None)

    def restore(self):
        if not (self.owed or any(self.inputs.values())) or not self.bus.active():
            return
        with locked(self.pending):
            current = read_pending(self.pending)
            for ident in self.owed - current:
                self.inputs.pop(ident, None)
            self.owed = current
            if self.owed or any(self.inputs.values()):
                self._restore()

    def expire(self):
        with locked(self.pending):
            self.owed = read_pending(self.pending)
            self.remember(set())
            self.inputs.clear()

    def _restore(self):
        owner, objects = self.bus.objects()
        if not owner:
            return
        for path, interfaces in objects.items():
            adapter = interfaces.get(ADAPTER, {})
            ident = address(adapter)
            if ident not in self.owed and not self.inputs.get(ident):
                continue
            if self.blocked(path) or adapter.get("PowerState") == "off-blocked":
                self.remember(self.owed - {ident})
                self.inputs.pop(ident, None)
                continue
            if ident in self.owed:
                if not adapter.get("Powered"):
                    result = self.bus.power(owner, path, ident, True, time.monotonic() + 1)
                    if result == "blocked":
                        self.remember(self.owed - {ident})
                        self.inputs.pop(ident, None)
                    if result != "ok":
                        continue
                self.remember(self.owed - {ident})
            elif not adapter.get("Powered"):
                # A new off choice after our restore takes precedence.
                self.inputs.pop(ident, None)
                continue
            wanted = self.inputs.get(ident, set())
            for device_path, item in objects.items():
                dev = item.get(DEVICE, {})
                device = address(dev)
                if dev.get("Adapter") == path and device in wanted:
                    wanted.remove(device)
                    if self.known_input(dev) and not dev.get("Connected"):
                        self.bus.connect_input(owner, device_path)


class DesktopBus:
    def __init__(self):
        from gi.repository import Gio, GLib
        self.gio, self.glib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def call(self, service, path, iface, method, args=None, ms=450):
        return self.bus.call_sync(service, path, iface, method, args, None,
                                  self.gio.DBusCallFlags.NO_AUTO_START, ms, None).unpack()

    def active(self):
        # User managers outlive fast user switching. Only the foreground desktop
        # on the hardware seat may apply this account's setting.
        G = self.glib
        try:
            seat, = self.call(LOGIN, LOGIN_PATH, MANAGER, "GetSeat", G.Variant("(s)", ("seat0",)))
            active, = self.call(LOGIN, seat, PROPS, "Get", G.Variant("(ss)", (LOGIN+".Seat", "ActiveSession")))
            props, = self.call(LOGIN, active[1], PROPS, "GetAll", G.Variant("(s)", (LOGIN+".Session",)))
            return props.get("Active") and not props.get("Remote") and props.get("User", (-1,))[0] == os.getuid() and props.get("Type") in ("wayland", "x11")
        except G.Error:
            return False

    def objects(self):
        try:
            owner, = self.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                               "GetNameOwner", self.glib.Variant("(s)", (BLUEZ,)))
            items, = self.call(owner, "/", OBJECTS, "GetManagedObjects")
            return owner, items
        except self.glib.Error:
            return None, {}

    def power(self, owner, path, ident, on, deadline):
        G = self.glib
        try:
            state, = self.call(owner, path, PROPS, "GetAll", G.Variant("(s)", (ADAPTER,)))
            if address(state) != ident:
                return "changed"
            if state.get("Powered") == on:
                return "ok" if on else "changed"
            ms = int((deadline - time.monotonic()) * 1000)
            if ms <= 0:
                return "failed"
            self.call(owner, path, PROPS, "Set", G.Variant("(ssv)", (ADAPTER, "Powered", G.Variant("b", on))), ms)
            return "ok"
        except G.Error as error:
            name = self.gio.DBusError.get_remote_error(error) or ""
            if name.endswith(".Blocked") or "rfkill" in error.message.lower():
                return "blocked"
            # No reply is ambiguous. Keep the record in case BlueZ changed power.
            if not name or name.endswith((".NoReply", ".Timeout", ".InProgress")):
                return "pending"
            return "failed"

    def connect_input(self, owner, path):
        self.bus.call(owner, path, DEVICE, "Connect", None, None, self.gio.DBusCallFlags.NO_AUTO_START,
                      10000, None, None, None)

    def inhibit(self):
        G = self.glib
        reply, files = self.bus.call_with_unix_fd_list_sync(LOGIN, LOGIN_PATH, MANAGER, "Inhibit",
            G.Variant("(ssss)", ("sleep", "Monet Bluetooth", "Apply the Bluetooth sleep setting", "delay")),
            G.VariantType.new("(h)"), self.gio.DBusCallFlags.NO_AUTO_START, 1200, None, None)
        return files.get(reply.unpack()[0])


class SleepWatcher:
    def __init__(self, desktop, policy, path):
        self.desktop, self.policy, self.path = desktop, policy, path
        self.loop = desktop.glib.MainLoop()
        self.lock_fd = None
        self.sleeping = False
        self.timer = 0
        self.until = 0
        self.failed = False

    def unlock(self):
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    def lock(self):
        if self.lock_fd is None:
            self.lock_fd = self.desktop.inhibit()

    def cancel_timer(self):
        if self.timer:
            self.desktop.glib.source_remove(self.timer)
            self.timer = 0

    def retry(self):
        self.timer = 0
        if not self.sleeping:
            try:
                self.policy.restore()
            except OSError as error:
                print("Could not update Bluetooth restore state:", error, file=sys.stderr)
            if self.policy.owed or any(self.policy.inputs.values()):
                if time.monotonic() < self.until:
                    self.timer = self.desktop.glib.timeout_add(850, self.retry)
                else:
                    # A radio attached days later must keep its owner's new choice.
                    self.policy.expire()
        return False

    def recover(self):
        self.cancel_timer()
        self.until = time.monotonic() + 10
        self.retry()

    def preparing(self, bus, sender, path, iface, name, args):
        asleep, = args.unpack()
        if asleep == self.sleeping:
            return
        self.sleeping = asleep
        if asleep:
            self.cancel_timer()
            try:
                if self.lock_fd is not None:
                    self.policy.prepare(read_mode(self.path))
            except OSError as error:
                print("Could not save Bluetooth sleep state:", error, file=sys.stderr)
            finally:
                self.unlock()
        else:
            try:
                self.lock()
            except self.desktop.glib.Error:
                self.failed = True
                self.loop.quit()
                return
            self.recover()

    def new_login_owner(self, bus, sender, path, iface, name, args):
        _, old, new = args.unpack()
        if old:
            self.unlock()
        if new:
            # Reconnect to the replacement login manager and obtain a fresh fd.
            self.failed = True
            self.loop.quit()

    def radio_added(self, bus, sender, path, iface, name, args):
        if self.sleeping or time.monotonic() >= self.until:
            return
        if not self.policy.owed and not any(self.policy.inputs.values()):
            return
        _, interfaces = args.unpack()
        if ADAPTER in interfaces or DEVICE in interfaces:
            self.cancel_timer()
            self.timer = self.desktop.glib.timeout_add(40, self.retry)

    def stop(self):
        self.unlock()
        self.loop.quit()
        return False

    def run(self):
        G, gio = self.desktop.glib, self.desktop.gio
        subscribe = self.desktop.bus.signal_subscribe
        flags = gio.DBusSignalFlags.NONE
        subscribe(LOGIN, MANAGER, "PrepareForSleep", LOGIN_PATH, None, flags, self.preparing)
        subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged", "/org/freedesktop/DBus",
                  LOGIN, flags, self.new_login_owner)
        subscribe(BLUEZ, OBJECTS, "InterfacesAdded", "/", None, flags, self.radio_added)
        G.unix_signal_add(G.PRIORITY_DEFAULT, signal.SIGTERM, self.stop)
        try:
            self.lock()
            sleeping, = self.desktop.call(LOGIN, LOGIN_PATH, PROPS, "Get", G.Variant("(ss)", (MANAGER, "PreparingForSleep")))
            self.sleeping = bool(sleeping)
            if read_mode(self.path) != "restore" and self.policy.owed:
                self.policy.expire()
            if self.sleeping:
                self.unlock()
            elif self.policy.owed:
                self.recover()
            notify = os.getenv("NOTIFY_SOCKET")
            if notify:
                with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                    sock.sendto(b"READY=1", "\0" + notify[1:] if notify.startswith("@") else notify)
            self.loop.run()
        finally:
            self.unlock()
            self.cancel_timer()
            if read_mode(self.path) == "off":
                self.policy.restore()
        return 1 if self.failed else 0


def command(args):
    path = config_path()
    try:
        if args == ["status"]:
            mode = read_mode(path)
            if mode != "off":
                result = subprocess.run(["systemctl", "--user", "is-active", "--quiet", UNIT], timeout=4)
                if result.returncode:
                    print(json.dumps(dict(ok=False, mode=mode)))
                    return 1
        elif len(args) == 1 and args[0] in ("off", "restore", "stay-off"):
            configure(path, args[0])
            mode = args[0]
        else:
            return 2
        print(json.dumps(dict(ok=True, mode=mode)))
        return 0
    except (OSError, subprocess.SubprocessError):
        try:
            mode = read_mode(path)
        except OSError:
            mode = "off"
        print(json.dumps(dict(ok=False, mode=mode)))
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "watch":
        # The boot connector knows which paired and trusted devices are input devices.
        loader = SourceFileLoader("monet_input_connect", str(Path(sys.argv[2])/"monet-input-connect"))
        module = module_from_spec(spec_from_loader(loader.name, loader))
        loader.exec_module(module)
        desktop = DesktopBus()
        watcher = SleepWatcher(desktop, SleepPolicy(desktop, pending_path(), module.known_input), config_path())
        sys.exit(watcher.run())
    sys.exit(command(sys.argv[1:]))
