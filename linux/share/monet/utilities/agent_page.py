"""Account limits and locally selected session statistics in Monet Utilities."""
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QProgressBar, QPushButton, QTabWidget, QVBoxLayout, QWidget)
from actions import tr
from codex_limits import enable, generation
from pages import row


class AgentUsage(QTabWidget):
    def __init__(self, home):
        super().__init__()
        self.home = home
        self.settings = home.settings
        self.pending = None
        self.file_request = 0
        self.account = QWidget()
        self.addTab(self.account, tr("Account limits"))
        layout = QVBoxLayout(self.account)
        self.switch = QCheckBox(tr("Show Codex account limits"))
        self.switch.setChecked(bool(generation(self.settings)))
        layout.addWidget(self.switch)
        info = QLabel(tr("Uses the signed-in Codex CLI to check your remaining allowance when you open this page or notch Activity."))
        info.setWordWrap(True)
        layout.addWidget(info)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.bars = []
        for i in range(2):
            name, bar, reset = QLabel(), QProgressBar(), QLabel()
            name.setTextFormat(Qt.PlainText)
            reset.setTextFormat(Qt.PlainText)
            reset.setWordWrap(True)
            bar.setRange(0, 1000)
            layout.addWidget(name)
            layout.addWidget(bar)
            layout.addWidget(reset)
            self.bars.append((name, bar, reset))
        layout.addStretch()
        buttons = QHBoxLayout()
        self.check = QPushButton(tr("Refresh"), clicked=lambda: self.load_limits(True))
        buttons.addWidget(self.check)
        self.cli_button = QPushButton(tr("Choose Codex CLI…"), clicked=self.choose_cli)
        buttons.addWidget(self.cli_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.switch.toggled.connect(self.toggle)
        self.timer = QTimer(self, interval=60000)
        self.timer.timeout.connect(self.load_limits)
        session = QWidget()
        self.addTab(session, tr("Session file"))
        box = QVBoxLayout(session)
        label = QLabel(tr("Choose a local Codex, Claude Code or Copilot CLI session log, or an OpenCode database."))
        label.setWordWrap(True)
        box.addWidget(label)
        self.text = QPlainTextEdit(readOnly=True)
        box.addWidget(self.text)
        row(box, (tr("Choose session…"), self.choose_file), (tr("Refresh"), self.load_file), (tr("Forget"), self.forget_file))
        if self.settings.value("agentFile", "") and not self.switch.isChecked():
            self.setCurrentWidget(session)
        self.currentChanged.connect(self.refresh)
        self.paint_limits({})

    def toggle(self, on):
        enable(self.settings, on)
        self.pending = None
        signal = QDBusMessage.createSignal("/Utilities", "org.monet.Utilities", "CodexLimitsChanged")
        signal.setArguments([generation(self.settings)])
        QDBusConnection.sessionBus().send(signal)
        self.refresh()

    def choose_cli(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose the Codex CLI executable"), self.settings.value("codexExecutable", ""))
        if path:
            if not os.access(path, os.X_OK) or not Path(path).is_file():
                self.status.setText(tr("Choose an executable file."))
                return
            self.settings.setValue("codexExecutable", path)
            self.settings.sync()
            if self.switch.isChecked():
                self.toggle(True)
            else:
                self.cli_button.setToolTip(path)

    def paint_limits(self, result):
        rows = result.get("rows", [])
        for index, (name, bar, reset) in enumerate(self.bars):
            active = index < len(rows)
            for widget in (name, bar, reset):
                widget.setVisible(active)
            if active:
                item = rows[index]
                name.setText(item["name"])
                bar.setAccessibleName(item["name"] + " · " + item["remaining"])
                bar.setValue(round(item["value"] * 10))
                bar.setFormat(item["remaining"])
                reset.setText(item["reset"])
                reset.setVisible(bool(item["reset"]))
        self.status.setText(result.get("checked") or result.get("details", ""))
        self.status.setVisible(bool(self.status.text()))
        self.cli_button.setToolTip(self.settings.value("codexExecutable", ""))
        self.check.setEnabled(self.switch.isChecked() and not self.pending)

    def refresh(self, *_):
        self.timer.stop()
        if self.currentWidget() is self.account:
            self.load_limits()
            if self.isVisible() and self.switch.isChecked():
                self.timer.start()
        else:
            self.load_file()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def load_limits(self, force=False):
        key = generation(self.settings)
        if not key:
            self.paint_limits({})
            return
        if self.pending == key:
            return
        self.pending = key
        self.check.setEnabled(False)
        self.status.setText(tr("Checking Codex limits…"))
        self.status.show()
        def done(result):
            if self.pending == key:
                self.pending = None
                self.paint_limits(result)
        def failed(_):
            done({"details": tr("Could not check Codex limits. Try refreshing.")})
        def loaded(output):
            try:
                done(json.loads(output))
            except (ValueError, TypeError):
                failed(None)
        args = ["--refresh"] if force else []
        self.home.worker([sys.executable, Path(__file__).with_name("codex_limits.py"), *args], loaded, failed)

    def load_file(self):
        self.file_request += 1
        request = self.file_request
        if not self.settings.value("agentFile", ""):
            self.text.setPlainText(tr("No session selected."))
            return
        def received(out):
            if request == self.file_request:
                self.text.setPlainText(out.strip() or tr("No usage figures were reported in recent session events."))
        self.home.worker([sys.executable, Path(__file__).with_name("agents.py")], received)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose a local session log or database"))
        if path:
            self.settings.setValue("agentFile", path)
            self.settings.sync()
            self.load_file()

    def forget_file(self):
        self.settings.remove("agentFile")
        self.settings.sync()
        self.load_file()
