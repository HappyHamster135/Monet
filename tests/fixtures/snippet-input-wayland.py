"""Exercise real text editors on a private Wayland display with a private IBus."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def editor(toolkit):
    home = Path.home()
    if toolkit == "qt":
        from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget
        from PySide6.QtCore import Qt, QTimer
        app = QApplication([])
        window = QWidget()
        box = QVBoxLayout(window)
        fields = [QLineEdit(), QLineEdit(), QPlainTextEdit()]
        if os.environ.get("MONET_FIXTURE_PRIVATE"):
            fields[1].setInputMethodHints(Qt.ImhSensitiveData)
        else:
            fields[1].setEchoMode(QLineEdit.Password)
        for field in fields:
            box.addWidget(field)
        fields[0].setFocus()
        window.show()
        timer = QTimer()
        timer.timeout.connect(lambda: snapshot(home, [fields[0].text(), fields[1].text(), fields[2].toPlainText()], [f.hasFocus() for f in fields]))
        timer.start(40)
        return app.exec()

    import gi
    gtk4 = toolkit == "gtk4"
    gi.require_version("Gtk", "4.0" if gtk4 else "3.0")
    from gi.repository import GLib, Gtk
    window = Gtk.Window()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    if gtk4:
        window.set_child(box)
    else:
        window.add(box)
    fields = [Gtk.Entry(), Gtk.Entry(), Gtk.TextView()]
    if os.environ.get("MONET_FIXTURE_PRIVATE"):
        fields[1].set_input_hints(Gtk.InputHints.PRIVATE)
    else:
        fields[1].set_visibility(False)
        fields[1].set_input_purpose(Gtk.InputPurpose.PASSWORD)
    for field in fields:
        if gtk4:
            box.append(field)
        else:
            box.add(field)
    if gtk4:
        window.present()
    else:
        window.show_all()
    fields[0].grab_focus()
    def update():
        focus = window.get_focus()
        buffer = fields[2].get_buffer()
        texts = [fields[0].get_text(), fields[1].get_text(), buffer.get_text(*buffer.get_bounds(), True)]
        return snapshot(home, texts,
                        [window.is_active() and (focus == f or bool(focus and focus.is_ancestor(f))) for f in fields])
    GLib.timeout_add(40, update)
    GLib.MainLoop().run()


def snapshot(home, texts, focus):
    name = os.environ.get("MONET_FIXTURE_ENTRY", "entry")
    temporary = home / (name + ".tmp")
    temporary.write_text(json.dumps([texts, focus]))
    temporary.replace(home / name)
    return True


def wait(check, message):
    until = time.monotonic() + 7
    while time.monotonic() < until:
        if check():
            return
        time.sleep(.05)
    raise AssertionError(message() if callable(message) else message)


def worker():
    from wayland_pointer import Pointer
    from PySide6.QtCore import QSettings
    settings = QSettings("Monet", "Utilities")
    settings.setValue("snippets", json.dumps({"Greeting": "Hello, Åsa!"}))
    settings.setValue("snippetShortcuts", json.dumps({"Greeting": "hi"}))
    settings.sync()
    def available():
        result = subprocess.run(["ibus", "list-engine", "--name-only"], capture_output=True, timeout=3)
        return b"monet-snippets" in result.stdout.split()
    wait(available, "IBus did not discover the packaged input method")
    import gi
    gi.require_version("IBus", "1.0")
    from gi.repository import IBus
    IBus.init()
    bus = IBus.Bus()
    layout_engine = "xkb:se::swe" if os.environ["XKB_DEFAULT_LAYOUT"] == "se" else "xkb:us::eng"
    wait(lambda: bus.set_global_engine(layout_engine), "IBus did not select the fixture keyboard layout")
    for _ in range(2):
        subprocess.run([sys.executable, Path(os.environ["MONET_FIXTURE_UTILITIES"]) / "snippet_input.py", "--activate"], check=True)
    saved = subprocess.check_output(["gsettings", "get", "org.freedesktop.ibus.general", "preload-engines"], text=True)
    assert saved.strip() == repr([layout_engine, "monet-snippets"]), saved
    assert bus.get_global_engine().get_name() == "monet-snippets"
    pointer = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / os.environ["WAYLAND_DISPLAY"], version=4)
    home = Path.home()
    path = home / "entry"
    def state():
        return json.loads(path.read_text()) if path.exists() else []
    def check(fields, focus):
        expected = [fields, [i == focus for i in range(3)]]
        wait(lambda: state() == expected, lambda: (expected, state()))
    def type_keys(sequence):
        for ch in sequence:
            code = {";": 39, "h": 35, "i": 23, "x": 45, " ": 57, "tab": 15, "bs": 14}[ch]
            shift = ch == ";" and os.environ["XKB_DEFAULT_LAYOUT"] == "se"
            if shift:
                code = 51
                pointer.key(42, True)
            pointer.key(code, True)
            pointer.key(code, False)
            if shift:
                pointer.key(42, False)
            if os.environ["MONET_FIXTURE_SYSTEM_KEYMAP"] == "1":
                time.sleep(.004)
    for toolkit in ("qt", "gtk"):
        path.unlink(missing_ok=True)
        client = subprocess.Popen([sys.executable, __file__, toolkit])
        try:
            check(["", "", ""], 0)
            type_keys(";hi;")
            check(["Hello, Åsa!", "", ""], 0)
            type_keys(" ;hx ")
            check(["Hello, Åsa! ;hx ", "", ""], 0)
            type_keys(["tab"])
            check(["Hello, Åsa! ;hx ", "", ""], 1)
            type_keys(";hi;")
            check(["Hello, Åsa! ;hx ", ";hi;", ""], 1)
            type_keys(["tab"])
            check(["Hello, Åsa! ;hx ", ";hi;", ""], 2)
            type_keys(";hi;")
            check(["Hello, Åsa! ;hx ", ";hi;", "Hello, Åsa!"], 2)
            type_keys([";", "h", "bs", "h", "i", ";"])
            last = "Hello, Åsa!Hello, Åsa!"
            check(["Hello, Åsa! ;hx ", ";hi;", last], 2)
            settings.setValue("hidden", '["snippets"]')
            settings.sync()
            type_keys(";hi;")
            last += ";hi;"
            check(["Hello, Åsa! ;hx ", ";hi;", last], 2)
            settings.setValue("hidden", "[]")
            settings.setValue("snippets", json.dumps({"Greeting": "Changed\nΔ"}))
            settings.sync()
            type_keys(";hi;")
            last += "Changed\nΔ"
            check(["Hello, Åsa! ;hx ", ";hi;", last], 2)
            type_keys(";h")
            time.sleep(.12)
            other_path = home / "other"
            other_path.unlink(missing_ok=True)
            other = subprocess.Popen([sys.executable, __file__, "gtk" if toolkit == "qt" else "qt"],
                                     env=dict(os.environ, MONET_FIXTURE_ENTRY="other"))
            try:
                wait(lambda: other_path.exists() and json.loads(other_path.read_text())[1][0], "New window did not focus")
                type_keys("i; ")
                wait(lambda: json.loads(other_path.read_text())[0][0] == "i; ", "Shortcut crossed between apps")
                wait(lambda: state()[0][2] == last + ";h", lambda: ("Partial shortcut on focus change", state()))
            finally:
                other.terminate()
                other.wait(timeout=3)
            settings.setValue("snippets", json.dumps({"Greeting": "Hello, Åsa!"}))
            settings.sync()
        finally:
            client.terminate()
            client.wait(timeout=3)
    # GTK's Wayland frontend forwards password/PIN purposes. The direct GTK4
    # IBus frontend also transmits its separate PRIVATE hint for visible text.
    for toolkit, options in (("qt", {"MONET_FIXTURE_PRIVATE": "1"}), ("gtk4", {}),
                             ("gtk4", {"GTK_IM_MODULE": "ibus", "MONET_FIXTURE_PRIVATE": "1"})):
        path.unlink(missing_ok=True)
        client = subprocess.Popen([sys.executable, __file__, toolkit], env=dict(os.environ, **options))
        try:
            check(["", "", ""], 0)
            type_keys(["tab"])
            check(["", "", ""], 1)
            type_keys(";hi;")
            check(["", ";hi;", ""], 1)
        finally:
            client.terminate()
            client.wait(timeout=3)
    print("Verified Qt and GTK expansion, password and private fields, live edits, backspace, literal typing and focus changes.", flush=True)
    (home / "passed").touch()


def run(installed, layout, use_system):
    with private_session() as env:
        home = Path(env["HOME"])
        binary = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        env.update(WAYLAND_DISPLAY="monet-snippets-test", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="KDE",
                   QT_QPA_PLATFORM="wayland", GDK_BACKEND="wayland", IBUS_USE_PORTAL="0",
                   GSETTINGS_BACKEND="keyfile", LP_NUM_THREADS="1", LIBGL_ALWAYS_SOFTWARE="1")
        Path(env["XDG_CONFIG_HOME"], "kxkbrc").write_text("[Layout]\nUse=true\nLayoutList=" + layout + "\n")
        env.update(XKB_DEFAULT_LAYOUT=layout, GTK_A11Y="none", MONET_FIXTURE_SYSTEM_KEYMAP=str(int(use_system)))
        env.pop("QT_IM_MODULE", None)
        env.pop("GTK_IM_MODULE", None)
        address = "unix:path=" + env["XDG_RUNTIME_DIR"] + "/private-ibus"
        env["IBUS_ADDRESS"] = address
        if installed:
            env["MONET_FIXTURE_UTILITIES"] = "/usr/share/monet/utilities"
            env["IBUS_COMPONENT_PATH"] = "/usr/share/ibus/component"
        else:
            env["MONET_FIXTURE_UTILITIES"] = str(ROOT / "linux/share/monet/utilities")
            components = home / "component"
            components.mkdir()
            xml = (ROOT / "linux/share/ibus/component/monet-snippets.xml").read_text()
            (components / "monet-snippets.xml").write_text(xml.replace("@DATADIR@", str(ROOT / "linux/share")).replace("@LIBEXECDIR@", "/usr/libexec"))
            env["IBUS_COMPONENT_PATH"] = str(components) + ":/usr/share/ibus/component"
        # Create the test account's existing IBus layout before starting its panel.
        layout_engine = "xkb:se::swe" if layout == "se" else "xkb:us::eng"
        for key, value in (("preload-engines", repr([layout_engine])),
                           ("use-system-keyboard-layout", str(use_system).lower())):
            subprocess.run(["gsettings", "set", "org.freedesktop.ibus.general", key, value], env=env, check=True)
        session = home / "session.sh"
        session.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, __file__, "worker"]) + "\n")
        session.chmod(0o700)
        im = home / "im.sh"
        daemon_args = "--address=" + address + " --panel disable --config disable --emoji-extension disable --cache none"
        im.write_text("#!/bin/sh\nexec " + shlex.join(["/usr/libexec/ibus-ui-gtk3", "--enable-wayland-im", "--exec-daemon", "--daemon-args", daemon_args]) + "\n")
        im.chmod(0o700)
        server = subprocess.Popen([binary, "--virtual", "--width", "900", "--height", "600", "--no-lockscreen",
                                   "--no-kactivities", "--socket", env["WAYLAND_DISPLAY"], "--inputmethod", im,
                                   "--exit-with-session", session], env=env, start_new_session=True)
        try:
            server.wait(timeout=55)
            assert (home / "passed").exists(), "Private snippet input session failed"
        finally:
            stop(server)


if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1].startswith("--"):
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--installed", action="store_true")
        parser.add_argument("--layout", choices=("us", "se"), default="us")
        parser.add_argument("--system-keymap", action="store_true")
        args = parser.parse_args()
        run(args.installed, args.layout, args.system_keymap)
    elif sys.argv[1] == "worker":
        worker()
    else:
        editor(sys.argv[1])
