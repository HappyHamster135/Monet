"""Explicit native account choice. Secrets leave on a private pipe only after Fill."""
import json
import sys
import threading

from PySide6.QtCore import QThread, QTimer, Signal, Slot, Qt, SLOT
from PySide6.QtDBus import QDBusConnection
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QDialogButtonBox
from app_logins import AppIdentity, AppLoginStore, allowed, candidate, change_policy, valid_text
from app_prompt import OfferDialog, SaveWorker
from vault import NativeWallet, Vault, VaultError


class FillWorker(SaveWorker):
    completed = Signal(str, object, str)

    @Slot(str, object)
    def run(self, action, values):
        try:
            if not self.guard(): raise VaultError('Filling was cancelled.')
            if self.vault is None:
                self.vault = Vault(self.factory(), app_id='Monet App Logins')
                self.vault.unlock(str(self.vault.call('localWallet')), listing=False)
                self.store = AppLoginStore(self.vault, self.identity, self.guard)
            if action == 'accounts':
                result = self.store.accounts(values['service'], values['username'])
            elif action == 'fill':
                result = self.store.retrieve(values)
                try: change_policy(saved=self.identity)
                except Exception: pass
            else: raise VaultError('This action is not available.')
            self.completed.emit(action, result, '')
        except VaultError as exc:
            self.completed.emit('error', None, str(exc))
        except Exception:
            self.completed.emit('error', None, 'The saved accounts could not be opened. Try again.')


class FillDialog(QDialog):
    requested = Signal(str, object)
    finishing = Signal()
    screen_changed = OfferDialog.screen_changed
    provider_changed = OfferDialog.provider_changed
    finish = OfferDialog.finish

    def __init__(self, identity, context, user_requested=False, factory=NativeWallet, permitted=allowed):
        super().__init__()
        from app import tr
        self.tr, self.identity, self.context, self.permitted = tr, identity, context, permitted
        self.cancelled = threading.Event()
        self.busy = self.loaded = False
        self.result_login = {}
        self.setWindowTitle(tr('Monet Passwords')); self.setMinimumWidth(460); self.setMaximumWidth(580)
        self.setWindowIcon(QIcon.fromTheme('preferences-desktop-user-password'))
        box = QVBoxLayout(self); box.setContentsMargins(28, 26, 28, 26); box.setSpacing(18)
        title = QLabel(tr('Choose an app login')); title.setObjectName('title'); title.setWordWrap(True); box.addWidget(title)
        name = QLabel(identity.name); name.setTextFormat(Qt.PlainText); name.setObjectName('appName'); box.addWidget(name)
        source = QLabel(identity.document or identity.executable); source.setTextFormat(Qt.PlainText); source.setWordWrap(True)
        source.setObjectName('muted'); box.addWidget(source)
        if context['service']:
            service = QLabel(context['service']); service.setTextFormat(Qt.PlainText); service.setWordWrap(True); box.addWidget(service)
        info = QLabel(tr('Choose the account to fill in this app. Monet fills the fields; you decide when to sign in.'))
        info.setWordWrap(True); box.addWidget(info)
        self.accounts = QListWidget(); self.accounts.setObjectName('accounts'); self.accounts.setMinimumHeight(160)
        self.accounts.setAccessibleName(tr('Saved app accounts')); box.addWidget(self.accounts)
        self.feedback = QLabel(tr('Open your saved logins to choose an account. Unlock your vault if asked.'))
        self.feedback.setWordWrap(True); self.feedback.setTextFormat(Qt.PlainText); box.addWidget(self.feedback)
        buttons = QDialogButtonBox()
        self.refresh = buttons.addButton(tr('Open saved logins'), QDialogButtonBox.ActionRole)
        self.cancel = buttons.addButton(tr('Not now'), QDialogButtonBox.RejectRole)
        self.fill = buttons.addButton(tr('Fill selected account'), QDialogButtonBox.AcceptRole)
        self.fill.setAutoDefault(False); self.refresh.setAutoDefault(False); self.cancel.setDefault(True)
        buttons.rejected.connect(self.reject); buttons.accepted.connect(self.submit)
        self.refresh.clicked.connect(self.load); self.accounts.itemSelectionChanged.connect(self.controls); box.addWidget(buttons)
        self.thread = QThread(self); self.worker = FillWorker(identity, self.cancelled, factory, permitted)
        self.worker.moveToThread(self.thread); self.requested.connect(self.worker.run)
        self.worker.completed.connect(self.completed); self.finishing.connect(self.worker.finish)
        self.thread.finished.connect(self.worker.deleteLater); self.thread.start()
        self.deadline = QTimer(self); self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.reject); self.deadline.start(90000)
        OfferDialog.apply_theme(self)
        dark = QApplication.palette().color(QPalette.Window).lightness() < 128
        self.setStyleSheet(self.styleSheet() + 'QListWidget#accounts { border: 1px solid ' + ('#444c4b' if dark else '#d8dcd6') +
            '; border-radius: 8px; } QListWidget::item { padding: 12px; margin: 3px; border-radius: 6px; } '
            'QListWidget::item:selected { background: ' + ('#34544f' if dark else '#d9e6e0') + '; }')
        self.controls()
        if user_requested: QTimer.singleShot(0, self.load)

    def showEvent(self, event):
        super().showEvent(event); self.cancel.setFocus()

    def controls(self):
        self.fill.setEnabled(not self.busy and self.accounts.currentItem() is not None)
        self.refresh.setEnabled(not self.busy); self.accounts.setEnabled(not self.busy)

    def load(self):
        if self.busy: return
        if not self.permitted(self.identity): self.reject(); return
        self.busy = True; self.accounts.clear(); self.controls()
        self.feedback.setText(self.tr('Opening saved logins… Unlock your vault if asked.'))
        self.requested.emit('accounts', self.context)

    def submit(self):
        item = self.accounts.currentItem()
        if self.busy or not item: return
        if not self.permitted(self.identity): self.reject(); return
        self.busy = True; self.controls()
        self.requested.emit('fill', item.data(Qt.UserRole))

    def completed(self, action, result, error):
        if self.cancelled.is_set(): return
        self.busy = False
        if error:
            self.feedback.setText(self.tr(error)); self.accounts.clear()
        elif action == 'accounts':
            self.loaded = True; self.refresh.setText(self.tr('Refresh'))
            for row in result:
                item = QListWidgetItem(row['username'] or self.tr('Account without a username'))
                item.setData(Qt.UserRole, row); self.accounts.addItem(item)
            self.feedback.setText(self.tr('Select an account, then choose Fill selected account.') if result else
                                  self.tr('No saved login matches this app and service. Add or review it in Monet Passwords.'))
            if len(result) == 1: self.accounts.setCurrentRow(0)
        elif action == 'fill':
            self.result_login = result; self.accept(); return
        self.controls(); self.cancel.setDefault(True); self.cancel.setFocus()

    def done(self, result):
        self.cancelled.set(); self.deadline.stop(); self.accounts.clear()
        if result != QDialog.Accepted: self.result_login = {}
        super().done(result)


def main():
    try:
        raw = sys.stdin.buffer.read(131073)
        if len(raw) > 131072: return 1
        data = json.loads(raw); identity = AppIdentity(**data['identity'])
        context = candidate(data['values'])
        if context['password'] or context['kind'] != 'login': return 1
        if not all(valid_text(v, 4096, False) for v in (identity.scope, identity.name, identity.executable)): return 1
        if not allowed(identity): return 1
        import dbus
        bus = dbus.SessionBus()
        if bool(bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver').GetActive(
                dbus_interface='org.freedesktop.ScreenSaver', timeout=2)): return 1
    except Exception:
        return 1
    app = QApplication(sys.argv[:1]); app.setStyle('Fusion')
    app.setApplicationName('monet-passwords'); app.setDesktopFileName('monet-passwords')
    dialog = FillDialog(identity, context, data.get('user_requested') is True)
    qtbus = QDBusConnection.sessionBus()
    qtbus.connect('org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver',
                  'ActiveChanged', dialog, SLOT('screen_changed(bool)'))
    qtbus.connect('org.freedesktop.secrets', '', 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                  dialog, SLOT('provider_changed(QString,QVariantMap,QStringList)'))
    approved = dialog.exec() == QDialog.Accepted
    dialog.finish()
    print(json.dumps({'status': 'filled' if approved else 'declined', 'login': dialog.result_login if approved else {}}))
    dialog.result_login.clear()
    return 0
