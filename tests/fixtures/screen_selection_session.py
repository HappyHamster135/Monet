"""Run screen-selection tests in a private compositor and session bus."""
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from tools.test import private_session, stop


def run_selection_test(fixture, installed, display):
    with private_session() as env:
        home = Path(env["HOME"])
        binary = home / "kwin_wayland"
        shutil.copy2(shutil.which("kwin_wayland"), binary)
        binary.chmod(0o700)
        env.update(WAYLAND_DISPLAY=display, QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland",
                   XDG_CURRENT_DESKTOP="KDE", XDG_CONFIG_DIRS=str(home / "config-dirs"),
                   PLASMA_SESSION_GUI_TEST="1", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="1")
        session = home / "session.sh"
        args = [sys.executable, str(fixture.resolve()), "--worker"]
        if installed:
            args.append("--installed")
        session.write_text("#!/bin/sh\nexec " + shlex.join(args) + "\n")
        session.chmod(0o700)
        server = subprocess.Popen([binary, "--virtual", "--width", "900", "--height", "560", "--no-lockscreen",
                                   "--no-kactivities", "--socket", env["WAYLAND_DISPLAY"],
                                   "--exit-with-session", session], env=env, start_new_session=True)
        try:
            server.wait(timeout=60)
            assert (home / "passed").is_file()
        finally:
            stop(server)
