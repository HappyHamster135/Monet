"""Event-driven Zen setup page. Status reads installation metadata only."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class BrowserPage(QWidget):
    requested = Signal(str)

    def __init__(self, tr, parent=None):
        super().__init__(parent)
        self.tr = tr
        self.state = None
        self.busy = False
        self.action = ''
        layout = QVBoxLayout(self); layout.setContentsMargins(26, 26, 26, 26); layout.setSpacing(18)
        title = QLabel(tr('Zen autofill')); title.setObjectName('pageTitle'); layout.addWidget(title)
        intro = QLabel(tr('Save a login once. Fill it next time. Your passwords stay in Monet’s encrypted vault.'))
        intro.setWordWrap(True); layout.addWidget(intro)
        card = QWidget(); card.setObjectName('detailSurface')
        box = QVBoxLayout(card); box.setContentsMargins(24, 24, 24, 24); box.setSpacing(16)
        self.title = QLabel(tr('Checking Zen…')); self.title.setObjectName('entryTitle'); self.title.setWordWrap(True); box.addWidget(self.title)
        self.detail = QLabel(); self.detail.setWordWrap(True); box.addWidget(self.detail)
        self.pairing = QLabel(); self.pairing.setWordWrap(True); self.pairing.setObjectName('muted'); box.addWidget(self.pairing)
        buttons = QHBoxLayout()
        self.primary = QPushButton(tr('Continue')); self.primary.setObjectName('addLogin')
        self.primary.clicked.connect(lambda: self.requested.emit(self.action)); buttons.addWidget(self.primary)
        self.refresh = QPushButton(tr('Check again')); self.refresh.clicked.connect(lambda: self.requested.emit('refresh'))
        buttons.addWidget(self.refresh); buttons.addStretch(); box.addLayout(buttons)
        self.feedback = QLabel(); self.feedback.setWordWrap(True); box.addWidget(self.feedback)
        layout.addWidget(card)
        title = QLabel(tr('How it works')); title.setObjectName('fieldLabel'); layout.addWidget(title)
        for text in (tr('1. Sign in to a website in Zen. Monet asks before saving a new login or updating a password.'),
                     tr('2. On your next visit, choose the saved account. Turn on single-account autofill to fill automatically when there is one match.'),
                     tr('3. Unlock your vault once per session, or after it locks. The connector has no separate password.')):
            label = QLabel(text); label.setWordWrap(True); layout.addWidget(label)
        self.options = QPushButton(tr('Autofill settings in Zen'))
        self.options.clicked.connect(lambda: self.requested.emit('options')); layout.addWidget(self.options)
        note = QLabel(tr('Existing Zen passwords stay in Zen. Monet offers to save them when you use them; no CSV file is needed.'))
        note.setObjectName('muted'); note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.set_busy(True)

    def show_state(self, state):
        self.state = state
        tr = self.tr
        if state['problem'] and (state['profile'] or state['problem'] != 'Open your default Zen profile once, then connect it from Monet Passwords.'):
            self.title.setText(tr('Zen needs attention'))
            self.detail.setText(tr(state['problem']))
            self.action, text = 'manage', tr('Open Zen add-ons')
        elif not state['profile']:
            self.title.setText(tr('Start with Zen'))
            self.detail.setText(tr('Open Zen once to create its profile, then come back and choose Check again.'))
            self.action, text = 'open', tr('Open Zen')
        elif not state['configured']:
            self.title.setText(tr('Allow Zen to use Monet Passwords'))
            self.detail.setText(tr('Enable the local connection, then add the signed connector in Zen. If Zen is already open, restart it after enabling.'))
            self.action, text = 'enable', tr('Enable Zen connection')
        elif state['addon'] == 'missing':
            self.title.setText(tr('Add the Monet connector'))
            self.detail.setText(tr('Approve Add in Zen. Then open the connector, choose Connect and approve Monet’s pairing request.') if state['bundled']
                                else tr(state['bundle_problem']) if state.get('bundle_problem')
                                else tr('The signed Monet connector is missing from this installation. Update Monet and try again.'))
            self.action, text = ('install' if state['bundled'] else ''), tr('Add to Zen')
        elif state['addon'] == 'disabled':
            self.title.setText(tr('Enable the Monet connector'))
            self.detail.setText(tr('In Zen’s add-ons, enable Monet Passwords. Keep only one password connector enabled to avoid duplicate prompts.'))
            self.action, text = 'manage', tr('Open Zen add-ons')
        elif state.get('update_available'):
            self.title.setText(tr('A connector update is ready'))
            self.detail.setText(tr('Approve the update in Zen to use the connector included with this version of Monet. Your saved pairing and settings stay in place.'))
            self.action, text = 'install', tr('Update Zen connector')
        else:
            self.title.setText(tr('Installed in Zen'))
            self.detail.setText(tr('Open the connector to check its connection. If it asks to connect, choose Connect and approve Monet’s request. Pairing is needed only once.'))
            self.action, text = 'popup', tr('Open Zen connector')
        self.primary.setText(text)
        self.set_busy(False)

    def set_pairing(self, view_open, saved):
        tr = self.tr
        self.pairing.setText(tr('A browser pairing is saved in this vault. You can revoke access in Connected apps.') if view_open and saved
                             else tr('Opening your vault in Saved logins lets you check and manage saved browser pairings.'))

    def set_busy(self, busy):
        self.busy = busy
        self.primary.setEnabled(not busy and bool(self.action))
        self.refresh.setEnabled(not busy)
        self.options.setEnabled(not busy and bool(self.state and self.state.get('options')))
