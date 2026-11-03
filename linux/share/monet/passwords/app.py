"""Native Monet Passwords UI. Secret operations stay on one worker, off the UI thread."""
import gettext
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt, QEvent, QMimeData, QSize, SLOT
from PySide6.QtDBus import QDBusConnection, QDBusServiceWatcher
from PySide6.QtGui import QFont, QIcon, QGuiApplication, QKeySequence, QShortcut, QPalette
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QComboBox, QStackedWidget,
    QScrollArea, QFormLayout, QDialog, QDialogButtonBox, QMessageBox, QFrame, QSplitter)
from vault import NativeWallet, Vault, VaultError, display_label

WORDS = gettext.translation('monet', fallback=True)
tr = WORDS.gettext


class Worker(QObject):
    done = Signal(int, str, object, str)

    def __init__(self, factory=NativeWallet):
        super().__init__()
        self.factory = factory
        self.vault = None

    @Slot(int, str, object)
    def perform(self, token, action, args):
        result, error = None, ''
        try:
            if self.vault is None:
                self.vault = Vault(self.factory())
            if action == 'forget':
                self.vault.release()
            elif action in ('available', 'unlock', 'list_entries', 'select', 'add', 'save', 'delete', 'apps', 'disconnect', 'lock', 'check'):
                result = getattr(self.vault, action)(*args)
            else:
                raise VaultError('This action is not available.')
        except VaultError as exc:
            error = tr(str(exc))
        except Exception:
            # Never log provider exceptions: messages can include entry values.
            error = tr('The vault operation failed. Your passwords have not been exported. Try unlocking again.')
        self.done.emit(token, action, result, error)

    @Slot()
    def finish(self):
        if self.vault:
            self.vault.release()
            try:
                self.vault.transport.close_connection()
            except Exception:
                pass


class SecretClipboard(QObject):
    """Expiry clears our token only, preserving anything copied afterwards."""
    def __init__(self, clipboard, parent=None):
        super().__init__(parent)
        self.clipboard, self.token = clipboard, b''
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.clear)

    def copy(self, text):
        self.token = secrets.token_bytes(24)
        data = QMimeData()
        data.setText(text)
        data.setData('x-kde-passwordManagerHint', b'secret')
        data.setData('application/x-monet-password-copy', self.token)
        self.clipboard.setMimeData(data)
        self.timer.start(30000)

    def clear(self):
        self.timer.stop()
        data = self.clipboard.mimeData()
        if self.token and data and bytes(data.data('application/x-monet-password-copy')) == self.token:
            self.clipboard.clear()
        self.token = b''


class SecretField(QWidget):
    def __init__(self, key, value, clipboard, parent=None):
        super().__init__(parent)
        self.value = value
        self.shown = False
        self.clipboard = clipboard
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 6, 0, 10)
        label = QLabel(tr(display_label(key))); label.setTextFormat(Qt.PlainText)
        label.setObjectName('fieldLabel'); layout.addWidget(label)
        row = QHBoxLayout()
        self.display = QLabel('••••••••••••'); self.display.setTextFormat(Qt.PlainText)
        self.display.setWordWrap(True); self.display.setMinimumHeight(34)
        self.display.setAccessibleName(tr('Hidden saved value'))
        row.addWidget(self.display, 1)
        self.reveal = QPushButton(tr('Show')); self.reveal.setObjectName('revealValue')
        self.reveal.clicked.connect(self.toggle); row.addWidget(self.reveal)
        self.copy_button = QPushButton(tr('Copy')); self.copy_button.setObjectName('copyValue')
        self.copy_button.clicked.connect(self.copy_value); row.addWidget(self.copy_button)
        layout.addLayout(row)
        self.timer = QTimer(self); self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_value)
        self.copy_timer = QTimer(self); self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(lambda: self.copy_button.setText(tr('Copy')))

    def copy_value(self):
        self.clipboard.copy(self.value)
        self.copy_button.setText(tr('Copied')); self.copy_timer.start(2000)

    def toggle(self):
        if self.shown:
            self.hide_value()
        else:
            self.shown = True; self.display.setText(self.value or tr('Empty value'))
            self.display.setAccessibleName(tr('Revealed saved value'))
            self.reveal.setText(tr('Hide')); self.timer.start(15000)

    def hide_value(self):
        self.timer.stop(); self.shown = False
        self.display.setText('••••••••••••'); self.display.setAccessibleName(tr('Hidden saved value'))
        self.reveal.setText(tr('Show'))

    def forget(self):
        self.hide_value(); self.copy_timer.stop(); self.value = ''


class Editor(QDialog):
    def __init__(self, entry=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Edit login') if entry else tr('Add login'))
        self.setMinimumWidth(500)
        self.fields = {}
        self.preserved = {}
        layout = QVBoxLayout(self)
        info = QLabel(tr('Changes are saved in the encrypted desktop vault. Website autofill is managed by your browser.'))
        info.setWordWrap(True); layout.addWidget(info)
        form = QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.title = QLineEdit(entry['key'] if entry else '')
        self.title.setObjectName('loginTitle'); self.title.setMaxLength(200)
        self.title.setReadOnly(entry is not None); form.addRow(tr('Title'), self.title)
        fields = entry['fields'] if entry else {'Username': '', 'Password': '', 'Website': '', 'Notes': ''}
        for key, value in fields.items():
            edit = QLineEdit(); edit.setMaxLength(65536)
            if '\n' in value or '\r' in value or len(value.encode('utf-16-be')) > 131072:
                self.preserved[key] = value
                edit.setPlaceholderText(tr('Multiline app data is preserved. Edit it in its original app.'))
                edit.setReadOnly(True)
            else:
                edit.setText(value)
            edit.setObjectName('edit-' + key)
            # All provider fields are concealed, including unrecognized secret names.
            public = key.casefold() in ('username', 'user', 'website', 'url', 'notes')
            edit.setEchoMode(QLineEdit.Normal if public else QLineEdit.Password)
            edit.setContextMenuPolicy(Qt.NoContextMenu)
            edit.setInputMethodHints(Qt.ImhNoPredictiveText | Qt.ImhSensitiveData)
            self.fields[key] = edit
            label = QLabel(tr(display_label(key))); label.setTextFormat(Qt.PlainText)
            form.addRow(label, edit)
        panel = QWidget(); panel.setLayout(form)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)
        scroll.setFrameShape(QFrame.NoFrame); layout.addWidget(scroll)
        if 'Password' in self.fields:
            generate = QPushButton(tr('Generate strong password'))
            generate.clicked.connect(lambda: self.fields['Password'].setText(secrets.token_urlsafe(24)))
            layout.addWidget(generate)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setTextFormat(Qt.PlainText)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.resize(560, min(650, 230 + len(fields) * 60))

    def values(self):
        return {key: self.preserved.get(key, edit.text()) for key, edit in self.fields.items()}

    def wipe(self):
        self.preserved.clear()
        for edit in self.fields.values():
            edit.clear()
        self.title.clear()

    def done(self, result):
        self.wipe()
        super().done(result)


class PasswordsWindow(QMainWindow):
    request = Signal(int, str, object)

    def __init__(self, helper, factory=NativeWallet, listen=True):
        super().__init__()
        self.helper = str(helper)
        self.token = 0
        self.busy = False
        self.unlocked = False
        self.rows = []
        self.entry = None
        self.fields = []
        self.editor = None
        self.pending_refresh = False
        self.pending_check = False
        self.setWindowTitle(tr('Passwords'))
        self.setWindowIcon(QIcon.fromTheme('preferences-desktop-user-password'))
        self.resize(1060, 740); self.setMinimumSize(820, 540)
        self.clipboard = SecretClipboard(QApplication.clipboard(), self)
        self.thread = QThread(self)
        self.worker = Worker(factory); self.worker.moveToThread(self.thread)
        self.request.connect(self.worker.perform)
        self.worker.done.connect(self.finished)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.start()
        self.build()
        self.shortcut = QShortcut(QKeySequence('Ctrl+F'), self)
        self.shortcut.activated.connect(self.search.setFocus)
        if listen:
            bus = QDBusConnection.sessionBus()
            bus.connect('org.kde.kwalletd6', '/modules/kwalletd6', 'org.kde.KWallet', 'walletClosed', self, SLOT('wallet_closed(QString)'))
            bus.connect('org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver', 'ActiveChanged', self, SLOT('screen_locked(bool)'))
            bus.connect('org.freedesktop.secrets', '', 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                        self, SLOT('secret_properties(QString,QVariantMap,QStringList)'))
            self.watcher = QDBusServiceWatcher('org.kde.kwalletd6', bus, QDBusServiceWatcher.WatchForUnregistration, self)
            self.watcher.serviceUnregistered.connect(lambda _: self.clear_session())
            self.secret_watcher = QDBusServiceWatcher('org.freedesktop.secrets', bus, QDBusServiceWatcher.WatchForUnregistration, self)
            self.secret_watcher.serviceUnregistered.connect(lambda _: self.clear_session())
        self.dispatch('available')

    def build(self):
        root = QWidget(); self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        sidebar = QWidget(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar); side.setContentsMargins(18, 24, 18, 18); side.setSpacing(16)
        title = QLabel(tr('Passwords')); title.setFont(QFont('Fraunces 72pt SuperSoft', 24))
        side.addWidget(title)
        subtitle = QLabel(tr('Your logins, clearly.')); side.addWidget(subtitle)
        self.navigation = QListWidget(); self.navigation.setObjectName('passwordNavigation')
        for label in (tr('All saved entries'), tr('My logins'), tr('Network'), tr('Apps'), tr('Connected apps'), tr('Preferences')):
            item = QListWidgetItem(label); item.setSizeHint(QSize(170, 42))
            self.navigation.addItem(item)
        self.navigation.setCurrentRow(0); self.navigation.currentRowChanged.connect(self.page_changed)
        side.addWidget(self.navigation, 1)
        self.state_label = QLabel(tr('View locked')); side.addWidget(self.state_label)
        self.lock_button = QPushButton(tr('Lock vault')); self.lock_button.setEnabled(False)
        self.lock_button.setToolTip(tr('Lock saved passwords for all apps until the vault is unlocked again.'))
        self.lock_button.clicked.connect(self.lock_vault); side.addWidget(self.lock_button)
        outer.addWidget(sidebar)
        self.pages = QStackedWidget(); outer.addWidget(self.pages, 1)
        main = QWidget(); layout = QVBoxLayout(main); layout.setContentsMargins(26, 22, 26, 18)
        self.page_title = QLabel(tr('All saved entries')); self.page_title.setFont(QFont('Inter', 20, QFont.DemiBold))
        layout.addWidget(self.page_title)
        line = QHBoxLayout(); self.wallets = QComboBox(); self.wallets.setMinimumWidth(150)
        self.wallets.currentTextChanged.connect(self.wallet_changed)
        line.addWidget(self.wallets)
        self.unlock_button = QPushButton(tr('Open vault')); self.unlock_button.setObjectName('unlockVault')
        self.unlock_button.clicked.connect(self.open_or_hide)
        line.addWidget(self.unlock_button)
        self.refresh_button = QPushButton(tr('Refresh')); self.refresh_button.clicked.connect(lambda: self.dispatch('list_entries'))
        self.refresh_button.setEnabled(False); line.addWidget(self.refresh_button); line.addStretch()
        self.add_button = QPushButton(tr('Add login')); self.add_button.setObjectName('addLogin')
        self.add_button.setEnabled(False); self.add_button.clicked.connect(self.add_login); line.addWidget(self.add_button)
        layout.addLayout(line)
        self.search = QLineEdit(); self.search.setPlaceholderText(tr('Search by name or app')); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_rows); layout.addWidget(self.search)
        self.message = QLabel(tr('Open your vault to view saved entries. Your existing vault password still works.'))
        self.message.setWordWrap(True); self.message.setTextFormat(Qt.PlainText); layout.addWidget(self.message)
        split = QSplitter(Qt.Horizontal); self.list = QListWidget(); self.list.setObjectName('savedEntries')
        self.list.currentItemChanged.connect(self.select_item); split.addWidget(self.list)
        self.details = QScrollArea(); self.details.setWidgetResizable(True); self.details.setFrameShape(QFrame.NoFrame)
        split.addWidget(self.details); split.setSizes([260, 450]); layout.addWidget(split, 1)
        self.clear_details()
        foot = QLabel(tr('Passwords stay hidden until you show them. Copies clear after 30 seconds.'))
        foot.setWordWrap(True); layout.addWidget(foot)
        self.pages.addWidget(main)
        apps = QWidget(); app_layout = QVBoxLayout(apps); app_layout.setContentsMargins(26, 26, 26, 26)
        title = QLabel(tr('Connected apps')); title.setFont(QFont('Inter', 20, QFont.DemiBold)); app_layout.addWidget(title)
        text = QLabel(tr('Apps currently connected through the desktop vault. Disconnect closes that connection; it does not permanently block the app. Browser autofill is controlled in the browser.'))
        text.setWordWrap(True); app_layout.addWidget(text)
        self.app_list = QListWidget(); app_layout.addWidget(self.app_list, 1)
        reload_apps = QPushButton(tr('Refresh connections')); reload_apps.clicked.connect(lambda: self.dispatch('apps'))
        app_layout.addWidget(reload_apps)
        disconnect = QPushButton(tr('Disconnect selected app')); disconnect.clicked.connect(self.disconnect_app)
        app_layout.addWidget(disconnect)
        self.app_message = QLabel(); self.app_message.setWordWrap(True); self.app_message.setTextFormat(Qt.PlainText); app_layout.addWidget(self.app_message)
        self.pages.addWidget(apps)
        prefs = QWidget(); pref = QVBoxLayout(prefs); pref.setContentsMargins(26, 26, 26, 26); pref.setSpacing(18)
        title = QLabel(tr('Preferences')); title.setFont(QFont('Inter', 20, QFont.DemiBold)); pref.addWidget(title)
        text = QLabel(tr('Monet Passwords uses your existing encrypted desktop vault. Separate login and vault passwords work. Automatic desktop sign-in still requires one vault unlock each session.'))
        text.setWordWrap(True); pref.addWidget(text)
        text = QLabel(tr('Keep saved passwords unlocked')); pref.addWidget(text)
        self.policy = QComboBox(); self.policy.addItem(tr('Until sign-out'), 'session')
        self.policy.addItem(tr('Lock after 10 minutes idle'), '10'); self.policy.addItem(tr('Lock after 30 minutes idle'), '30')
        pref.addWidget(self.policy)
        apply = QPushButton(tr('Apply unlocking preference')); apply.clicked.connect(self.apply_policy); pref.addWidget(apply)
        self.pref_message = QLabel(tr('Some vault settings take effect at your next sign-in.'))
        self.pref_message.setWordWrap(True); pref.addWidget(self.pref_message)
        browser = QPushButton(tr('Browser passwords and autofill')); browser.clicked.connect(lambda: self.helper_action('wallet-browser'))
        pref.addWidget(browser)
        accounts = QPushButton(tr('Sign-in settings')); accounts.clicked.connect(lambda: self.helper_action('open', 'users'))
        pref.addWidget(accounts)
        text = QLabel(tr('App-managed keys remain available to their apps. Unknown binary formats are labelled clearly and are never converted or overwritten. New logins added here can be copied into apps; they do not automatically appear in browser autofill.'))
        text.setWordWrap(True); pref.addWidget(text); pref.addStretch()
        self.pages.addWidget(prefs)
        self.apply_theme()

    def apply_theme(self):
        dark = QApplication.palette().color(QPalette.Window).lightness() < 128
        paper, side, ink, border, accent = ('#242828', '#1e2323', '#eeeae2', '#444c4b', '#34544f') if dark else (
            '#faf9f6', '#efefea', '#252b29', '#d8dcd6', '#d9e6e0')
        self.setStyleSheet('''
            QMainWindow, QDialog { font-family: Inter; font-size: 14px; }
            QMainWindow, QDialog, QLabel, QScrollArea, QScrollArea > QWidget > QWidget {
                background: PAPER; color: INK;
            }
            QMainWindow > QWidget { background: PAPER; }
            QListWidget { border: none; background: transparent; color: INK; font-size: 14px; }
            QListWidget::item { padding: 10px 8px; border-radius: 7px; }
            QListWidget::item:selected { background: ACCENT; color: INK; }
            QListWidget::item:hover { background: ACCENT; }
            QLabel#fieldLabel { font-weight: 600; }
            QPushButton { padding: 8px 13px; border: 1px solid BORDER; border-radius: 8px;
                background: PAPER; color: INK; font-size: 14px; }
            QPushButton:hover { background: ACCENT; }
            QPushButton:disabled { color: #858b87; }
            QPushButton:focus, QLineEdit:focus { border: 1px solid #60988a; }
            QLineEdit, QComboBox { padding: 8px; border: 1px solid BORDER; border-radius: 8px;
                background: PAPER; color: INK; font-size: 14px; }
            QWidget#sidebar, QWidget#sidebar QLabel { background: SIDE; color: INK; }
        '''.replace('PAPER', paper).replace('SIDE', side).replace('INK', ink).replace('BORDER', border).replace('ACCENT', accent))

    def dispatch(self, action, args=None):
        if self.busy:
            return
        self.busy = True
        self.wallets.setEnabled(False); self.unlock_button.setEnabled(False)
        self.search.setEnabled(False); self.navigation.setEnabled(False)
        self.add_button.setEnabled(False); self.refresh_button.setEnabled(False); self.list.setEnabled(False)
        if action in ('unlock', 'list_entries'):
            self.message.setText(tr('Opening vault…') if action == 'unlock' else tr('Refreshing…'))
        self.request.emit(self.token, action, args or [])

    @Slot(int, str, object, str)
    def finished(self, token, action, result, error):
        # Background connection cleanup must not finish a newer unlock request.
        if token != self.token or action == 'forget':
            return
        self.busy = False
        if error:
            if action == 'check':
                self.clear_session()
            self.message.setText(error); self.app_message.setText(error)
            if self.editor:
                self.editor.error.setText(error); self.editor.buttons.setEnabled(True)
            if action == 'unlock':
                self.unlocked = False
        elif action == 'available':
            self.wallets.blockSignals(True); self.wallets.clear(); self.wallets.addItems(result['wallets'])
            self.wallets.setCurrentText(result['default']); self.wallets.blockSignals(False)
        elif action in ('unlock', 'list_entries', 'delete'):
            self.unlocked = True; self.rows = result; self.clear_details(); self.filter_rows()
            self.message.setText(tr('Choose an entry to view its saved fields.') if result else tr('No saved entries yet. Add your first login.'))
        elif action in ('select', 'add', 'save'):
            if self.editor and action in ('add', 'save'):
                self.editor.accept(); self.editor = None
            self.show_entry(result)
            if action == 'add':
                row = {'folder': result['folder'], 'key': result['key'], 'title': result['key'], 'category': 'Logins'}
                self.rows.append(row); self.filter_rows()
                self.show_entry(result)
            self.message.setText(tr('Saved in your encrypted vault.') if action in ('add', 'save') else '')
        elif action in ('apps', 'disconnect'):
            self.app_list.clear(); self.app_list.addItems(result)
            self.app_message.setText('' if result else tr('No connected desktop apps reported.'))
        elif action == 'lock':
            self.clear_session()
        self.update_controls()
        if self.pending_check and action != 'check' and self.unlocked:
            self.pending_check = False
            self.dispatch('check')

    def update_controls(self):
        self.wallets.setEnabled(not self.busy)
        self.unlock_button.setEnabled(not self.busy and bool(self.wallets.currentText()))
        self.unlock_button.setText(tr('Close view') if self.unlocked else tr('Open vault'))
        self.refresh_button.setEnabled(not self.busy and self.unlocked)
        self.add_button.setEnabled(not self.busy and self.unlocked)
        self.lock_button.setEnabled(self.unlocked)
        self.list.setEnabled(not self.busy)
        self.search.setEnabled(not self.busy); self.navigation.setEnabled(not self.busy)
        self.state_label.setText(tr('Vault open') if self.unlocked else tr('View locked'))

    def open_or_hide(self):
        if self.unlocked:
            self.clear_session()
        else:
            self.dispatch('unlock', [self.wallets.currentText()])

    def wallet_changed(self, _):
        if self.unlocked:
            self.clear_session()

    def filter_rows(self, *_):
        query = self.search.text().casefold().strip()
        group = {1: 'Logins', 2: 'Network', 3: 'Apps'}.get(self.navigation.currentRow())
        self.list.blockSignals(True); self.list.clear()
        for row in self.rows:
            if group and row['category'] != group:
                continue
            if query and query not in (row['title'] + ' ' + row['folder']).casefold():
                continue
            item = QListWidgetItem(row['title'] + '\n' + row['folder'])
            item.setData(Qt.UserRole, row); item.setToolTip(row['title']); self.list.addItem(item)
        self.list.blockSignals(False)
        self.clear_details()

    def select_item(self, item, _previous):
        self.clear_details()
        if item and self.unlocked:
            row = item.data(Qt.UserRole)
            self.dispatch('select', [row['folder'], row['key']])

    def clear_details(self):
        self.entry = None
        for field in self.fields:
            field.forget()
        self.fields = []
        old = self.details.takeWidget()
        if old:
            old.deleteLater()
        content = QWidget(); box = QVBoxLayout(content)
        label = QLabel(tr('Select a saved entry')); label.setWordWrap(True)
        box.addWidget(label); box.addStretch(); self.details.setWidget(content)

    def show_entry(self, entry):
        self.clear_details(); self.entry = entry
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(20, 10, 8, 10)
        name = next((row['title'] for row in self.rows if row['folder'] == entry['folder'] and row['key'] == entry['key']), entry['key'])
        title = QLabel(name); title.setTextFormat(Qt.PlainText); title.setWordWrap(True)
        title.setFont(QFont('Inter', 18, QFont.DemiBold)); layout.addWidget(title)
        folder = QLabel(entry['folder']); folder.setTextFormat(Qt.PlainText); folder.setWordWrap(True); layout.addWidget(folder)
        if entry['note']:
            note = QLabel(tr(entry['note'])); note.setWordWrap(True); layout.addWidget(note)
        for key, value in entry['fields'].items():
            field = SecretField(key, value, self.clipboard, content)
            self.fields.append(field); layout.addWidget(field)
        actions = QHBoxLayout()
        if entry['editable']:
            edit = QPushButton(tr('Edit')); edit.clicked.connect(self.edit_login); actions.addWidget(edit)
            delete = QPushButton(tr('Delete entry')); delete.clicked.connect(self.delete_entry); actions.addWidget(delete)
        layout.addLayout(actions); layout.addStretch()
        old = self.details.takeWidget()
        if old: old.deleteLater()
        self.details.setWidget(content)

    def add_login(self):
        if not self.unlocked or self.busy: return
        self.open_editor(None)

    def edit_login(self):
        if self.entry and not self.busy and self.entry['editable']:
            self.open_editor(self.entry)

    def open_editor(self, entry):
        self.conceal()
        self.editor = Editor(entry, self)
        self.editor.buttons.accepted.connect(lambda: self.save_editor(entry is None))
        self.editor.finished.connect(self.editor_closed)
        self.editor.open()

    def editor_closed(self, _):
        self.editor = None

    def save_editor(self, new):
        if not self.editor or self.busy: return
        values = self.editor.values(); self.editor.buttons.setEnabled(False)
        if new:
            self.dispatch('add', [self.editor.title.text(), values['Username'], values['Password'], values['Website'], values['Notes']])
        else:
            self.dispatch('save', [values])

    def delete_entry(self):
        if not self.entry or self.busy or not self.entry['editable']: return
        self.conceal()
        dialog = QMessageBox(QMessageBox.Warning, tr('Delete saved entry?'),
            tr('This permanently removes the selected entry. Its app may ask you to sign in again, and any data protected by this entry may become unreadable.'),
            QMessageBox.Cancel | QMessageBox.Yes, self)
        dialog.setDefaultButton(QMessageBox.Cancel); dialog.setTextFormat(Qt.PlainText)
        if dialog.exec() == QMessageBox.Yes:
            self.dispatch('delete')

    def disconnect_app(self):
        item = self.app_list.currentItem()
        if not item or not self.unlocked or self.busy: return
        if QMessageBox.question(self, tr('Disconnect app?'), tr('Close this app’s current vault connection? It may reconnect later.'),
                                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes:
            self.dispatch('disconnect', [item.text()])

    def page_changed(self, page):
        self.conceal()
        if page < 4:
            self.pages.setCurrentIndex(0)
            self.page_title.setText(self.navigation.item(page).text()); self.filter_rows()
        elif page == 4:
            self.pages.setCurrentIndex(1)
            if self.unlocked: self.dispatch('apps')
            else: self.app_message.setText(tr('Open a vault from All saved entries first.'))
        else:
            self.pages.setCurrentIndex(2); self.load_policy()

    def helper_action(self, *args):
        # Only fixed non-secret settings commands cross a process boundary.
        try:
            subprocess.Popen([self.helper, *args], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            self.pref_message.setText(tr('These settings could not be opened.'))

    def load_policy(self):
        # Async QProcess; no disk/DBus wait on the UI thread.
        self.policy_command('wallet-status')

    def apply_policy(self):
        self.policy_command('wallet-policy', self.policy.currentData())

    def policy_command(self, *args):
        from PySide6.QtCore import QProcess
        if getattr(self, 'policy_process', None): return
        proc = QProcess(self); self.policy_process = proc
        def finished(code, _status):
            if self.policy_process is not proc: return
            data = bytes(proc.readAllStandardOutput())
            try: result = json.loads(data)
            except (ValueError, UnicodeError): result = {}
            state = result.get('state', result)
            index = self.policy.findData(state.get('policy', ''))
            if index >= 0: self.policy.setCurrentIndex(index)
            if args[0] == 'wallet-policy':
                self.pref_message.setText(tr('Saved. Some vault settings take effect at your next sign-in.')
                                          if code == 0 and result.get('ok') else tr('The unlocking preference could not be saved.'))
            proc.deleteLater(); self.policy_process = None
        proc.finished.connect(finished)
        proc.errorOccurred.connect(lambda _: finished(-1, None))
        deadline = QTimer(proc); deadline.setSingleShot(True)
        deadline.timeout.connect(proc.kill); deadline.start(15000)
        proc.start(self.helper, list(args))

    def conceal(self):
        for field in self.fields:
            field.hide_value()

    def clear_session(self):
        self.token += 1; self.busy = False; self.unlocked = False
        self.pending_check = False
        if self.editor: self.editor.reject(); self.editor = None
        self.clear_details(); self.rows = []; self.list.clear(); self.app_list.clear()
        self.clipboard.clear()
        self.request.emit(self.token, 'forget', [])
        self.message.setText(tr('Password view locked. Open your vault to continue.'))
        self.update_controls()

    @Slot(str)
    def wallet_closed(self, name):
        # Also emitted when an unrelated app disconnects from an open vault.
        if name == self.wallets.currentText() and self.unlocked:
            self.conceal()
            if self.busy: self.pending_check = True
            else: self.dispatch('check')

    @Slot(str, 'QVariantMap', 'QStringList')
    def secret_properties(self, interface, changes, _invalidated):
        if interface == 'org.freedesktop.Secret.Collection' and changes.get('Locked') is True:
            self.clear_session()

    @Slot(bool)
    def screen_locked(self, locked):
        if locked: self.clear_session()

    def lock_vault(self):
        if not self.unlocked: return
        # Clear displayed values immediately, including a late in-flight read.
        self.token += 1; self.busy = False
        if self.editor: self.editor.reject(); self.editor = None
        self.clear_details(); self.clipboard.clear()
        self.rows = []; self.list.clear(); self.unlocked = False; self.update_controls()
        self.dispatch('lock')

    def event(self, event):
        if event.type() in (QEvent.WindowDeactivate, QEvent.Hide) and hasattr(self, 'fields'):
            self.conceal()
        if event.type() == QEvent.ApplicationPaletteChange and hasattr(self, 'pages'):
            self.apply_theme()
        return super().event(event)

    def closeEvent(self, event):
        self.clear_session()
        self.request.emit(self.token, 'forget', [])
        # No forced termination while a vault write is running.
        if self.thread.isRunning():
            self.hide()
            self.thread.quit()
            if not self.thread.wait(100):
                event.ignore()
                self.thread.finished.connect(self.close)
                return
        event.accept()


def main(data, helper):
    global WORDS, tr
    locale = Path(data) / 'locale'
    WORDS = gettext.translation('monet', localedir=str(locale if locale.is_dir() else Path('/usr/share/locale')), fallback=True)
    tr = WORDS.gettext
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    app = QApplication(sys.argv[:1]); app.setApplicationName('monet-passwords')
    app.setApplicationDisplayName(tr('Passwords')); app.setDesktopFileName('monet-passwords')
    app.setOrganizationName('monet')
    page = 'connections' if '--connections' in sys.argv else 'preferences' if '--preferences' in sys.argv else ''
    name = 'monet-passwords-' + str(os.getuid())
    socket = QLocalSocket(); socket.connectToServer(name)
    if socket.waitForConnected(200):
        socket.write((page or 'show').encode()); socket.waitForBytesWritten(200); socket.disconnectFromServer(); return 0
    QLocalServer.removeServer(name); server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(name): return 1
    window = PasswordsWindow(helper)
    def show_page(page):
        if page in ('connections', 'preferences'):
            window.navigation.setCurrentRow(4 if page == 'connections' else 5)
        window.showNormal(); window.raise_(); window.activateWindow()
    def activate():
        peer = server.nextPendingConnection()
        def read():
            page = bytes(peer.read(32)).decode('ascii', errors='ignore')
            peer.close(); peer.deleteLater(); show_page(page)
        if peer.bytesAvailable(): read()
        else: peer.readyRead.connect(read)
    server.newConnection.connect(activate)
    if page:
        # Discovery is asynchronous; navigation can still be selected programmatically.
        window.navigation.setCurrentRow(4 if page == 'connections' else 5)
    window.show()
    return app.exec()
