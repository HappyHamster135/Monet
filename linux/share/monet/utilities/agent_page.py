"""Account limits and locally selected session statistics in Monet Utilities."""
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget)
from actions import tr
from codex_limits import enable, generation
from pages import row


class AgentUsage(QTabWidget):
    def __init__(self, home):
        super().__init__()
        self.home = home
        self.settings = home.settings
        self.pending = set()
        self.file_request = 0
        self.account = QWidget()
        self.addTab(self.account, tr("Account limits"))
        layout = QVBoxLayout(self.account)
        providers = QHBoxLayout()
        label = QLabel(tr("Provider"))
        self.picker = QComboBox()
        self.picker.addItem("Codex", "codex")
        self.picker.addItem("Claude Code", "claude")
        self.picker.setCurrentIndex(max(0, self.picker.findData(self.settings.value("agentProvider", "codex"))))
        label.setBuddy(self.picker)
        providers.addWidget(label)
        providers.addWidget(self.picker, 1)
        layout.addLayout(providers)
        self.switch = QCheckBox()
        layout.addWidget(self.switch)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.bars = []
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        contents = QWidget()
        self.row_layout = QVBoxLayout(contents)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(contents)
        layout.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        self.check = QPushButton(tr("Refresh"), clicked=lambda: self.load_limits(True))
        buttons.addWidget(self.check)
        self.cli_button = QPushButton(tr("Choose Codex CLI…"), clicked=self.choose_cli)
        buttons.addWidget(self.cli_button)
        buttons.addStretch()
        layout.addLayout(buttons)
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
        self.configure_provider()
        self.picker.currentIndexChanged.connect(self.change_provider)
        self.switch.toggled.connect(self.toggle)
        if self.settings.value("agentFile", "") and not any(generation(self.settings, p) for p in ("codex", "claude")):
            self.setCurrentWidget(session)
        self.currentChanged.connect(self.refresh)
        self.paint_limits({})

    @property
    def provider(self):
        return self.picker.currentData()

    def configure_provider(self):
        claude = self.provider == "claude"
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(generation(self.settings, self.provider)))
        self.switch.blockSignals(False)
        self.switch.setText(tr("Show Claude Code account limits") if claude else tr("Show Codex account limits"))
        self.info.setText(tr("Uses your signed-in Claude Code CLI to read subscription limits when you open this page or notch Activity.")
                          if claude else tr("Uses the signed-in Codex CLI to check your remaining allowance when you open this page or notch Activity."))
        self.cli_button.setText(tr("Choose Claude Code CLI…") if claude else tr("Choose Codex CLI…"))
        self.paint_limits({})

    def change_provider(self):
        self.settings.setValue("agentProvider", self.provider)
        self.configure_provider()
        self.refresh()

    def open_provider(self, provider):
        self.picker.setCurrentIndex(self.picker.findData(provider))
        self.setCurrentWidget(self.account)
        self.refresh()

    def toggle(self, on):
        enable(self.settings, on, self.provider)
        self.paint_limits({})
        name = "ClaudeLimitsChanged" if self.provider == "claude" else "CodexLimitsChanged"
        signal = QDBusMessage.createSignal("/Utilities", "org.monet.Utilities", name)
        signal.setArguments([generation(self.settings, self.provider)])
        QDBusConnection.sessionBus().send(signal)
        self.refresh()

    def choose_cli(self):
        title = tr("Choose the Claude Code executable") if self.provider == "claude" else tr("Choose the Codex CLI executable")
        path, _ = QFileDialog.getOpenFileName(self, title, self.settings.value(self.provider + "Executable", ""))
        if path:
            if not os.access(path, os.X_OK) or not Path(path).is_file():
                self.status.setText(tr("Choose an executable file."))
                return
            self.settings.setValue(self.provider + "Executable", path)
            self.settings.sync()
            if self.switch.isChecked():
                self.toggle(True)
            else:
                self.cli_button.setToolTip(path)

    def add_bar(self):
        name, bar, reset = QLabel(), QProgressBar(), QLabel()
        name.setTextFormat(Qt.PlainText)
        name.setWordWrap(True)
        reset.setTextFormat(Qt.PlainText)
        reset.setWordWrap(True)
        bar.setRange(0, 1000)
        line = QHBoxLayout()
        line.addWidget(name, 1)
        line.addWidget(reset)
        self.row_layout.addLayout(line)
        self.row_layout.addWidget(bar)
        self.bars.append((name, bar, reset))

    def paint_limits(self, result):
        rows = result.get("rows", [])
        while len(self.bars) < len(rows):
            self.add_bar()
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
        self.cli_button.setToolTip(self.settings.value(self.provider + "Executable", ""))
        self.check.setEnabled(self.switch.isChecked() and generation(self.settings, self.provider) not in self.pending)

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
        provider = self.provider
        key = generation(self.settings, provider)
        if not key:
            self.paint_limits({})
            return
        self.check.setEnabled(False)
        self.status.setText(tr("Checking Claude Code limits…") if provider == "claude" else tr("Checking Codex limits…"))
        self.status.show()
        if key in self.pending:
            return
        self.pending.add(key)
        def done(result):
            self.pending.discard(key)
            if self.provider == provider and key == generation(self.settings, provider):
                self.paint_limits(result)
        def failed(_):
            done({"details": tr("Could not check Claude Code limits. Try refreshing.") if provider == "claude" else tr("Could not check Codex limits. Try refreshing.")})
        def loaded(output):
            try:
                done(json.loads(output))
            except (ValueError, TypeError):
                failed(None)
        args = ["--refresh"] if force else []
        if provider == "claude":
            args.append("--claude")
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
