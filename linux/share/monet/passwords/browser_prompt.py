"""Native consent UI. Input contains site/account metadata, never a password."""
import json
import sys
from PySide6.QtCore import Qt, QTimer, SLOT, QObject, Slot
from PySide6.QtDBus import QDBusConnection
from PySide6.QtGui import QPalette, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QLineEdit, QCheckBox, QDialogButtonBox


def main():
    from app import tr
    try:
        data = json.loads(sys.stdin.buffer.read(16385))
        kind = data.get('kind')
        if kind not in ('connect', 'save', 'update', 'fill'): return 1
    except (ValueError, AttributeError): return 1
    app = QApplication(sys.argv[:1]); app.setStyle('Fusion')
    app.setApplicationName('monet-passwords'); app.setDesktopFileName('monet-passwords')
    app.setWindowIcon(QIcon.fromTheme('preferences-desktop-user-password'))
    dialog = QDialog(); dialog.setWindowTitle(tr('Monet Passwords'))
    dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dialog.setMinimumWidth(440); dialog.setMaximumWidth(540)
    box = QVBoxLayout(dialog); box.setContentsMargins(26, 24, 26, 24); box.setSpacing(16)
    headings = {'connect': tr('Connect Zen to your passwords?'), 'save': tr('Save this login?'),
                'update': tr('Update this password?'), 'fill': tr('Allow autofill on this website?')}
    title = QLabel(headings[kind]); title.setObjectName('title'); title.setWordWrap(True); box.addWidget(title)
    name = None; remember = None
    if kind == 'connect':
        text = tr('Zen uses the signed KeePassXC-Browser connector to talk to Monet. Saving and updating logins requires your approval. You can revoke this browser connection at any time.')
        label = QLabel(text); label.setWordWrap(True); box.addWidget(label)
        name = QLineEdit('Zen'); name.setMaxLength(60); name.setAccessibleName(tr('Browser connection name'))
        box.addWidget(name)
    else:
        site = data.get('site', '')
        user = data.get('username', '')
        if not isinstance(site, str) or len(site) > 8192 or not isinstance(user, str) or len(user) > 65536: return 1
        label = QLabel(site); label.setTextFormat(Qt.PlainText); label.setWordWrap(True); label.setObjectName('site'); box.addWidget(label)
        if kind in ('save', 'update'):
            label = QLabel(user or tr('No username')); label.setTextFormat(Qt.PlainText); label.setWordWrap(True); box.addWidget(label)
            text = tr('The new password will replace this account’s saved password. Nothing changes until you approve.') if kind == 'update' else tr('Store this login in your encrypted Monet vault and offer it on this website next time.')
            label = QLabel(text); label.setWordWrap(True); box.addWidget(label)
        else:
            label = QLabel(tr('Only logins saved for this exact website will be shared. Monet never submits the sign-in form for you.'))
            label.setWordWrap(True); box.addWidget(label)
            remember = QCheckBox(tr('Remember this website for this browser')); remember.setChecked(True); box.addWidget(remember)
    buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
    button = buttons.button(QDialogButtonBox.Save)
    button.setText({'connect': tr('Connect'), 'save': tr('Save login'), 'update': tr('Update password'), 'fill': tr('Allow autofill')}[kind])
    button.setAutoDefault(False); button.setDefault(False)
    cancel = buttons.button(QDialogButtonBox.Cancel); cancel.setDefault(True); cancel.setFocus()
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); box.addWidget(buttons)
    class Screen(QObject):
        @Slot(bool)
        def changed(self, active):
            if active: dialog.reject()
    screen = Screen()
    QDBusConnection.sessionBus().connect('org.freedesktop.ScreenSaver','/ScreenSaver','org.freedesktop.ScreenSaver','ActiveChanged',screen,SLOT('changed(bool)'))
    dark = app.palette().color(QPalette.Window).lightness() < 128
    paper,ink,border,accent=('#242828','#eeeae2','#444c4b','#34544f') if dark else ('#faf9f6','#252b29','#d8dcd6','#d9e6e0')
    dialog.setStyleSheet('''QWidget { background: PAPER; color: INK; font-family: Inter; font-size: 14px; }
        QLabel { background: transparent; } QLabel#title { font-size: 23px; font-weight: 600; }
        QLabel#site { font-size: 16px; font-weight: 600; }
        QPushButton, QLineEdit { padding: 9px 14px; border: 1px solid BORDER; border-radius: 8px; }
        QPushButton:hover { background: ACCENT; }
        QCheckBox { spacing: 10px; }'''.replace('PAPER',paper).replace('INK',ink).replace('BORDER',border).replace('ACCENT',accent))
    deadline = QTimer(dialog); deadline.setSingleShot(True); deadline.timeout.connect(dialog.reject); deadline.start(85000)
    approved = dialog.exec() == QDialog.Accepted
    print(json.dumps({'approved': approved, 'name': name.text() if approved and name else '',
                      'remember': bool(approved and remember and remember.isChecked())}))
    return 0
