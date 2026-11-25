"""Choose when the current clipboard becomes empty."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from actions import tr
from clipboard_expiry import DELAYS, Policy


class ClipboardExpiryPage(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.saved = None
        self.busy = False
        self.command = [sys.executable, Path(__file__).with_name("clipboard_expiry.py")]
        layout = QVBoxLayout(self)
        hint = QLabel(tr("Choose when Paste should forget the last item you copied. You can still select saved items from Clipboard history."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        self.delay = QComboBox()
        labels = (tr("Never"), tr("15 seconds"), tr("30 seconds"), tr("1 minute"), tr("5 minutes"),
                  tr("15 minutes"), tr("1 hour"))
        for seconds, label in zip(DELAYS, labels, strict=True):
            self.delay.addItem(label, seconds)
        form.addRow(tr("Time after copying"), self.delay)
        self.lock = QCheckBox(tr("Clear when the screen locks"))
        self.sleep = QCheckBox(tr("Clear when the computer sleeps"))
        layout.addWidget(self.lock)
        layout.addWidget(self.sleep)
        self.save = QPushButton(tr("Apply"))
        layout.addWidget(self.save, 0, Qt.AlignLeft)
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch()
        self.delay.currentIndexChanged.connect(self.edited)
        self.lock.toggled.connect(self.edited)
        self.sleep.toggled.connect(self.edited)
        self.save.clicked.connect(self.apply)

    def selection(self):
        return Policy(self.delay.currentData(), self.lock.isChecked(), self.sleep.isChecked())

    def edited(self):
        self.message.clear()
        self.save.setEnabled(self.saved is not None and self.saved != self.selection() and not self.busy)

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.setEnabled(False)
        def loaded(result):
            policy = Policy(**json.loads(result))
            self.saved = policy
            self.save.setText(tr("Apply"))
            for control in (self.delay, self.lock, self.sleep):
                control.setEnabled(True)
            self.delay.setCurrentIndex(self.delay.findData(policy.seconds))
            self.lock.setChecked(policy.lock)
            self.sleep.setChecked(policy.sleep)
            self.busy = False
            self.setEnabled(True)
            self.edited()
        def failed(error):
            self.busy = False
            self.saved = None
            self.setEnabled(True)
            for control in (self.delay, self.lock, self.sleep):
                control.setEnabled(False)
            self.message.setText(error)
            self.save.setText(tr("Retry"))
            self.save.setEnabled(True)
        self.owner.worker([*self.command, "status"], loaded, failed)

    def apply(self):
        if self.saved is None:
            self.refresh()
            return
        policy = self.selection()
        self.busy = True
        self.setEnabled(False)
        def finish(ok):
            self.busy = False
            self.setEnabled(True)
            if ok:
                self.saved = policy
            self.edited()
            self.message.setText(tr("Settings saved.") if ok else tr("Couldn’t apply clipboard settings."))
        def failed(error):
            finish(False)
            self.owner.issue(error)
        self.owner.worker([*self.command, "apply", json.dumps(asdict(policy))],
                          lambda _: finish(True), failed, finish_on_close=True)
