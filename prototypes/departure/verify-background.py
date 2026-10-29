"""VM-only live Store-service/inhibitor test; never invokes a real restart helper."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / 'linux/libexec' / name))
    value = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(value)
    return value


jobs = module('monet-store-jobs')
queue = jobs.Queue()
APP = {'id': 'org.monet.BackgroundFixture', 'name': 'Background fixture',
       'ref': 'app/org.monet.BackgroundFixture/x86_64/stable'}


def execute(job, progress, cancelled):
    (queue.folder / 'worker-pid').write_text(str(os.getpid()))
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if cancelled():
            return {'cancelled': True}
        if (queue.folder / 'finish').exists():
            return {'ok': True}
        time.sleep(.05)
    return {'error': 'fixture-timeout'}


if sys.argv[1:] == ['--worker']:
    queue.run(execute)
    raise SystemExit(0)

from PySide6.QtCore import QProcess, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout

leave = module('monet-leave')
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
output = Path(sys.argv[1]).resolve()
output.mkdir(parents=True)
assert queue.folder.resolve().is_relative_to(output), 'Use an isolated XDG_STATE_HOME under the output folder'
unit = None


def wait(check):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        QTest.qWait(50)
        if check():
            return
    raise AssertionError('Live background-work fixture did not settle')


def inhibitors():
    return json.loads(subprocess.check_output(['busctl', '--system', '--json=short', 'call',
        'org.freedesktop.login1', '/org/freedesktop/login1', 'org.freedesktop.login1.Manager',
        'ListInhibitors'], text=True, timeout=3))['data'][0]


def own_inhibitors():
    found = []
    for row in inhibitors():
        try:
            if unit in Path(f'/proc/{row[5]}/cgroup').read_text():
                found.append(row)
        except FileNotFoundError:
            pass
    return found


def start():
    global unit
    for name in ('finish', 'worker-pid'):
        (queue.folder / name).unlink(missing_ok=True)
    queue.submit(APP, 'install')
    jobs.start_worker(__file__)
    wait(lambda: (queue.folder / 'worker-pid').exists())
    pid = int((queue.folder / 'worker-pid').read_text())
    assert str(Path(__file__).resolve()).encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
    match = re.search(r'/(monet-store-downloads-[0-9a-f]{32}\.service)(?:/|\n|$)', Path(f'/proc/{pid}/cgroup').read_text())
    assert match
    unit = match[1]
    wait(lambda: bool(own_inhibitors()))
    assert all(row[0] == 'shutdown' and row[3] == 'block' for row in own_inhibitors())


gate = output / 'restart-stub.py'
gate.write_text("import sys\nfrom pathlib import Path\nprint('MONET-SWITCH-READY', flush=True)\n"
                "answer=sys.stdin.readline()\n"
                "if answer == 'continue\\n': Path(sys.argv[1]).write_text(answer)\n"
                "sys.exit(0 if answer == 'continue\\n' else 1)\n")


class Switch(leave.Departure):
    def capture(self):
        self.phase = 'prepare'
        self.process.start(sys.executable, [str(gate), str(self.acceptance)])


def switch(name):
    companion = QDialog()
    companion.setWindowTitle('Untouched fixture app')
    QVBoxLayout(companion).addWidget(QLabel('This window must stay open while background work is running.'))
    companion.show()
    closes = []

    def windows(close=None):
        if close:
            assert close == 'fixture'
            closes.append(close)
            companion.close()
        return [{'id': 'fixture', 'app': 'fixture.desktop', 'closeable': True}] if companion.isVisible() else []

    resume = SimpleNamespace(EDITORS=set(), BROWSER='browser.desktop', departure_windows=windows,
                             refresh_departure=lambda *_: True)
    window = Switch(SimpleNamespace(resume_helper=lambda: resume, TRIP_APPS=output/'unused.json'), '/never/run')
    window.acceptance = output / (name + '-accepted')
    window.show()
    window.move(20, 20)
    wait(lambda: 'Waiting for background work' in window.message.text())
    for _ in range(5):
        QTest.qWait(450)
        assert companion.isVisible() and not closes and not window.acceptance.exists()
    assert app.primaryScreen().availableGeometry().contains(window.frameGeometry())
    assert window.grab().save(str(output / (name + '.png')))
    return window, companion, closes


try:
    start()
    window, companion, closes = switch('waiting')
    assert queue.read()[0]['state'] == 'running'
    (queue.folder / 'finish').touch()
    wait(lambda: window.phase == 'done')
    assert window.acceptance.read_text() == 'continue\n' and closes == ['fixture']
    assert queue.read()[0]['state'] == 'done'
    wait(lambda: not own_inhibitors())
    window.close(); companion.close()

    start()
    window, companion, closes = switch('cancelled')
    QTest.keyClick(window, Qt.Key_Escape)
    wait(lambda: window.phase == 'done')
    assert companion.isVisible() and not closes and not window.acceptance.exists()
    assert queue.read()[0]['state'] == 'running' and own_inhibitors()
    queue.change(APP['id'], 'cancel')
    wait(lambda: queue.read()[0]['state'] == 'cancelled' and not own_inhibitors())
    window.close(); companion.close()

    start()
    subprocess.run(['systemctl', '--user', 'stop', unit], check=True, timeout=10)
    wait(lambda: not own_inhibitors())
    queue.recover()
    assert queue.read()[0]['state'] == 'interrupted'
    proof = {'worker_service_inhibits_shutdown': True, 'windows_wait_untouched': True,
             'worker_completion_allows_one_acceptance': True, 'escape_preserves_worker_and_windows': True,
             'queue_cancellation_releases_inhibitor': True, 'service_loss_releases_inhibitor_and_retains_retry': True,
             'dialog_fits_screen': True, 'scale': os.environ.get('QT_SCALE_FACTOR', '1')}
    (output / 'proof.json').write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof), flush=True)
finally:
    if unit:
        subprocess.run(['systemctl', '--user', 'stop', unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
