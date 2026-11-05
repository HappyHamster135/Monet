#!/usr/bin/python3
"""Actual Qt/GTK controls on a private display. All values are synthetic."""
import os
import importlib.util
from pathlib import Path
import subprocess
import sys

assert os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
role, toolkit, mode = sys.argv[1:4]
USERNAME, PASSWORD, SERVER = 'fixture@example.invalid', 'synthetic-fill-only', 'server.example.invalid'

if role == 'observe':
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GLib
    from app_detector import Detector
    seen, offered = [], []
    filling = mode != 'save'
    def offer(identity, values):
        if toolkit == 'flatpak': assert identity.scope == 'flatpak:org.monet.AutofillFixture'
        assert values['username'] == USERNAME and values['service'] == SERVER
        offered.append(True)
    def suggest(target):
        if seen: return
        if toolkit == 'flatpak': assert target.identity.scope == 'flatpak:org.monet.AutofillFixture'
        seen.append('pending')
        def choose():
            result = target.apply(dict(username=USERNAME, password=PASSWORD, service=SERVER))
            seen[-1] = result
            return False
        GLib.timeout_add(450, choose)
    detector = Detector(Atspi, GLib, offer, lambda _: True, suggest=suggest if filling else None)
    detector.start()
    fixture = None
    if toolkit == 'flatpak':
        spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('flatpak-fixture.py'))
        sandbox=importlib.util.module_from_spec(spec);spec.loader.exec_module(sandbox)
        binary=os.environ['MONET_SANDBOX_WIDGET_BINARY']
        fixture,command=sandbox.command(binary,[mode],(Path(binary).parent,))
    else: command=[sys.executable, __file__, 'form', toolkit, mode]
    form = subprocess.Popen(command)
    def finished():
        if form.poll() is not None:
            Atspi.event_quit(); return False
        return True
    GLib.timeout_add(100, finished)
    GLib.timeout_add_seconds(9, lambda: (Atspi.event_quit(), False)[1])
    Atspi.event_main(); detector.clear()
    if form.poll() is None: form.kill()
    code=form.wait()
    if fixture: fixture.cleanup()
    assert code == 0, 'Native control values did not match the chosen account'
    if filling:
        assert seen == [mode not in ('changed-server', 'changed-action')], 'Wrong native fill result'
        assert not offered, 'Autofill must not re-offer the same login for saving'
    else: assert offered == [True], 'Native form was not detected'
    print('PASS: ' + toolkit + ' ' + mode)
elif toolkit == 'qt':
    from PySide6.QtWidgets import QApplication, QWidget, QFormLayout, QLineEdit, QPushButton
    from PySide6.QtCore import QTimer, Qt
    app = QApplication([]); window = QWidget(); window.setWindowTitle('Synthetic native app')
    layout = QFormLayout(window)
    server = QLineEdit(SERVER); layout.addRow('Server', server)
    user = QLineEdit(USERNAME if mode in ('save', 'readonly', 'steps') else ''); layout.addRow('Username', user)
    if mode == 'readonly': user.setReadOnly(True)
    password = QLineEdit(); password.setEchoMode(QLineEdit.Password); layout.addRow('Password', password)
    button = QPushButton('Sign in'); layout.addRow(button)
    submitted = []
    def submit():
        submitted.append(True)
        for control in (user, server, password, button): control.hide()
    button.clicked.connect(submit)
    window.show(); window.activateWindow(); window.raise_()
    if mode == 'steps':
        password.hide(); button.setText('Continue')
        def second_page():
            user.hide(); server.hide(); password.show(); button.setText('Sign in'); password.setFocus()
        QTimer.singleShot(600, user.setFocus); QTimer.singleShot(1000, second_page)
    else: QTimer.singleShot(1000, password.setFocus)
    if mode == 'changed-action': QTimer.singleShot(1200, lambda: button.setText('Create account'))
    if mode == 'changed-server': QTimer.singleShot(1200, lambda: server.setText('changed.example.invalid'))
    if mode == 'save':
        QTimer.singleShot(1200, lambda: password.setText(PASSWORD))
        QTimer.singleShot(1700, button.setFocus); QTimer.singleShot(1900, button.click)
    def verify():
        good = (user.text() == USERNAME and password.text() == PASSWORD and not submitted) if mode not in ('save', 'changed-server', 'changed-action') else (
            not password.text() and not submitted if mode in ('changed-server', 'changed-action') else submitted == [True])
        app.exit(0 if good else 1)
    QTimer.singleShot(2800, verify)
    sys.exit(app.exec())
else:
    import gi
    gi.require_version('Gtk', '3.0' if toolkit == 'gtk3' else '4.0')
    from gi.repository import Gtk, GLib
    Gtk.init([]) if toolkit == 'gtk3' else Gtk.init()
    window = Gtk.Window(title='Synthetic native app'); window.set_default_size(500, 300)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    window.add(box) if toolkit == 'gtk3' else window.set_child(box)
    def append(widget):
        if toolkit == 'gtk3': box.pack_start(widget, False, False, 0)
        else: box.append(widget)
    def field(title, text='', secret=False):
        entry = Gtk.PasswordEntry() if secret and toolkit == 'gtk4' else Gtk.Entry()
        if secret and toolkit == 'gtk3': entry.set_visibility(False)
        entry.set_text(text)
        caption = Gtk.Label.new_with_mnemonic(title)
        caption.set_mnemonic_widget(entry)
        append(caption); append(entry)
        return entry
    server = field('_Server', SERVER)
    user = field('_Username', USERNAME if mode in ('save', 'readonly') else '')
    if mode == 'readonly': user.set_editable(False)
    password = field('_Password', secret=True)
    button = Gtk.Button(label='Sign in'); append(button)
    submitted = []
    def submit(*_):
        submitted.append(True)
        for control in (user, server, password, button): control.set_visible(False)
    button.connect('clicked', submit)
    if toolkit == 'gtk3': window.show_all()
    window.present()
    def once(ms, callback):
        GLib.timeout_add(ms, lambda: (callback(), False)[1])
    once(1000, password.grab_focus)
    if mode == 'changed-action': once(1200, lambda: button.set_label('Create account'))
    if mode == 'changed-server': once(1200, lambda: server.set_text('changed.example.invalid'))
    if mode == 'save':
        once(1200, lambda: password.set_text(PASSWORD)); once(1700, button.grab_focus)
        once(1900, lambda: button.emit('clicked'))
    loop = GLib.MainLoop(); outcome = [False]
    def verify():
        outcome[0] = (user.get_text() == USERNAME and password.get_text() == PASSWORD and not submitted) if mode not in ('save', 'changed-server', 'changed-action') else (
            not password.get_text() and not submitted if mode in ('changed-server', 'changed-action') else submitted == [True])
        loop.quit()
    once(2800, verify); loop.run()
    window.destroy()
    sys.exit(0 if outcome[0] else 1)
