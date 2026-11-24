"""BlueZ and login1 on a disposable bus for the sleep/wake regression."""
import os
import sys
from pathlib import Path

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

runtime = Path(os.environ["XDG_RUNTIME_DIR"])
assert runtime.parent.name.startswith("monet-tests-")
assert os.environ["DBUS_SESSION_BUS_ADDRESS"].startswith("unix:path=" + str(runtime / "bus"))
DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
bluez = dbus.service.BusName("org.bluez", bus)
login = dbus.service.BusName("org.freedesktop.login1", bus)
log = Path(sys.argv[1])
PROPS = "org.freedesktop.DBus.Properties"
MANAGER = "org.freedesktop.login1.Manager"
ADAPTER = "org.bluez.Adapter1"
DEVICE = "org.bluez.Device1"
ROOT = "/org/freedesktop/login1"
SEAT = ROOT + "/seat/seat0"
SESSION = ROOT + "/session/s1"
CONTROL = "org.monet.Test"
objects = {}
nodes = []
asleep = False
active = True
pipes = []


def record(event):
    with log.open("a") as out:
        print(event, file=out, flush=True)


class Login(dbus.service.Object):
    @dbus.service.method(MANAGER, in_signature="s", out_signature="o")
    def GetSeat(self, name):
        assert name == "seat0"
        return SEAT

    @dbus.service.method(MANAGER, in_signature="ssss", out_signature="h")
    def Inhibit(self, what, who, why, how):
        assert (what, how) == ("sleep", "delay")
        reader, writer = os.pipe2(os.O_NONBLOCK)
        pipes.append(reader)
        handle = dbus.types.UnixFd(writer)
        os.close(writer)
        record("inhibit")
        return handle

    @dbus.service.method(PROPS, in_signature="ss", out_signature="v")
    def Get(self, iface, key):
        assert (iface, key) == (MANAGER, "PreparingForSleep")
        return dbus.Boolean(asleep)

    @dbus.service.signal(MANAGER, signature="b")
    def PrepareForSleep(self, sleeping):
        pass

    @dbus.service.method(CONTROL, in_signature="s", out_signature="s")
    def Action(self, action):
        global asleep, active
        if action in ("sleep", "wake"):
            asleep = action == "sleep"
            self.PrepareForSleep(asleep)
        elif action == "released":
            try:
                return "yes" if not os.read(pipes[-1], 1) else "no"
            except BlockingIOError:
                return "no"
        elif action == "replug":
            for node in nodes:
                node.remove_from_connection()
            nodes.clear()
            objects.clear()
            setup_adapters("hci13", False)
        elif action == "background":
            active = False
        else:
            raise ValueError(action)
        return "ok"


class Seat(dbus.service.Object):
    @dbus.service.method(PROPS, in_signature="ss", out_signature="v")
    def Get(self, iface, key):
        assert key == "ActiveSession"
        return dbus.Struct(("s1", dbus.ObjectPath(SESSION)), signature="so")


class Session(dbus.service.Object):
    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        return {"User": dbus.Struct((dbus.UInt32(os.getuid()), dbus.ObjectPath("/u")), signature="uo"),
                "Type": "wayland", "Active": dbus.Boolean(active), "Remote": dbus.Boolean(False)}


class Manager(dbus.service.Object):
    @dbus.service.method("org.freedesktop.DBus.ObjectManager", out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        return objects


class Adapter(dbus.service.Object):
    def __init__(self, path, address, powered):
        super().__init__(bluez, path)
        self.path = path
        self.props = {"Address": address, "Powered": dbus.Boolean(powered)}
        objects[path] = {ADAPTER: self.props}

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        assert iface == ADAPTER
        return self.props

    @dbus.service.method(PROPS, in_signature="ssv")
    def Set(self, iface, key, value):
        assert (iface, key) == (ADAPTER, "Powered")
        self.props[key] = dbus.Boolean(value)
        record(f"{self.path} {int(value)}")
        if not value:
            for obj in objects.values():
                if DEVICE in obj and obj[DEVICE]["Adapter"] == self.path:
                    obj[DEVICE]["Connected"] = dbus.Boolean(False)


class Device(dbus.service.Object):
    def __init__(self, adapter, num, icon, connected):
        path = adapter + f"/dev_{num}"
        super().__init__(bluez, path)
        self.path = path
        objects[path] = {DEVICE: {"Adapter": dbus.ObjectPath(adapter), "Address": f"AA:CC:FF:00:00:0{num}",
                                 "Paired": dbus.Boolean(True), "Trusted": dbus.Boolean(True),
                                 "Blocked": dbus.Boolean(False), "Icon": icon, "Connected": dbus.Boolean(connected),
                                 "UUIDs": dbus.Array(["00001812-0000-1000-8000-00805f9b34fb"], signature="s")}}

    @dbus.service.method(DEVICE)
    def Connect(self):
        objects[self.path][DEVICE]["Connected"] = dbus.Boolean(True)
        record("connect " + self.path)


def setup_adapters(hci, powered):
    path = "/org/bluez/" + hci
    nodes.extend([Adapter(path, "00:11:22:33:44:55", powered),
                  Adapter("/org/bluez/hci17", "00:11:22:33:44:66", False),
                  Device(path, 1, "input-mouse", powered), Device(path, 2, "input-keyboard", False),
                  Device(path, 3, "audio-headset", powered)])


manager = Manager(bluez, "/")
login_manager, seat, session = Login(login, ROOT), Seat(login, SEAT), Session(login, SESSION)
setup_adapters("hci12", True)
record("ready")
GLib.MainLoop().run()
