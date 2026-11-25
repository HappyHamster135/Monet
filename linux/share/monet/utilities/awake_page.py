"""Manual timers and opt-in conditions for the desktop's Keep awake service."""
import json

from PySide6.QtCore import Qt, SLOT, Slot
from PySide6.QtDBus import QDBusConnection, QDBusServiceWatcher
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from actions import stored, tr
from close_rules import application_aliases
from quit_protection import AppPicker, installed_apps


class AwakePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.owner = window
        self.apps = installed_apps()
        self.selected = []
        self.revision = 0
        self.bus = QDBusConnection.sessionBus()
        self.subscription = ('org.monet.KeepAwake', '/org/monet/KeepAwake',
                             'org.monet.KeepAwake', 'StatusChanged', self, SLOT('receive(QString)'))
        self.watcher = QDBusServiceWatcher('org.monet.KeepAwake', self.bus, QDBusServiceWatcher.WatchForUnregistration, self)
        self.watcher.serviceUnregistered.connect(lambda _: self.refresh() if self.isVisible() else None)
        layout = QVBoxLayout(self)
        self.timer = QComboBox()
        self.timer.setAccessibleName(tr('Manual timer'))
        for title, mode in [(tr('Off'), 'off'), (tr('30 minutes'), '30'),
                            (tr('1 hour'), '60'), (tr('Until turned off'), 'on')]:
            self.timer.addItem(title, mode)
        self.timer.activated.connect(self.set_timer)
        timer_row = QFormLayout()
        timer_row.addRow(tr('Manual timer'), self.timer)
        layout.addLayout(timer_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form = QWidget()
        choices = QVBoxLayout(form)
        self.enabled_rules = QCheckBox(tr('Use automatic rules'))
        choices.addWidget(self.enabled_rules)
        self.conditions = QWidget()
        options = QVBoxLayout(self.conditions)
        options.setContentsMargins(16, 0, 0, 0)
        hint = QLabel(tr('Keep this PC awake when any of these conditions applies.'))
        hint.setWordWrap(True)
        options.addWidget(hint)
        self.power = QCheckBox(tr('Connected to power'))
        self.external = QCheckBox(tr('An external display is connected'))
        options.addWidget(self.power)
        options.addWidget(self.external)
        self.pick = QPushButton(tr('Choose applications…'))
        self.pick.clicked.connect(self.choose)
        options.addWidget(self.pick, 0, Qt.AlignLeft)
        self.app_names = QLabel()
        self.app_names.setTextFormat(Qt.PlainText)
        self.app_names.setWordWrap(True)
        options.addWidget(self.app_names)
        self.display = QCheckBox(tr('Also keep the screen on and delay automatic locking'))
        options.addWidget(self.display)
        choices.addWidget(self.conditions)
        choices.addStretch()
        scroll.setWidget(form)
        layout.addWidget(scroll, 1)
        self.enabled_rules.toggled.connect(self.conditions.setEnabled)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.apply = QPushButton(tr('Apply changes'))
        self.apply.clicked.connect(self.save)
        layout.addWidget(self.apply, 0, Qt.AlignRight)

    def showEvent(self, event):
        self.owner.settings.sync()
        rules = stored(self.owner.settings, 'awakeRules', {})
        apps = rules.get('apps', {})
        self.selected = sorted(apps) if isinstance(apps, dict) else []
        self.enabled_rules.setChecked(rules.get('enabled') is True)
        self.conditions.setEnabled(self.enabled_rules.isChecked())
        for key in ('power', 'external', 'display'):
            getattr(self, key).setChecked(rules.get(key) is True)
        self.list_apps()
        self.bus.connect(*self.subscription)
        self.refresh()

    def hideEvent(self, event):
        self.revision += 1
        self.bus.disconnect(*self.subscription)

    def choose(self):
        picker = AppPicker(self.selected, self)
        if picker.exec() == QDialog.Accepted:
            self.selected = picker.selection()
            self.list_apps()

    def app_name(self, key):
        return self.apps.get(key, (key.removesuffix('.desktop'), ''))[0]

    def list_apps(self):
        names = sorted(map(self.app_name, self.selected), key=str.casefold)
        self.app_names.setText(tr('While open: {apps}').format(apps=', '.join(names)) if names
                               else tr('No applications selected'))

    def refresh(self):
        self.revision += 1
        revision = self.revision
        def received(out):
            if self.revision == revision:
                self.receive(out)
        self.owner.worker([self.owner.helpers / 'monet-quick', 'keep-awake-status'], received)

    @Slot(str)
    def receive(self, text):
        self.revision += 1
        state = json.loads(text)
        seconds = state.get('duration', 0)
        self.timer.setCurrentIndex(self.timer.findData({1800:'30', 3600:'60', -1:'on'}.get(seconds, 'off')))
        reasons = [tr('power connected') if key == 'power' else tr('external display') if key == 'external'
                   else self.app_name(key) for key in state.get('reasons', [])]
        if seconds:
            reasons.insert(0, tr('manual timer'))
        if state.get('error'):
            self.status.setText(tr('Keep awake is unavailable. Apply your choices to retry.'))
        elif state.get('active') and reasons:
            self.status.setText(tr('Keeping this PC awake because of {conditions}.').format(conditions=', '.join(reasons)))
        elif state.get('watching'):
            self.status.setText(tr('Waiting for a matching condition.'))
        else:
            self.status.setText(tr('This PC is using its usual sleep settings.'))

    def set_timer(self, index):
        self.timer.setEnabled(False)
        def done(out):
            self.timer.setEnabled(True)
            self.receive(json.dumps(json.loads(out)['state']))
        def failed(message):
            self.timer.setEnabled(True)
            self.refresh()
            self.owner.issue(message)
        self.owner.worker([self.owner.helpers / 'monet-quick', 'keep-awake', self.timer.itemData(index)], done, failed)

    def save(self):
        enabled = self.enabled_rules.isChecked()
        if enabled and not (self.external.isChecked() or self.power.isChecked() or self.selected):
            self.status.setText(tr('Choose a condition or turn off automatic rules.'))
            return
        rules = dict(enabled=enabled, power=self.power.isChecked(), external=self.external.isChecked(),
                     display=self.display.isChecked(), apps=application_aliases(self.selected))
        self.owner.settings.setValue('awakeRules', json.dumps(rules))
        self.owner.settings.sync()
        if self.owner.settings.status() != self.owner.settings.Status.NoError:
            self.status.setText(tr('Could not save Keep awake rules.'))
            return
        self.apply.setEnabled(False)
        def done(out):
            self.apply.setEnabled(True)
            self.receive(out)
        def failed(message):
            self.apply.setEnabled(True)
            self.status.setText(tr('Could not apply Keep awake rules. {reason}').format(reason=message))
        self.owner.worker([self.owner.helpers / 'monet-quick', 'keep-awake-rules'], done, failed, finish_on_close=True)
