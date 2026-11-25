"""Configure optional desktop resource alerts and see which sensors are available."""
import json
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from actions import tr
from monitor_alerts import LIMITS, NAMES, REPEATS, UNIT, preferences
from monitor_readings import Sampler


class Updates(QObject):
    loaded = Signal(int, object, bool)


class MonitorPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.owner = window
        self.boxes = {}
        self.spins = {}
        self.labels = {}
        self.generation = 0
        self.saving = False
        self.updates = Updates()
        self.updates.loaded.connect(self.loaded, Qt.QueuedConnection)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("Choose which desktop notifications to receive. CPU, temperature and memory alerts wait for 12 seconds of sustained activity."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setColumnStretch(0, 1)
        grid.setVerticalSpacing(2)
        grid.addWidget(QLabel(tr("Alert")), 0, 0)
        grid.addWidget(QLabel(tr("Limit")), 0, 1)
        grid.addWidget(QLabel(tr("Current reading")), 0, 2)
        for row, (key, name) in enumerate(NAMES.items(), 1):
            checkbox = QCheckBox(name)
            self.boxes[key] = checkbox
            grid.addWidget(checkbox, row, 0)
            if key == "memory":
                detail = QLabel(self.format_value("memory", LIMITS["memory"][2]))
                detail.setToolTip(tr("All runnable tasks are waiting for memory at least 10% of the time."))
                grid.addWidget(detail, row, 1)
            else:
                spin = QSpinBox()
                low, high, _ = LIMITS[key]
                spin.setRange(low, high)
                spin.setSuffix(" °C" if key.endswith("-temp") else "%")
                spin.setAccessibleName(tr("{alert} limit").format(alert=name))
                checkbox.toggled.connect(spin.setEnabled)
                self.spins[key] = spin
                grid.addWidget(spin, row, 1)
            label = QLabel("…")
            label.setTextFormat(Qt.PlainText)
            self.labels[key] = label
            grid.addWidget(label, row, 2)
        grid.setRowStretch(len(NAMES) + 1, 1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        options = QHBoxLayout()
        label = QLabel(tr("Repeat after"))
        self.repeat = QComboBox()
        self.repeat.setAccessibleName(label.text())
        label.setBuddy(self.repeat)
        for minutes in REPEATS:
            self.repeat.addItem(tr("{minutes} minutes").format(minutes=minutes), minutes)
        options.addWidget(label)
        options.addWidget(self.repeat)
        options.addStretch()
        self.refresh_button = QPushButton(tr("Refresh readings"))
        self.refresh_button.clicked.connect(self.refresh)
        options.addWidget(self.refresh_button)
        layout.addLayout(options)
        detail = tr("Disk alerts repeat after six hours, or sooner if free space falls below half the limit. Battery charge alerts apply while discharging.")
        for widget in (self.repeat, self.boxes["disk"], self.boxes["battery"]):
            widget.setToolTip(detail)
            widget.setAccessibleDescription(detail)
        buttons = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        buttons.addWidget(self.status, 1)
        self.apply = QPushButton(tr("Apply changes"))
        self.apply.clicked.connect(self.save)
        buttons.addWidget(self.apply)
        layout.addLayout(buttons)

    def showEvent(self, event):
        super().showEvent(event)
        selected, limits, repeat = preferences(self.owner.settings)
        for key, checkbox in self.boxes.items():
            checkbox.setChecked(key in selected)
            if key in self.spins:
                self.spins[key].setValue(limits[key])
                self.spins[key].setEnabled(key in selected)
        self.repeat.setCurrentIndex(self.repeat.findData(repeat))
        self.refresh()

    def hideEvent(self, event):
        self.generation += 1
        super().hideEvent(event)

    def refresh(self):
        self.generation += 1
        number = self.generation
        self.refresh_button.setEnabled(False)
        updates = self.updates
        def sample():
            sampler = Sampler()
            sampler.sample({"cpu"})
            time.sleep(.25)
            readings = sampler.sample(set(LIMITS))
            try:
                active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", UNIT], timeout=3).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                active = False
            updates.loaded.emit(number, readings, active)
        QThreadPool.globalInstance().start(sample)

    @Slot(int, object, bool)
    def loaded(self, number, readings, active):
        if number != self.generation:
            return
        for key, checkbox in self.boxes.items():
            found = [r for r in readings if r.kind == key]
            checkbox.setEnabled(bool(found) or checkbox.isChecked())
            label = self.labels[key]
            if not found:
                label.setText(tr("Unavailable"))
                label.setToolTip("")
                continue
            values = [r.value for r in found]
            value = min(values) if key in {"disk", "battery"} else max(values)
            label.setText(self.format_value(key, value))
            label.setToolTip("\n".join(r.name + "  " + self.format_value(key, r.value) for r in found if r.name))
        self.refresh_button.setEnabled(True)
        selected, _, _ = preferences(self.owner.settings)
        if selected:
            self.status.setText(tr("Monitoring is on.") if active else tr("Monitoring is stopped. Apply your choices to start it."))
        else:
            self.status.setText(tr("System alerts are off."))

    @staticmethod
    def format_value(key, value):
        if key == "memory":
            return tr("{percent}% stalled").format(percent=f"{value:.1f}")
        if key == "disk":
            return tr("{percent}% free").format(percent=f"{value:.1f}")
        return f"{value:.0f} °C" if key.endswith("-temp") else f"{value:.0f}%"

    def save(self):
        if self.saving:
            return
        settings = self.owner.settings
        values = {key: spin.value() for key, spin in self.spins.items()}
        values.update(enabled=[k for k, c in self.boxes.items() if c.isChecked()], repeat=self.repeat.currentData())
        settings.setValue("monitorAlerts", json.dumps(values))
        settings.sync()
        if settings.status() != settings.Status.NoError:
            self.status.setText(tr("Could not save the alert settings."))
            return
        self.saving = True
        self.setEnabled(False)
        self.status.setText(tr("Applying alert settings…"))
        def finished(error=""):
            self.saving = False
            self.setEnabled(True)
            if error:
                self.generation += 1
                self.refresh_button.setEnabled(True)
                self.status.setText(tr("Could not apply alert settings. {reason}").format(reason=error))
            elif self.isVisible():
                self.refresh()
        self.owner.worker([sys.executable, Path(__file__).with_name("monitor_alerts.py"), "sync"],
                          lambda _: finished(), finished, finish_on_close=True)
