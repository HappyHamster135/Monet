"""Check the installed shortcut guard in a separate KWin session with disposable apps."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
from tools.test import private_session, stop
from wayland_pointer import Pointer


def wait(check, message):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.025)
    raise AssertionError(message)


def client(home, name):
    from PySide6.QtGui import QAction, QKeySequence
    from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit

    app = QApplication([])
    app.setDesktopFileName("org.monet." + name)
    window = QMainWindow()
    window.setWindowTitle(name)
    window.setCentralWidget(QPlainTextEdit())
    def record(action):
        with (home / "actions").open("a") as log:
            log.write(name + " " + action + "\n")
    for keys in ("Ctrl+Q", "Ctrl+W", "Ctrl+Shift+Q", "Ctrl+Shift+W", "Ctrl+J"):
        command = QAction(window)
        command.setShortcut(QKeySequence(keys))
        command.triggered.connect(lambda unused=False, value=keys: record(value))
        window.addAction(command)
    window.show()
    (home / (name + ".ready")).touch()
    app.exec()


def worker(home, platform):
    from PySide6.QtWidgets import QApplication
    from quit_protection import QuitProtection
    from tests.test_resume import r

    app = QApplication([])
    panel = QuitProtection()
    quit, close = (panel.tabs.widget(i) for i in (0, 1))
    procs = []
    def start(name):
        p = subprocess.Popen([sys.executable, __file__, "--client", name], start_new_session=True,
                             env=dict(os.environ, QT_QPA_PLATFORM=platform))
        procs.append(p)
        wait(lambda: (home / (name + ".ready")).exists(), name + " did not start")

    def focus(name):
        assert r.kwin_script("const w = windows().find(w => w.caption === '" + name +
                             "'); if (w) workspace.activeWindow = w; reply(!!w)") is True
        wait(lambda: r.kwin_script("reply(workspace.activeWindow?.caption)") == name, "Focus failed")

    keyboard = Pointer(Path(os.environ["XDG_RUNTIME_DIR"]) / "monet-guard-test", version=4)
    ctrl, shift, q, w, j = 29, 42, 16, 17, 36
    def chord(*codes, duration=.035):
        for code in codes:
            keyboard.key(code, True)
            time.sleep(.015)
        time.sleep(duration)
        for code in reversed(codes):
            keyboard.key(code, False)
            time.sleep(.015)

    def expect(*events):
        time.sleep(.1)
        log = home / "actions"
        got = log.read_text().splitlines() if log.exists() else []
        assert got == list(events), (events, got)
        log.write_text("")

    def configure():
        app.processEvents()
        time.sleep(.08)

    try:
        plugins = subprocess.check_output(["busctl", "--user", "get-property", "org.kde.KWin", "/Plugins",
                                           "org.kde.KWin.Plugins", "LoadedPlugins"], text=True)
        assert '"monet_quit_guard"' in plugins, plugins
        start("GuardOne")
        start("GuardTwo")
        wait(lambda: r.kwin_script("reply(workspace.activeWindow?.caption)") == "GuardTwo",
             "The second client did not finish mapping")
        focus("GuardOne")
        # This rule was saved before KWin started. It must already protect W.
        assert close.enable.isChecked() and not quit.enable.isChecked()
        chord(ctrl, q)
        chord(ctrl, w)
        expect("GuardOne Ctrl+Q")
        chord(ctrl, w)
        expect("GuardOne Ctrl+W")
        close.enable.setChecked(False)
        configure()
        chord(ctrl, w)
        expect("GuardOne Ctrl+W")
        quit.feedback.setChecked(False)
        quit.hold.setValue(.35)
        quit.enable.setChecked(True)
        configure()
        chord(ctrl, q)
        chord(ctrl, j)
        chord(ctrl, w)
        expect("GuardOne Ctrl+J", "GuardOne Ctrl+W")
        chord(ctrl, q, duration=.65)
        expect("GuardOne Ctrl+Q")

        # Releasing Ctrl first or switching away and back cancels a pending hold.
        keyboard.key(ctrl, True)
        keyboard.key(q, True)
        time.sleep(.08)
        keyboard.key(ctrl, False)
        time.sleep(.45)
        keyboard.key(q, False)
        expect()
        quit.hold.setValue(1.5)
        configure()
        keyboard.key(ctrl, True)
        keyboard.key(q, True)
        focus("GuardTwo")
        focus("GuardOne")
        time.sleep(1.55)
        keyboard.key(q, False)
        keyboard.key(ctrl, False)
        expect()

        quit.mode.setCurrentIndex(quit.mode.findData("twice"))
        quit.interval.setValue(.35)
        close.mode.setCurrentIndex(close.mode.findData("modifier"))
        close.feedback.setChecked(False)
        close.enable.setChecked(True)
        configure()
        chord(ctrl, q)
        time.sleep(.38)
        chord(ctrl, q)
        expect()
        chord(ctrl, q)
        expect("GuardOne Ctrl+Q")
        chord(ctrl, w)
        expect()
        chord(ctrl, shift, w)
        chord(ctrl, shift, q)
        expect("GuardOne Ctrl+W", "GuardOne Ctrl+Shift+Q")

        for extra, code in (("alt", 56), ("meta", 125)):
            close.modifier.setCurrentIndex(close.modifier.findData(extra))
            configure()
            chord(ctrl, code, w)
            expect("GuardOne Ctrl+W")

        # Exercise desktop-file matching and both list directions while running.
        quit.apps = ["org.monet.GuardOne.desktop"]
        quit.scope.setCurrentIndex(quit.scope.findData("selected"))
        configure()
        chord(ctrl, q)
        expect()
        focus("GuardTwo")
        chord(ctrl, q)
        expect("GuardTwo Ctrl+Q")
        quit.scope.setCurrentIndex(quit.scope.findData("except"))
        configure()
        chord(ctrl, q)
        expect()
        focus("GuardOne")
        chord(ctrl, q)
        expect("GuardOne Ctrl+Q")
        quit.enable.setChecked(False)
        close.enable.setChecked(False)
        configure()
        chord(ctrl, w)
        expect("GuardOne Ctrl+W")
        # Use the shipped editor for the unsaved-document flow.
        document = home / "guard-check.txt"
        document.write_text("Original")
        editor = subprocess.Popen(["kwrite", str(document)], start_new_session=True,
                                  env=dict(os.environ, QT_QPA_PLATFORM=platform))
        procs.append(editor)
        def active():
            return r.kwin_script("const w=workspace.activeWindow; reply(w ? {pid:w.pid, "
                                 "title:w.caption, transient:w.transient, id:String(w.internalId)} : {})")
        wait(lambda: "guard-check.txt" in active().get("title", ""), "KWrite did not show the document")
        window = active()
        quit.scope.setCurrentIndex(quit.scope.findData("all"))
        quit.mode.setCurrentIndex(quit.mode.findData("hold"))
        quit.hold.setValue(.35)
        quit.enable.setChecked(True)
        configure()
        time.sleep(.45)
        chord(30)  # The letter A in the private fixture's default keyboard layout.
        chord(ctrl, q)
        time.sleep(.15)
        assert active().get("id") == window["id"], active()
        chord(ctrl, q, duration=.55)
        wait(lambda: active().get("transient") and active().get("pid") == window["pid"],
             "KWrite did not show its unsaved-changes dialog")
        chord(1)  # Escape cancels KWrite's dialog.
        wait(lambda: active().get("id") == window["id"], "Cancel did not return to the editor")
        chord(ctrl, 31)  # Ctrl+S saves the edited document.
        wait(lambda: document.read_text().rstrip("\n") in ("aOriginal", "Originala"), "KWrite did not keep the edit")
        chord(ctrl, q, duration=.55)
        wait(lambda: not r.kwin_script("reply(windows().some(w => w.pid === " + str(window["pid"]) + "))"),
             "Confirmed quit did not close the saved document")
        print(platform, "confirmed both shortcut rules, focus cancellation, per-app scope and KWrite save/cancel",
              flush=True)
        (home / "passed").touch()
    finally:
        for p in reversed(procs):
            stop(p)


def run(platform, plugin):
    with private_session() as env:
        home = Path(env["HOME"])
        prefs = Path(env["XDG_CONFIG_HOME"]) / "Monet"
        prefs.mkdir()
        (prefs / "QuitProtection.conf").write_text("[close]\nenabled=true\nmode=twice\ndoubleMs=1000\nfeedback=false\n")
        binary = home / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        env.update(WAYLAND_DISPLAY="monet-guard-test", XDG_SESSION_TYPE="wayland",
                   XDG_CURRENT_DESKTOP="KDE", QT_QPA_PLATFORM="wayland",
                   LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1")
        if plugin:
            dest = home / "plugins/kwin/plugins"
            dest.mkdir(parents=True)
            shutil.copyfile(plugin, dest / "monet_quit_guard.so")
            env["QT_PLUGIN_PATH"] = str(dest.parents[1])
        session = home / "session.sh"
        session.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, __file__, "--worker", platform]) + "\n")
        session.chmod(0o700)
        server = subprocess.Popen([binary, "--virtual", "--width", "900", "--height", "600", "--xwayland",
                                   "--no-lockscreen", "--no-kactivities", "--socket", env["WAYLAND_DISPLAY"],
                                   "--exit-with-session", session], env=env, start_new_session=True)
        try:
            server.wait(timeout=55)
            assert (home / "passed").exists(), "Private quit protection check failed for " + platform
        finally:
            stop(server)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["wayland", "xcb"], default="wayland")
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--client")
    parser.add_argument("--worker")
    opts = parser.parse_args()
    if opts.client:
        client(Path.home(), opts.client)
    elif opts.worker:
        worker(Path.home(), opts.worker)
    else:
        run(opts.platform, opts.plugin)
