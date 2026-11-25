"""Exercise the desktop runner against a window with a D-BusMenu export."""
import json
import os

import dbus
import dbus.service


def check_menu_search(bus, runner, other, call, config):
    assert bus.request_name("org.kde.krunner") == 1
    window = {"id": "original", "pid": os.getpid(), "title": "Document",
              "service": "org.monet.MenuFixture", "path": "/Menu"}
    menu_interface = "com.canonical.dbusmenu"
    clicks = []
    target_reads = []
    enabled = True
    shown = False

    class Compositor(dbus.service.Object):
        @dbus.service.method("org.monet.AppMenuTarget", out_signature="a{sv}")
        def target(self):
            target_reads.append(True)
            return window

    def item(number, label, children=(), **props):
        return dbus.Struct((dbus.Int32(number), dbus.Dictionary(dict(props, label=label), signature="sv"),
                            dbus.Array(children, signature="v")), signature="ia{sv}av")

    class Menu(dbus.service.Object):
        @dbus.service.method(menu_interface, in_signature="iias", out_signature="u(ia{sv}av)")
        def GetLayout(self, parent, depth, props):
            save = item(3, "_Save __copy", enabled=enabled, shortcut=[["Ctrl", "S"]])
            file_menu = item(1, "_File", [save] if shown else [], **{"children-display": "submenu"})
            hidden = item(4, "Internal", [item(5, "Save invisible")], visible=False)
            return 1, file_menu if parent == 1 else item(0, "", [file_menu, hidden, item(2, "_View", [item(6, "Save __copy")])])

        @dbus.service.method(menu_interface, in_signature="i", out_signature="b")
        def AboutToShow(self, number):
            nonlocal shown
            shown = True
            return True

        @dbus.service.method(menu_interface, in_signature="isvu")
        def Event(self, number, name, data, timestamp):
            clicks.append((int(number), str(name)))

    compositor = Compositor(dbus.service.BusName("org.kde.KWin", bus), "/MonetAppMenu")
    menu = Menu(dbus.service.BusName(window["service"], bus), window["path"])
    assert not other.Match("menu:") and not target_reads
    rows, = call(runner.Match, "tools menu: save")
    assert shown and [row[1] for row in rows] == ["Save _copy", "Save _copy"]
    assert "File · Ctrl+S" in rows[0][-1]["subtext"]
    key = rows[0][0]
    assert key != rows[1][0] and "save" not in key.casefold()
    call(other.Run, key, "")
    assert not clicks
    call(runner.Run, key, "")
    assert clicks == [(3, "clicked")]
    window["id"] = "second"
    call(runner.Run, key, "")
    window["id"] = "original"
    enabled = False
    call(runner.Run, key, "")
    enabled = True
    config.setValue("hidden", json.dumps(["command-bar"]))
    config.sync()
    assert not runner.Match("menu: file")
    call(runner.Run, key, "")
    assert clicks == [(3, "clicked")]
    menu.remove_from_connection()
    compositor.remove_from_connection()
