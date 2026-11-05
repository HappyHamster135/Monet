"""Monet app-login consent. Private pipe in; status only out. Unlock only after Save."""
import json
import sys
import threading

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt, SLOT
from PySide6.QtDBus import QDBusConnection
from PySide6.QtGui import QPalette, QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QFormLayout, QLabel,
                              QLineEdit, QDialogButtonBox)
from app_logins import AppIdentity, AppLoginStore, allowed, candidate, change_policy, valid_text
from vault import NativeWallet, Vault, VaultError


class SaveWorker(QObject):
    finished = Signal(str, str)

    def __init__(self, identity, cancelled, factory=NativeWallet, permitted=allowed):
        super().__init__()
        self.identity, self.cancelled, self.factory, self.permitted = identity, cancelled, factory, permitted
        self.vault = self.store = self.prepared = None

    def guard(self):
        return not self.cancelled.is_set() and self.permitted(self.identity)

    @Slot(str, object)
    def run(self, action, values):
        try:
            if not self.guard(): raise VaultError('Saving was cancelled.')
            if self.vault is None:
                self.vault = Vault(self.factory(), app_id='Monet App Logins')
                self.vault.unlock(str(self.vault.call('localWallet')), listing=False)
                self.store = AppLoginStore(self.vault, self.identity, self.guard)
            if action == 'save':
                self.prepared = self.store.prepare(values)
                if self.prepared['before'] and not self.prepared['unchanged']:
                    self.finished.emit('confirm-update', '')
                    return
            result = self.store.commit(self.prepared)
            try: change_policy(saved=self.identity)
            except Exception: pass  # A completed encrypted write is still saved.
            self.finished.emit(result, '')
        except VaultError as exc:
            self.finished.emit('error', str(exc))
        except Exception:
            self.finished.emit('error', 'The login could not be saved. Try again in Monet Passwords.')

    @Slot()
    def finish(self):
        self.prepared = None
        try:
            if self.vault:
                try: self.vault.release()
                finally: self.vault.transport.close_connection()
        except Exception:
            pass
        finally:
            self.thread().quit()


class OfferDialog(QDialog):
    requested = Signal(str, object)
    finishing = Signal()

    def __init__(self, identity, values, factory=NativeWallet, permitted=allowed, ignore=None):
        super().__init__()
        from app import tr
        self.tr, self.identity, self.values = tr, identity, candidate(values)
        self.permitted = permitted
        self.ignore = ignore or (lambda app: change_policy(ignore=app))
        self.cancelled = threading.Event()
        self.result_name, self.updating, self.busy = 'declined', False, False
        self.setWindowTitle(tr('Monet Passwords')); self.setMinimumWidth(460); self.setMaximumWidth(580)
        self.setWindowIcon(QIcon.fromTheme('preferences-desktop-user-password'))
        layout = QVBoxLayout(self); layout.setContentsMargins(28, 26, 28, 26); layout.setSpacing(18)
        self.heading = QLabel(tr('Save this app login?')); self.heading.setObjectName('title')
        self.heading.setWordWrap(True); layout.addWidget(self.heading)
        app_label = QLabel(identity.name); app_label.setTextFormat(Qt.PlainText)
        app_label.setObjectName('appName'); app_label.setWordWrap(True); layout.addWidget(app_label)
        origin = QLabel(identity.document or identity.executable); origin.setTextFormat(Qt.PlainText)
        origin.setObjectName('muted'); origin.setWordWrap(True); layout.addWidget(origin)
        self.detail = QLabel(tr('Save the login you just entered in your encrypted Monet vault.') if values['password']
                             else tr('This app keeps its password field private. Enter the password once here to save this login.'))
        self.detail.setWordWrap(True); layout.addWidget(self.detail)
        form = QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.username = QLineEdit(values['username']); self.username.setMaxLength(320)
        self.username.setObjectName('offerUsername'); self.username.setAccessibleName(tr('Username or email'))
        form.addRow(tr('Username or email'), self.username)
        self.service = QLineEdit(values.get('service', '')); self.service.setMaxLength(200)
        self.service.setObjectName('offerService'); self.service.setPlaceholderText(tr('Optional server or account label'))
        form.addRow(tr('Service'), self.service)
        self.password = QLineEdit(values['password']); self.password.setEchoMode(QLineEdit.Password)
        self.password.setMaxLength(4096); self.password.setObjectName('offerPassword')
        self.password.setAccessibleName(tr('Password')); form.addRow(tr('Password'), self.password)
        for edit in (self.username, self.service, self.password): edit.setMinimumHeight(44)
        layout.addLayout(form)
        note = QLabel(tr('Find it later in Monet Passwords. Saving does not confirm that the app accepted the login.'))
        note.setObjectName('muted'); note.setWordWrap(True); layout.addWidget(note)
        self.feedback = QLabel(); self.feedback.setWordWrap(True); self.feedback.setTextFormat(Qt.PlainText)
        layout.addWidget(self.feedback)
        self.buttons = QDialogButtonBox()
        self.never = self.buttons.addButton(tr('Never for this app'), QDialogButtonBox.ActionRole)
        self.cancel = self.buttons.addButton(tr('Not now'), QDialogButtonBox.RejectRole)
        self.save = self.buttons.addButton(tr('Save login'), QDialogButtonBox.AcceptRole)
        self.never.setAutoDefault(False); self.save.setAutoDefault(False)
        self.cancel.setDefault(True); self.cancel.setFocus()
        self.never.clicked.connect(self.skip_app); self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self.submit); layout.addWidget(self.buttons)
        self.password.textChanged.connect(self.update_save)
        self.thread = QThread(self)
        self.worker = SaveWorker(identity, self.cancelled, factory, permitted)
        self.worker.moveToThread(self.thread)
        self.requested.connect(self.worker.run); self.worker.finished.connect(self.completed)
        self.finishing.connect(self.worker.finish); self.thread.finished.connect(self.worker.deleteLater)
        self.thread.start()
        self.deadline = QTimer(self); self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.reject); self.deadline.start(90000)
        self.update_save(); self.apply_theme()

    def apply_theme(self):
        dark = QApplication.palette().color(QPalette.Window).lightness() < 128
        paper, ink, border, accent, dim = ('#242828','#eeeae2','#444c4b','#34544f','#b4bdb6') if dark else (
            '#faf9f6','#252b29','#d8dcd6','#d9e6e0','#67766d')
        self.setStyleSheet('''QWidget { background: PAPER; color: INK; font-family: Inter; font-size: 14px; }
            QLabel { background: transparent; } QLabel#title { font-size: 23px; font-weight: 600; }
            QLabel#appName { font-size: 17px; font-weight: 600; } QLabel#muted { color: DIM; }
            QPushButton, QLineEdit { padding: 9px 12px; border: 1px solid BORDER; border-radius: 8px; }
            QPushButton:hover { background: ACCENT; } QPushButton:focus, QLineEdit:focus { border: 2px solid #357f72; }
            QPushButton:disabled { color: DIM; }'''.replace('PAPER',paper).replace('INK',ink)
            .replace('BORDER',border).replace('ACCENT',accent).replace('DIM',dim))

    def update_save(self):
        self.save.setEnabled(not self.busy and bool(self.password.text()))

    def showEvent(self, event):
        super().showEvent(event)
        self.cancel.setFocus()

    def submit(self):
        if self.busy or not self.password.text(): return
        if not self.permitted(self.identity): self.reject(); return
        values = dict(self.values, username=self.username.text(), password=self.password.text(), service=self.service.text())
        try: values = candidate(values)
        except ValueError:
            self.feedback.setText(self.tr('Check the username, service and password.')); return
        self.busy = True; self.update_save(); self.never.setEnabled(False)
        for edit in (self.username, self.password, self.service): edit.setReadOnly(True)
        self.feedback.setText(self.tr('Saving… Unlock your vault if asked.'))
        self.requested.emit('update' if self.updating else 'save', values)

    def completed(self, status, error):
        if self.cancelled.is_set(): return
        self.busy = False
        if status == 'confirm-update':
            self.updating = True
            self.heading.setText(self.tr('Update this app password?'))
            self.detail.setText(self.tr('This app and account already have a saved login. Replace its password with the one you just entered?'))
            self.save.setText(self.tr('Update password')); self.feedback.clear()
        elif status == 'error':
            self.feedback.setText(self.tr(error))
            self.updating = False; self.save.setText(self.tr('Save login'))
            for edit in (self.username, self.password, self.service): edit.setReadOnly(False)
        else:
            self.result_name = status; self.accept(); return
        self.never.setEnabled(True); self.update_save(); self.cancel.setDefault(True); self.cancel.setFocus()

    def skip_app(self):
        if self.busy: return
        try: self.ignore(self.identity)
        except Exception:
            self.feedback.setText(self.tr('This preference could not be saved. Try again.')); return
        self.result_name = 'ignored'; self.reject()

    @Slot(bool)
    def screen_changed(self, active):
        if active: self.reject()

    @Slot(str, 'QVariantMap', 'QStringList')
    def provider_changed(self, interface, changes, invalidated):
        if interface == 'org.freedesktop.Secret.Collection' and (changes.get('Locked') is True or 'Locked' in invalidated):
            self.reject()

    def done(self, result):
        self.cancelled.set(); self.deadline.stop()
        self.password.clear(); self.username.clear(); self.service.clear(); self.values.clear()
        super().done(result)

    def finish(self):
        self.cancelled.set(); self.finishing.emit()
        # The UI is already closed. A blocked vault unlock is bounded by its D-Bus
        # timeout; the supervising service can terminate the entire prompt sooner.
        self.thread.wait(130000)


def main():
    try:
        raw = sys.stdin.buffer.read(131073)
        if len(raw) > 131072: return 1
        data = json.loads(raw)
        identity = AppIdentity(**data['identity']); values = candidate(data['values'])
        if not all(valid_text(x, 4096, False) for x in (identity.scope, identity.name, identity.executable)):
            return 1
        if not allowed(identity): return 1
        import dbus
        bus = dbus.SessionBus()
        if bool(bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver').GetActive(
                dbus_interface='org.freedesktop.ScreenSaver', timeout=2)):
            return 1
    except Exception:
        return 1
    app = QApplication(sys.argv[:1]); app.setStyle('Fusion')
    app.setApplicationName('monet-passwords'); app.setDesktopFileName('monet-passwords')
    dialog = OfferDialog(identity, values)
    values.clear(); data.clear()
    qtbus = QDBusConnection.sessionBus()
    qtbus.connect('org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver',
                  'ActiveChanged', dialog, SLOT('screen_changed(bool)'))
    qtbus.connect('org.freedesktop.secrets', '', 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                  dialog, SLOT('provider_changed(QString,QVariantMap,QStringList)'))
    dialog.exec(); dialog.finish()
    print(json.dumps({'status': dialog.result_name}))
    return 0
