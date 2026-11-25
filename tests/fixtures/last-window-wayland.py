"""Exercise the last-window preference, compositor and quit actions on a private display."""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop

APP = "org.monet.CloseFixture"
SCRIPT = "monet-quit-on-close"


def client(media=False):
    from PySide6.QtCore import ClassInfo, QObject, Property, QTimer, Slot
    from PySide6.QtDBus import QDBusConnection
    from PySide6.QtWidgets import QApplication, QDialog, QWidget
    app = QApplication([])
    ident = "org.monet.MediaCloseFixture" if media else APP
    app.setDesktopFileName(ident)
    app.setQuitOnLastWindowClosed(False)
    windows = []
    def opened(title, dialog=False):
        w = QDialog(next(w for w in windows if w.isVisible())) if dialog else QWidget()
        w.setWindowTitle(title)
        w.resize(270, 180)
        windows.append(w)
        w.show()
    @ClassInfo(**{"D-Bus Interface": "org.monet.FixtureControl"})
    class Control(QObject):
        @Slot(str)
        def Open(self, title):
            opened(title)
        @Slot()
        def Dialog(self):
            opened("Save dialog", True)
        @Slot()
        def BackgroundDialog(self):
            dialog = QDialog()
            dialog.setWindowTitle("Background work")
            windows.append(dialog)
            dialog.show()
    @ClassInfo(**{"D-Bus Interface": "org.qtproject.Qt.QCoreApplication"})
    class Application(QObject):
        @Slot()
        def quit(self):
            declined = (Path.home() / "decline").exists()
            with (Path.home() / "quit-requests").open("a") as log:
                log.write("quit\n")
            # Model an app which may ask the user about background work.
            if not declined:
                QTimer.singleShot(0, app.quit)
    @ClassInfo(**{"D-Bus Interface": "org.mpris.MediaPlayer2"})
    class Player(QObject):
        @Property(bool, constant=True)
        def CanQuit(self):
            return True
        @Slot()
        def Quit(self):
            QTimer.singleShot(0, app.quit)
    appbus = QDBusConnection.sessionBus()
    control, application = Control(), Application()
    assert appbus.registerObject("/fixture", control, QDBusConnection.ExportAllSlots)
    if media:
        player = Player()
        assert appbus.registerObject("/org/mpris/MediaPlayer2", player, QDBusConnection.ExportAllContents)
        assert appbus.registerService("org.mpris.MediaPlayer2.CloseTestPlayer")
    else:
        assert appbus.registerObject("/MainApplication", application, QDBusConnection.ExportAllSlots)
    assert appbus.registerService(ident)
    opened("Music player" if media else "First")
    sys.exit(app.exec())


def tray_menu(app):
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    watcher = "org.kde.StatusNotifierWatcher"
    menu = "com.canonical.dbusmenu"
    name = dbus.service.BusName(watcher, bus)
    class Watcher(dbus.service.Object):
        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
        def Get(self, interface, prop):
            assert interface == watcher and prop == "RegisteredStatusNotifierItems"
            return dbus.Array([bus.get_unique_name() + "/StatusNotifierItem"], signature="s")
    class Item(dbus.service.Object):
        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
        def Get(self, interface, prop):
            assert interface == "org.kde.StatusNotifierItem" and prop == "Menu"
            return dbus.ObjectPath("/Menu")
    class Menu(dbus.service.Object):
        @dbus.service.method(menu, in_signature="iias", out_signature="u(ia{sv}av)")
        def GetLayout(self, parent, depth, properties):
            assert parent == 0
            child = dbus.Struct((9, {"label": "Avsluta", "icon-name": "application-exit"},
                                 dbus.Array([], signature="v")), signature="ia{sv}av", variant_level=1)
            return 1, (0, {}, [child])
        @dbus.service.method(menu, in_signature="isvu", out_signature="")
        def Event(self, number, event, value, stamp):
            assert number == 9 and event == "clicked"
            GLib.idle_add(app.quit)
    return name, Watcher(bus, "/StatusNotifierWatcher"), Item(bus, "/StatusNotifierItem"), Menu(bus, "/Menu")


def gtk_client(tray=False):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, Gtk
    ident = "org.monet.TrayCloseFixture" if tray else "org.monet.GtkCloseFixture"
    gtk = Gtk.Application(application_id=ident)
    gtk.hold()
    action = Gio.SimpleAction.new("quit", None)
    action.connect("activate", lambda *_: gtk.quit())
    if tray:
        service = tray_menu(gtk)
    else:
        gtk.add_action(action)
    def activate(app):
        w = Gtk.ApplicationWindow(application=app, title="Tray background app" if tray else "GTK background app")
        w.set_default_size(300, 200)
        w.present()
    gtk.connect("activate", activate)
    sys.exit(gtk.run([]))


def worker(native, installed):
    import dbus
    import dbus.service
    from PySide6.QtWidgets import QApplication
    from quit_on_close import QuitOnClose
    from tests.test_resume import r
    assert os.environ["WAYLAND_DISPLAY"] == "last-window-test"
    assert os.environ["XDG_RUNTIME_DIR"].startswith("/tmp/monet-tests-")
    app = QApplication([])
    bus = dbus.SessionBus()
    panel = QuitOnClose()
    log = Path.home() / "quit-requests"
    processes = []
    def launch(*args):
        p = subprocess.Popen(args, start_new_session=True)
        processes.append(p)
        return p
    def wait(predicate, message):
        until = time.monotonic() + 7
        while time.monotonic() < until:
            app.processEvents()
            if predicate():
                return
            time.sleep(.04)
        raise AssertionError(message)
    def has(title):
        return r.kwin_script("reply(workspace.stackingOrder.some(w=>!w.deleted && w.caption===" + json.dumps(title) + "))")
    def act(title, action):
        assert r.kwin_script("const w=workspace.stackingOrder.find(w=>!w.deleted && w.caption===" + json.dumps(title) + "); if(w){" + action + ";} reply(!!w)")
    def close(title):
        act(title, "w.closeWindow()")
        wait(lambda: not has(title), "Window did not close: " + title)
    def quiet():
        time.sleep(.85)
        assert not log.exists() and app_proc.poll() is None, "Unexpected application quit"
    def script_loaded():
        obj = bus.get_object("org.kde.KWin", "/Scripting", introspect=False)
        return obj.isScriptLoaded(SCRIPT, dbus_interface="org.kde.kwin.Scripting")
    def controller():
        return dbus.Interface(bus.get_object(APP, "/fixture", introspect=False), "org.monet.FixtureControl")
    try:
        saved = os.environ.get("MONET_CLOSE_SAVED_TEST") == "1"
        assert bool(script_loaded()) == saved and not bus.name_has_owner("org.monet.QuitOnClose")
        app_proc = launch(sys.executable, __file__, "--client")
        wait(lambda: has("First"), "First window")
        close("First")
        if saved:
            wait(lambda: app_proc.poll() == 0, "Saved preference after compositor startup")
            assert log.read_text() == "quit\n"
            print("Verified saved quit rule at desktop startup.", flush=True)
            (Path.home() / "passed").touch()
            return
        quiet()
        panel.set_apps([APP + ".desktop"])
        assert script_loaded(), panel.status.text()
        control = controller()
        control.Open("Second")
        control.Open("Third")
        wait(lambda: has("Second") and has("Third"), "Two windows")
        control.Dialog()
        wait(lambda: has("Save dialog"), "Transient dialog")
        close("Save dialog")
        act("Third", "w.minimized=true")
        # Minimized and off-workspace windows both prevent a quit.
        assert r.kwin_script("workspace.createDesktop(1,'Second desktop'); reply(true)")
        act("Third", "w.desktops=[workspace.desktops[1]]")
        close("Second")
        quiet()
        act("Third", "w.desktops=[workspace.desktops[0]]")
        act("Third", "w.minimized=false")
        close("Third")
        control.Open("Reopened")
        wait(lambda: has("Reopened"), "Replacement window")
        quiet()
        shutdown = dbus.service.BusName("org.kde.Shutdown", bus)
        close("Reopened")
        quiet()
        del shutdown
        control.Open("After logout cancelled")
        wait(lambda: has("After logout cancelled"), "After cancelled logout")
        flag = Path.home() / "decline"
        flag.touch()
        close("After logout cancelled")
        wait(lambda: log.exists(), "App did not receive its own Quit action")
        assert app_proc.poll() is None and log.read_text() == "quit\n"
        flag.unlink()
        control.Open("After cancellation")
        wait(lambda: has("After cancellation"), "App ignored its quit request")
        control.BackgroundDialog()
        wait(lambda: has("Background work"), "Background dialog")
        close("After cancellation")
        time.sleep(.7)
        assert app_proc.poll() is None and log.read_text() == "quit\n"
        backend = dbus.Interface(bus.get_object("org.monet.QuitOnClose", "/org/monet/QuitOnClose"), "org.monet.QuitOnClose")
        assert backend.Prepare(APP + ".desktop", str(app_proc.pid), str(round(time.time()*1000))) == ""
        close("Background work")
        wait(lambda: app_proc.poll() == 0, "Graceful exit")
        assert log.read_text() == "quit\nquit\n"
        player_proc = launch(sys.executable, __file__, "--media-player")
        wait(lambda: has("Music player"), "Media window")
        panel.set_apps(["org.monet.MediaCloseFixture.desktop"])
        close("Music player")
        wait(lambda: player_proc.poll() == 0, "MPRIS player quit")
        gtk = launch(sys.executable, __file__, "--gtk")
        wait(lambda: has("GTK background app"), "GTK window")
        close("GTK background app")
        time.sleep(.7)
        assert gtk.poll() is None, "An unselected app was closed"
        launch(sys.executable, __file__, "--gtk")
        wait(lambda: has("GTK background app"), "GTK reopened")
        panel.set_apps(["org.monet.GtkCloseFixture.desktop"])
        close("GTK background app")
        wait(lambda: gtk.poll() == 0, "GTK quit action")
        tray = launch(sys.executable, __file__, "--tray")
        wait(lambda: has("Tray background app"), "Tray application")
        panel.set_apps(["org.monet.TrayCloseFixture.desktop"])
        close("Tray background app")
        wait(lambda: tray.poll() == 0, "Localized tray menu Quit")
        if native:
            native_id = "org.monet.NativeCloseFixture.desktop"
            panel.set_apps([native_id])
            child = launch("env", "QT_QPA_PLATFORM=" + os.environ["MONET_CLOSE_CLIENT_PLATFORM"], native)
            wait(lambda: has("Native background app"), "Native window")
            close("Native background app")
            time.sleep(.85)
            assert child.poll() is None, "An app without a Quit action was terminated by default"
            # The fixture opens another window on SIGUSR1.
            import signal
            child.send_signal(signal.SIGUSR1)
            wait(lambda: has("Native background app"), "Native window reopened")
            panel.fallback.setChecked(True)
            close("Native background app")
            wait(lambda: child.poll() == -signal.SIGTERM, "Opted-in native termination")
        panel.set_apps([])
        assert not script_loaded(), panel.status.text()
        if installed:
            subprocess.run(["/usr/libexec/monet-quick","utilities","quit-on-close"], check=True, timeout=8)
            wait(lambda: has("Quit on last window"), "Installed Utilities entry")
            close("Quit on last window")
        print("Verified last-window rules, cancellation, native app quit and preference activation.", flush=True)
        (Path.home() / "passed").touch()
    finally:
        for proc in processes:
            stop(proc)


def run(native, installed, platform, saved):
    import dbus
    with private_session() as env:
        home = Path(env["HOME"])
        data = Path(env["XDG_DATA_HOME"])
        share = Path("/usr/share") if installed else ROOT / "linux/share"
        utils = share / "monet/utilities"
        env.update(WAYLAND_DISPLAY="last-window-test", QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland",
                   XDG_CURRENT_DESKTOP="KDE", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1",
                   PYTHONPATH=str(utils), GSETTINGS_BACKEND="memory", GTK_A11Y="none", MONET_CLOSE_CLIENT_PLATFORM=platform)
        env["DBUS_SYSTEM_BUS_ADDRESS"] = env["DBUS_SESSION_BUS_ADDRESS"]
        if saved:
            from PySide6.QtCore import QSettings
            cfgdir = Path(env["XDG_CONFIG_HOME"])
            conf = QSettings(str(cfgdir / "monet/quit-on-close.conf"), QSettings.IniFormat)
            conf.setValue("applications", json.dumps({APP + ".desktop": []}))
            conf.sync()
            (cfgdir / "kwinrc").write_text("[Plugins]\nmonet-quit-on-closeEnabled=true\n")
            env["MONET_CLOSE_SAVED_TEST"] = "1"
        if not installed:
            shutil.copytree(share/"kwin/scripts"/SCRIPT, data/"kwin/scripts"/SCRIPT)
        apps = data / "applications"
        apps.mkdir()
        def entry(ident, exe):
            (apps / (ident + ".desktop")).write_text("[Desktop Entry]\nType=Application\nName=Fixture\nExec=" + exe + "\n")
        entry(APP, sys.executable)
        entry("org.monet.MediaCloseFixture", sys.executable)
        entry("org.monet.GtkCloseFixture", sys.executable)
        entry("org.monet.TrayCloseFixture", sys.executable)
        if native:
            entry("org.monet.NativeCloseFixture", native)
        services = home / "services"
        services.mkdir()
        filename = "org.monet.QuitOnClose.service"
        descriptor = (share/"dbus-1/services"/filename).read_text().replace("@DATADIR@", str(share))
        (services/filename).write_text(descriptor)
        config = home.parent / "bus.conf"
        config.write_text(config.read_text().replace("</busconfig>", "<servicedir>" + str(services) + "</servicedir></busconfig>"))
        bus = dbus.bus.BusConnection(env["DBUS_SESSION_BUS_ADDRESS"])
        daemon = dbus.Interface(bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"), "org.freedesktop.DBus")
        daemon.UpdateActivationEnvironment({"DBUS_SYSTEM_BUS_ADDRESS": env["DBUS_SYSTEM_BUS_ADDRESS"]})
        daemon.ReloadConfig()
        binary = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        script = home / "session.sh"
        cmd = [sys.executable, __file__, "--worker"]
        if native:
            cmd.extend(["--native", native])
        if installed:
            cmd.append("--installed")
        script.write_text("#!/bin/sh\nexec " + shlex.join(cmd) + "\n")
        script.chmod(0o700)
        server = subprocess.Popen([binary, "--virtual", "--xwayland", "--no-lockscreen", "--no-kactivities",
                                   "--socket", env["WAYLAND_DISPLAY"], "--exit-with-session", script], env=env, start_new_session=True)
        try:
            server.wait(timeout=95)
            assert (home / "passed").exists(), "Private desktop test failed"
        finally:
            stop(server)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved", action="store_true")
    parser.add_argument("--media-player", action="store_true")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--gtk", action="store_true")
    parser.add_argument("--client", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--platform", choices=("wayland","xcb"), default="wayland")
    parser.add_argument("--native", help="Path to the compiled last-window native fixture")
    args = parser.parse_args()
    if args.client or args.media_player:
        os.environ["QT_QPA_PLATFORM"] = os.environ["MONET_CLOSE_CLIENT_PLATFORM"]
        client(args.media_player)
    elif args.gtk or args.tray:
        gtk_client(args.tray)
    elif args.worker:
        worker(args.native, args.installed)
    else:
        run(args.native, args.installed, args.platform, args.saved)
