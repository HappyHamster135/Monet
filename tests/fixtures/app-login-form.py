#!/usr/bin/python3
"""Synthetic native login forms; used only inside an isolated X server/session bus."""
import os
from pathlib import Path
import subprocess
import sys

assert os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
mode = sys.argv[2]

if sys.argv[1] == 'observe':
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GLib
    from app_detector import Detector
    seen = []
    def offer(identity, values):
        assert identity.name == 'app-login-form'
        assert values['username'] == 'demo@example.invalid'
        assert values['password'] == ''  # Qt correctly conceals the real value.
        assert values['kind'] == (mode if mode in ('register', 'change') else 'login')
        seen.append(True)
    detector = Detector(Atspi, GLib, offer, lambda _: True)
    detector.start()
    form = subprocess.Popen([sys.executable, __file__, 'form', mode])
    def finished():
        if form.poll() is not None:
            Atspi.event_quit(); return False
        return True
    GLib.timeout_add(100, finished)
    GLib.timeout_add_seconds(8, lambda: (Atspi.event_quit(), False)[1])
    Atspi.event_main(); detector.clear()
    if form.poll() is None: form.kill()
    assert form.wait() == 0
    assert len(seen) == (0 if mode in ('cancel', 'close') else 1), 'Unexpected number of native offers'
    print('PASS: ' + mode)
else:
    from PySide6.QtWidgets import QApplication, QWidget, QFormLayout, QLineEdit, QPushButton
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    app = QApplication([]); window = QWidget(); window.setWindowTitle('Synthetic account')
    form = QFormLayout(window)
    username = QLineEdit('demo@example.invalid'); form.addRow('Email', username)
    if mode == 'change':
        old = QLineEdit('old-synthetic'); old.setEchoMode(QLineEdit.Password); form.addRow('Current password', old)
    password = QLineEdit(); password.setEchoMode(QLineEdit.Password)
    form.addRow('New password' if mode == 'change' else 'Password', password)
    confirm = None
    if mode in ('register', 'change'):
        confirm = QLineEdit(); confirm.setEchoMode(QLineEdit.Password); form.addRow('Confirm password', confirm)
    submit = QPushButton('Register' if mode == 'register' else 'Change password' if mode == 'change' else 'Sign in'); form.addRow(submit)
    cancel = QPushButton('Cancel'); form.addRow(cancel)
    def hide_form():
        for widget in (username, password, confirm, submit, cancel):
            if widget: widget.hide()
    submit.clicked.connect(hide_form); cancel.clicked.connect(hide_form)
    window.show(); window.activateWindow(); window.raise_()
    def type_password():
        password.setFocus(); QTest.keyClicks(password, 'synthetic-only')
        if confirm: confirm.setText('synthetic-only')
    QTimer.singleShot(1000, type_password)
    button = cancel if mode == 'cancel' else submit
    QTimer.singleShot(1800, button.setFocus)
    QTimer.singleShot(2200, window.close if mode == 'close' else lambda: QTest.mouseClick(button, Qt.LeftButton))
    QTimer.singleShot(3000, app.quit)
    app.exec()
