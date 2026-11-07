"""A private X server for driving Ark's actual password and error dialogs."""
from contextlib import contextmanager
import os
import importlib.util
from pathlib import Path
import select
import subprocess
import threading
import time
from unittest.mock import patch

from tools.test import stop


def install_archive_actions(root):
    """Use the preview plan's real file modes, including unprivileged trust."""
    spec = importlib.util.spec_from_file_location('archive_preview_modes', root/'tools/install-desktop-preview.py')
    preview = importlib.util.module_from_spec(spec); spec.loader.exec_module(preview)
    plan = preview.plan()
    data = Path(os.environ['XDG_DATA_HOME'])
    for relative in ['applications/monet-archive.desktop', 'kio/servicemenus/monet-archive-open.desktop']:
        target = data/relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((root/'linux/share'/relative).read_text().replace('@LIBEXECDIR@', str(root/'linux/libexec')))
        target.chmod(plan[target][1])


@contextmanager
def desktop():
    process = subprocess.Popen(['Xvfb', '-displayfd', '1', '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    try:
        assert select.select([process.stdout], [], [], 10)[0], 'Private X server did not start'
        display = ':' + process.stdout.readline().strip()
        with patch.dict(os.environ, DISPLAY=display, QT_QPA_PLATFORM='xcb', QT_FORCE_STDERR_LOGGING='1'):
            yield
    finally:
        stop(process); process.stdout.close()


def focus_title(window):
    """Ignore a dialog only when it vanished between X11 discovery and access."""
    title = subprocess.run(['xdotool', 'getwindowname', window], capture_output=True, text=True)
    focus = (subprocess.run(['xdotool', 'windowfocus', '--sync', window], capture_output=True, text=True)
             if title.returncode == 0 else title)
    if title.returncode or focus.returncode:
        current = subprocess.run(['xdotool', 'search', '--onlyvisible', '--class', '[Aa]rk'],
                                 capture_output=True, text=True)
        if current.returncode in (0, 1) and window not in current.stdout.splitlines():
            return None
        title.check_returncode()
        focus.check_returncode()
    return title.stdout.strip()


def run_job(queue, token, respond=None, timeout=20, repeat=False):
    """Return dialog titles; leave the queue and native worker in a terminal state."""
    worker = threading.Thread(target=queue.run, args=(token,), kwargs={'reveal': False}, daemon=True)
    worker.start()
    seen = {}; titles = []
    try:
        deadline = time.monotonic() + timeout
        while worker.is_alive() and time.monotonic() < deadline:
            if respond:
                windows = subprocess.run(['xdotool', 'search', '--onlyvisible', '--class', '[Aa]rk'],
                    capture_output=True, text=True)
                for window in windows.stdout.splitlines():
                    if window in seen and (not repeat or time.monotonic() - seen[window] < .75): continue
                    title = focus_title(window)
                    if title is None: continue
                    seen[window] = time.monotonic()
                    titles.append(title)
                    respond(window, title)
            worker.join(.05)
        assert not worker.is_alive(), ('Ark did not finish', titles, queue.read(token))
        return titles
    finally:
        if worker.is_alive():
            queue.control(token, 'cancel')
            worker.join(5)
        assert not worker.is_alive(), 'Native extraction worker did not stop'


def key(window, value):
    # Use the focused private X server. A key press can close the dialog before
    # key release; sending both to its old window ID would report BadWindow.
    subprocess.run(['xdotool', 'key', '--clearmodifiers', value], check=True)


def run_dialog(dialog, respond, timeout=20):
    """Drive the real extractor UI while the parent Qt dialog stays responsive."""
    from PySide6.QtCore import QProcess
    from PySide6.QtTest import QTest
    worker=dialog.findChild(QProcess,'archiveExtractor')
    deadline=time.monotonic()+timeout;seen=set();titles=[]
    try:
        while worker.state()!=QProcess.NotRunning and time.monotonic()<deadline:
            windows=subprocess.run(['xdotool','search','--onlyvisible','--class','[Aa]rk'],capture_output=True,text=True)
            for window in windows.stdout.splitlines():
                if window in seen:continue
                title=focus_title(window)
                if title is None:continue
                seen.add(window);titles.append(title)
                respond(window,title)
            QTest.qWait(20)
        assert worker.state()==QProcess.NotRunning, ('Extractor dialog did not finish',titles)
        return titles
    finally:
        if worker.state()!=QProcess.NotRunning:
            dialog.reject()
            for _ in range(100):
                if worker.state()==QProcess.NotRunning:break
                QTest.qWait(20)


def text(value):
    subprocess.run(['xdotool', 'type', '--clearmodifiers', '--delay', '10', '--', value], check=True)
