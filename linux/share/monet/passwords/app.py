"""Native Monet Passwords UI. Secret operations stay on one worker, off the UI thread."""
import gettext
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt, QEvent, QMimeData, QSize, SLOT, QRectF
from PySide6.QtDBus import QDBusConnection, QDBusServiceWatcher
from PySide6.QtGui import QFont, QIcon, QGuiApplication, QKeySequence, QShortcut, QPalette, QColor, QPainter, QPainterPath, QPixmap, QPen
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QComboBox, QStackedWidget,
    QScrollArea, QFormLayout, QDialog, QDialogButtonBox, QMessageBox, QFrame, QSplitter, QFileDialog, QStyledItemDelegate, QStyle, QPlainTextEdit)
from vault import NativeWallet, Vault, VaultError, display_label, entry_title

WORDS = gettext.translation('monet', fallback=True)
tr = WORDS.gettext


def navigation_icon(index, color):
    """Small native outline icons stay legible in both Monet palettes."""
    pixmap = QPixmap(48, 48); pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap); painter.scale(2, 2)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen); painter.setBrush(Qt.NoBrush)
    path = QPainterPath()
    if index == 0:
        painter.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
        path.moveTo(8, 10); path.lineTo(8, 7); path.cubicTo(8, 2, 16, 2, 16, 7); path.lineTo(16, 10)
        painter.drawLine(12, 14, 12, 17)
    elif index == 1:
        for x, y in ((2, 8), (5, 12), (8, 16)):
            path.moveTo(x, y); path.quadTo(12, y - (12 - x), 24 - x, y)
        painter.drawEllipse(QRectF(11, 19, 2, 2))
    elif index == 2:
        for x, y in ((4, 4), (14, 4), (4, 14), (14, 14)):
            painter.drawRoundedRect(QRectF(x, y, 6, 6), 1, 1)
    elif index == 3:
        path.moveTo(9, 8); path.lineTo(5, 8); path.cubicTo(0, 8, 0, 16, 5, 16); path.lineTo(9, 16)
        path.moveTo(15, 8); path.lineTo(19, 8); path.cubicTo(24, 8, 24, 16, 19, 16); path.lineTo(15, 16)
        painter.drawLine(8, 12, 16, 12)
    elif index == 5:
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawEllipse(QRectF(8, 3, 8, 18))
        painter.drawLine(3, 12, 21, 12)
    else:
        for y, knob in ((6, 9), (12, 16), (18, 7)):
            painter.drawLine(3, y, knob - 2, y); painter.drawLine(knob + 2, y, 21, y)
            painter.drawEllipse(QRectF(knob - 2, y - 2, 4, 4))
    painter.drawPath(path); painter.end()
    return QIcon(pixmap)


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
            if action in ('browser_status', 'browser_enable'):
                from browser_setup import inspect, apply
                if action == 'browser_enable': apply(*args)
                result = inspect(*args)
            elif self.vault is None:
                self.vault = Vault(self.factory())
            if action in ('browser_status', 'browser_enable'):
                pass
            elif action == 'forget':
                self.vault.release()
            elif action in ('available', 'unlock', 'list_entries', 'select', 'add', 'save', 'delete', 'apps', 'disconnect', 'lock', 'check', 'prepare_import', 'import_logins', 'cancel_import', 'connections', 'revoke_browser'):
                result = getattr(self.vault, action)(*args)
                if action == 'select' and result.get('folder') == 'Monet App Logins':
                    # Opening a legacy app entry explicitly makes its app eligible
                    # for quiet suggestions too; this never opens another entry.
                    from app_logins import AppIdentity, change_policy, valid_text
                    fields = result['fields']
                    if valid_text(fields.get('Application ID'), 4096, False):
                        try: change_policy(saved=AppIdentity(fields['Application ID'], fields.get('Application', ''), ''))
                        except Exception: pass
            else:
                raise VaultError('This action is not available.')
        except VaultError as exc:
            error = tr(str(exc))
        except ValueError as exc:
            error = (tr(str(exc)) if action.startswith('browser_') and type(exc) is ValueError else
                     tr('The vault operation failed. Your passwords have not been exported. Try unlocking again.'))
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


class EntryDelegate(QStyledItemDelegate):
    """Compact account rows; no secret reads, favicons or network requests."""
    def paint(self, painter, option, index):
        row = index.data(Qt.UserRole) or {}
        painter.save()
        rect = option.rect.adjusted(1, 1, -1, -1)
        dark = QApplication.palette().color(QPalette.Window).lightness() < 128
        selected = bool(option.state & (QStyle.State_Selected | QStyle.State_MouseOver))
        ink = QColor('#eeeae2' if dark else '#252b29')
        muted = QColor('#b4bdb6' if dark else '#67766d')
        painter.setRenderHint(QPainter.Antialiasing)
        if selected:
            painter.setPen(Qt.NoPen); painter.setBrush(QColor('#34544f' if dark else '#d9e6e0'))
            painter.drawRoundedRect(rect, 8, 8)
        badge = QRectF(rect.x() + 10, rect.y() + 15, 34, 34)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor('#444c4b' if dark else '#e7ebe5'))
        painter.drawRoundedRect(badge, 9, 9)
        painter.setPen(ink); painter.setFont(QFont('Inter', 13, QFont.DemiBold))
        painter.drawText(badge, Qt.AlignCenter, row.get('title', '?')[:1].upper())
        text_rect = rect.adjusted(54, 10, -10, -34)
        painter.setFont(QFont('Inter', 10, QFont.DemiBold))
        painter.drawText(text_rect, Qt.AlignVCenter, painter.fontMetrics().elidedText(row.get('title', ''), Qt.ElideRight, text_rect.width()))
        subtitle = tr('App encryption key') if row.get('internal') else tr('Saved login') if row.get('category') == 'Logins' else row.get('folder', '')
        painter.setPen(muted); painter.setFont(QFont('Inter', 9))
        painter.drawText(rect.adjusted(54, 34, -10, -8), Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(subtitle, Qt.ElideRight, text_rect.width()))
        painter.restore()


class SecretField(QWidget):
    def __init__(self, key, value, clipboard, parent=None):
        super().__init__(parent)
        self.value = value
        self.public = key.casefold() in ('username', 'user', 'website', 'url', 'notes', 'application', 'service')
        self.setObjectName('secretField')
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
        self.reveal.setVisible(not self.public and bool(value)); self.copy_button.setEnabled(bool(value))
        self.hide_value()

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
        self.display.setText(self.value if self.public else '••••••••••••' if self.value else tr('Not saved'))
        self.display.setAccessibleName(tr('Saved value') if self.public else tr('Hidden saved value'))
        self.reveal.setText(tr('Show'))

    def forget(self):
        self.value = ''; self.hide_value(); self.copy_timer.stop()


class Editor(QDialog):
    def __init__(self, entry=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Edit login') if entry else tr('Add login'))
        self.setMinimumWidth(500)
        self.fields = {}
        self.preserved = {}
        layout = QVBoxLayout(self)
        info = QLabel(tr('Changes are saved in your encrypted vault. App logins stay separate from website logins.'))
        info.setWordWrap(True); layout.addWidget(info)
        form = QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.title = QLineEdit(entry_title(entry.get('folder', ''), entry['key']) if entry else '')
        self.title.setObjectName('loginTitle'); self.title.setMaxLength(200)
        self.title.setReadOnly(entry is not None); form.addRow(tr('Title'), self.title)
        fields = entry['fields'] if entry else {'Username': '', 'Password': '', 'Website': '', 'Notes': ''}
        for key, value in fields.items():
            if key == 'Application ID':
                self.preserved[key] = value
                continue
            if key == 'Notes':
                edit = QPlainTextEdit(value); edit.setMaximumHeight(100)
                edit.setContextMenuPolicy(Qt.NoContextMenu)
                self.fields[key] = edit
                form.addRow(tr('Notes'), edit)
                continue
            edit = QLineEdit(); edit.setMaxLength(65536)
            if '\n' in value or '\r' in value or len(value.encode('utf-16-be')) > 131072:
                self.preserved[key] = value
                edit.setPlaceholderText(tr('Multiline app data is preserved. Edit it in its original app.'))
                edit.setReadOnly(True)
            else:
                edit.setText(value)
            edit.setObjectName('edit-' + key)
            # All provider fields are concealed, including unrecognized secret names.
            public = key.casefold() in ('username', 'user', 'website', 'url', 'notes', 'application', 'service')
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
        return {key: self.preserved.get(key, edit.toPlainText() if isinstance(edit, QPlainTextEdit) else edit.text())
                for key, edit in self.fields.items()}

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
        self.browser_connected = False
        self.rows = []
        self.entry = None
        self.fields = []
        self.editor = None
        self.import_dialog = None
        self.pending_refresh = False
        self.pending_check = False
        self.setWindowTitle(tr('Passwords'))
        self.setWindowIcon(QIcon.fromTheme('preferences-desktop-user-password'))
        self.resize(1080, 720); self.setMinimumSize(900, 580)
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
        sidebar = QWidget(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(192)
        side = QVBoxLayout(sidebar); side.setContentsMargins(16, 26, 16, 18); side.setSpacing(12)
        title = QLabel(tr('Passwords')); title.setObjectName('brandTitle'); title.setFont(QFont('Fraunces 72pt SuperSoft', 21))
        side.addWidget(title)
        subtitle = QLabel(tr('Your personal vault')); subtitle.setObjectName('muted'); side.addWidget(subtitle)
        self.navigation = QListWidget(); self.navigation.setObjectName('passwordNavigation')
        self.navigation.setIconSize(QSize(18, 18))
        for label in (tr('Saved logins'), tr('Wi-Fi & VPN'), tr('App data'), tr('Connected apps'), tr('Preferences'), tr('Zen autofill')):
            item = QListWidgetItem(label); item.setSizeHint(QSize(156, 44))
            self.navigation.addItem(item)
        self.navigation.setCurrentRow(0); self.navigation.currentRowChanged.connect(self.page_changed)
        side.addWidget(self.navigation, 1)
        self.state_label = QLabel(tr('View closed')); side.addWidget(self.state_label)
        self.lock_button = QPushButton(tr('Lock vault')); self.lock_button.setEnabled(False)
        self.lock_button.setToolTip(tr('Lock saved passwords for all apps until the vault is unlocked again.'))
        self.lock_button.clicked.connect(self.lock_vault); side.addWidget(self.lock_button)
        outer.addWidget(sidebar)
        self.pages = QStackedWidget(); outer.addWidget(self.pages, 1)
        main = QWidget(); layout = QVBoxLayout(main); layout.setContentsMargins(26, 22, 26, 18)
        self.page_title = QLabel(tr('Saved logins')); self.page_title.setObjectName('pageTitle'); self.page_title.setFont(QFont('Inter', 20, QFont.DemiBold))
        layout.addWidget(self.page_title)
        line = QHBoxLayout(); self.wallets = QComboBox(); self.wallets.setMinimumWidth(110); self.wallets.setAccessibleName(tr('Encrypted vault'))
        self.wallets.currentTextChanged.connect(self.wallet_changed)
        line.addWidget(self.wallets)
        self.unlock_button = QPushButton(tr('Open vault')); self.unlock_button.setObjectName('unlockVault')
        self.unlock_button.clicked.connect(self.open_or_hide)
        line.addWidget(self.unlock_button)
        self.refresh_button = QPushButton(tr('Refresh')); self.refresh_button.clicked.connect(lambda: self.dispatch('list_entries'))
        self.refresh_button.setEnabled(False); line.addWidget(self.refresh_button); line.addStretch()
        self.import_button = QPushButton(tr('Import…')); self.import_button.clicked.connect(self.choose_import)
        self.import_button.setEnabled(False); line.addWidget(self.import_button)
        self.add_button = QPushButton(tr('Add login')); self.add_button.setObjectName('addLogin')
        self.add_button.setEnabled(False); self.add_button.clicked.connect(self.add_login); line.addWidget(self.add_button)
        layout.addLayout(line)
        self.search = QLineEdit(); self.search.setPlaceholderText(tr('Search saved logins')); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_rows); layout.addWidget(self.search)
        self.message = QLabel(tr('Open your vault to view saved entries. Your existing vault password still works.'))
        self.message.setWordWrap(True); self.message.setTextFormat(Qt.PlainText); layout.addWidget(self.message)
        split = QSplitter(Qt.Horizontal); self.list = QListWidget(); self.list.setObjectName('savedEntries'); self.list.setItemDelegate(EntryDelegate(self.list))
        self.list.setMinimumWidth(225); self.list.setSpacing(3)
        self.list.currentItemChanged.connect(self.select_item); split.addWidget(self.list)
        self.details = QScrollArea(); self.details.setWidgetResizable(True); self.details.setFrameShape(QFrame.NoFrame)
        split.addWidget(self.details); split.setChildrenCollapsible(False); split.setHandleWidth(16); split.setSizes([265, 475]); layout.addWidget(split, 1)
        self.clear_details()
        foot = QLabel(tr('Passwords stay hidden until you show them. Copies clear after 30 seconds.'))
        foot.setObjectName('muted'); foot.setWordWrap(True); layout.addWidget(foot)
        self.pages.addWidget(main)
        apps = QWidget(); app_layout = QVBoxLayout(apps); app_layout.setContentsMargins(26, 26, 26, 26)
        title = QLabel(tr('Connected apps')); title.setFont(QFont('Inter', 20, QFont.DemiBold)); app_layout.addWidget(title)
        text = QLabel(tr('Apps currently connected through the desktop vault. Disconnect closes that connection; it does not permanently block the app. Browser autofill is controlled in the browser.'))
        text.setWordWrap(True); app_layout.addWidget(text)
        self.browser_list = QListWidget(); self.browser_list.setMaximumHeight(180)
        label = QLabel(tr('Saved browser connections')); app_layout.addWidget(label); app_layout.addWidget(self.browser_list)
        forget_browser = QPushButton(tr('Revoke selected browser')); forget_browser.clicked.connect(self.revoke_browser)
        app_layout.addWidget(forget_browser)
        label = QLabel(tr('Current desktop connections')); app_layout.addWidget(label)
        self.app_list = QListWidget(); app_layout.addWidget(self.app_list, 1)
        reload_apps = QPushButton(tr('Refresh connections')); reload_apps.clicked.connect(lambda: self.dispatch('connections'))
        app_layout.addWidget(reload_apps)
        disconnect = QPushButton(tr('Disconnect selected app')); disconnect.clicked.connect(self.disconnect_app)
        app_layout.addWidget(disconnect)
        self.app_message = QLabel(); self.app_message.setWordWrap(True); self.app_message.setTextFormat(Qt.PlainText); app_layout.addWidget(self.app_message)
        self.apps_unlock = QPushButton(tr('Open vault')); self.apps_unlock.clicked.connect(self.open_or_hide)
        app_layout.addWidget(self.apps_unlock)
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
        offers = QPushButton(tr('App login settings')); offers.clicked.connect(lambda: self.helper_action('open', 'passwords'))
        pref.addWidget(offers)
        browser = QPushButton(tr('Optional Zen connection')); browser.clicked.connect(self.connect_zen)
        pref.addWidget(browser)
        accounts = QPushButton(tr('Sign-in settings')); accounts.clicked.connect(lambda: self.helper_action('open', 'users'))
        pref.addWidget(accounts)
        text = QLabel(tr('App-managed keys remain available to their apps. Unknown binary formats are labelled clearly and are never converted or overwritten. Connect Zen to save logins with your approval and autofill matching websites. Browser connections can be revoked in Connected apps.'))
        text.setWordWrap(True); pref.addWidget(text); pref.addStretch()
        self.pages.addWidget(prefs)
        from browser_ui import BrowserPage
        self.browser_page = BrowserPage(tr, self)
        self.browser_page.requested.connect(self.browser_action)
        self.pages.addWidget(self.browser_page)
        self.apply_theme()

    def apply_theme(self):
        dark = QApplication.palette().color(QPalette.Window).lightness() < 128
        paper, side, ink, border, accent = ('#242828', '#1e2323', '#eeeae2', '#444c4b', '#34544f') if dark else (
            '#faf9f6', '#efefea', '#252b29', '#d8dcd6', '#d9e6e0')
        muted = '#b4bdb6' if dark else '#67766d'
        card = '#2d3331' if dark else '#ffffff'
        for index in range(self.navigation.count()):
            item = self.navigation.item(index)
            item.setIcon(navigation_icon(index, ink))
        self.setStyleSheet("""
            QWidget { font-family: Inter; font-size: 14px; color: INK; background: PAPER; }
            QMainWindow, QDialog { background: PAPER; }
            QLabel { background: transparent; border: none; }
            QLabel#brandTitle { font-family: 'Fraunces 72pt SuperSoft'; font-size: 28px; }
            QLabel#pageTitle { font-size: 25px; font-weight: 600; padding-bottom: 8px; }
            QLabel#entryTitle { font-size: 22px; font-weight: 600; padding-bottom: 4px; }
            QLabel#muted { color: MUTED; font-size: 12px; }
            QWidget#sidebar { background: SIDE; border-right: 1px solid BORDER; }
            QWidget#sidebar QLabel { background: transparent; }
            QWidget#detailSurface { background: CARD; border-radius: 12px; }
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget::item { padding: 7px; border-radius: 8px; }
            QListWidget::item:selected, QListWidget::item:hover { background: ACCENT; color: INK; }
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background: CARD; border: none; }
            QLabel#fieldLabel { color: MUTED; font-size: 12px; font-weight: 500; }
            QWidget#secretField { background: CARD; border-bottom: 1px solid BORDER; }
            QPushButton { padding: 8px 12px; border: 1px solid BORDER; border-radius: 8px;
                background: CARD; color: INK; }
            QPushButton:hover { background: ACCENT; }
            QPushButton:disabled { color: MUTED; }
            QPushButton#addLogin { background: ACCENT; font-weight: 600; }
            QPushButton:focus, QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #60988a; }
            QLineEdit, QPlainTextEdit, QComboBox { padding: 8px; border: 1px solid BORDER; border-radius: 8px;
                background: CARD; color: INK; selection-background-color: ACCENT; selection-color: INK; }
            QSplitter::handle { background: PAPER; }
        """.replace('PAPER', paper).replace('SIDE', side).replace('INK', ink).replace('BORDER', border)
            .replace('ACCENT', accent).replace('MUTED', muted).replace('CARD', card))

    def dispatch(self, action, args=None):
        if self.busy:
            return
        self.busy = True
        self.wallets.setEnabled(False); self.unlock_button.setEnabled(False)
        self.search.setEnabled(False); self.navigation.setEnabled(False)
        self.import_button.setEnabled(False); self.add_button.setEnabled(False); self.refresh_button.setEnabled(False); self.list.setEnabled(False)
        self.apps_unlock.setEnabled(False)
        self.browser_page.set_busy(True)
        for button in self.details.findChildren(QPushButton, 'emptyUnlock'): button.setEnabled(False)
        if action in ('unlock', 'list_entries'):
            self.message.setText(tr('Opening vault…') if action == 'unlock' else tr('Refreshing…'))
        self.request.emit(self.token, action, args or [])

    @Slot(int, str, object, str)
    def finished(self, token, action, result, error):
        # Background connection cleanup must not finish a newer unlock request.
        if token != self.token or action in ('forget', 'cancel_import'):
            return
        self.busy = False
        if error:
            if action == 'check':
                self.clear_session()
            self.message.setText(error); self.app_message.setText(error)
            if action.startswith('browser_'): self.browser_page.feedback.setText(error)
            if self.editor:
                self.editor.error.setText(error); self.editor.buttons.setEnabled(True)
            if action == 'import_logins' and self.import_dialog:
                self.import_dialog.reject()
            if action == 'unlock':
                self.unlocked = False
        elif action == 'available':
            self.wallets.blockSignals(True); self.wallets.clear(); self.wallets.addItems(result['wallets'])
            self.wallets.setCurrentText(result['default']); self.wallets.blockSignals(False)
        elif action in ('browser_status', 'browser_enable'):
            self.browser_page.show_state(result)
            if action == 'browser_enable':
                self.browser_page.feedback.setText(tr('Connection enabled. Restart Zen if it was open, then finish connecting here.'))
        elif action in ('unlock', 'list_entries', 'delete'):
            self.unlocked = True; self.rows = result; self.clear_details(); self.filter_rows()
            self.message.setText(tr('Your vault is open.'))
        elif action == 'prepare_import':
            self.confirm_import(result)
        elif action == 'import_logins':
            if self.import_dialog: self.import_dialog.accept(); self.import_dialog = None
            self.rows = result['rows']; self.navigation.setCurrentRow(0); self.filter_rows()
            self.message.setText(tr('Imported %1 logins. Skipped %2 identical logins.').replace('%1', str(result['added'])).replace('%2', str(result['skipped'])))
            if result['incomplete']:
                self.message.setText(tr('Import stopped. %1 logins were saved. Unlock and import the file again to finish; identical logins will be skipped.').replace('%1', str(result['added'])))
        elif action in ('select', 'add', 'save'):
            if self.editor and action in ('add', 'save'):
                self.editor.accept(); self.editor = None
            self.show_entry(result)
            if action == 'add':
                row = {'folder': result['folder'], 'key': result['key'], 'title': result['key'], 'category': 'Logins'}
                self.rows.append(row); self.navigation.setCurrentRow(0); self.search.clear(); self.filter_rows()
                self.show_entry(result)
            self.message.setText(tr('Saved in your encrypted vault.') if action in ('add', 'save') else '')
        elif action in ('connections', 'revoke_browser'):
            self.browser_connected = bool(result['browsers'])
            self.app_list.clear(); self.app_list.addItems(result['apps'])
            self.browser_list.clear()
            for row in result['browsers']:
                item = QListWidgetItem(row['name'] + ' · ' + tr('%1 allowed websites').replace('%1', str(len(row['sites']))))
                item.setData(Qt.UserRole, row['id']); self.browser_list.addItem(item)
            self.app_message.setText(tr('Revoked browsers must connect again. Saved logins are kept.') if action == 'revoke_browser' else '')
            if not self.entry and self.navigation.currentRow() == 0: self.clear_details()
        elif action in ('apps', 'disconnect'):
            self.app_list.clear(); self.app_list.addItems(result)
            self.app_message.setText('' if result else tr('No connected desktop apps reported.'))
        elif action == 'lock':
            self.clear_session()
        self.update_controls()
        if self.pending_check and action != 'check' and self.unlocked:
            self.pending_check = False
            self.dispatch('check')
        elif action in ('unlock', 'list_entries') and not error and self.unlocked:
            self.dispatch('connections')
        elif action == 'available' and self.navigation.currentRow() == 5:
            self.browser_action('refresh')

    def update_controls(self):
        self.wallets.setEnabled(not self.busy)
        self.unlock_button.setEnabled(not self.busy and bool(self.wallets.currentText()))
        self.unlock_button.setText(tr('Close view') if self.unlocked else tr('Open vault'))
        self.unlock_button.setToolTip(tr('Hide your saved entries without locking the vault for other apps.') if self.unlocked
                                     else tr('Open your saved entries. Enter your vault password only if asked.'))
        self.refresh_button.setEnabled(not self.busy and self.unlocked)
        self.add_button.setEnabled(not self.busy and self.unlocked)
        self.import_button.setEnabled(not self.busy and self.unlocked)
        self.lock_button.setEnabled(self.unlocked)
        self.list.setEnabled(not self.busy)
        self.search.setEnabled(not self.busy); self.navigation.setEnabled(not self.busy)
        self.state_label.setText(tr('Vault open') if self.unlocked else tr('View closed'))
        self.apps_unlock.setVisible(not self.unlocked)
        self.apps_unlock.setEnabled(not self.busy and bool(self.wallets.currentText()))
        self.browser_page.set_busy(self.busy)
        self.browser_page.set_pairing(self.unlocked, self.browser_connected)
        for button in self.details.findChildren(QPushButton, 'emptyUnlock'):
            button.setEnabled(not self.busy and bool(self.wallets.currentText()))

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
        group = {0: 'Logins', 1: 'Network', 2: 'Apps'}.get(self.navigation.currentRow())
        self.list.blockSignals(True); self.list.clear()
        for row in self.rows:
            if group and row['category'] != group:
                continue
            if query and query not in (row['title'] + ' ' + row['folder']).casefold():
                continue
            item = QListWidgetItem(row['title'])
            item.setSizeHint(QSize(220, 68))
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
        content = QWidget(); content.setObjectName('detailSurface'); box = QVBoxLayout(content)
        box.setContentsMargins(28, 32, 28, 28); box.setSpacing(16)
        box.addStretch()
        label = QLabel(tr('Open your vault') if not self.unlocked else tr('No matching logins') if self.search.text().strip() and not self.list.count()
                       else tr('Your logins, in one place') if self.navigation.currentRow() == 0 else tr('Select an entry'))
        label.setObjectName('entryTitle'); label.setFont(QFont('Inter', 18, QFont.DemiBold)); label.setWordWrap(True); box.addWidget(label)
        text = (tr('Turn on app login offers in Password settings, or add a login here. Supported apps can ask to save accounts in your encrypted vault.')
                if self.navigation.currentRow() == 0 else tr('Choose an item from the list to see its details.'))
        if not self.unlocked:
            text = tr('Use your vault password if asked. Your saved app and website logins appear here.')
        elif self.search.text().strip() and not self.list.count():
            text = tr('Try a different name or clear your search to see all saved entries.')
        hint = QLabel(text); hint.setObjectName('muted'); hint.setWordWrap(True); box.addWidget(hint)
        if not self.unlocked:
            button = QPushButton(tr('Open vault')); button.setObjectName('emptyUnlock')
            button.setEnabled(not self.busy and bool(self.wallets.currentText()))
            button.clicked.connect(self.open_or_hide); box.addWidget(button, alignment=Qt.AlignLeft)
        elif self.navigation.currentRow() == 0 and not self.search.text().strip():
            offers = QPushButton(tr('App login settings')); offers.clicked.connect(lambda: self.helper_action('open', 'passwords'))
            box.addWidget(offers, alignment=Qt.AlignLeft)
        box.addStretch(); self.details.setWidget(content)

    def show_entry(self, entry):
        self.clear_details(); self.entry = entry
        content = QWidget(); content.setObjectName('detailSurface'); layout = QVBoxLayout(content); layout.setContentsMargins(24, 24, 24, 24); layout.setSpacing(12)
        name = next((row['title'] for row in self.rows if row['folder'] == entry['folder'] and row['key'] == entry['key']), entry['key'])
        title = QLabel(name); title.setTextFormat(Qt.PlainText); title.setWordWrap(True)
        title.setObjectName('entryTitle'); title.setFont(QFont('Inter', 18, QFont.DemiBold)); layout.addWidget(title)
        folder = QLabel(tr('Saved app login') if entry['folder'] == 'Monet App Logins' else tr('Saved login') if entry['folder'] == 'Monet Logins' else tr('Managed by the app') if entry.get('internal') else entry['folder']); folder.setObjectName('muted'); folder.setTextFormat(Qt.PlainText); folder.setWordWrap(True); layout.addWidget(folder)
        if entry['note']:
            note = QLabel(tr(entry['note'])); note.setWordWrap(True); layout.addWidget(note)
        for key in sorted(entry['fields'], key=lambda k: ({'Username': 0, 'Website': 1, 'Password': 2, 'Notes': 3}.get(k, 4), k)):
            if key == 'Application ID': continue
            value = entry['fields'][key]
            if not value and key in ('Notes', 'Username', 'Website'): continue
            field = SecretField(key, value, self.clipboard, content)
            self.fields.append(field); layout.addWidget(field)
        actions = QHBoxLayout()
        if entry['editable']:
            edit = QPushButton(tr('Edit')); edit.clicked.connect(self.edit_login); actions.addWidget(edit); actions.addStretch()
            delete = QPushButton(tr('Delete entry')); delete.clicked.connect(self.delete_entry); actions.addWidget(delete)
        layout.addLayout(actions); layout.addStretch()
        old = self.details.takeWidget()
        if old: old.deleteLater()
        self.details.setWidget(content)

    def choose_import(self):
        if self.busy or not self.unlocked: return
        self.conceal()
        path, _ = QFileDialog.getOpenFileName(self, tr('Import browser passwords'), '', tr('Browser CSV exports (*.csv)'))
        if path: self.dispatch('prepare_import', [path])

    def confirm_import(self, summary):
        dialog = QDialog(self); self.import_dialog = dialog
        dialog.setWindowTitle(tr('Import browser passwords')); dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog); layout.setContentsMargins(24, 24, 24, 24); layout.setSpacing(16)
        title = QLabel(tr('%1 logins ready to import').replace('%1', str(summary['count'])))
        title.setObjectName('entryTitle'); title.setFont(QFont('Inter', 18, QFont.DemiBold)); layout.addWidget(title)
        text = QLabel(tr('Identical logins are skipped. Existing passwords are never overwritten. Browser autofill stays in your browser.'))
        text.setWordWrap(True); layout.addWidget(text)
        text = QLabel(tr('%1 empty or repeated rows were skipped. The exported CSV is unencrypted; delete it when you no longer need it.').replace('%1', str(summary['skipped'])))
        text.setWordWrap(True); layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(tr('Import logins'))
        buttons.button(QDialogButtonBox.Save).setEnabled(summary['count'] > 0)
        def commit():
            if self.busy: return
            buttons.setEnabled(False); self.dispatch('import_logins')
        buttons.accepted.connect(commit); buttons.rejected.connect(dialog.reject)
        dialog.rejected.connect(lambda: self.request.emit(self.token, 'cancel_import', []))
        dialog.finished.connect(lambda _: setattr(self, 'import_dialog', None))
        layout.addWidget(buttons); dialog.open()

    def cancel_import_view(self):
        if self.worker.vault: self.worker.vault.import_cancelled.set()
        if self.import_dialog:
            self.import_dialog.reject(); self.import_dialog = None

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

    def connect_zen(self):
        self.navigation.setCurrentRow(5)

    def browser_action(self, action):
        if self.busy: return
        if action in ('enable', 'refresh'):
            self.browser_page.feedback.clear()
            self.dispatch('browser_enable' if action == 'enable' else 'browser_status',
                          [str(Path(self.helper).with_name('monet-passwords-browser'))])
            return
        from browser_setup import browser_command
        try:
            command = browser_command(self.browser_page.state or {}, action)
            subprocess.Popen(command, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.browser_page.feedback.setText(tr('Continue in Zen, then come back here.'))
        except (OSError, ValueError):
            self.browser_page.feedback.setText(tr('Zen could not be opened. Check that it is installed, then try again.'))

    def revoke_browser(self):
        item = self.browser_list.currentItem()
        if not item or not self.unlocked or self.busy: return
        self.conceal()
        if QMessageBox.question(self, tr('Revoke browser connection?'),
                tr('This browser will lose access to Monet passwords until you connect it again. Your saved logins will be kept.'),
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes:
            self.dispatch('revoke_browser', [item.data(Qt.UserRole)])

    def disconnect_app(self):
        item = self.app_list.currentItem()
        if not item or not self.unlocked or self.busy: return
        if QMessageBox.question(self, tr('Disconnect app?'), tr('Close this app’s current vault connection? It may reconnect later.'),
                                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes:
            self.dispatch('disconnect', [item.text()])

    def page_changed(self, page):
        self.conceal()
        if page < 3:
            self.pages.setCurrentIndex(0)
            self.page_title.setText(self.navigation.item(page).text())
            self.search.setPlaceholderText(tr('Search saved logins') if page == 0 else tr('Search by name or app'))
            self.filter_rows()
        elif page == 3:
            self.pages.setCurrentIndex(1)
            if self.unlocked: self.dispatch('connections')
            else: self.app_message.setText(tr('Open your vault to manage app access.'))
        elif page == 4:
            self.pages.setCurrentIndex(2); self.load_policy()
        else:
            self.pages.setCurrentIndex(3); self.browser_action('refresh')

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
        self.browser_connected = False
        self.pending_check = False
        self.cancel_import_view()
        if self.editor: self.editor.reject(); self.editor = None
        self.rows = []; self.list.clear(); self.app_list.clear(); self.browser_list.clear()
        self.clipboard.clear()
        self.request.emit(self.token, 'forget', [])
        self.message.setText(tr('View closed. Apps may still use the unlocked vault.'))
        self.update_controls()
        self.clear_details()

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
        self.cancel_import_view()
        if self.editor: self.editor.reject(); self.editor = None
        self.clear_details(); self.clipboard.clear()
        self.rows = []; self.list.clear(); self.unlocked = False; self.update_controls()
        self.dispatch('lock')

    def event(self, event):
        if event.type() in (QEvent.WindowDeactivate, QEvent.Hide) and hasattr(self, 'fields'):
            self.conceal()
        if event.type() == QEvent.ApplicationPaletteChange and hasattr(self, 'pages'):
            self.apply_theme()
        if (event.type() == QEvent.WindowActivate and hasattr(self, 'pages')
                and self.unlocked and not self.busy and not self.editor and not self.import_dialog):
            # Refresh browser saves when returning to the app, without polling or
            # replacing a form the user is editing.
            if self.navigation.currentRow() == 5: self.browser_action('refresh')
            elif self.navigation.currentRow() != 4:
                self.dispatch('connections' if self.navigation.currentRow() == 3 else 'list_entries')
        elif (event.type() == QEvent.WindowActivate and hasattr(self, 'browser_page')
                and not self.busy and self.navigation.currentRow() == 5):
            self.browser_action('refresh')
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
    app = QApplication(sys.argv[:1]); app.setStyle('Fusion'); app.setApplicationName('monet-passwords')
    app.setApplicationDisplayName(tr('Passwords')); app.setDesktopFileName('monet-passwords')
    app.setOrganizationName('monet')
    page = 'browser' if '--connect-zen' in sys.argv else 'connections' if '--connections' in sys.argv else 'preferences' if '--preferences' in sys.argv else ''
    name = 'monet-passwords-' + str(os.getuid())
    socket = QLocalSocket(); socket.connectToServer(name)
    if socket.waitForConnected(200):
        socket.write((page or 'show').encode()); socket.waitForBytesWritten(200); socket.disconnectFromServer(); return 0
    QLocalServer.removeServer(name); server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(name): return 1
    window = PasswordsWindow(helper)
    def show_page(page):
        if page in ('connections', 'preferences', 'browser'):
            window.navigation.setCurrentRow({'connections': 3, 'preferences': 4, 'browser': 5}[page])
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
        window.navigation.setCurrentRow({'connections': 3, 'preferences': 4, 'browser': 5}[page])
    window.show()
    return app.exec()
