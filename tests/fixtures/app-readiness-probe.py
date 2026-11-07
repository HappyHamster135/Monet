#!/usr/bin/python3
"""Observe the real Settings/Store process without adding production timers.

Both revisions run through the same Qt probe. Ready means initial data has
settled and a subsequent frame was submitted, not that remote artwork arrived.
Only helper command names/counts and exit codes are recorded, never arguments.
"""
import argparse
import json
import os
from pathlib import Path
import runpy
import resource
import subprocess
import sys
import time
import urllib.error
import urllib.request

STARTED = time.monotonic()
CPU_STARTED = time.process_time()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('app', choices=('settings', 'store'))
parser.add_argument('helper', type=Path)
args = parser.parse_args()

from PySide6.QtCore import QObject, QProcess, QTimer, Qt, Slot
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from PySide6.QtQuick import QQuickWindow

counts = {'started': 0, 'finished': 0, 'failed': 0, 'commands': {}}
process_start = QProcess.start
engine_load = QQmlApplicationEngine.load
original_run = subprocess.run
observers = []


def event(phase, **details):
    print('MONET_READINESS ' + json.dumps(dict(phase=phase, elapsed_ms=round(
        (time.monotonic() - STARTED) * 1000, 3), **details)), flush=True)


def readonly_run(command, *positional, **options):
    # A measurement must never refresh the real machine's Flatpak metadata.
    # The installed-app listing still reads the actual system installation.
    if isinstance(command, (list, tuple)) and command and Path(str(command[0])).name == 'flatpak':
        if command[1:2] != ['list']:
            event('metadata-refresh-suppressed')
            return subprocess.CompletedProcess(command, 1, stdout='', stderr='benchmark: metadata refresh disabled')
    return original_run(command, *positional, **options)


def offline(*_args, **_kwargs):
    raise urllib.error.URLError('benchmark: optional network data disabled')


def track_start(process, *positional):
    label = str(positional[1][0]) if len(positional) > 1 and positional[1] else 'unknown'
    # The first argument is an internal command, not file names/URLs/passwords.
    label = label if label.replace('-', '').isalnum() and len(label) < 48 else 'other'
    counts['started'] += 1
    counts['commands'][label] = counts['commands'].get(label, 0) + 1
    done = False

    def finished(code, *_):
        nonlocal done
        if done: return
        done = True
        counts['finished'] += 1
        if code: counts['failed'] += 1

    def failed(error):
        if error == QProcess.FailedToStart: finished(-1)

    process.finished.connect(finished)
    process.errorOccurred.connect(failed)
    return process_start(process, *positional)


class Observer(QObject):
    def __init__(self, engine, window):
        super().__init__(window)
        self.window = window
        self.first = False
        self.ready = False
        self.awaiting_ready_frame = False
        expression = ('loaded' if args.app == 'store' else
            'Object.keys(waiting).length === 0 && (typeof loadScheduled === "undefined" || !loadScheduled)')
        self.expression = QQmlExpression(engine.rootContext(), window, expression, self)
        self.expression.setNotifyOnValueChanged(True)
        self.expression.valueChanged.connect(self.check)
        window.frameSwapped.connect(self.frame, Qt.QueuedConnection)
        self.timer = QTimer(self); self.timer.setInterval(10); self.timer.timeout.connect(self.check)
        self.timer.start()
        event('window-created')

    @Slot()
    def frame(self):
        if not self.first:
            self.first = True
            event('first-frame')
        if self.awaiting_ready_frame:
            self.awaiting_ready_frame = False
            self.timer.stop()
            event('ready-frame', helpers=dict(counts), process_cpu_ms=round(
                1000 * (time.process_time() - CPU_STARTED), 3), peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            if os.environ.get('MONET_READINESS_CAPTURE'):
                try:
                    event('capture-complete', ok=self.window.grabWindow().save(os.environ['MONET_READINESS_CAPTURE']))
                except (AttributeError, RuntimeError) as error:
                    event('capture-complete', ok=False, message=str(error))

    @Slot()
    def check(self):
        if self.ready: return
        result, undefined = self.expression.evaluate()
        if self.expression.hasError():
            event('probe-error', message=self.expression.error().description()); self.timer.stop(); return
        settled = bool(result) and not undefined
        if args.app == 'settings':
            settled = settled and self.first and counts['commands'].get('status', 0) > 0 and counts['started'] == counts['finished']
        if settled:
            self.ready = True
            self.awaiting_ready_frame = True
            event('initial-data-settled', helpers=dict(counts))
            self.window.update()


def observe_load(engine, *positional, **options):
    result = engine_load(engine, *positional, **options)
    for window in engine.rootObjects():
        if hasattr(window, 'frameSwapped'):
            observers.append(Observer(engine, window))
    return result


subprocess.run = readonly_run
urllib.request.urlopen = offline
QProcess.start = track_start
QQmlApplicationEngine.load = observe_load
sys.argv = [str(args.helper), *(['power'] if args.app == 'settings' else [])]
sys.path.insert(0, str(args.helper.parent))
event('probe-ready')
runpy.run_path(str(args.helper), run_name='__main__')
